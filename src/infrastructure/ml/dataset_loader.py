"""
Carregador, Validador e Gerador de Datasets no formato Ultralytics YOLOv11 para o SolarGuard Vision.
Suporta as 6 classes de anomalias térmicas fotovoltaicas.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import shutil
import random
from src.core.logger import get_logger

logger = get_logger("YoloDatasetLoader")

# Mapeamento oficial de classes de anomalias térmicas
PV_CLASSES: Dict[int, str] = {
    0: "hotspot",
    1: "disconnected_module",
    2: "pid",
    3: "soiling",
    4: "shading",
    5: "healthy_module",
}


class YoloDatasetLoader:
    """
    Gerencia e valida datasets de termografia fotovoltaica no formato YOLO.
    """

    def __init__(self, classes: Optional[Dict[int, str]] = None) -> None:
        self.classes = classes or PV_CLASSES

    def create_yaml_config(
        self,
        dataset_dir: str | Path,
        output_yaml_path: Optional[str | Path] = None,
        train_rel_path: str = "images/train",
        val_rel_path: str = "images/val",
        test_rel_path: Optional[str] = "images/test",
    ) -> Path:
        """
        Gera o arquivo de configuração dataset.yaml exigido pelo YOLOv11.
        
        :param dataset_dir: Diretório raiz do dataset.
        :param output_yaml_path: Caminho do arquivo YAML a ser criado (padrão: dataset_dir/data.yaml).
        :param train_rel_path: Subdiretório relativo de treino.
        :param val_rel_path: Subdiretório relativo de validação.
        :param test_rel_path: Subdiretório relativo de teste.
        :return: Path do arquivo YAML gerado.
        """
        dataset_dir = Path(dataset_dir).resolve()
        yaml_path = Path(output_yaml_path) if output_yaml_path else dataset_dir / "data.yaml"
        yaml_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            f"# ==============================================================================",
            f"# SolarGuard Vision - Configuração do Dataset YOLOv11",
            f"# ==============================================================================",
            f"path: {dataset_dir.as_posix()}",
            f"train: {train_rel_path}",
            f"val: {val_rel_path}",
        ]

        if test_rel_path and (dataset_dir / test_rel_path).exists():
            lines.append(f"test: {test_rel_path}")

        lines.append("")
        lines.append("names:")
        for idx, name in sorted(self.classes.items()):
            lines.append(f"  {idx}: {name}")

        yaml_content = "\n".join(lines) + "\n"
        yaml_path.write_text(yaml_content, encoding="utf-8")
        logger.info(f"Arquivo de configuração YOLO gerado em: {yaml_path}")
        return yaml_path

    def validate_dataset(self, dataset_dir: str | Path) -> dict:
        """
        Valida a integridade estrutural e de anotações do dataset YOLO.
        Verifica correspondência entre imagens e arquivos .txt de labels,
        além dos limites das bounding boxes normalizadas [0, 1].
        """
        dataset_dir = Path(dataset_dir)
        summary: dict = {
            "valid": True,
            "train_images": 0,
            "val_images": 0,
            "test_images": 0,
            "class_counts": {name: 0 for name in self.classes.values()},
            "errors": [],
            "warnings": [],
        }

        splits = [("train", "images/train", "labels/train"), ("val", "images/val", "labels/val")]
        if (dataset_dir / "images/test").exists():
            splits.append(("test", "images/test", "labels/test"))

        for split_name, img_sub, lbl_sub in splits:
            img_dir = dataset_dir / img_sub
            lbl_dir = dataset_dir / lbl_sub

            if not img_dir.exists():
                summary["valid"] = False
                summary["errors"].append(f"Diretório de imagens ausente: {img_dir}")
                continue

            # Extensões válidas de imagem
            img_files = [f for f in img_dir.iterdir() if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".tif", ".tiff"]]
            summary[f"{split_name}_images"] = len(img_files)

            for img_file in img_files:
                lbl_file = lbl_dir / f"{img_file.stem}.txt" if lbl_dir.exists() else None

                # Se arquivo de label não existe, é tratado como imagem de fundo (negativo/saudável sem anomalias)
                if not lbl_file or not lbl_file.exists():
                    continue

                try:
                    lines = lbl_file.read_text(encoding="utf-8").strip().splitlines()
                    for line_idx, line in enumerate(lines, 1):
                        parts = line.strip().split()
                        if len(parts) != 5:
                            summary["warnings"].append(
                                f"{lbl_file.name}:{line_idx} - formato inválido (esperado 5 campos, encontrado {len(parts)})."
                            )
                            continue

                        cls_id = int(parts[0])
                        cx, cy, w, h = map(float, parts[1:])

                        if cls_id not in self.classes:
                            summary["warnings"].append(
                                f"{lbl_file.name}:{line_idx} - class_id={cls_id} desconhecido."
                            )
                            continue

                        # Validação de limites normalizados [0.0, 1.0]
                        if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                            summary["warnings"].append(
                                f"{lbl_file.name}:{line_idx} - coordenadas normalizadas fora de [0, 1]: {parts[1:]}"
                            )

                        cls_name = self.classes[cls_id]
                        summary["class_counts"][cls_name] += 1

                except Exception as ex:
                    summary["warnings"].append(f"Erro ao ler anotação {lbl_file.name}: {ex}")

        return summary

    def split_dataset(
        self,
        source_images_dir: str | Path,
        source_labels_dir: str | Path,
        target_dataset_dir: str | Path,
        train_ratio: float = 0.8,
        val_ratio: float = 0.2,
        seed: int = 42,
    ) -> Path:
        """
        Organiza e particiona um conjunto bruto de fotos e anotações em train e val.
        """
        source_images_dir = Path(source_images_dir)
        source_labels_dir = Path(source_labels_dir)
        target_dir = Path(target_dataset_dir)

        images = [f for f in source_images_dir.iterdir() if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".tif", ".tiff"]]
        random.seed(seed)
        random.shuffle(images)

        train_count = int(len(images) * train_ratio)
        train_imgs = images[:train_count]
        val_imgs = images[train_count:]

        for split_name, img_list in [("train", train_imgs), ("val", val_imgs)]:
            split_img_dir = target_dir / "images" / split_name
            split_lbl_dir = target_dir / "labels" / split_name
            split_img_dir.mkdir(parents=True, exist_ok=True)
            split_lbl_dir.mkdir(parents=True, exist_ok=True)

            for img_file in img_list:
                shutil.copy2(img_file, split_img_dir / img_file.name)
                lbl_file = source_labels_dir / f"{img_file.stem}.txt"
                if lbl_file.exists():
                    shutil.copy2(lbl_file, split_lbl_dir / lbl_file.name)

        logger.info(f"Dataset particionado: {len(train_imgs)} treino, {len(val_imgs)} validação em {target_dir}")
        return self.create_yaml_config(target_dir)
