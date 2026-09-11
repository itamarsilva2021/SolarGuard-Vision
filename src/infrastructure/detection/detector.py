"""
Motor de Detecção e Inferência YOLOv11 para Anomalias Térmicas Fotovoltaicas.
Implementa a interface IAnomalyDetector com renderização de bounding boxes e extração de recortes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Union, Tuple, TYPE_CHECKING
import cv2
import numpy as np

from src.domain.interfaces.anomaly_detector import IAnomalyDetector
from src.domain.entities.thermal_anomaly import ThermalAnomaly
from src.domain.enums.anomaly_type import AnomalyType
from src.domain.enums.severity_level import SeverityLevel
from src.domain.value_objects.bounding_box import BoundingBox
from src.infrastructure.detection.model_loader import ModelLoader
from src.core.logger import get_logger

if TYPE_CHECKING:
    from src.infrastructure.detection.defect_classifier import DefectClassifier

logger = get_logger("Detector")


class Detector(IAnomalyDetector):
    """
    Motor central de detecção de anomalias fotovoltaicas.
    Executa inferência do YOLOv11, correlaciona as caixas delimitadoras com a matriz de temperatura
    e fornece métodos para visualização e exibição técnica de Bounding Boxes.
    """

    # Cores BGR para plotagem por classe de defeito
    CLASS_COLORS = {
        AnomalyType.HOTSPOT: (0, 0, 255),             # Vermelho
        AnomalyType.DISCONNECTED_MODULE: (0, 140, 255),# Laranja
        AnomalyType.PID: (204, 0, 204),               # Roxo / Magenta
        AnomalyType.SOILING: (0, 215, 255),           # Amarelo Ouro
        AnomalyType.SHADING: (255, 191, 0),           # Azul Celeste
        AnomalyType.HEALTHY_MODULE: (0, 255, 0),      # Verde
    }

    def __init__(
        self,
        model_path: Optional[str | Path] = None,
        confidence_threshold: float = 0.35,
        iou_threshold: float = 0.50,
        defect_classifier: Optional[DefectClassifier] = None,
    ) -> None:
        """
        :param model_path: Caminho opcional para os pesos (.pt).
        :param confidence_threshold: Limiar de confiança mínimo para manter detecções.
        :param iou_threshold: Limiar de supressão de não-máximos (NMS).
        :param defect_classifier: Instância do classificador radiométrico.
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        if defect_classifier is None:
            from src.infrastructure.detection.defect_classifier import DefectClassifier
            self.classifier = DefectClassifier()
        else:
            self.classifier = defect_classifier

    def detect(
        self,
        image_bgr_or_rgb: Union[np.ndarray, str, Path],
        temperature_matrix: Optional[np.ndarray] = None,
        confidence_threshold: Optional[float] = None,
    ) -> List[ThermalAnomaly]:
        """
        Executa a inferência na imagem e retorna a lista de entidades ThermalAnomaly.
        
        :param image_bgr_or_rgb: Imagem em numpy array (BGR ou RGB) ou caminho do arquivo.
        :param temperature_matrix: Matriz radiométrica 2D em graus Celsius (°C).
        :param confidence_threshold: Sobrescreve o limiar de confiança padrão.
        :return: Lista de anomalias detectadas com Bounding Boxes e cálculo de Delta T.
        """
        # Carregar imagem se for string ou Path
        if isinstance(image_bgr_or_rgb, (str, Path)):
            img_path = Path(image_bgr_or_rgb)
            if not img_path.exists():
                raise FileNotFoundError(f"Arquivo de imagem não encontrado: {img_path}")
            img = cv2.imread(str(img_path))
            if img is None:
                raise ValueError(f"Não foi possível decodificar imagem para inferência: {img_path}")
        else:
            img = image_bgr_or_rgb

        h, w = img.shape[:2]
        conf_thr = confidence_threshold if confidence_threshold is not None else self.confidence_threshold

        # Carregar modelo via ModelLoader
        model = ModelLoader.load_model(self.model_path)

        # Executar inferência Ultralytics
        results = model.predict(
            source=img,
            conf=conf_thr,
            iou=self.iou_threshold,
            verbose=False,
        )

        anomalies: List[ThermalAnomaly] = []
        if not results or len(results) == 0:
            return anomalies

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return anomalies

        # Processar cada predição encontrada
        for box in boxes:
            # Coordenadas normalizadas da Bounding Box (suporta tensor, ndarray ou list)
            raw_box = box.xyxyn[0]
            if hasattr(raw_box, "tolist"):
                xyxy_norm = raw_box.tolist()
            else:
                xyxy_norm = list(raw_box)

            conf = float(box.conf[0])
            cls_id = int(box.cls[0])

            x_min, y_min, x_max, y_max = xyxy_norm

            # Garantir limites válidos
            x_min = max(0.0, min(1.0, x_min))
            y_min = max(0.0, min(1.0, y_min))
            x_max = max(x_min + 0.001, min(1.0, x_max))
            y_max = max(y_min + 0.001, min(1.0, y_max))

            bbox = BoundingBox(
                x_min=round(x_min, 4),
                y_min=round(y_min, 4),
                x_max=round(x_max, 4),
                y_max=round(y_max, 4),
                is_normalized=True,
            )

            # Obter nome ou id da classe
            raw_label = model.names.get(cls_id, str(cls_id)) if hasattr(model, "names") else cls_id
            anomaly_type = self.classifier.parse_anomaly_type(raw_label)

            # Avaliação radiométrica de temperatura e severidade IEC
            (
                severity,
                delta_t_obj,
                max_temp,
                min_temp,
                avg_temp,
                technical_notes,
            ) = self.classifier.evaluate_thermal_diagnosis(
                anomaly_type=anomaly_type,
                bbox=bbox,
                temperature_matrix=temperature_matrix,
            )

            anomaly = ThermalAnomaly(
                anomaly_type=anomaly_type,
                severity=severity,
                confidence=round(conf, 4),
                bbox=bbox,
                max_temp_celsius=max_temp,
                min_temp_celsius=min_temp,
                avg_temp_celsius=avg_temp,
                delta_t=delta_t_obj,
                notes=technical_notes,
            )
            anomalies.append(anomaly)

        return anomalies

    def render_detections(
        self,
        image: np.ndarray,
        anomalies: List[ThermalAnomaly],
        color_by: str = "severity",
        show_delta_t: bool = True,
        line_thickness: int = 2,
    ) -> np.ndarray:
        """
        Desenha e renderiza as caixas delimitadoras (Bounding Boxes), rótulos e métricas sobre a imagem.
        
        :param image: Imagem BGR sobre a qual desenhar.
        :param anomalies: Lista de anomalias detectadas.
        :param color_by: 'severity' (cores da norma IEC) ou 'class' (cores por tipo de falha).
        :param show_delta_t: Se True, anexa a medição de Delta T na etiqueta.
        :param line_thickness: Espessura da linha da caixa.
        :return: Imagem anotada pronta para exibição na UI ou exportação.
        """
        annotated = image.copy()
        h, w = annotated.shape[:2]

        for anomaly in anomalies:
            pixel_bbox = anomaly.bbox.to_pixels(w, h)
            x1 = int(round(pixel_bbox.x_min))
            y1 = int(round(pixel_bbox.y_min))
            x2 = int(round(pixel_bbox.x_max))
            y2 = int(round(pixel_bbox.y_max))

            # Determina a cor com base na severidade ou classe
            if color_by == "severity":
                # Conversão Hex -> BGR para OpenCV
                hex_color = anomaly.severity.color_hex.lstrip("#")
                r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
                box_color = (b, g, r)
            else:
                box_color = self.CLASS_COLORS.get(anomaly.anomaly_type, (0, 255, 255))

            # Desenha retângulo da bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, line_thickness, cv2.LINE_AA)

            # Montagem do texto do rótulo
            conf_pct = int(anomaly.confidence * 100)
            class_name = anomaly.anomaly_type.display_name.split("(")[0].strip()
            label = f"{class_name} {conf_pct}%"

            if show_delta_t and anomaly.delta_t is not None:
                label += f" | dT {anomaly.delta_t.value:+.1f}C"
            elif show_delta_t and anomaly.max_temp_celsius is not None:
                label += f" | {anomaly.max_temp_celsius:.1f}C"

            # Desenha fundo da etiqueta com cantos limpos
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.42
            font_thickness = 1
            (tw, th), baseline = cv2.getTextSize(label, font, font_scale, font_thickness)

            label_y1 = max(0, y1 - th - 6)
            label_y2 = y1
            label_x2 = min(w, x1 + tw + 8)

            # Tarja de fundo
            cv2.rectangle(annotated, (x1, label_y1), (label_x2, label_y2), box_color, -1)

            # Texto contrastante (preto para fundos claros/amarelos, branco para escuros)
            text_color = (0, 0, 0) if (box_color[0] + box_color[1] + box_color[2]) > 380 else (255, 255, 255)
            cv2.putText(
                annotated,
                label,
                (x1 + 4, y1 - 4),
                font,
                font_scale,
                text_color,
                font_thickness,
                cv2.LINE_AA,
            )

        return annotated

    def extract_defect_crop(
        self,
        image: np.ndarray,
        anomaly: ThermalAnomaly,
        padding_pixels: int = 16,
    ) -> np.ndarray:
        """
        Extrai o recorte da anomalia com margem de segurança (padding) para relatórios fotográficos.
        """
        h, w = image.shape[:2]
        pixel_bbox = anomaly.bbox.to_pixels(w, h)

        x1 = max(0, int(pixel_bbox.x_min - padding_pixels))
        y1 = max(0, int(pixel_bbox.y_min - padding_pixels))
        x2 = min(w, int(pixel_bbox.x_max + padding_pixels))
        y2 = min(h, int(pixel_bbox.y_max + padding_pixels))

        crop = image[y1:y2, x1:x2]
        return crop
