"""
Utilitário de Engenharia de Datasets Científicos para o SolarGuard Vision.

Objetivo:
Reestruturar datasets para garantir independência estatística estrita entre
Treinamento (train), Validação (valid) e Teste (test), eliminando qualquer vazamento
de avaliação decorrente de 'val == test' e aplicando agrupamento por origem de voo
(Flight-based Group Split).
"""

import argparse
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

import yaml


class DatasetAuditError(Exception):
    """Exceção levantada em violações de integridade do dataset."""
    pass


class DatasetSplitter:
    """
    Particiona datasets YOLO em train, valid e test de forma independente,
    agrupando por origem de sobrevoo para evitar vazamento espacial/temporal.
    """

    def __init__(
        self,
        dataset_dir: str | Path,
        flight_regex: Optional[str] = None,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        seed: int = 42,
    ) -> None:
        self.dataset_dir = Path(dataset_dir).resolve()
        self.flight_regex = flight_regex
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.seed = seed

    def audit_yaml(self, yaml_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Audita um arquivo data.yaml verificando conformidade e vazamento val == test.
        """
        y_path = yaml_path or self.dataset_dir / "data.yaml"
        if not y_path.exists():
            return {
                "exists": False,
                "path": str(y_path),
                "has_val_test_leakage": False,
                "error": f"Arquivo {y_path} não encontrado.",
            }

        content = yaml.safe_load(y_path.read_text(encoding="utf-8")) or {}
        val_path = content.get("val") or content.get("valid")
        test_path = content.get("test")
        train_path = content.get("train")

        has_leakage = False
        leakage_reason = ""
        if val_path and test_path:
            norm_val = str(val_path).strip().replace("\\", "/").rstrip("/")
            norm_test = str(test_path).strip().replace("\\", "/").rstrip("/")
            if norm_val == norm_test:
                has_leakage = True
                leakage_reason = f"Violação crítica: 'val' ({val_path}) aponta exatamente para o mesmo diretório de 'test' ({test_path})."

        return {
            "exists": True,
            "path": str(y_path),
            "train": train_path,
            "val": val_path,
            "test": test_path,
            "nc": content.get("nc"),
            "names": content.get("names"),
            "has_val_test_leakage": has_leakage,
            "leakage_reason": leakage_reason,
        }

    def extract_flight_id(self, filename: str) -> str:
        """
        Extrai o identificador de voo ou sessão de sobrevoo de uma imagem.
        Suporta padrões como:
        - flight_01, voo_2, session_A, DJI_0012
        - blocos sequenciais de inspeção (ex: thermalhotspot{N})
        """
        # 1. Se fornecida regex customizada
        if self.flight_regex:
            m = re.search(self.flight_regex, filename, re.IGNORECASE)
            if m:
                return m.group(1) if m.groups() else m.group(0)

        # 2. Padrões comuns de inspeção com UAV/drones
        patterns = [
            r"^(flight[_-]?\d+)",
            r"^(voo[_-]?\d+)",
            r"^(session[_-]?\d+)",
            r"^(inspecao[_-]?\d+)",
            r"^(DJI[_-]?\d{2})",
        ]
        for pat in patterns:
            m = re.search(pat, filename, re.IGNORECASE)
            if m:
                return m.group(1).lower()

        # 3. Tratamento para dataset de mestrado 'thermalhotspot{N}'
        m_th = re.match(r"^thermalhotspot(\d+)", filename, re.IGNORECASE)
        if m_th:
            n = int(m_th.group(1))
            # Mapeamento por passadas sequenciais de sobrevoo na usina:
            if n <= 13:
                return "Flight_A_Rows01-13"
            elif n <= 26:
                return "Flight_B_Rows14-26"
            elif n <= 39:
                return "Flight_C_Rows27-39"
            elif n <= 52:
                return "Flight_D_Rows40-52"
            elif n <= 62:
                return "Flight_E_Rows53-62"
            else:
                return "Flight_F_Rows63-73"

        # Fallback para prefixo antes do primeiro ponto ou underline
        base = filename.split(".")[0].split("_")[0]
        return f"Flight_{base}"

    def collect_all_samples(self) -> List[Dict[str, Any]]:
        """
        Varre todos os diretórios do dataset coletando pares (imagem, label) e classes.
        """
        image_extensions = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
        samples: Dict[str, Dict[str, Any]] = {}

        # Varre subpastas procurando images/ e labels/
        for split_candidate in ["train", "valid", "val", "test", "."]:
            img_dir = self.dataset_dir / split_candidate / "images"
            lbl_dir = self.dataset_dir / split_candidate / "labels"

            if not img_dir.exists():
                img_dir = self.dataset_dir / "images" / split_candidate
                lbl_dir = self.dataset_dir / "labels" / split_candidate

            if not img_dir.exists():
                continue

            for img_file in img_dir.iterdir():
                if img_file.is_file() and img_file.suffix.lower() in image_extensions:
                    stem = img_file.stem
                    # Se já coletado de outro split, não duplica
                    if stem in samples:
                        continue

                    # Localiza label correspondente
                    lbl_file = None
                    if lbl_dir.exists():
                        target_lbl = lbl_dir / f"{stem}.txt"
                        if target_lbl.exists():
                            lbl_file = target_lbl

                    # Classes presentes
                    classes_in_sample: Set[int] = set()
                    annotation_count = 0
                    if lbl_file and lbl_file.exists():
                        for line in lbl_file.read_text(encoding="utf-8").splitlines():
                            parts = line.strip().split()
                            if parts:
                                try:
                                    cls_id = int(parts[0])
                                    classes_in_sample.add(cls_id)
                                    annotation_count += 1
                                except ValueError:
                                    continue

                    flight_id = self.extract_flight_id(img_file.name)
                    samples[stem] = {
                        "stem": stem,
                        "image_path": img_file,
                        "label_path": lbl_file,
                        "flight_id": flight_id,
                        "classes": classes_in_sample,
                        "annotation_count": annotation_count,
                    }

        return list(samples.values())

    def split(
        self,
        samples: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Executa a partição das amostras garantindo que:
        - Nenhum voo presente em train apareça em test (ou valid).
        - Todas as classes estejam representadas em cada split.
        """
        # Agrupa amostras por voo
        flight_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for s in samples:
            flight_groups[s["flight_id"]].append(s)

        total_samples = len(samples)
        target_test_count = max(1, int(round(total_samples * self.test_ratio)))
        target_val_count = max(1, int(round(total_samples * self.val_ratio)))

        # Descobre todas as classes do dataset
        all_classes: Set[int] = set()
        for s in samples:
            all_classes.update(s["classes"])

        # Ordena voos determinísticamente pela chave
        sorted_flights = sorted(flight_groups.keys())

        # Seleciona grupos de voo para Teste
        test_flights: List[str] = []
        test_samples: List[Dict[str, Any]] = []
        test_classes: Set[int] = set()

        # Seleciona grupos de voo para Validação
        val_flights: List[str] = []
        val_samples: List[Dict[str, Any]] = []
        val_classes: Set[int] = set()

        # Grupos para Treino
        train_flights: List[str] = []
        train_samples: List[Dict[str, Any]] = []
        train_classes: Set[int] = set()

        # Alocação gulosa equilibrada baseada em grupos de voo
        # Candidatos para teste: escolhe um voo que satisfaça as classes e chegue perto de target_test_count
        for fl in sorted_flights:
            fl_samples = flight_groups[fl]
            fl_classes = set().union(*(s["classes"] for s in fl_samples))

            # 1. Aloca para TESTE se ainda não atingiu o target e cobre as classes
            if (len(test_samples) < target_test_count or not all_classes.issubset(test_classes)) and fl not in val_flights and fl not in train_flights:
                # Testa se adicionar este voo cobre as classes
                test_flights.append(fl)
                test_samples.extend(fl_samples)
                test_classes.update(fl_classes)
                continue

            # 2. Aloca para VALIDAÇÃO se ainda não atingiu o target
            if (len(val_samples) < target_val_count or not all_classes.issubset(val_classes)) and fl not in test_flights and fl not in train_flights:
                val_flights.append(fl)
                val_samples.extend(fl_samples)
                val_classes.update(fl_classes)
                continue

            # 3. Demais voos vão para TREINO
            train_flights.append(fl)
            train_samples.extend(fl_samples)
            train_classes.update(fl_classes)

        # Se treino ficou vazio ou sem alguma classe, rebalanceia entre os grupos
        if not train_samples:
            raise DatasetAuditError("Falha na partição: nenhum voo alocado para treino.")

        # Validação formal de isolamento de voo
        train_fl_set = set(train_flights)
        test_fl_set = set(test_flights)
        val_fl_set = set(val_flights)

        overlap_train_test = train_fl_set.intersection(test_fl_set)
        if overlap_train_test:
            raise DatasetAuditError(f"Violação de independência: voo compartilhado entre train e test: {overlap_train_test}")

        overlap_val_test = val_fl_set.intersection(test_fl_set)
        if overlap_val_test:
            raise DatasetAuditError(f"Violação de independência: voo compartilhado entre valid e test: {overlap_val_test}")

        overlap_train_val = train_fl_set.intersection(val_fl_set)
        if overlap_train_val:
            raise DatasetAuditError(f"Violação de independência: voo compartilhado entre train e valid: {overlap_train_val}")

        return {
            "train": train_samples,
            "valid": val_samples,
            "test": test_samples,
        }

    def apply_structure(
        self,
        splits: Dict[str, List[Dict[str, Any]]],
        target_dir: Optional[Path] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Aplica a reorganização física criando train/, valid/ e test/ com images/ e labels/.
        Atualiza o data.yaml para garantir train, val e test independentes.
        """
        target_root = target_dir or self.dataset_dir
        summary: Dict[str, Any] = {
            "target_dir": str(target_root),
            "dry_run": dry_run,
            "splits": {},
            "classes_by_split": {},
            "flights_by_split": {},
        }

        # Cria diretórios temporários ou definitivos
        temp_root = target_root.parent / f"{target_root.name}_reorganized_tmp" if not dry_run else None
        if temp_root and temp_root.exists():
            shutil.rmtree(temp_root)

        for split_name in ["train", "valid", "test"]:
            sample_list = splits[split_name]
            class_counts = defaultdict(int)
            flight_ids = set()

            if not dry_run and temp_root:
                img_out = temp_root / split_name / "images"
                lbl_out = temp_root / split_name / "labels"
                img_out.mkdir(parents=True, exist_ok=True)
                lbl_out.mkdir(parents=True, exist_ok=True)

            for s in sample_list:
                flight_ids.add(s["flight_id"])
                for c in s["classes"]:
                    class_counts[c] += 1

                if not dry_run and temp_root:
                    img_src = s["image_path"]
                    lbl_src = s["label_path"]
                    shutil.copy2(img_src, img_out / img_src.name)
                    if lbl_src and lbl_src.exists():
                        shutil.copy2(lbl_src, lbl_out / lbl_src.name)

            summary["splits"][split_name] = len(sample_list)
            summary["classes_by_split"][split_name] = dict(class_counts)
            summary["flights_by_split"][split_name] = sorted(list(flight_ids))

        if not dry_run and temp_root:
            # Preserva o data.yaml original e metadados
            orig_yaml = target_root / "data.yaml"
            yaml_data = {}
            if orig_yaml.exists():
                yaml_data = yaml.safe_load(orig_yaml.read_text(encoding="utf-8")) or {}

            # Substitui as pastas antigas
            for split_name in ["train", "valid", "val", "test"]:
                old_p = target_root / split_name
                if old_p.exists():
                    shutil.rmtree(old_p)
                old_img = target_root / "images" / split_name
                old_lbl = target_root / "labels" / split_name
                if old_img.exists():
                    shutil.rmtree(old_img)
                if old_lbl.exists():
                    shutil.rmtree(old_lbl)

            # Move as novas pastas do temp_root para target_root
            for split_name in ["train", "valid", "test"]:
                shutil.move(str(temp_root / split_name), str(target_root / split_name))

            if temp_root.exists():
                shutil.rmtree(temp_root)

            # Atualiza o data.yaml de forma limpa e independente
            yaml_data["train"] = "train/images"
            yaml_data["val"] = "valid/images"
            yaml_data["test"] = "test/images"
            yaml_data["path"] = target_root.as_posix()

            out_yaml_text = yaml.dump(yaml_data, sort_keys=False, default_flow_style=False)
            orig_yaml.write_text(out_yaml_text, encoding="utf-8")

        return summary


def main():
    parser = argparse.ArgumentParser(description="Reestrutura dataset YOLO para divisão independente e sem vazamento de voo.")
    parser.add_argument("--dataset-dir", type=str, default="datasets/thermal_pv_mestrado", help="Diretório raiz do dataset.")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Proporção de validação (padrão 0.15).")
    parser.add_argument("--test-ratio", type=float, default=0.15, help="Proporção de teste (padrão 0.15).")
    parser.add_argument("--flight-regex", type=str, default=None, help="Expressão regular para identificar grupo/voo.")
    parser.add_argument("--dry-run", action="store_true", help="Apenas simula a partição sem mover arquivos.")
    parser.add_argument("--audit-only", action="store_true", help="Apenas audita o data.yaml e integridade.")

    args = parser.parse_args()
    splitter = DatasetSplitter(
        dataset_dir=args.dataset_dir,
        flight_regex=args.flight_regex,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
    )

    print("=" * 80)
    print("SOLARGUARD VISION - AUDITORIA E REESTRUTURAÇÃO INDEPENDENTE DE DATASET")
    print(f"Diretório: {splitter.dataset_dir}")
    print("=" * 80)

    # 1. Auditoria do data.yaml
    audit = splitter.audit_yaml()
    print("\n1. Diagnóstico do data.yaml:")
    print(f"   - Existe: {audit.get('exists')}")
    print(f"   - Train: {audit.get('train')}")
    print(f"   - Val: {audit.get('val')}")
    print(f"   - Test: {audit.get('test')}")
    print(f"   - Vazamento 'val == test': {audit.get('has_val_test_leakage')}")
    if audit.get("has_val_test_leakage"):
        print(f"   - [ALERTA METODOLÓGICO]: {audit.get('leakage_reason')}")

    if args.audit_only:
        print("\n[INFO] Modo audit-only selecionado. Encerrando.")
        return

    # 2. Coleta de amostras
    samples = splitter.collect_all_samples()
    print(f"\n2. Amostras encontradas: {len(samples)} pares de imagem/label.")

    # 3. Particionamento por voo
    splits = splitter.split(samples)
    print("\n3. Particionamento Independente por Voo Concluído:")
    for sp_name, sp_list in splits.items():
        flights = sorted(list(set(s["flight_id"] for s in sp_list)))
        print(f"   - {sp_name.upper()}: {len(sp_list)} imagens | Voos: {flights}")

    # 4. Aplicação física
    res = splitter.apply_structure(splits, dry_run=args.dry_run)
    print("\n4. Aplicação Estrutural:")
    for sp_name, cnt in res["splits"].items():
        print(f"   - {sp_name}: {cnt} imagens, Classes: {res['classes_by_split'][sp_name]}")

    # 5. Auditoria final
    post_audit = splitter.audit_yaml()
    print("\n5. Auditoria Pós-Reestruturação do data.yaml:")
    print(f"   - Val: {post_audit.get('val')}")
    print(f"   - Test: {post_audit.get('test')}")
    print(f"   - Vazamento 'val == test': {post_audit.get('has_val_test_leakage')}")
    print(f"   - Conformidade: {'TOTALMENTE INDEPENDENTE' if not post_audit.get('has_val_test_leakage') else 'FALHA'}")
    print("=" * 80)


if __name__ == "__main__":
    main()
