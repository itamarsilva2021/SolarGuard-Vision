"""
Módulo de Validação e Benchmark do Modelo YOLOv11 para o SolarGuard Vision.
Avalia mAP@50, mAP@50:95, Precisão e Revocação macro e por classe.
"""

from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

from src.infrastructure.ml.training_metrics import ValidationMetrics, ClassMetrics
from src.infrastructure.ml.dataset_loader import PV_CLASSES
from src.core.logger import get_logger

logger = get_logger("YoloV11Validator")


class YoloV11Validator:
    """
    Validador independente para avaliar pontos de checagem (.pt) no conjunto de validação ou teste.
    """

    def __init__(self, class_names: Optional[Dict[int, str]] = None) -> None:
        self.class_names = class_names or PV_CLASSES

    def evaluate(
        self,
        weights_path: str | Path,
        data_yaml: str | Path,
        imgsz: int = 640,
        device: str = "auto",
        conf_threshold: float = 0.001,
        iou_threshold: float = 0.60,
    ) -> ValidationMetrics:
        """
        Executa a avaliação do modelo no conjunto de dados de validação especificado no data.yaml.
        
        :param weights_path: Caminho do arquivo de pesos .pt (ex: best.pt).
        :param data_yaml: Caminho do arquivo data.yaml do dataset.
        :param imgsz: Resolução da imagem para inferência.
        :param device: Dispositivo de execução ('cpu', '0', 'auto').
        :param conf_threshold: Limiar de confiança de detecção.
        :param iou_threshold: Limiar de IoU para Non-Maximum Suppression (NMS).
        :return: Objeto ValidationMetrics estruturado com os resultados.
        """
        from ultralytics import YOLO

        weights_path = Path(weights_path).resolve()
        data_yaml = Path(data_yaml).resolve()

        if not weights_path.exists():
            raise FileNotFoundError(f"Pesos do modelo não encontrados: {weights_path}")
        if not data_yaml.exists():
            raise FileNotFoundError(f"Arquivo data.yaml não encontrado: {data_yaml}")

        logger.info(f"Iniciando validação do modelo {weights_path.name} com {data_yaml.name}...")
        model = YOLO(str(weights_path))

        val_args = {
            "data": str(data_yaml),
            "imgsz": imgsz,
            "conf": conf_threshold,
            "iou": iou_threshold,
            "verbose": False,
            "plots": False,
        }
        if device != "auto":
            val_args["device"] = device

        metrics_result = model.val(**val_args)

        # Extração de métricas globais
        box_metrics = metrics_result.box
        map50 = float(box_metrics.map50)
        map50_95 = float(box_metrics.map)
        precision = float(box_metrics.mp)
        recall = float(box_metrics.mr)

        inference_speed = float(metrics_result.speed.get("inference", 0.0))

        # Extração de métricas por classe
        per_class_metrics: Dict[str, ClassMetrics] = {}
        names = model.names or self.class_names

        if hasattr(box_metrics, "maps") and box_metrics.maps is not None:
            maps_per_class = box_metrics.maps
            precisions = getattr(box_metrics, "p", [precision] * len(names))
            recalls = getattr(box_metrics, "r", [recall] * len(names))

            for cls_idx, cls_name in names.items():
                if cls_idx < len(maps_per_class):
                    p_val = float(precisions[cls_idx]) if cls_idx < len(precisions) else precision
                    r_val = float(recalls[cls_idx]) if cls_idx < len(recalls) else recall
                    map_val = float(maps_per_class[cls_idx])

                    per_class_metrics[cls_name] = ClassMetrics(
                        class_name=cls_name,
                        class_id=cls_idx,
                        precision=p_val,
                        recall=r_val,
                        map50=map_val,
                        map50_95=map_val,
                    )

        validation_metrics = ValidationMetrics(
            map50=map50,
            map50_95=map50_95,
            precision=precision,
            recall=recall,
            class_metrics=per_class_metrics,
            inference_time_ms=inference_speed,
            evaluated_at=datetime.now(),
        )

        logger.info(
            f"Validação concluída: mAP50={map50:.4f}, mAP50-95={map50_95:.4f}, "
            f"Precisão={precision:.4f}, Revocação={recall:.4f}"
        )
        return validation_metrics
