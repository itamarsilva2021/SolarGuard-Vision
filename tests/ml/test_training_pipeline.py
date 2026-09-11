"""
Testes unitários e de integração para o pipeline de treinamento YOLOv11 do SolarGuard Vision.
Valida o carregador de dataset, data augmentation, métricas, exportador de best.pt e orquestrador.
"""

import pytest
import numpy as np
import cv2
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.infrastructure.ml.dataset_loader import YoloDatasetLoader, PV_CLASSES
from src.infrastructure.ml.augmentation import ThermalDataAugmentation
from src.infrastructure.ml.training_metrics import ValidationMetrics, ClassMetrics
from src.infrastructure.ml.model_exporter import ModelExporter
from src.infrastructure.ml.yolo_trainer import YoloV11Trainer
from src.infrastructure.ml.yolo_validator import YoloV11Validator
from src.application.services.training_pipeline_service import TrainingPipelineService
from src.application.dtos.training_dtos import TrainingPipelineRequest


@pytest.fixture
def mock_dataset_dir(tmp_path) -> Path:
    """Cria uma estrutura mínima válida de dataset YOLO com 6 classes para testes."""
    ds_dir = tmp_path / "mock_yolo_dataset"
    (ds_dir / "images" / "train").mkdir(parents=True, exist_ok=True)
    (ds_dir / "images" / "val").mkdir(parents=True, exist_ok=True)
    (ds_dir / "labels" / "train").mkdir(parents=True, exist_ok=True)
    (ds_dir / "labels" / "val").mkdir(parents=True, exist_ok=True)

    # Cria 2 imagens de treino e 1 de validação sintéticas
    img_train_1 = ds_dir / "images" / "train" / "img_001.jpg"
    img_train_2 = ds_dir / "images" / "train" / "img_002.jpg"
    img_val_1 = ds_dir / "images" / "val" / "img_val_001.jpg"

    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.imwrite(str(img_train_1), dummy_img)
    cv2.imwrite(str(img_train_2), dummy_img)
    cv2.imwrite(str(img_val_1), dummy_img)

    # Anotações: img_001 tem hotspot (0) e disconnected_module (1)
    lbl_train_1 = ds_dir / "labels" / "train" / "img_001.txt"
    lbl_train_1.write_text("0 0.5 0.5 0.2 0.2\n1 0.3 0.3 0.1 0.1\n")

    # img_002 tem pid (2) e soiling (3)
    lbl_train_2 = ds_dir / "labels" / "train" / "img_002.txt"
    lbl_train_2.write_text("2 0.6 0.6 0.15 0.15\n3 0.8 0.8 0.1 0.1\n")

    # img_val_1 tem shading (4) e healthy_module (5)
    lbl_val_1 = ds_dir / "labels" / "val" / "img_val_001.txt"
    lbl_val_1.write_text("4 0.2 0.2 0.1 0.1\n5 0.7 0.7 0.2 0.2\n")

    return ds_dir


class TestYoloDatasetLoader:
    def test_create_yaml_config(self, mock_dataset_dir):
        loader = YoloDatasetLoader()
        yaml_path = loader.create_yaml_config(mock_dataset_dir)

        assert yaml_path.exists()
        content = yaml_path.read_text(encoding="utf-8")
        assert "hotspot" in content
        assert "disconnected_module" in content
        assert "pid" in content
        assert "soiling" in content
        assert "shading" in content
        assert "healthy_module" in content

    def test_validate_valid_dataset(self, mock_dataset_dir):
        loader = YoloDatasetLoader()
        summary = loader.validate_dataset(mock_dataset_dir)

        assert summary["valid"] is True
        assert summary["train_images"] == 2
        assert summary["val_images"] == 1
        assert summary["class_counts"]["hotspot"] == 1
        assert summary["class_counts"]["disconnected_module"] == 1
        assert summary["class_counts"]["pid"] == 1
        assert summary["class_counts"]["soiling"] == 1
        assert summary["class_counts"]["shading"] == 1
        assert summary["class_counts"]["healthy_module"] == 1

    def test_split_dataset(self, tmp_path):
        loader = YoloDatasetLoader()
        raw_imgs = tmp_path / "raw_images"
        raw_lbls = tmp_path / "raw_labels"
        target_dir = tmp_path / "split_dataset"

        raw_imgs.mkdir(parents=True, exist_ok=True)
        raw_lbls.mkdir(parents=True, exist_ok=True)

        # Cria 10 imagens e labels
        for i in range(10):
            img_p = raw_imgs / f"frame_{i:03d}.jpg"
            lbl_p = raw_lbls / f"frame_{i:03d}.txt"
            cv2.imwrite(str(img_p), np.zeros((50, 50, 3), dtype=np.uint8))
            lbl_p.write_text("0 0.5 0.5 0.2 0.2\n")

        loader.split_dataset(raw_imgs, raw_lbls, target_dir, train_ratio=0.8, val_ratio=0.2)

        train_imgs = list((target_dir / "images" / "train").glob("*.jpg"))
        val_imgs = list((target_dir / "images" / "val").glob("*.jpg"))

        assert len(train_imgs) == 8
        assert len(val_imgs) == 2
        assert (target_dir / "data.yaml").exists()


class TestThermalDataAugmentation:
    def test_augmentation_hyperparameters(self):
        params = ThermalDataAugmentation.get_yolo_augmentation_hyperparameters()
        assert "hsv_h" in params
        assert "degrees" in params
        assert "mosaic" in params
        assert params["mosaic"] == 1.0
        assert params["fliplr"] == 0.5

    def test_horizontal_and_vertical_flip(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        bboxes = [(0, 0.3, 0.4, 0.2, 0.2)]  # class 0, cx=0.3, cy=0.4

        # Flip horizontal: cx novo deve ser 1.0 - 0.3 = 0.7
        _, h_flipped = ThermalDataAugmentation.horizontal_flip(img, bboxes)
        assert pytest.approx(h_flipped[0][1]) == 0.7
        assert pytest.approx(h_flipped[0][2]) == 0.4

        # Flip vertical: cy novo deve ser 1.0 - 0.4 = 0.6
        _, v_flipped = ThermalDataAugmentation.vertical_flip(img, bboxes)
        assert pytest.approx(v_flipped[0][1]) == 0.3
        assert pytest.approx(v_flipped[0][2]) == 0.6

    def test_thermal_sensor_noise_and_contrast(self):
        img = np.full((50, 50, 3), 100, dtype=np.uint8)
        noisy = ThermalDataAugmentation.inject_thermal_sensor_noise(img, sigma=5.0)
        assert noisy.shape == img.shape
        assert noisy.dtype == np.uint8

        contrast = ThermalDataAugmentation.adjust_thermal_contrast_and_gain(img, alpha=1.2, beta=-10)
        assert contrast.shape == img.shape
        assert contrast.dtype == np.uint8


class TestValidationMetrics:
    def test_fitness_and_serialization(self):
        metrics = ValidationMetrics(
            map50=0.92,
            map50_95=0.74,
            precision=0.88,
            recall=0.85,
            inference_time_ms=8.5,
        )

        expected_fitness = round(0.1 * 0.92 + 0.9 * 0.74, 4)
        assert metrics.fitness == expected_fitness

        as_dict = metrics.to_dict()
        assert as_dict["map50"] == 0.92
        assert as_dict["map50_95"] == 0.74
        assert as_dict["inference_time_ms"] == 8.5


class TestModelExporter:
    def test_export_best_weights_and_manifest(self, tmp_path):
        exporter = ModelExporter(models_dir=tmp_path / "models")

        # Cria peso fictício best.pt
        fake_weights = tmp_path / "runs" / "weights" / "best.pt"
        fake_weights.parent.mkdir(parents=True, exist_ok=True)
        fake_weights.write_bytes(b"FAKE_YOLO_WEIGHTS_CONTENT_V11")

        metrics = ValidationMetrics(
            map50=0.945,
            map50_95=0.782,
            precision=0.91,
            recall=0.89,
        )

        exported = exporter.export_best_weights(
            source_weights=fake_weights,
            model_name="best.pt",
            metrics=metrics,
            extra_metadata={"epochs": 50, "dataset": "SolarGuard-Dataset-v1"},
        )

        assert exported.exists()
        assert exported.name == "best.pt"

        # Verifica manifesto JSON criado junto ao .pt
        manifest_file = exported.with_suffix(".json")
        assert manifest_file.exists()

        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest_data["model_name"] == "best.pt"
        assert manifest_data["architecture"] == "YOLOv11"
        assert manifest_data["num_classes"] == 6
        assert manifest_data["metrics"]["map50"] == 0.945
        assert manifest_data["extra_metadata"]["dataset"] == "SolarGuard-Dataset-v1"
        assert len(manifest_data["sha256"]) == 64


class TestTrainingPipelineService:
    def test_pipeline_with_mocked_training(self, mock_dataset_dir, tmp_path):
        # Mock do Trainer e Validator para validar a orquestração ponta a ponta
        mock_trainer = MagicMock(spec=YoloV11Trainer)
        mock_weights_path = tmp_path / "best.pt"
        mock_weights_path.write_bytes(b"MOCK_BEST_WEIGHTS")
        mock_trainer.train.return_value = mock_weights_path

        mock_validator = MagicMock(spec=YoloV11Validator)
        mock_metrics = ValidationMetrics(
            map50=0.95,
            map50_95=0.81,
            precision=0.92,
            recall=0.90,
        )
        mock_validator.evaluate.return_value = mock_metrics

        exporter = ModelExporter(models_dir=tmp_path / "exported_models")

        service = TrainingPipelineService(
            trainer=mock_trainer,
            validator=mock_validator,
            exporter=exporter,
        )

        request = TrainingPipelineRequest(
            dataset_dir=mock_dataset_dir,
            epochs=20,
            batch_size=8,
            export_model_name="solarguard_best.pt",
        )

        result = service.run_pipeline(request)

        assert result.is_success is True
        response = result.value
        assert response.success is True
        assert Path(response.weights_path).exists()
        assert Path(response.manifest_path).exists()
        assert response.metrics.map50 == 0.95
        assert "Pipeline finalizado com sucesso" in response.message
