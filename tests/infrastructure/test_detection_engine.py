"""
Testes unitários e integrados para a Engine de Detecção (Etapa 6).
Valida ModelLoader, DefectClassifier e Detector com as 5 classes de falhas e exibição de bounding boxes.
"""

import pytest
import numpy as np
import cv2
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.domain.enums.anomaly_type import AnomalyType
from src.domain.enums.severity_level import SeverityLevel
from src.domain.value_objects.bounding_box import BoundingBox
from src.domain.entities.thermal_anomaly import ThermalAnomaly
from src.infrastructure.detection.model_loader import ModelLoader
from src.infrastructure.detection.defect_classifier import DefectClassifier
from src.infrastructure.detection.detector import Detector


class TestModelLoader:
    def test_optimal_device_detection(self):
        device = ModelLoader.get_optimal_device("auto")
        assert device in ["cpu", "cuda:0"]

        explicit_cpu = ModelLoader.get_optimal_device("cpu")
        assert explicit_cpu == "cpu"

    def test_resolve_model_path(self):
        # Quando chamado sem arquivo existente, retorna caminho default
        resolved = ModelLoader.resolve_model_path()
        assert isinstance(resolved, Path)

    def test_clear_cache(self):
        ModelLoader._cached_model = "DUMMY_MODEL"
        ModelLoader.clear_cache()
        assert ModelLoader._cached_model is None


class TestDefectClassifier:
    def test_class_mapping_for_all_five_faults(self):
        classifier = DefectClassifier()

        # 1. Hotspot
        assert classifier.parse_anomaly_type("hotspot") == AnomalyType.HOTSPOT
        assert classifier.parse_anomaly_type("0") == AnomalyType.HOTSPOT

        # 2. PID
        assert classifier.parse_anomaly_type("pid") == AnomalyType.PID
        assert classifier.parse_anomaly_type("2") == AnomalyType.PID

        # 3. Sujidade (Soiling)
        assert classifier.parse_anomaly_type("sujidade") == AnomalyType.SOILING
        assert classifier.parse_anomaly_type("soiling") == AnomalyType.SOILING
        assert classifier.parse_anomaly_type("3") == AnomalyType.SOILING

        # 4. Sombreamento (Shading)
        assert classifier.parse_anomaly_type("sombreamento") == AnomalyType.SHADING
        assert classifier.parse_anomaly_type("shading") == AnomalyType.SHADING
        assert classifier.parse_anomaly_type("4") == AnomalyType.SHADING

        # 5. Módulo Desconectado (Disconnected Module)
        assert classifier.parse_anomaly_type("modulo_desconectado") == AnomalyType.DISCONNECTED_MODULE
        assert classifier.parse_anomaly_type("disconnected_module") == AnomalyType.DISCONNECTED_MODULE
        assert classifier.parse_anomaly_type("1") == AnomalyType.DISCONNECTED_MODULE

    def test_evaluate_thermal_diagnosis_with_matrix(self):
        classifier = DefectClassifier()
        # Matriz térmica sintética: fundo a 35 °C, hotspot a 70 °C
        matrix = np.full((100, 100), 35.0, dtype=np.float32)
        matrix[40:60, 40:60] = 70.0

        bbox = BoundingBox(x_min=0.4, y_min=0.4, x_max=0.6, y_max=0.6, is_normalized=True)

        severity, delta_t, max_t, min_t, avg_t, notes = classifier.evaluate_thermal_diagnosis(
            anomaly_type=AnomalyType.HOTSPOT,
            bbox=bbox,
            temperature_matrix=matrix,
            reference_temperature=35.0,
        )

        assert severity == SeverityLevel.CRITICAL
        assert delta_t is not None
        assert delta_t.value == 35.0
        assert max_t == 70.0
        assert "Classe 3" in notes
        assert "Hotspot Crítico" in notes


class TestDetector:
    @pytest.fixture
    def sample_anomalies(self) -> list[ThermalAnomaly]:
        """Cria instâncias de teste representando as 5 classes de falhas."""
        anomalies = [
            # 1. Hotspot
            ThermalAnomaly(
                anomaly_type=AnomalyType.HOTSPOT,
                severity=SeverityLevel.CRITICAL,
                confidence=0.95,
                bbox=BoundingBox(0.2, 0.2, 0.3, 0.3),
                max_temp_celsius=72.0,
            ),
            # 2. PID
            ThermalAnomaly(
                anomaly_type=AnomalyType.PID,
                severity=SeverityLevel.MEDIUM,
                confidence=0.88,
                bbox=BoundingBox(0.4, 0.4, 0.55, 0.55),
                max_temp_celsius=52.0,
            ),
            # 3. Sujidade
            ThermalAnomaly(
                anomaly_type=AnomalyType.SOILING,
                severity=SeverityLevel.LOW,
                confidence=0.82,
                bbox=BoundingBox(0.6, 0.2, 0.75, 0.35),
                max_temp_celsius=42.0,
            ),
            # 4. Sombreamento
            ThermalAnomaly(
                anomaly_type=AnomalyType.SHADING,
                severity=SeverityLevel.LOW,
                confidence=0.90,
                bbox=BoundingBox(0.7, 0.6, 0.9, 0.8),
                max_temp_celsius=38.0,
            ),
            # 5. Módulo Desconectado
            ThermalAnomaly(
                anomaly_type=AnomalyType.DISCONNECTED_MODULE,
                severity=SeverityLevel.LOW,
                confidence=0.93,
                bbox=BoundingBox(0.1, 0.6, 0.3, 0.85),
                max_temp_celsius=41.0,
            ),
        ]
        return anomalies

    def test_render_bounding_boxes_severity_and_class(self, sample_anomalies):
        detector = Detector()
        base_img = np.zeros((400, 600, 3), dtype=np.uint8)

        # 1. Renderizar caixas coloridas por severidade IEC
        rendered_sev = detector.render_detections(base_img, sample_anomalies, color_by="severity")
        assert rendered_sev.shape == (400, 600, 3)
        # Imagem não pode mais ser totalmente preta (bounding boxes e rótulos desenhados)
        assert np.sum(rendered_sev) > 0

        # 2. Renderizar caixas coloridas por tipo de classe
        rendered_cls = detector.render_detections(base_img, sample_anomalies, color_by="class")
        assert rendered_cls.shape == (400, 600, 3)
        assert np.sum(rendered_cls) > 0

    def test_extract_defect_crop(self, sample_anomalies):
        detector = Detector()
        img = np.full((300, 300, 3), 120, dtype=np.uint8)
        # Desenha um círculo no local do hotspot
        cv2.circle(img, (75, 75), 15, (0, 0, 255), -1)

        crop = detector.extract_defect_crop(img, sample_anomalies[0], padding_pixels=10)
        assert crop.size > 0
        assert crop.ndim == 3
        # Recorte deve ter dimensões compatíveis com o bbox + padding
        h, w = crop.shape[:2]
        assert h > 20 and w > 20

    @patch("src.infrastructure.detection.detector.ModelLoader.load_model")
    def test_detect_with_mocked_yolo(self, mock_load_model):
        """Valida que o detector orquestra as caixas retornadas pelo YOLO."""
        # Criação de mocks para simular saída do predict do Ultralytics
        mock_box = MagicMock()
        mock_box.xyxyn = [[0.2, 0.3, 0.5, 0.6]]
        mock_box.conf = [0.94]
        mock_box.cls = [0]  # Hotspot

        mock_result = MagicMock()
        mock_result.boxes = [mock_box]

        mock_model = MagicMock()
        mock_model.names = {0: "hotspot", 1: "disconnected_module"}
        mock_model.predict.return_value = [mock_result]
        mock_load_model.return_value = mock_model

        detector = Detector()
        dummy_img = np.zeros((200, 200, 3), dtype=np.uint8)
        dummy_matrix = np.full((200, 200), 32.0, dtype=np.float32)
        dummy_matrix[60:120, 40:100] = 68.0  # Hotspot

        anomalies = detector.detect(dummy_img, temperature_matrix=dummy_matrix)

        assert len(anomalies) == 1
        anom = anomalies[0]
        assert anom.anomaly_type == AnomalyType.HOTSPOT
        assert anom.confidence == 0.94
        assert anom.severity == SeverityLevel.CRITICAL
        assert anom.delta_t is not None
        assert anom.delta_t.value == 36.0
