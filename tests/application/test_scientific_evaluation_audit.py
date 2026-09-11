"""
Testes unitários rigorosos para a auditoria de avaliação científica.
Valida o pareamento de detecção de objetos (IoU >= 0.45) e o cálculo estatístico correto:
- Caso A: GT existe, Predição correta (IoU >= 0.45, mesma classe) -> True Positive
- Caso B: GT existe, Nenhuma detecção válida (IoU < 0.45 ou sem predição) -> False Negative (y_pred = 'background')
- Caso C: GT existe, Classe incorreta (IoU >= 0.45, classe diferente) -> Classification Error / Confusion
- Caso D: Predição sem Ground Truth -> False Positive (y_true = 'background')
"""

import pytest
import numpy as np
from src.application.services.experimental_evaluation_service import ExperimentalEvaluationService
from src.application.validation.classification_metrics import ClassificationMetricsCalculator


class TestScientificEvaluationAudit:
    @pytest.fixture
    def class_names(self):
        return {
            0: "hotspot",
            1: "diode_failure",
            2: "cracking",
        }

    def test_case_a_true_positive(self, class_names):
        """
        Caso A:
        Ground Truth existe e há predição com IoU >= 0.45 e mesma classe.
        Deve resultar em match exato: y_true == y_pred.
        """
        gt_boxes = [
            (0, 0.5, 0.5, 0.2, 0.2),  # hotspot no centro
        ]
        pred_boxes = [
            (0, 0.51, 0.49, 0.2, 0.2, 0.92),  # hotspot quase idêntico (IoU ~ 0.90)
        ]

        y_true, y_pred = ExperimentalEvaluationService.match_detections_with_ground_truth(
            gt_boxes=gt_boxes,
            pred_boxes=pred_boxes,
            class_names=class_names,
            iou_threshold=0.45,
            background_label="background",
        )

        assert len(y_true) == 1
        assert len(y_pred) == 1
        assert y_true[0] == "hotspot"
        assert y_pred[0] == "hotspot"

        # Métricas
        metrics = ClassificationMetricsCalculator.calculate_from_labels(
            y_true=y_true,
            y_pred=y_pred,
            labels=["hotspot", "diode_failure", "cracking", "background"],
            target_classes=["hotspot", "diode_failure", "cracking"],
        )
        assert metrics.accuracy == 1.0
        assert metrics.weighted_precision == 1.0
        assert metrics.weighted_recall == 1.0
        assert metrics.weighted_f1 == 1.0
        assert metrics.macro_precision == pytest.approx(1.0 / 3.0)
        assert metrics.macro_recall == pytest.approx(1.0 / 3.0)
        assert metrics.macro_f1 == pytest.approx(1.0 / 3.0)
        assert metrics.per_class_metrics["hotspot"].true_positives == 1
        assert metrics.per_class_metrics["hotspot"].false_negatives == 0
        assert metrics.per_class_metrics["hotspot"].false_positives == 0
        assert metrics.per_class_metrics["hotspot"].precision == 1.0
        assert metrics.per_class_metrics["hotspot"].recall == 1.0
        assert metrics.per_class_metrics["hotspot"].f1_score == 1.0

    def test_case_b_false_negative_when_no_detection(self, class_names):
        """
        Caso B (Cenário 1):
        Ground Truth existe e NENHUMA detecção foi produzida pelo modelo.
        DEVE resultar em Falso Negativo (y_pred == 'background') e NUNCA em acerto!
        """
        gt_boxes = [
            (0, 0.5, 0.5, 0.2, 0.2),  # hotspot
        ]
        pred_boxes = []  # nenhuma detecção

        y_true, y_pred = ExperimentalEvaluationService.match_detections_with_ground_truth(
            gt_boxes=gt_boxes,
            pred_boxes=pred_boxes,
            class_names=class_names,
            iou_threshold=0.45,
            background_label="background",
        )

        assert len(y_true) == 1
        assert len(y_pred) == 1
        assert y_true[0] == "hotspot"
        assert y_pred[0] == "background"  # Falso Negativo mapeado explicitamente para background!
        assert y_pred[0] != y_true[0]  # NUNCA assume acerto

        metrics = ClassificationMetricsCalculator.calculate_from_labels(
            y_true=y_true,
            y_pred=y_pred,
            labels=["hotspot", "diode_failure", "cracking", "background"],
            target_classes=["hotspot", "diode_failure", "cracking"],
        )
        # Como o único GT não foi detectado:
        assert metrics.accuracy == 0.0
        assert metrics.per_class_metrics["hotspot"].true_positives == 0
        assert metrics.per_class_metrics["hotspot"].false_negatives == 1
        assert metrics.per_class_metrics["hotspot"].recall == 0.0

    def test_case_b_false_negative_when_iou_insufficient(self, class_names):
        """
        Caso B (Cenário 2):
        Ground Truth existe e há predição, porém em local distante (IoU < 0.45).
        DEVE resultar em FN para o GT e FP para a predição distante.
        """
        gt_boxes = [
            (0, 0.2, 0.2, 0.1, 0.1),  # hotspot canto superior esquerdo
        ]
        pred_boxes = [
            (0, 0.8, 0.8, 0.1, 0.1, 0.85),  # predição canto inferior direito (IoU = 0.0)
        ]

        y_true, y_pred = ExperimentalEvaluationService.match_detections_with_ground_truth(
            gt_boxes=gt_boxes,
            pred_boxes=pred_boxes,
            class_names=class_names,
            iou_threshold=0.45,
            background_label="background",
        )

        # Deve gerar 2 pares: (gt -> background) e (background -> pred)
        assert len(y_true) == 2
        assert len(y_pred) == 2

        # 1. O GT não teve match -> FN
        assert ("hotspot", "background") in list(zip(y_true, y_pred))
        # 2. A predição não teve GT -> FP
        assert ("background", "hotspot") in list(zip(y_true, y_pred))

        metrics = ClassificationMetricsCalculator.calculate_from_labels(
            y_true=y_true,
            y_pred=y_pred,
            labels=["hotspot", "background"],
            target_classes=["hotspot"],
        )
        assert metrics.accuracy == 0.0
        assert metrics.per_class_metrics["hotspot"].true_positives == 0
        assert metrics.per_class_metrics["hotspot"].false_negatives == 1
        assert metrics.per_class_metrics["hotspot"].false_positives == 1

    def test_case_c_classification_error(self, class_names):
        """
        Caso C:
        Ground Truth existe com classe X, e predição tem IoU >= 0.45 mas classe Y.
        Deve registrar confusão: y_true == 'hotspot', y_pred == 'diode_failure'.
        """
        gt_boxes = [
            (0, 0.5, 0.5, 0.2, 0.2),  # hotspot
        ]
        pred_boxes = [
            (1, 0.5, 0.5, 0.2, 0.2, 0.88),  # diode_failure no mesmo lugar (IoU = 1.0)
        ]

        y_true, y_pred = ExperimentalEvaluationService.match_detections_with_ground_truth(
            gt_boxes=gt_boxes,
            pred_boxes=pred_boxes,
            class_names=class_names,
            iou_threshold=0.45,
            background_label="background",
        )

        assert len(y_true) == 1
        assert len(y_pred) == 1
        assert y_true[0] == "hotspot"
        assert y_pred[0] == "diode_failure"

        metrics = ClassificationMetricsCalculator.calculate_from_labels(
            y_true=y_true,
            y_pred=y_pred,
            labels=["hotspot", "diode_failure", "cracking", "background"],
            target_classes=["hotspot", "diode_failure", "cracking"],
        )
        assert metrics.accuracy == 0.0
        assert metrics.per_class_metrics["hotspot"].false_negatives == 1
        assert metrics.per_class_metrics["diode_failure"].false_positives == 1

    def test_case_d_false_positive_ghost_detection(self, class_names):
        """
        Caso D:
        Predição existe sem nenhum Ground Truth na imagem.
        Deve registrar: y_true == 'background', y_pred == 'cracking'.
        """
        gt_boxes = []  # Imagem sem anomalias
        pred_boxes = [
            (2, 0.3, 0.3, 0.15, 0.15, 0.75),  # falso alarme de cracking
        ]

        y_true, y_pred = ExperimentalEvaluationService.match_detections_with_ground_truth(
            gt_boxes=gt_boxes,
            pred_boxes=pred_boxes,
            class_names=class_names,
            iou_threshold=0.45,
            background_label="background",
        )

        assert len(y_true) == 1
        assert len(y_pred) == 1
        assert y_true[0] == "background"
        assert y_pred[0] == "cracking"

        metrics = ClassificationMetricsCalculator.calculate_from_labels(
            y_true=y_true,
            y_pred=y_pred,
            labels=["hotspot", "diode_failure", "cracking", "background"],
            target_classes=["hotspot", "diode_failure", "cracking"],
        )
        assert metrics.per_class_metrics["cracking"].false_positives == 1
        assert metrics.per_class_metrics["cracking"].true_positives == 0

    def test_multi_detection_greedy_matching(self, class_names):
        """
        Verifica greedy matching:
        Duas predições para o mesmo GT. A de maior confiança (e IoU válido) deve fazer match,
        e a predição excedente vira False Positive (background -> pred).
        """
        gt_boxes = [
            (0, 0.5, 0.5, 0.2, 0.2),  # hotspot
        ]
        pred_boxes = [
            (0, 0.51, 0.51, 0.2, 0.2, 0.95),  # predição 1: alta confiança
            (0, 0.52, 0.52, 0.2, 0.2, 0.60),  # predição 2: menor confiança para o mesmo GT
        ]

        y_true, y_pred = ExperimentalEvaluationService.match_detections_with_ground_truth(
            gt_boxes=gt_boxes,
            pred_boxes=pred_boxes,
            class_names=class_names,
            iou_threshold=0.45,
            background_label="background",
        )

        assert len(y_true) == 2
        assert len(y_pred) == 2
        # Um par de TP
        assert ("hotspot", "hotspot") in list(zip(y_true, y_pred))
        # Um par de FP para a detecção redundante
        assert ("background", "hotspot") in list(zip(y_true, y_pred))
