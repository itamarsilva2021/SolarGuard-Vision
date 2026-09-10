"""
Coletor e processador de métricas de treinamento por época e avaliação de modelos YOLOv11.
Calcula automaticamente scores derivados como F1 e normaliza curvas de convergência.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import numpy as np


@dataclass
class EpochMetrics:
    """Métricas registradas para uma época específica do treinamento."""
    epoch: int
    train_loss: float
    val_loss: float
    precision: float
    recall: float
    map50: float
    map50_95: float
    learning_rate: float
    f1_score: float = 0.0

    def __post_init__(self) -> None:
        # Cálculo automático de F1-Score: 2 * (P * R) / (P + R + eps)
        eps = 1e-9
        if (self.precision + self.recall) > 0:
            self.f1_score = round(2.0 * (self.precision * self.recall) / (self.precision + self.recall + eps), 4)
        else:
            self.f1_score = 0.0


class MetricsCollector:
    """
    Acumula, valida e estrutura a progressão temporal de métricas durante o treinamento de IA.
    """

    def __init__(self) -> None:
        self.epochs_history: List[EpochMetrics] = []

    def record_epoch(
        self,
        epoch: int,
        train_loss: float,
        val_loss: float,
        precision: float,
        recall: float,
        map50: float,
        map50_95: float,
        learning_rate: float,
    ) -> EpochMetrics:
        """
        Registra as métricas observadas em uma época concluída.
        """
        # Clamp de métricas probabilísticas entre 0.0 e 1.0
        p_clamped = max(0.0, min(1.0, float(precision)))
        r_clamped = max(0.0, min(1.0, float(recall)))
        m50_clamped = max(0.0, min(1.0, float(map50)))
        m95_clamped = max(0.0, min(1.0, float(map50_95)))

        metrics = EpochMetrics(
            epoch=int(epoch),
            train_loss=round(float(train_loss), 4),
            val_loss=round(float(val_loss), 4),
            precision=round(p_clamped, 4),
            recall=round(r_clamped, 4),
            map50=round(m50_clamped, 4),
            map50_95=round(m95_clamped, 4),
            learning_rate=float(learning_rate),
        )
        self.epochs_history.append(metrics)
        return metrics

    def get_best_epoch(self, metric: str = "map50_95") -> Optional[EpochMetrics]:
        """Retorna a época com a maior pontuação na métrica alvo."""
        if not self.epochs_history:
            return None

        if metric in ["train_loss", "val_loss"]:
            # Para perdas, o melhor é o valor mínimo
            return min(self.epochs_history, key=lambda m: getattr(m, metric, float("inf")))
        return max(self.epochs_history, key=lambda m: getattr(m, metric, -float("inf")))

    def get_latest_metrics(self) -> Optional[EpochMetrics]:
        """Retorna as métricas da última época registrada."""
        return self.epochs_history[-1] if self.epochs_history else None

    def get_series(self, metric_name: str) -> List[float]:
        """Retorna uma lista contínua com os valores de uma métrica ao longo de todas as épocas."""
        return [getattr(m, metric_name, 0.0) for m in self.epochs_history]

    def get_summary(self) -> Dict[str, Any]:
        """Gera um resumo executivo com as melhores métricas alcançadas."""
        if not self.epochs_history:
            return {
                "total_epochs": 0,
                "best_epoch": 0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
                "map50": 0.0,
                "map50_95": 0.0,
            }

        best = self.get_best_epoch("map50_95") or self.epochs_history[-1]
        return {
            "total_epochs": len(self.epochs_history),
            "best_epoch": best.epoch,
            "precision": best.precision,
            "recall": best.recall,
            "f1_score": best.f1_score,
            "map50": best.map50,
            "map50_95": best.map50_95,
            "best_val_loss": min(self.get_series("val_loss")),
            "final_train_loss": self.epochs_history[-1].train_loss,
        }
