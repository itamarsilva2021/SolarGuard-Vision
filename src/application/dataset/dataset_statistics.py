"""
Calculadora de estatísticas descritivas e distribuição de classes em datasets YOLOv11.
Mapeia volume de anotações, proporções, densidade por imagem e características geométricas.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np

from src.application.dataset.annotation_validator import ParsedAnnotation
from src.application.dataset.dataset_validator import DatasetValidationReport
from src.infrastructure.ml.dataset_loader import PV_CLASSES


@dataclass(frozen=True)
class ClassDistributionItem:
    """Estatísticas detalhadas para uma classe específica."""
    class_id: int
    class_name: str
    instance_count: int
    percentage: float
    images_containing_count: int
    avg_box_width: float
    avg_box_height: float
    avg_box_area: float


@dataclass
class DatasetStatistics:
    """Estatísticas globais e por classe calculadas sobre o dataset."""
    total_images: int
    total_annotations: int
    annotated_images_count: int
    background_images_count: int
    
    # Métricas de densidade
    avg_boxes_per_image: float
    max_boxes_in_single_image: int
    min_boxes_in_single_image: int
    
    # Distribuição por classe
    class_distribution: List[ClassDistributionItem] = field(default_factory=list)
    counts_by_class_name: Dict[str, int] = field(default_factory=dict)
    percentages_by_class_name: Dict[str, float] = field(default_factory=dict)

    # Médias geométricas
    global_avg_width: float = 0.0
    global_avg_height: float = 0.0
    global_avg_aspect_ratio: float = 0.0


class DatasetStatisticsCalculator:
    """
    Computa métricas quantitativas e distribuições probabilísticas a partir
    das anotações validadas pelo DatasetValidator.
    """

    def __init__(self, allowed_classes: Optional[Dict[int, str]] = None) -> None:
        self.allowed_classes = allowed_classes or PV_CLASSES

    def calculate(self, validation_report: DatasetValidationReport) -> DatasetStatistics:
        """
        Calcula as estatísticas consolidadas do dataset a partir do relatório de validação.
        
        :param validation_report: DatasetValidationReport retornado pelo DatasetValidator.
        :return: DatasetStatistics consolidado.
        """
        total_images = validation_report.total_images
        annotations_by_img = validation_report.annotations_by_image

        all_annotations: List[ParsedAnnotation] = []
        boxes_per_image_counts: List[int] = []
        images_per_class: Dict[int, int] = {cid: 0 for cid in self.allowed_classes.keys()}
        annotations_per_class: Dict[int, List[ParsedAnnotation]] = {
            cid: [] for cid in self.allowed_classes.keys()
        }

        annotated_images_count = 0
        background_images_count = 0

        for img_path, anns in annotations_by_img.items():
            num_boxes = len(anns)
            boxes_per_image_counts.append(num_boxes)

            if num_boxes > 0:
                annotated_images_count += 1
                seen_in_image = set()
                for ann in anns:
                    all_annotations.append(ann)
                    if ann.class_id in annotations_per_class:
                        annotations_per_class[ann.class_id].append(ann)
                        if ann.class_id not in seen_in_image:
                            images_per_class[ann.class_id] += 1
                            seen_in_image.add(ann.class_id)
            else:
                background_images_count += 1

        total_annotations = len(all_annotations)

        # Densidade de caixas
        avg_boxes = float(np.mean(boxes_per_image_counts)) if boxes_per_image_counts else 0.0
        max_boxes = int(max(boxes_per_image_counts)) if boxes_per_image_counts else 0
        min_boxes = int(min(boxes_per_image_counts)) if boxes_per_image_counts else 0

        # Médias geométricas globais
        if all_annotations:
            widths = [a.width for a in all_annotations]
            heights = [a.height for a in all_annotations]
            aspect_ratios = [a.width / a.height if a.height > 0 else 1.0 for a in all_annotations]
            global_avg_w = float(np.mean(widths))
            global_avg_h = float(np.mean(heights))
            global_avg_ar = float(np.mean(aspect_ratios))
        else:
            global_avg_w, global_avg_h, global_avg_ar = 0.0, 0.0, 0.0

        # Distribuição detalhada por classe
        distribution_items: List[ClassDistributionItem] = []
        counts_by_name: Dict[str, int] = {}
        pcts_by_name: Dict[str, float] = {}

        for cid, cname in sorted(self.allowed_classes.items()):
            cls_anns = annotations_per_class[cid]
            count = len(cls_anns)
            pct = round((count / total_annotations * 100.0), 2) if total_annotations > 0 else 0.0

            if cls_anns:
                c_avg_w = float(np.mean([a.width for a in cls_anns]))
                c_avg_h = float(np.mean([a.height for a in cls_anns]))
                c_avg_area = float(np.mean([a.width * a.height for a in cls_anns]))
            else:
                c_avg_w, c_avg_h, c_avg_area = 0.0, 0.0, 0.0

            item = ClassDistributionItem(
                class_id=cid,
                class_name=cname,
                instance_count=count,
                percentage=pct,
                images_containing_count=images_per_class[cid],
                avg_box_width=round(c_avg_w, 4),
                avg_box_height=round(c_avg_h, 4),
                avg_box_area=round(c_avg_area, 4),
            )
            distribution_items.append(item)
            counts_by_name[cname] = count
            pcts_by_name[cname] = pct

        return DatasetStatistics(
            total_images=total_images,
            total_annotations=total_annotations,
            annotated_images_count=annotated_images_count,
            background_images_count=background_images_count,
            avg_boxes_per_image=round(avg_boxes, 2),
            max_boxes_in_single_image=max_boxes,
            min_boxes_in_single_image=min_boxes,
            class_distribution=distribution_items,
            counts_by_class_name=counts_by_name,
            percentages_by_class_name=pcts_by_name,
            global_avg_width=round(global_avg_w, 4),
            global_avg_height=round(global_avg_h, 4),
            global_avg_aspect_ratio=round(global_avg_ar, 2),
        )
