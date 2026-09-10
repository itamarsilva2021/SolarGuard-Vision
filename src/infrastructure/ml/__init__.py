"""
Módulo de Machine Learning e Treinamento YOLOv11 - SolarGuard Vision.
"""

from src.infrastructure.ml.training_metrics import ValidationMetrics, ClassMetrics, TrainingProgress
from src.infrastructure.ml.dataset_loader import YoloDatasetLoader, PV_CLASSES
from src.infrastructure.ml.augmentation import ThermalDataAugmentation
from src.infrastructure.ml.yolo_trainer import YoloV11Trainer
from src.infrastructure.ml.yolo_validator import YoloV11Validator
from src.infrastructure.ml.model_exporter import ModelExporter
from src.infrastructure.ml.experiment_repository import (
    ExperimentRecord,
    IExperimentRepository,
    SqliteExperimentRepository,
)
from src.infrastructure.ml.metrics_collector import MetricsCollector, EpochMetrics
from src.infrastructure.ml.training_history import TrainingHistory
from src.infrastructure.ml.experiment_tracker import ExperimentTracker, ExperimentRun
from src.infrastructure.ml.benchmark_generator import BenchmarkGenerator

__all__ = [
    "ValidationMetrics",
    "ClassMetrics",
    "TrainingProgress",
    "YoloDatasetLoader",
    "PV_CLASSES",
    "ThermalDataAugmentation",
    "YoloV11Trainer",
    "YoloV11Validator",
    "ModelExporter",
    "ExperimentRecord",
    "IExperimentRepository",
    "SqliteExperimentRepository",
    "MetricsCollector",
    "EpochMetrics",
    "TrainingHistory",
    "ExperimentTracker",
    "ExperimentRun",
    "BenchmarkGenerator",
]
