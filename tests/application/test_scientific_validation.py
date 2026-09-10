"""
Testes unitários e de integração para a suíte de validação científica da ETAPA 16.
Cobre cálculo de métricas (Accuracy, Precision, Recall, F1, mAP, ROC, AUC),
matriz de confusão, benchmark e exportação em PDF, Excel (.xlsx) e CSV.
"""

import os
import zipfile
import pytest
import numpy as np
from pathlib import Path

from src.application.validation.classification_metrics import (
    ClassificationMetricsCalculator,
    GlobalClassificationMetrics,
)
from src.application.validation.confusion_matrix_service import ConfusionMatrixService
from src.application.validation.roc_curve_service import RocCurveService, RocCurveData
from src.application.validation.benchmark_service import BenchmarkService, ModelBenchmarkResult
from src.application.validation.scientific_validation_report import (
    ScientificValidationReport,
    ScientificValidationReportData,
)


class TestClassificationMetrics:
    """Testes para o cálculo de métricas analíticas e estatísticas de classificação."""

    def test_perfect_classification(self):
        y_true = ["hotspot", "soiling", "hotspot", "pid", "disconnected_module"]
        y_pred = ["hotspot", "soiling", "hotspot", "pid", "disconnected_module"]

        metrics = ClassificationMetricsCalculator.calculate_from_labels(y_true, y_pred)

        assert metrics.total_samples == 5
        assert metrics.accuracy == pytest.approx(1.0)
        assert metrics.macro_precision == pytest.approx(1.0)
        assert metrics.macro_recall == pytest.approx(1.0)
        assert metrics.macro_f1 == pytest.approx(1.0)
        assert metrics.balanced_accuracy == pytest.approx(1.0)

        # Checa classe hotspot
        hs = metrics.per_class_metrics["hotspot"]
        assert hs.true_positives == 2
        assert hs.false_positives == 0
        assert hs.false_negatives == 0
        assert hs.f1_score == pytest.approx(1.0)

    def test_imperfect_classification_with_confusions(self):
        # 10 amostras com confusões realistas
        y_true = ["hotspot", "hotspot", "hotspot", "soiling", "soiling", "pid", "pid", "pid", "shading", "shading"]
        y_pred = ["hotspot", "hotspot", "soiling", "soiling", "hotspot", "pid", "pid", "pid", "shading", "soiling"]

        metrics = ClassificationMetricsCalculator.calculate_from_labels(y_true, y_pred)

        assert metrics.total_samples == 10
        # Corretos: 2 hotspot, 1 soiling, 3 pid, 1 shading = 7 corretos
        assert metrics.accuracy == pytest.approx(0.70)
        assert 0.0 < metrics.macro_f1 < 1.0
        assert 0.0 < metrics.weighted_f1 < 1.0

        # Verifica classe PID (100% perfeita)
        pid = metrics.per_class_metrics["pid"]
        assert pid.true_positives == 3
        assert pid.false_positives == 0
        assert pid.false_negatives == 0
        assert pid.precision == pytest.approx(1.0)
        assert pid.recall == pytest.approx(1.0)
        assert pid.f1_score == pytest.approx(1.0)

    def test_empty_lists_safety(self):
        metrics = ClassificationMetricsCalculator.calculate_from_labels([], [])
        assert metrics.total_samples == 0
        assert metrics.accuracy == 0.0
        assert metrics.macro_f1 == 0.0


class TestConfusionMatrixService:
    """Testes para construção, normalização e renderização da Matriz de Confusão."""

    def test_confusion_matrix_computation_and_normalization(self, tmp_path):
        service = ConfusionMatrixService()
        labels = ["hotspot", "soiling", "pid"]

        y_true = ["hotspot", "hotspot", "soiling", "soiling", "pid"]
        y_pred = ["hotspot", "soiling", "soiling", "soiling", "pid"]

        matrix, resolved = service.compute(y_true, y_pred, labels=labels)
        assert resolved == labels
        assert matrix.shape == (3, 3)

        # hotspot (row 0): 1 predito como hotspot, 1 predito como soiling, 0 como pid
        assert matrix[0, 0] == 1
        assert matrix[0, 1] == 1
        assert matrix[0, 2] == 0

        # soiling (row 1): 0 predito como hotspot, 2 predito como soiling
        assert matrix[1, 1] == 2

        # Normalização por linha (true / recall)
        norm_true = service.normalize(matrix, mode="true")
        assert norm_true[0, 0] == pytest.approx(0.5)
        assert norm_true[0, 1] == pytest.approx(0.5)
        assert norm_true[1, 1] == pytest.approx(1.0)

        # Plotagem gráfica
        img_path = tmp_path / "confusion_matrix.png"
        res_path = service.plot(matrix, labels, img_path, normalize_mode="true")
        assert res_path.exists()
        assert res_path.stat().st_size > 1000  # PNG válido gerado


class TestRocCurveService:
    """Testes para o cálculo de Curvas ROC, AUC e Youden's Index."""

    def test_perfect_binary_roc(self, tmp_path):
        service = RocCurveService()
        y_true = [1, 1, 1, 0, 0, 0]
        y_scores = [0.95, 0.88, 0.75, 0.30, 0.20, 0.10]

        roc = service.compute_binary_roc(y_true, y_scores, class_name="Hotspot")
        assert roc.class_name == "Hotspot"
        assert roc.auc == pytest.approx(1.0, abs=0.01)
        assert roc.optimal_threshold > 0.30
        assert roc.optimal_tpr == pytest.approx(1.0)
        assert roc.optimal_fpr == pytest.approx(0.0)

        # Renderização gráfica
        img_path = tmp_path / "roc_curve.png"
        res_img = service.plot_roc_curves(roc, img_path)
        assert res_img.exists()
        assert res_img.stat().st_size > 1000

    def test_multiclass_ovr_roc(self):
        service = RocCurveService()
        y_true = ["hotspot", "soiling", "hotspot", "soiling"]
        y_scores_dict = {
            "hotspot": [0.9, 0.2, 0.85, 0.15],
            "soiling": [0.1, 0.8, 0.15, 0.85],
        }

        ovr_results = service.compute_multiclass_ovr_roc(y_true, y_scores_dict)
        assert "hotspot" in ovr_results
        assert "soiling" in ovr_results
        assert ovr_results["hotspot"].auc == pytest.approx(1.0, abs=0.01)
        assert ovr_results["soiling"].auc == pytest.approx(1.0, abs=0.01)


class TestBenchmarkService:
    """Testes para cálculo de mAP e comparativo de modelos."""

    def test_ap_and_map_calculation(self):
        # 1. Teste de AP monótono
        recalls = np.array([0.2, 0.4, 0.6, 0.8, 1.0])
        precisions = np.array([1.0, 1.0, 0.8, 0.8, 0.6])
        ap = BenchmarkService.calculate_ap_from_pr(recalls, precisions)
        assert 0.7 <= ap <= 1.0

        # 2. Teste de mAP
        dets = {
            "hotspot": [(0.9, True), (0.8, True), (0.4, False)],
            "soiling": [(0.95, True), (0.5, False)],
        }
        gts = {"hotspot": 2, "soiling": 1}

        mean_ap, class_aps = BenchmarkService.calculate_map(dets, gts)
        assert 0.5 <= mean_ap <= 1.0
        assert "hotspot" in class_aps
        assert "soiling" in class_aps

    def test_model_ranking(self):
        service = BenchmarkService()
        m1 = service.evaluate_model("yolov11n", {"hotspot": 0.82, "soiling": 0.78}, global_precision=0.85, global_recall=0.80, inference_time_ms=12.5)
        m2 = service.evaluate_model("yolov11s", {"hotspot": 0.89, "soiling": 0.85}, global_precision=0.90, global_recall=0.88, inference_time_ms=25.0)

        ranked = service.rank_models([m1, m2], sort_by="map50")
        assert ranked[0].model_name == "yolov11s"
        assert ranked[1].model_name == "yolov11n"


class TestScientificValidationReport:
    """Testes para exportação unificada em PDF, Excel (.xlsx) e CSV."""

    @pytest.fixture
    def sample_report_data(self, tmp_path):
        y_true = ["hotspot", "hotspot", "soiling", "pid"]
        y_pred = ["hotspot", "hotspot", "soiling", "pid"]
        metrics = ClassificationMetricsCalculator.calculate_from_labels(y_true, y_pred)

        roc_service = RocCurveService()
        roc_data = {
            "hotspot": roc_service.compute_binary_roc([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1], class_name="hotspot")
        }

        bench_service = BenchmarkService()
        benchmark = bench_service.evaluate_model(
            "SolarGuard_YOLOv11_Thermal",
            {"hotspot": 0.94, "soiling": 0.88, "pid": 0.92},
            global_precision=0.92,
            global_recall=0.90,
            inference_time_ms=15.2,
        )

        # Gera PNGs sintéticos para matriz de confusão e ROC
        cm_service = ConfusionMatrixService()
        mat, _ = cm_service.compute(y_true, y_pred)
        cm_path = cm_service.plot(mat, ["hotspot", "soiling", "pid"], tmp_path / "test_cm.png")
        roc_path = roc_service.plot_roc_curves(roc_data, tmp_path / "test_roc.png")

        return ScientificValidationReportData(
            model_name="SolarGuard_YOLOv11_Thermal",
            dataset_name="Val_Thermal_PV_2026",
            metrics=metrics,
            roc_curves=roc_data,
            benchmark=benchmark,
            confusion_matrix_img=cm_path,
            roc_curve_img=roc_path,
            notes="Teste automatizado de auditoria científica para IEC TS 62446-3.",
        )

    def test_export_csv(self, sample_report_data, tmp_path):
        report_generator = ScientificValidationReport()
        csv_file = tmp_path / "validation_report.csv"

        out = report_generator.export_csv(sample_report_data, csv_file)
        assert out.exists()

        content = out.read_text(encoding="utf-8-sig")
        assert "SOLARGUARD VISION - RELATÓRIO CIENTÍFICO DE VALIDAÇÃO DE IA" in content
        assert "SolarGuard_YOLOv11_Thermal" in content
        assert "Acurácia Global (Accuracy)" in content
        assert "hotspot" in content

    def test_export_excel(self, sample_report_data, tmp_path):
        report_generator = ScientificValidationReport()
        xlsx_file = tmp_path / "validation_report.xlsx"

        out = report_generator.export_excel(sample_report_data, xlsx_file)
        assert out.exists()
        assert out.stat().st_size > 500

        # Valida que é um arquivo ZIP válido contendo a estrutura OpenXML
        with zipfile.ZipFile(out, "r") as zf:
            namelist = zf.namelist()
            assert "[Content_Types].xml" in namelist
            assert "xl/workbook.xml" in namelist
            assert "xl/worksheets/sheet1.xml" in namelist
            assert "xl/worksheets/sheet2.xml" in namelist

    def test_export_pdf(self, sample_report_data, tmp_path):
        report_generator = ScientificValidationReport()
        pdf_file = tmp_path / "validation_report.pdf"

        out = report_generator.export_pdf(sample_report_data, pdf_file)
        assert out.exists()
        assert out.stat().st_size > 5000

        # Valida cabeçalho PDF
        with open(out, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"
