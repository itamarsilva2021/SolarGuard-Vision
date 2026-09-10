"""
Métricas de Treinamento e Validação para o modelo YOLOv11 no SolarGuard Vision.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class ClassMetrics:
    """Métricas de detecção por classe individual de anomalia fotovoltaica."""
    class_name: str
    class_id: int
    precision: float
    recall: float
    map50: float
    map50_95: float
    instances_count: int = 0

    def to_dict(self) -> dict:
        return {
            "class_name": self.class_name,
            "class_id": self.class_id,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "map50": round(self.map50, 4),
            "map50_95": round(self.map50_95, 4),
            "instances_count": self.instances_count,
        }


@dataclass
class ValidationMetrics:
    """
    Métricas globais de validação do modelo YOLOv11.
    
    :param map50: Mean Average Precision com IoU threshold de 0.50 (mAP@0.50).
    :param map50_95: Mean Average Precision no intervalo [0.50, 0.95] (mAP@0.50:0.95).
    :param precision: Precisão macro média.
    :param recall: Revocação (Sensibilidade) macro média.
    :param fitness: Métrica de aptidão composta utilizada pelo Ultralytics (0.1*mAP50 + 0.9*mAP50-95).
    :param class_metrics: Dicionário contendo métricas detalhadas por classe.
    :param inference_time_ms: Tempo médio de inferência por imagem em milissegundos.
    :param evaluated_at: Data e hora da avaliação.
    """
    map50: float
    map50_95: float
    precision: float
    recall: float
    fitness: float = 0.0
    class_metrics: Dict[str, ClassMetrics] = field(default_factory=dict)
    inference_time_ms: float = 0.0
    evaluated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if self.fitness == 0.0 and (self.map50 > 0 or self.map50_95 > 0):
            object.__setattr__(self, "fitness", round(0.1 * self.map50 + 0.9 * self.map50_95, 4))

    @property
    def f1_score(self) -> float:
        """Calcula o F1-Score macro harmônico a partir de Precision e Recall."""
        if (self.precision + self.recall) > 0:
            return round((2.0 * self.precision * self.recall) / (self.precision + self.recall), 4)
        return 0.0

    @property
    def fps(self) -> float:
        """Calcula a taxa de quadros por segundo a partir da latência média de inferência."""
        if self.inference_time_ms > 0:
            return round(1000.0 / self.inference_time_ms, 1)
        return 0.0

    def to_dict(self) -> dict:
        return {
            "map50": round(self.map50, 4),
            "map50_95": round(self.map50_95, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "fitness": round(self.fitness, 4),
            "inference_time_ms": round(self.inference_time_ms, 2),
            "evaluated_at": self.evaluated_at.isoformat(),
            "classes": {k: v.to_dict() for k, v in self.class_metrics.items()},
        }


@dataclass
class TrainingProgress:
    """Progresso de uma época durante o treinamento."""
    epoch: int
    total_epochs: int
    train_box_loss: float
    train_cls_loss: float
    train_dfl_loss: float
    val_map50: Optional[float] = None
    val_map50_95: Optional[float] = None
    lr: float = 0.0
