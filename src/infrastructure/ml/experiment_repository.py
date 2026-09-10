"""
Repositório relacional SQLite para persistência e consulta de experimentos de IA (YOLOv11).
Implementa o padrão Repository para a tabela 'ai_experiments'.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
import uuid
from abc import ABC, abstractmethod

from src.infrastructure.database.connection import DatabaseManager
from src.core.logger import get_logger

logger = get_logger("ExperimentRepository")


@dataclass
class ExperimentRecord:
    """Registro relacional de um experimento de treinamento e avaliação de IA."""
    name: str
    epochs: int
    batch_size: int
    learning_rate: float
    precision: float
    recall: float
    f1_score: float
    map50: float
    map50_95: float
    yolo_version: str = "YOLOv11"
    dataset_path: Optional[str] = None
    weights_path: Optional[str] = None
    training_duration_seconds: Optional[float] = None
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Converte o registro para dicionário."""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "yolo_version": self.yolo_version,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "map50": round(self.map50, 4),
            "map50_95": round(self.map50_95, 4),
            "dataset_path": self.dataset_path,
            "weights_path": self.weights_path,
            "training_duration_seconds": self.training_duration_seconds,
            "hyperparameters": self.hyperparameters,
            "notes": self.notes,
        }


class IExperimentRepository(ABC):
    """Contrato abstrato para repositórios de experimentos de IA."""

    @abstractmethod
    def save(self, record: ExperimentRecord) -> ExperimentRecord:
        pass

    @abstractmethod
    def get_by_id(self, experiment_id: str) -> Optional[ExperimentRecord]:
        pass

    @abstractmethod
    def get_all(self, limit: int = 100) -> List[ExperimentRecord]:
        pass

    @abstractmethod
    def get_best_by_metric(self, metric: str = "map50_95") -> Optional[ExperimentRecord]:
        pass

    @abstractmethod
    def delete(self, experiment_id: str) -> bool:
        pass


class SqliteExperimentRepository(IExperimentRepository):
    """Implementação concreta em SQLite do repositório de experimentos."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or DatabaseManager()
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Garante que a tabela ai_experiments exista no banco."""
        create_sql = """
        CREATE TABLE IF NOT EXISTS ai_experiments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            yolo_version TEXT NOT NULL DEFAULT 'YOLOv11',
            epochs INTEGER NOT NULL,
            batch_size INTEGER NOT NULL,
            learning_rate REAL NOT NULL,
            precision REAL NOT NULL,
            recall REAL NOT NULL,
            f1_score REAL NOT NULL,
            map50 REAL NOT NULL,
            map50_95 REAL NOT NULL,
            dataset_path TEXT,
            weights_path TEXT,
            training_duration_seconds REAL,
            hyperparameters_json TEXT,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_ai_experiments_created_at ON ai_experiments(created_at);
        """
        with self.db.transaction() as conn:
            conn.executescript(create_sql)

    def save(self, record: ExperimentRecord) -> ExperimentRecord:
        """Salva ou atualiza um registro de experimento."""
        sql = """
        INSERT INTO ai_experiments (
            id, name, created_at, yolo_version, epochs, batch_size, learning_rate,
            precision, recall, f1_score, map50, map50_95, dataset_path, weights_path,
            training_duration_seconds, hyperparameters_json, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            precision = excluded.precision,
            recall = excluded.recall,
            f1_score = excluded.f1_score,
            map50 = excluded.map50,
            map50_95 = excluded.map50_95,
            weights_path = excluded.weights_path,
            notes = excluded.notes;
        """
        hyp_json = json.dumps(record.hyperparameters or {})
        with self.db.transaction() as conn:
            conn.execute(
                sql,
                (
                    record.id,
                    record.name,
                    record.created_at.isoformat(),
                    record.yolo_version,
                    record.epochs,
                    record.batch_size,
                    record.learning_rate,
                    record.precision,
                    record.recall,
                    record.f1_score,
                    record.map50,
                    record.map50_95,
                    record.dataset_path,
                    record.weights_path,
                    record.training_duration_seconds,
                    hyp_json,
                    record.notes,
                ),
            )
        logger.debug(f"Experimento '{record.name}' ({record.id}) persistido com sucesso.")
        return record

    def get_by_id(self, experiment_id: str) -> Optional[ExperimentRecord]:
        """Busca um experimento por ID universal."""
        sql = "SELECT * FROM ai_experiments WHERE id = ?;"
        with self.db.transaction() as conn:
            row = conn.execute(sql, (experiment_id,)).fetchone()
            if row:
                return self._row_to_record(row)
        return None

    def get_all(self, limit: int = 100) -> List[ExperimentRecord]:
        """Retorna todos os experimentos ordenados cronologicamente (mais recentes primeiro)."""
        sql = "SELECT * FROM ai_experiments ORDER BY created_at DESC LIMIT ?;"
        records: List[ExperimentRecord] = []
        with self.db.transaction() as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
            for r in rows:
                records.append(self._row_to_record(r))
        return records

    def get_best_by_metric(self, metric: str = "map50_95") -> Optional[ExperimentRecord]:
        """
        Retorna o experimento com a maior pontuação na métrica especificada
        ('map50_95', 'map50', 'f1_score', 'precision', 'recall').
        """
        valid_metrics = {"map50_95", "map50", "f1_score", "precision", "recall"}
        col = metric if metric in valid_metrics else "map50_95"

        sql = f"SELECT * FROM ai_experiments ORDER BY {col} DESC LIMIT 1;"
        with self.db.transaction() as conn:
            row = conn.execute(sql).fetchone()
            if row:
                return self._row_to_record(row)
        return None

    def delete(self, experiment_id: str) -> bool:
        """Remove um experimento por ID."""
        sql = "DELETE FROM ai_experiments WHERE id = ?;"
        with self.db.transaction() as conn:
            cursor = conn.execute(sql, (experiment_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_record(row: Any) -> ExperimentRecord:
        """Converte uma linha SQLite em ExperimentRecord."""
        try:
            created_at = datetime.fromisoformat(row["created_at"])
        except (ValueError, TypeError):
            created_at = datetime.now()

        try:
            hyp = json.loads(row["hyperparameters_json"]) if row["hyperparameters_json"] else {}
        except Exception:
            hyp = {}

        return ExperimentRecord(
            id=row["id"],
            name=row["name"],
            created_at=created_at,
            yolo_version=row["yolo_version"],
            epochs=row["epochs"],
            batch_size=row["batch_size"],
            learning_rate=row["learning_rate"],
            precision=row["precision"],
            recall=row["recall"],
            f1_score=row["f1_score"],
            map50=row["map50"],
            map50_95=row["map50_95"],
            dataset_path=row["dataset_path"],
            weights_path=row["weights_path"],
            training_duration_seconds=row["training_duration_seconds"],
            hyperparameters=hyp,
            notes=row["notes"],
        )
