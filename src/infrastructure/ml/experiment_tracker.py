"""
Rastreador de experimentos de treinamento e validação para modelos YOLOv11.
Gerencia ciclo de vida, captura hiperparâmetros, métricas e persiste na base relacional.
"""

from datetime import datetime
import time
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from src.infrastructure.ml.experiment_repository import (
    ExperimentRecord,
    IExperimentRepository,
    SqliteExperimentRepository,
)
from src.infrastructure.ml.metrics_collector import MetricsCollector, EpochMetrics
from src.infrastructure.ml.training_history import TrainingHistory
from src.core.logger import get_logger

logger = get_logger("ExperimentTracker")


class ExperimentRun:
    """Contexto de execução de um experimento individual."""

    def __init__(
        self,
        name: str,
        epochs: int,
        batch_size: int,
        learning_rate: float,
        repository: IExperimentRepository,
        yolo_version: str = "YOLOv11",
        dataset_path: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        self.name = name
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.repository = repository
        self.yolo_version = yolo_version
        self.dataset_path = dataset_path
        self.notes = notes

        self.start_time = time.time()
        self.created_at = datetime.now()
        self.weights_path: Optional[str] = None
        self.hyperparameters: Dict[str, Any] = {
            "epochs": epochs,
            "batch_size": batch_size,
            "lr0": learning_rate,
        }
        self.collector = MetricsCollector()
        self.history = TrainingHistory(self.collector)
        self.is_finished = False
        self.record: Optional[ExperimentRecord] = None

    def log_param(self, key: str, value: Any) -> None:
        """Registra um hiperparâmetro de treino."""
        self.hyperparameters[key] = value

    def log_params(self, params: Dict[str, Any]) -> None:
        """Registra múltiplos hiperparâmetros."""
        self.hyperparameters.update(params)

    def log_epoch(
        self,
        epoch: int,
        train_loss: float,
        val_loss: float,
        precision: float,
        recall: float,
        map50: float,
        map50_95: float,
        learning_rate: Optional[float] = None,
    ) -> EpochMetrics:
        """Registra o progresso de uma época de treinamento."""
        lr = learning_rate if learning_rate is not None else self.learning_rate
        return self.collector.record_epoch(
            epoch=epoch,
            train_loss=train_loss,
            val_loss=val_loss,
            precision=precision,
            recall=recall,
            map50=map50,
            map50_95=map50_95,
            learning_rate=lr,
        )

    def set_weights_path(self, path: str) -> None:
        """Define o caminho do arquivo de pesos gerado (.pt)."""
        self.weights_path = path

    def finish(self, final_metrics: Optional[Dict[str, float]] = None) -> ExperimentRecord:
        """
        Encerra o experimento, consolida as métricas e persiste no SQLite.
        """
        if self.is_finished and self.record:
            return self.record

        duration = round(time.time() - self.start_time, 2)

        # Se métricas finais forem passadas explicitamente, usa-as; caso contrário, extrai do collector
        summary = self.collector.get_summary()

        if final_metrics:
            p = float(final_metrics.get("precision", summary["precision"]))
            r = float(final_metrics.get("recall", summary["recall"]))
            m50 = float(final_metrics.get("map50", summary["map50"]))
            m95 = float(final_metrics.get("map50_95", summary["map50_95"]))
            eps = 1e-9
            f1 = float(final_metrics.get("f1_score", 2.0 * (p * r) / (p + r + eps) if (p + r) > 0 else 0.0))
        else:
            p = summary["precision"]
            r = summary["recall"]
            f1 = summary["f1_score"]
            m50 = summary["map50"]
            m95 = summary["map50_95"]

        record = ExperimentRecord(
            name=self.name,
            epochs=self.epochs,
            batch_size=self.batch_size,
            learning_rate=self.learning_rate,
            precision=p,
            recall=r,
            f1_score=f1,
            map50=m50,
            map50_95=m95,
            yolo_version=self.yolo_version,
            dataset_path=self.dataset_path,
            weights_path=self.weights_path,
            training_duration_seconds=duration,
            hyperparameters=self.hyperparameters,
            notes=self.notes,
            created_at=self.created_at,
        )

        saved_record = self.repository.save(record)
        self.record = saved_record
        self.is_finished = True
        logger.info(
            f"Experimento '{saved_record.name}' concluído em {duration}s. "
            f"mAP50-95: {saved_record.map50_95:.4f}, F1: {saved_record.f1_score:.4f}"
        )
        return saved_record

    def __enter__(self) -> "ExperimentRun":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self.is_finished:
            if exc_val:
                self.notes = f"Interrompido por erro: {exc_val}"
            self.finish()


class ExperimentTracker:
    """
    Fachada principal para gerenciamento e rastreamento de experimentos de ML.
    """

    def __init__(self, repository: Optional[IExperimentRepository] = None) -> None:
        self.repo = repository or SqliteExperimentRepository()

    def start_run(
        self,
        name: str,
        epochs: int = 50,
        batch_size: int = 16,
        learning_rate: float = 0.01,
        yolo_version: str = "YOLOv11",
        dataset_path: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> ExperimentRun:
        """
        Inicia uma nova sessão de rastreamento de experimento.
        """
        return ExperimentRun(
            name=name,
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            repository=self.repo,
            yolo_version=yolo_version,
            dataset_path=dataset_path,
            notes=notes,
        )

    def get_history(self, limit: int = 50) -> List[ExperimentRecord]:
        """Consulta todos os experimentos registrados."""
        return self.repo.get_all(limit=limit)

    def get_leaderboard(self, metric: str = "map50_95", limit: int = 10) -> List[ExperimentRecord]:
        """Gera ranking dos melhores modelos segundo a métrica desejada."""
        all_exps = self.repo.get_all(limit=100)
        return sorted(all_exps, key=lambda x: getattr(x, metric, 0.0), reverse=True)[:limit]
