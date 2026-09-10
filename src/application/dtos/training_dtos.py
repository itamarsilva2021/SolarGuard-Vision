"""
DTOs para o pipeline de treinamento e validação do modelo YOLOv11.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
from src.infrastructure.ml.training_metrics import ValidationMetrics


@dataclass
class TrainingPipelineRequest:
    """Requisição para execução do pipeline de treinamento."""
    dataset_dir: str | Path
    base_model: str = "yolo11n.pt"
    epochs: int = 50
    imgsz: int = 640
    batch_size: int = 16
    device: str = "auto"
    patience: int = 15
    learning_rate: float = 0.01
    experiment_name: Optional[str] = None
    export_model_name: str = "best.pt"
    export_onnx: bool = False


@dataclass
class TrainingPipelineResponse:
    """Resultado da execução do pipeline de treinamento."""
    success: bool
    weights_path: str
    manifest_path: str
    metrics: ValidationMetrics
    dataset_yaml_path: str
    onnx_path: Optional[str] = None
    total_time_seconds: float = 0.0
    message: str = ""
