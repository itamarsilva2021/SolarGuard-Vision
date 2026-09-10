"""
Suíte de testes de integração e unitários para a camada de Auditoria de Datasets YOLOv11 (Etapa 13).
Cobre validação relacional, detecção de classes inválidas, cálculo estatístico,
análise de balanceamento, geração de relatório PDF e interface PySide6.
"""

import pytest
from pathlib import Path
from PIL import Image

from src.application.dataset.annotation_validator import AnnotationValidator
from src.application.dataset.dataset_validator import DatasetValidator
from src.application.dataset.dataset_statistics import DatasetStatisticsCalculator
from src.application.dataset.balance_analyzer import DatasetBalanceAnalyzer, BalanceSeverity
from src.application.dataset.dataset_audit import DatasetAuditor, DatasetAuditResult
from src.application.dataset.dataset_report import DatasetPdfReportGenerator
from src.infrastructure.ml.dataset_loader import PV_CLASSES


@pytest.fixture
def mock_dataset(tmp_path: Path) -> Path:
    """
    Cria uma estrutura de dataset YOLOv11 sintética contendo:
    - Imagens válidas com anotações de diferentes classes
    - 1 imagem sem label (background/órfã)
    - 1 label órfão sem imagem
    - 1 anotação com classe inválida
    - 1 imagem com label vazio
    """
    ds_dir = tmp_path / "pv_dataset"
    img_dir = ds_dir / "images" / "train"
    lbl_dir = ds_dir / "labels" / "train"
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    # Imagem 1: Válida com 2 anotações (hotspot e pid)
    img1 = Image.new("RGB", (640, 512), color=(100, 100, 100))
    img1.save(img_dir / "img_001.jpg")
    (lbl_dir / "img_001.txt").write_text("0 0.5 0.5 0.1 0.1\n2 0.3 0.3 0.2 0.1\n", encoding="utf-8")

    # Imagem 2: Válida com 1 anotação (hotspot)
    img2 = Image.new("RGB", (640, 512), color=(120, 120, 120))
    img2.save(img_dir / "img_002.jpg")
    (lbl_dir / "img_002.txt").write_text("0 0.6 0.6 0.15 0.15\n", encoding="utf-8")

    # Imagem 3: Válida com 1 anotação com classe inválida (classe 99)
    img3 = Image.new("RGB", (640, 512), color=(140, 140, 140))
    img3.save(img_dir / "img_003.jpg")
    (lbl_dir / "img_003.txt").write_text("99 0.4 0.4 0.2 0.2\n", encoding="utf-8")

    # Imagem 4: Imagem sem arquivo de label (Objetivo 1)
    img4 = Image.new("RGB", (640, 512), color=(160, 160, 160))
    img4.save(img_dir / "img_004_no_label.jpg")

    # Imagem 5: Imagem com label vazio (background)
    img5 = Image.new("RGB", (640, 512), color=(180, 180, 180))
    img5.save(img_dir / "img_005_empty.jpg")
    (lbl_dir / "img_005_empty.txt").write_text("", encoding="utf-8")

    # Label Órfão: Arquivo .txt sem imagem correspondente (Objetivo 2)
    (lbl_dir / "orphan_without_image.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")

    return ds_dir


class TestAnnotationValidator:
    """Testes para o validador de sintaxe e limites geométricos YOLO."""

    def test_validate_valid_line(self):
        validator = AnnotationValidator()
        ann, err = validator.validate_line("0 0.5 0.5 0.2 0.2", 1, "test.txt")
        assert err is None
        assert ann is not None
        assert ann.class_id == 0
        assert ann.class_name == "hotspot"
        assert ann.x_center == 0.5
        assert ann.width == 0.2

    def test_detect_invalid_class_id(self):
        validator = AnnotationValidator()
        ann, err = validator.validate_line("99 0.5 0.5 0.2 0.2", 1, "test.txt")
        assert ann is None
        assert err is not None
        assert "classe inválida id=99" in err.error_message.lower()

    def test_detect_malformed_token_count(self):
        validator = AnnotationValidator()
        ann, err = validator.validate_line("0 0.5 0.5 0.2", 1, "test.txt")
        assert ann is None
        assert err is not None
        assert "esperado 5 campos" in err.error_message.lower()

    def test_detect_degenerate_box(self):
        validator = AnnotationValidator()
        ann, err = validator.validate_line("0 0.5 0.5 -0.1 0.2", 1, "test.txt")
        assert ann is None
        assert err is not None
        assert "degenerada" in err.error_message.lower()

    def test_detect_out_of_bounds_coordinates(self):
        validator = AnnotationValidator()
        ann, err = validator.validate_line("0 1.8 0.5 0.2 0.2", 1, "test.txt")
        assert ann is None
        assert err is not None
        assert "fora do espaço normalizado" in err.error_message.lower()


class TestDatasetValidator:
    """Testes para validação relacional imagem-rótulo do dataset."""

    def test_detect_all_inconsistencies(self, mock_dataset):
        validator = DatasetValidator()
        report = validator.validate(mock_dataset)

        assert report.total_images == 5
        assert report.total_labels == 5

        # Objetivo 1: Imagens sem label
        assert len(report.images_without_label_file) == 1
        assert any("img_004_no_label" in p for p in report.images_without_label_file)
        assert len(report.empty_label_images) == 1
        assert any("img_005_empty" in p for p in report.empty_label_images)

        # Objetivo 2: Labels sem imagem (órfãos)
        assert len(report.orphan_labels) == 1
        assert any("orphan_without_image" in p for p in report.orphan_labels)

        # Objetivo 3: Classes inválidas detectadas
        assert len(report.invalid_class_errors) == 1
        assert "classe inválida id=99" in report.invalid_class_errors[0].error_message.lower()

        # Dataset não consistente devido às inconsistências
        assert report.is_consistent is False


class TestDatasetStatisticsCalculator:
    """Testes para cálculo de métricas descritivas e distribuição."""

    def test_calculate_distribution(self, mock_dataset):
        validator = DatasetValidator()
        report = validator.validate(mock_dataset)

        calc = DatasetStatisticsCalculator()
        stats = calc.calculate(report)

        assert stats.total_images == 5
        # Total de anotações válidas: 2 em img1 + 1 em img2 = 3 (classe 99 em img3 foi rejeitada)
        assert stats.total_annotations == 3

        # Contagens por classe
        assert stats.counts_by_class_name["hotspot"] == 2
        assert stats.counts_by_class_name["pid"] == 1
        assert stats.counts_by_class_name["soiling"] == 0

        # Percentuais
        assert stats.percentages_by_class_name["hotspot"] == pytest.approx(66.67, abs=0.1)
        assert stats.percentages_by_class_name["pid"] == pytest.approx(33.33, abs=0.1)

        # Médias geométricas calculadas
        assert stats.global_avg_width > 0
        assert stats.global_avg_height > 0
        assert stats.avg_boxes_per_image > 0


class TestDatasetBalanceAnalyzer:
    """Testes para o analisador de desbalanceamento."""

    def test_balanced_dataset(self):
        counts = {
            "hotspot": 100,
            "disconnected_module": 105,
            "pid": 95,
            "soiling": 102,
            "shading": 98,
            "healthy_module": 100,
        }
        result = DatasetBalanceAnalyzer.analyze(counts)
        assert result.severity == BalanceSeverity.BALANCED
        assert result.imbalance_ratio <= 3.0
        assert result.normalized_entropy >= 0.95
        assert len(result.empty_classes) == 0

    def test_severe_imbalance_with_empty_classes(self):
        counts = {
            "hotspot": 500,
            "disconnected_module": 10,
            "pid": 0,  # Classe zerada
            "soiling": 0,
            "shading": 5,
            "healthy_module": 300,
        }
        result = DatasetBalanceAnalyzer.analyze(counts)
        assert result.severity == BalanceSeverity.SEVERE_IMBALANCE
        assert "pid" in result.empty_classes
        assert "soiling" in result.empty_classes
        assert len(result.recommendations) > 0
        assert any("crítico" in rec.lower() for rec in result.recommendations)

    def test_moderate_imbalance(self):
        counts = {
            "hotspot": 200,
            "disconnected_module": 50,
            "pid": 40,
            "soiling": 60,
            "shading": 50,
            "healthy_module": 180,
        }
        # IR = 200 / 40 = 5.0 (moderado: 3.0 < IR <= 10.0)
        result = DatasetBalanceAnalyzer.analyze(counts)
        assert result.severity == BalanceSeverity.MODERATE_IMBALANCE
        assert result.imbalance_ratio == 5.0


class TestDatasetAuditor:
    """Testes para a fachada central DatasetAuditor."""

    def test_audit_execution_and_rejection_criteria(self, mock_dataset):
        auditor = DatasetAuditor()
        result = auditor.audit(mock_dataset)

        assert isinstance(result, DatasetAuditResult)
        assert result.is_approved_for_training is False  # Rejeitado devido a órfãos e classes vazias
        assert "REPROVADO" in result.executive_summary

        data_dict = result.to_dict()
        assert "dataset_path" in data_dict
        assert "summary" in data_dict
        assert "class_distribution" in data_dict


class TestDatasetPdfReportGenerator:
    """Testes para compilação do relatório PDF com ReportLab."""

    def test_generate_pdf_report(self, mock_dataset, tmp_path):
        auditor = DatasetAuditor()
        result = auditor.audit(mock_dataset)

        pdf_path = tmp_path / "relatorio_auditoria.pdf"
        generator = DatasetPdfReportGenerator()
        out_path = generator.generate_report(result, pdf_path)

        assert out_path.exists()
        assert out_path.is_file()
        assert out_path.stat().st_size > 3000  # PDF não vazio e estruturado


class TestDatasetAuditWindowHeadless:
    """Testes de inicialização da interface PySide6."""

    def test_window_widgets_initialization(self):
        pytest.importorskip("PySide6")
        from PySide6.QtWidgets import QApplication
        from src.presentation.dataset_audit_window import DatasetAuditWindow

        app = QApplication.instance() or QApplication([])
        window = DatasetAuditWindow()

        assert window.windowTitle() == "SolarGuard Vision - Auditoria de Dataset YOLOv11"
        assert window.path_input is not None
        assert window.audit_btn is not None
        assert window.table.columnCount() == 5
        assert window.pdf_btn is not None
