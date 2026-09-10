"""
Suíte de testes de integração e unitários para a infraestrutura de experimentos,
métricas e benchmarking de modelos YOLOv11 (Etapa 14).
"""

import pytest
from pathlib import Path
from datetime import datetime

from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.ml.experiment_repository import (
    ExperimentRecord,
    SqliteExperimentRepository,
)
from src.infrastructure.ml.metrics_collector import MetricsCollector, EpochMetrics
from src.infrastructure.ml.training_history import TrainingHistory
from src.infrastructure.ml.experiment_tracker import ExperimentTracker
from src.infrastructure.ml.benchmark_generator import BenchmarkGenerator


@pytest.fixture
def in_memory_db():
    """Fornece uma instância isolada do SQLite em memória."""
    db = DatabaseManager(db_path=":memory:")
    return db


@pytest.fixture
def experiment_repo(in_memory_db):
    """Fornece um repositório configurado no banco em memória."""
    return SqliteExperimentRepository(db_manager=in_memory_db)


@pytest.fixture
def sample_experiments():
    """Gera lista de experimentos de exemplo para testes de benchmarking."""
    return [
        ExperimentRecord(
            name="YOLOv11-Nano Baseline",
            yolo_version="YOLOv11n",
            epochs=50,
            batch_size=16,
            learning_rate=0.01,
            precision=0.82,
            recall=0.79,
            f1_score=0.8045,
            map50=0.85,
            map50_95=0.62,
        ),
        ExperimentRecord(
            name="YOLOv11-Small Augmented",
            yolo_version="YOLOv11s",
            epochs=100,
            batch_size=16,
            learning_rate=0.005,
            precision=0.89,
            recall=0.86,
            f1_score=0.8747,
            map50=0.91,
            map50_95=0.71,
        ),
        ExperimentRecord(
            name="YOLOv11-Medium ClassWeighted",
            yolo_version="YOLOv11m",
            epochs=100,
            batch_size=8,
            learning_rate=0.003,
            precision=0.93,
            recall=0.90,
            f1_score=0.9148,
            map50=0.95,
            map50_95=0.77,
        ),
    ]


class TestExperimentRepository:
    """Testes para o repositório relacional de experimentos."""

    def test_save_and_retrieve_by_id(self, experiment_repo):
        record = ExperimentRecord(
            name="Exp-001 Test",
            epochs=30,
            batch_size=16,
            learning_rate=0.01,
            precision=0.88,
            recall=0.82,
            f1_score=0.849,
            map50=0.89,
            map50_95=0.68,
            hyperparameters={"optimizer": "AdamW", "weight_decay": 0.0005},
        )
        saved = experiment_repo.save(record)
        assert saved.id is not None

        retrieved = experiment_repo.get_by_id(saved.id)
        assert retrieved is not None
        assert retrieved.name == "Exp-001 Test"
        assert retrieved.map50_95 == pytest.approx(0.68)
        assert retrieved.hyperparameters.get("optimizer") == "AdamW"

    def test_get_all_and_best_by_metric(self, experiment_repo, sample_experiments):
        for exp in sample_experiments:
            experiment_repo.save(exp)

        all_records = experiment_repo.get_all(limit=10)
        assert len(all_records) == 3

        # O melhor em mAP50-95 deve ser o YOLOv11-Medium (0.77)
        best = experiment_repo.get_best_by_metric("map50_95")
        assert best is not None
        assert best.name == "YOLOv11-Medium ClassWeighted"
        assert best.map50_95 == pytest.approx(0.77)

    def test_delete_experiment(self, experiment_repo):
        record = ExperimentRecord(
            name="To Delete",
            epochs=10,
            batch_size=8,
            learning_rate=0.01,
            precision=0.5,
            recall=0.5,
            f1_score=0.5,
            map50=0.5,
            map50_95=0.3,
        )
        saved = experiment_repo.save(record)
        assert experiment_repo.delete(saved.id) is True
        assert experiment_repo.get_by_id(saved.id) is None


class TestMetricsCollector:
    """Testes para coleta e processamento de métricas de época."""

    def test_epoch_recording_and_f1_calculation(self):
        collector = MetricsCollector()
        m1 = collector.record_epoch(
            epoch=1,
            train_loss=2.5,
            val_loss=2.4,
            precision=0.80,
            recall=0.60,
            map50=0.65,
            map50_95=0.45,
            learning_rate=0.01,
        )
        # F1 = 2 * (0.8 * 0.6) / (0.8 + 0.6) = 0.96 / 1.4 = 0.6857
        assert m1.f1_score == pytest.approx(0.6857, abs=1e-3)
        assert len(collector.epochs_history) == 1

    def test_get_best_epoch_and_summary(self):
        collector = MetricsCollector()
        collector.record_epoch(1, 2.0, 2.1, 0.7, 0.6, 0.65, 0.40, 0.01)
        collector.record_epoch(2, 1.5, 1.6, 0.8, 0.7, 0.75, 0.55, 0.008)
        collector.record_epoch(3, 1.1, 1.2, 0.85, 0.80, 0.85, 0.65, 0.005)

        best = collector.get_best_epoch("map50_95")
        assert best is not None
        assert best.epoch == 3
        assert best.map50_95 == pytest.approx(0.65)

        summary = collector.get_summary()
        assert summary["total_epochs"] == 3
        assert summary["best_epoch"] == 3
        assert summary["map50"] == pytest.approx(0.85)


class TestTrainingHistory:
    """Testes para séries temporais e detecção de anomalias de treino."""

    def test_overfitting_detection(self):
        collector = MetricsCollector()
        # Simula 6 épocas onde train_loss cai e val_loss sobe consecutivamente
        for ep in range(1, 8):
            train_l = 2.0 - (ep * 0.2)
            val_l = 1.0 + (ep * 0.3)
            collector.record_epoch(ep, train_l, val_l, 0.8, 0.8, 0.8, 0.6, 0.001)

        history = TrainingHistory(collector)
        is_overfit, start_ep, msg = history.detect_overfitting(patience=4)
        assert is_overfit is True
        assert start_ep is not None
        assert "overfitting detectado" in msg.lower()

    def test_tabular_dictionary_export(self):
        collector = MetricsCollector()
        collector.record_epoch(1, 2.0, 2.0, 0.5, 0.5, 0.5, 0.3, 0.01)
        collector.record_epoch(2, 1.5, 1.6, 0.6, 0.6, 0.6, 0.4, 0.01)

        history = TrainingHistory(collector)
        df_dict = history.to_dict()
        assert len(df_dict["epoch"]) == 2
        assert df_dict["train_loss"] == [2.0, 1.5]


class TestExperimentTracker:
    """Testes para a fachada e context manager do ExperimentTracker."""

    def test_tracked_run_lifecycle(self, experiment_repo):
        tracker = ExperimentTracker(repository=experiment_repo)

        with tracker.start_run("Inception Run", epochs=2, batch_size=8, learning_rate=0.005) as run:
            run.log_param("backbone", "cspdarknet")
            run.log_epoch(1, 1.8, 1.9, 0.70, 0.65, 0.68, 0.45)
            run.log_epoch(2, 1.2, 1.3, 0.85, 0.80, 0.82, 0.60)
            run.set_weights_path("models/best.pt")

        # Após o 'with', o experimento deve estar automaticamente finalizado e salvo
        assert run.is_finished is True
        saved = experiment_repo.get_by_id(run.record.id)
        assert saved is not None
        assert saved.name == "Inception Run"
        assert saved.map50_95 == pytest.approx(0.60)
        assert saved.weights_path == "models/best.pt"
        assert saved.hyperparameters.get("backbone") == "cspdarknet"


class TestBenchmarkGenerator:
    """Testes para geração de gráficos comparativos Matplotlib."""

    def test_generate_metrics_comparison_chart(self, sample_experiments, tmp_path):
        out_chart = tmp_path / "benchmark_comparison.png"
        res_path = BenchmarkGenerator.plot_metrics_comparison(sample_experiments, out_chart)

        assert res_path.exists()
        assert res_path.is_file()
        assert res_path.stat().st_size > 10000  # Imagem PNG de alta resolução gerada

    def test_generate_training_curves_chart(self, tmp_path):
        collector = MetricsCollector()
        for ep in range(1, 11):
            collector.record_epoch(
                epoch=ep,
                train_loss=2.0 / ep,
                val_loss=2.2 / ep,
                precision=0.5 + (ep * 0.04),
                recall=0.4 + (ep * 0.05),
                map50=0.5 + (ep * 0.04),
                map50_95=0.3 + (ep * 0.05),
                learning_rate=0.01 * (0.95 ** ep),
            )
        history = TrainingHistory(collector)

        out_chart = tmp_path / "training_curves.png"
        res_path = BenchmarkGenerator.plot_training_curves(history, out_chart)

        assert res_path.exists()
        assert res_path.is_file()
        assert res_path.stat().st_size > 10000

    def test_generate_radar_chart(self, sample_experiments, tmp_path):
        out_chart = tmp_path / "radar_benchmark.png"
        res_path = BenchmarkGenerator.plot_radar_comparison(sample_experiments, out_chart)

        assert res_path.exists()
        assert res_path.is_file()
        assert res_path.stat().st_size > 10000
