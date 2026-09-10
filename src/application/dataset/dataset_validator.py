"""
Validador de integridade e consistência relacional de datasets YOLOv11.
Detecta imagens sem labels, labels órfãos, classes desconhecidas e arquivos corrompidos.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from PIL import Image

from src.application.dataset.annotation_validator import (
    AnnotationValidator,
    AnnotationError,
    ParsedAnnotation,
)
from src.infrastructure.ml.dataset_loader import PV_CLASSES
from src.core.logger import get_logger

logger = get_logger("DatasetValidator")


@dataclass
class DatasetValidationReport:
    """Relatório consolidado de validação relacional do dataset."""
    dataset_path: str
    total_images: int = 0
    total_labels: int = 0
    valid_pairs: int = 0
    
    # Objetivo 1: Imagens sem labels
    images_without_label_file: List[str] = field(default_factory=list)
    empty_label_images: List[str] = field(default_factory=list)
    
    # Objetivo 2: Labels sem imagem
    orphan_labels: List[str] = field(default_factory=list)
    
    # Objetivo 3: Classes inválidas e anotações malformadas
    invalid_class_errors: List[AnnotationError] = field(default_factory=list)
    syntax_errors: List[AnnotationError] = field(default_factory=list)
    corrupted_images: List[str] = field(default_factory=list)
    
    # Anotações válidas agrupadas por imagem
    annotations_by_image: Dict[str, List[ParsedAnnotation]] = field(default_factory=dict)

    @property
    def is_consistent(self) -> bool:
        """Indica se o dataset está livre de erros críticos estruturais."""
        return (
            len(self.orphan_labels) == 0
            and len(self.invalid_class_errors) == 0
            and len(self.syntax_errors) == 0
            and len(self.corrupted_images) == 0
        )

    @property
    def total_annotations_count(self) -> int:
        """Número total de caixas delimitadoras anotadas com sucesso."""
        return sum(len(ann_list) for ann_list in self.annotations_by_image.values())


class DatasetValidator:
    """
    Varre a estrutura de pastas do dataset YOLOv11 e valida a paridade imagem-rótulo.
    """

    IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

    def __init__(
        self,
        allowed_classes: Optional[Dict[int, str]] = None,
        annotation_validator: Optional[AnnotationValidator] = None,
    ) -> None:
        self.allowed_classes = allowed_classes or PV_CLASSES
        self.ann_validator = annotation_validator or AnnotationValidator(self.allowed_classes)

    def validate(self, dataset_path: str | Path) -> DatasetValidationReport:
        """
        Executa a varredura completa do dataset em busca de inconsistências relacionais.
        
        :param dataset_path: Caminho raiz do dataset YOLO.
        :return: DatasetValidationReport detalhado.
        """
        root = Path(dataset_path).resolve()
        report = DatasetValidationReport(dataset_path=str(root))

        if not root.exists():
            logger.error(f"Diretório do dataset não encontrado: {root}")
            return report

        if root.is_file() and root.suffix.lower() in [".yaml", ".yml"]:
            root = root.parent

        # Identifica pares de diretórios (splits ou estrutura única plana)
        splits = self._resolve_splits(root)

        for img_dir, lbl_dir in splits:
            self._validate_split(img_dir, lbl_dir, report)

        logger.info(
            f"Validação concluída: {report.total_images} imagens, {report.total_labels} labels, "
            f"{len(report.images_without_label_file)} imagens sem label, {len(report.orphan_labels)} labels órfãos."
        )
        return report

    def _resolve_splits(self, root: Path) -> List[Tuple[Path, Path]]:
        """Identifica os diretórios de imagens e anotações do dataset."""
        splits: List[Tuple[Path, Path]] = []

        # Caso 1: Estrutura padrão Ultralytics YOLO com images/train / images/val / images/valid / images/test
        for split_name in ["train", "val", "valid", "test"]:
            img_dir = root / "images" / split_name
            lbl_dir = root / "labels" / split_name
            if img_dir.exists() and lbl_dir.exists():
                splits.append((img_dir, lbl_dir))

        # Caso 1b: Estrutura Roboflow/Ultralytics train/images, valid/images, test/images
        if not splits:
            for split_name in ["train", "val", "valid", "test"]:
                img_dir = root / split_name / "images"
                lbl_dir = root / split_name / "labels"
                if img_dir.exists() and lbl_dir.exists():
                    splits.append((img_dir, lbl_dir))

        # Caso 2: Estrutura simples com images/ e labels/ no topo
        if not splits:
            img_top = root / "images"
            lbl_top = root / "labels"
            if img_top.exists() and lbl_top.exists():
                splits.append((img_top, lbl_top))

        # Caso 3: Pasta única contendo imagens e arquivos .txt misturados
        if not splits:
            splits.append((root, root))

        return splits

    def _validate_split(self, img_dir: Path, lbl_dir: Path, report: DatasetValidationReport) -> None:
        """Valida um split específico (ex: images/train vs labels/train)."""
        # Mapeia todas as imagens por stem (nome sem extensão)
        img_map: Dict[str, Path] = {}
        if img_dir.exists():
            for f in img_dir.iterdir():
                if f.is_file() and f.suffix.lower() in self.IMAGE_EXTENSIONS:
                    img_map[f.stem] = f
                    report.total_images += 1

        # Mapeia todos os arquivos de rótulo .txt
        lbl_map: Dict[str, Path] = {}
        if lbl_dir.exists():
            for f in lbl_dir.iterdir():
                if f.is_file() and f.suffix.lower() == ".txt" and f.name != "classes.txt":
                    lbl_map[f.stem] = f
                    report.total_labels += 1

        # 1. Checagem de Imagens (verificar se têm label e se estão íntegras)
        for stem, img_path in img_map.items():
            # Teste de leitura básica de integridade da imagem
            try:
                with Image.open(img_path) as img:
                    img.verify()
            except Exception:
                report.corrupted_images.append(str(img_path))

            if stem not in lbl_map:
                # Objetivo 1: Imagem sem arquivo de label
                report.images_without_label_file.append(str(img_path))
                report.annotations_by_image[str(img_path)] = []
            else:
                # Possui arquivo de label: validar conteúdo
                lbl_path = lbl_map[stem]
                valid_anns, errors = self.ann_validator.validate_file(lbl_path)

                if len(valid_anns) == 0 and len(errors) == 0:
                    # Arquivo vazio (imagem de fundo / background puro)
                    report.empty_label_images.append(str(img_path))

                for err in errors:
                    if "classe inválida" in err.error_message.lower():
                        report.invalid_class_errors.append(err)
                    else:
                        report.syntax_errors.append(err)

                report.annotations_by_image[str(img_path)] = valid_anns
                report.valid_pairs += 1

        # 2. Objetivo 2: Checagem de Labels Órfãos (labels sem imagem correspondente)
        for stem, lbl_path in lbl_map.items():
            if stem not in img_map:
                report.orphan_labels.append(str(lbl_path))
