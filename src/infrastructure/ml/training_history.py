"""
Estrutura e análise de histórico temporal de treinamento de IA.
Oferece diagnóstico automático de overfitting, convergência e preparação para plotagem.
"""

from typing import List, Dict, Tuple, Optional, Any
import numpy as np

from src.infrastructure.ml.metrics_collector import EpochMetrics, MetricsCollector


class TrainingHistory:
    """
    Gerencia séries temporais de métricas de treinamento e diagnostica padrões de aprendizado.
    """

    def __init__(self, metrics_collector: Optional[MetricsCollector] = None) -> None:
        self.collector = metrics_collector or MetricsCollector()

    @property
    def epochs(self) -> List[EpochMetrics]:
        return self.collector.epochs_history

    def add_epoch(self, epoch_metrics: EpochMetrics) -> None:
        """Adiciona uma época diretamente ao histórico."""
        self.collector.epochs_history.append(epoch_metrics)

    def detect_overfitting(self, patience: int = 5, divergence_threshold: float = 0.15) -> Tuple[bool, Optional[int], str]:
        """
        Detecta se o modelo começou a sobreajustar (overfitting).
        Critério: val_loss aumenta consecutivamente enquanto train_loss continua caindo,
        ou a diferença relativa (val_loss - train_loss) / train_loss ultrapassa o limiar.
        
        :param patience: Número de épocas consecutivas de degradação da validação.
        :param divergence_threshold: Razão de divergência entre perda de treino e validação.
        :return: (is_overfitting, época_início, mensagem_diagnostico).
        """
        if len(self.epochs) < patience + 2:
            return False, None, "Dados insuficientes para diagnóstico de overfitting."

        val_losses = self.collector.get_series("val_loss")
        train_losses = self.collector.get_series("train_loss")

        # 1. Checagem de aumento consecutivo da perda de validação
        consecutive_increases = 0
        overfitting_start_epoch = None

        for i in range(1, len(val_losses)):
            if val_losses[i] > val_losses[i - 1]:
                consecutive_increases += 1
                if consecutive_increases == 1:
                    overfitting_start_epoch = self.epochs[i].epoch
                if consecutive_increases >= patience:
                    msg = (
                        f"Overfitting detectado a partir da época {overfitting_start_epoch}: "
                        f"val_loss aumentou consecutivamente por {patience} épocas."
                    )
                    return True, overfitting_start_epoch, msg
            else:
                consecutive_increases = 0
                overfitting_start_epoch = None

        # 2. Checagem de divergência excessiva entre treino e validação
        latest = self.epochs[-1]
        if latest.train_loss > 0:
            diff_ratio = (latest.val_loss - latest.train_loss) / latest.train_loss
            if diff_ratio > divergence_threshold:
                msg = (
                    f"Risco de Overfitting: val_loss ({latest.val_loss:.4f}) está {diff_ratio*100:.1f}% "
                    f"acima da train_loss ({latest.train_loss:.4f})."
                )
                return True, latest.epoch, msg

        return False, None, "Treinamento convergindo de forma estável sem evidência de overfitting severo."

    def detect_early_stop_candidate(self, patience: int = 8, min_delta: float = 0.002) -> Tuple[bool, str]:
        """
        Verifica se a métrica mAP50-95 estagnou e o treinamento deve ser interrompido antecipadamente.
        """
        map_scores = self.collector.get_series("map50_95")
        if len(map_scores) < patience + 1:
            return False, "Épocas insuficientes para avaliar early stopping."

        best_score = max(map_scores[:-patience])
        recent_scores = map_scores[-patience:]

        improved = any(s > (best_score + min_delta) for s in recent_scores)
        if not improved:
            return True, f"mAP50-95 estagnou nas últimas {patience} épocas (melhor histórico: {best_score:.4f})."

        return False, "Modelo ainda apresentando ganhos de generalização."

    def to_dict(self) -> Dict[str, List[Any]]:
        """Prepara todas as séries temporais em formato de dicionário tabular."""
        return {
            "epoch": [m.epoch for m in self.epochs],
            "train_loss": [m.train_loss for m in self.epochs],
            "val_loss": [m.val_loss for m in self.epochs],
            "precision": [m.precision for m in self.epochs],
            "recall": [m.recall for m in self.epochs],
            "f1_score": [m.f1_score for m in self.epochs],
            "map50": [m.map50 for m in self.epochs],
            "map50_95": [m.map50_95 for m in self.epochs],
            "learning_rate": [m.learning_rate for m in self.epochs],
        }
