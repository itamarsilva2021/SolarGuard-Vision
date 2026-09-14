"""
Testes unitários e de integração para a ETAPA 19:
Avaliação Experimental e Validação Científica com Dataset Real (Mestrado).
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.application.services.experimental_evaluation_service import (
    ExperimentalEvaluationService,
    ExperimentalEvaluationResult,
)
from src.infrastructure.ml.experiment_repository import (
    SqliteExperimentRepository,
    ExperimentRecord,
)
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.ml.training_metrics import ValidationMetrics, ClassMetrics
from src.application.dataset.dataset_audit import DatasetAuditor
from src.application.dataset.balance_analyzer import BalanceSeverity


@pytest.fixture
def in_memory_db():
    return DatabaseManager(":memory:")


@pytest.fixture
def exp_repo(in_memory_db):
    return SqliteExperimentRepository(in_memory_db)


@pytest.fixture
def sample_dataset_path(tmp_path):
    """Cria um dataset térmico temporário realista com 2 classes (estilo Roboflow Mestrado)."""
    root = tmp_path / "sample_thermal_dataset"
    (root / "train" / "images").mkdir(parents=True)
    (root / "train" / "labels").mkdir(parents=True)
    (root / "valid" / "images").mkdir(parents=True)
    (root / "valid" / "labels").mkdir(parents=True)

    # Imagens dummy
    import cv2
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.imwrite(str(root / "train" / "images" / "img1.jpg"), img)
    cv2.imwrite(str(root / "train" / "images" / "img2.jpg"), img)
    cv2.imwrite(str(root / "valid" / "images" / "val1.jpg"), img)

    # Labels: 0="hotspot group", 1="panel with hotspots"
    (root / "train" / "labels" / "img1.txt").write_text("0 0.5 0.5 0.2 0.2\n")
    (root / "train" / "labels" / "img2.txt").write_text("1 0.4 0.4 0.3 0.3\n")
    (root / "valid" / "labels" / "val1.txt").write_text("0 0.5 0.5 0.2 0.2\n1 0.4 0.4 0.3 0.3\n")

    # data.yaml
    yaml_content = (
        f"path: {root.as_posix()}\n"
        "train: train/images\n"
        "val: valid/images\n"
        "names: ['hotspot group', 'panel with hotspots']\n"
    )
    (root / "data.yaml").write_text(yaml_content)
    return root


class TestExperimentalEvaluationService:
    def test_auditor_auto_detects_classes_from_yaml(self, sample_dataset_path):
        auditor = DatasetAuditor(allowed_classes=None)
        res = auditor.audit(sample_dataset_path)

        assert res.is_approved_for_training is True
        assert res.validation.total_images == 3
        assert res.statistics.total_annotations == 4
        assert "hotspot group" in res.statistics.counts_by_class_name
        assert "panel with hotspots" in res.statistics.counts_by_class_name

    def test_run_stage_19_orchestration(self, sample_dataset_path, exp_repo, tmp_path):
        output_dir = tmp_path / "test_reports"
        service = ExperimentalEvaluationService(
            experiment_repository=exp_repo,
            output_dir=output_dir,
        )

        dummy_val_metrics = ValidationMetrics(
            map50=0.852,
            map50_95=0.621,
            precision=0.884,
            recall=0.820,
            class_metrics={
                "hotspot group": ClassMetrics(
                    class_name="hotspot group",
                    class_id=0,
                    precision=0.89,
                    recall=0.83,
                    map50=0.87,
                    map50_95=0.64,
                    instances_count=10,
                ),
                "panel with hotspots": ClassMetrics(
                    class_name="panel with hotspots",
                    class_id=1,
                    precision=0.87,
                    recall=0.81,
                    map50=0.83,
                    map50_95=0.60,
                    instances_count=8,
                ),
            },
            inference_time_ms=14.5,
        )

        dummy_weights = tmp_path / "best.pt"
        dummy_weights.write_text("fake_weights")

        with patch.object(service, "_extract_real_ground_truth_and_predictions") as mock_extract, \
             patch("src.application.services.experimental_evaluation_service.YoloV11Trainer.train") as mock_train, \
             patch("src.application.services.experimental_evaluation_service.YoloV11Validator.evaluate") as mock_eval:

            mock_train.return_value = dummy_weights
            mock_eval.return_value = dummy_val_metrics
            mock_extract.return_value = (
                ["hotspot group", "panel with hotspots", "hotspot group"],
                ["hotspot group", "panel with hotspots", "hotspot group"],
                ["hotspot group", "panel with hotspots"],
            )

            result = service.run_stage_19_experiment(
                dataset_path=sample_dataset_path,
                epochs=2,
                batch_size=2,
                experiment_name="test_mestrado_experiment",
            )

            assert isinstance(result, ExperimentalEvaluationResult)
            assert result.audit_result.is_approved_for_training is True
            assert result.validation_metrics.map50 == 0.852
            assert result.confusion_matrix.shape == (2, 2)
            assert result.global_classification_metrics.accuracy == 1.0

            # Verifica persistência no banco
            saved = exp_repo.get_by_id(result.experiment_record.id)
            assert saved is not None
            assert saved.name == "test_mestrado_experiment"
            assert saved.precision == 0.884

            # Verifica existência dos arquivos gerados
            assert result.audit_pdf_path.exists()
            assert result.validation_pdf_path.exists()
            assert result.validation_xlsx_path.exists()
            assert result.validation_csv_path.exists()
            assert result.confusion_matrix_img_path.exists()

    def test_resolve_val_dirs_dynamic_conventions(self, tmp_path):
        """Valida a resolução dinâmica para diferentes convenções de pastas YOLO."""
        # Cenário 1: val/images e val/labels (Padrão YOLO/Roboflow alternativo)
        ds1 = tmp_path / "ds_val_standard"
        (ds1 / "val" / "images").mkdir(parents=True)
        (ds1 / "val" / "labels").mkdir(parents=True)
        img_dir, lbl_dir = ExperimentalEvaluationService._resolve_val_dirs(ds1)
        assert img_dir == ds1 / "val" / "images"
        assert lbl_dir == ds1 / "val" / "labels"

        # Cenário 2: valid/images e valid/labels
        ds2 = tmp_path / "ds_valid_roboflow"
        (ds2 / "valid" / "images").mkdir(parents=True)
        (ds2 / "valid" / "labels").mkdir(parents=True)
        img_dir, lbl_dir = ExperimentalEvaluationService._resolve_val_dirs(ds2)
        assert img_dir == ds2 / "valid" / "images"
        assert lbl_dir == ds2 / "valid" / "labels"

        # Cenário 3: Configurado explicitamente no data.yaml
        ds3 = tmp_path / "ds_custom_yaml"
        custom_val_img = ds3 / "custom_split" / "images"
        custom_val_lbl = ds3 / "custom_split" / "labels"
        custom_val_img.mkdir(parents=True)
        custom_val_lbl.mkdir(parents=True)
        yaml_file = ds3 / "data.yaml"
        yaml_file.write_text("val: custom_split/images\nnames: ['pv_panel']\n")
        img_dir, lbl_dir = ExperimentalEvaluationService._resolve_val_dirs(ds3, data_yaml_path=yaml_file)
        assert img_dir == custom_val_img
        assert lbl_dir == custom_val_lbl
