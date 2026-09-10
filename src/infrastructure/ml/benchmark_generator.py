"""
Gerador de gráficos e relatórios visuais de benchmark comparativo para modelos YOLOv11.
Utiliza Matplotlib no modo headless ('Agg') para geração de gráficos de alta qualidade.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np

# Configura Matplotlib em backend headless antes de importar pyplot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.infrastructure.ml.experiment_repository import ExperimentRecord
from src.infrastructure.ml.training_history import TrainingHistory
from src.core.logger import get_logger

logger = get_logger("BenchmarkGenerator")


class BenchmarkGenerator:
    """
    Constrói gráficos comparativos de desempenho, curvas de perda e diagramas de benchmark.
    """

    PALETTE = ["#0284C7", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"]

    @classmethod
    def plot_metrics_comparison(
        cls,
        experiments: List[ExperimentRecord],
        output_path: str | Path,
        title: str = "Comparativo de Performance de Modelos YOLOv11",
    ) -> Path:
        """
        Gera gráfico de barras agrupadas comparando Precision, Recall, F1, mAP50 e mAP50-95.
        
        :param experiments: Lista de experimentos a comparar (máx recomendado: 6).
        :param output_path: Caminho de saída da imagem (.png).
        :param title: Título principal do gráfico.
        :return: Path do arquivo gerado.
        """
        out_path = Path(output_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if not experiments:
            raise ValueError("A lista de experimentos não pode estar vazia.")

        exps = experiments[:6]  # Limita aos 6 primeiros para manter legibilidade visual
        num_models = len(exps)

        metrics_names = ["Precisão", "Recall", "F1-Score", "mAP50", "mAP50-95"]
        x = np.arange(len(metrics_names))
        bar_width = 0.8 / num_models

        fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

        for idx, exp in enumerate(exps):
            values = [
                exp.precision,
                exp.recall,
                exp.f1_score,
                exp.map50,
                exp.map50_95,
            ]
            offset = (idx - (num_models - 1) / 2) * bar_width
            color = cls.PALETTE[idx % len(cls.PALETTE)]
            label = f"{exp.name} ({exp.yolo_version})"
            bars = ax.bar(x + offset, values, bar_width, label=label, color=color, alpha=0.9, edgecolor="none")

            # Valores no topo das barras
            for bar in bars:
                height = bar.get_height()
                if height > 0.05:
                    ax.annotate(
                        f"{height:.2f}",
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha="center",
                        va="bottom",
                        fontsize=7,
                        color="#334155",
                    )

        ax.set_title(title, fontsize=14, fontweight="bold", color="#0F172A", pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels(metrics_names, fontsize=11, fontweight="bold", color="#1E293B")
        ax.set_ylim(0.0, 1.15)
        ax.set_ylabel("Score Normalizado [0.0 - 1.0]", fontsize=10, color="#475569")
        ax.grid(axis="y", linestyle="--", alpha=0.3, color="#94A3B8")
        ax.legend(frameon=True, facecolor="#F8FAFC", edgecolor="#E2E8F0", fontsize=9, loc="upper right")

        plt.tight_layout()
        fig.savefig(str(out_path), bbox_inches="tight")
        plt.close(fig)

        logger.info(f"Gráfico comparativo de métricas gerado em: {out_path}")
        return out_path

    @classmethod
    def plot_training_curves(
        cls,
        history: TrainingHistory,
        output_path: str | Path,
        title: str = "Evolução do Treinamento YOLOv11",
    ) -> Path:
        """
        Gera gráfico duplo contendo a curva de perdas (Loss) e a curva de métricas (mAP/F1) por época.
        """
        out_path = Path(output_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if not history.epochs:
            raise ValueError("Histórico de treinamento vazio.")

        data = history.to_dict()
        epochs = data["epoch"]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

        # Subplot 1: Curva de Perdas
        ax1.plot(epochs, data["train_loss"], label="Train Loss", color="#0284C7", linewidth=2)
        ax1.plot(epochs, data["val_loss"], label="Val Loss", color="#EF4444", linewidth=2, linestyle="--")
        ax1.set_title("Evolução da Perda (Loss)", fontsize=11, fontweight="bold", color="#0F172A")
        ax1.set_xlabel("Épocas", fontsize=10, color="#475569")
        ax1.set_ylabel("Loss", fontsize=10, color="#475569")
        ax1.grid(True, linestyle="--", alpha=0.3)
        ax1.legend(frameon=True, facecolor="#F8FAFC")

        # Subplot 2: Curva de Acurácia
        ax2.plot(epochs, data["map50"], label="mAP@50", color="#10B981", linewidth=2)
        ax2.plot(epochs, data["map50_95"], label="mAP@50-95", color="#8B5CF6", linewidth=2)
        ax2.plot(epochs, data["f1_score"], label="F1-Score", color="#F59E0B", linewidth=1.5, linestyle=":")
        ax2.set_title("Evolução das Métricas de Validação", fontsize=11, fontweight="bold", color="#0F172A")
        ax2.set_xlabel("Épocas", fontsize=10, color="#475569")
        ax2.set_ylabel("Score [0 - 1]", fontsize=10, color="#475569")
        ax2.set_ylim(0.0, 1.05)
        ax2.grid(True, linestyle="--", alpha=0.3)
        ax2.legend(frameon=True, facecolor="#F8FAFC")

        fig.suptitle(title, fontsize=13, fontweight="bold", color="#0F172A", y=0.98)
        plt.tight_layout()
        fig.savefig(str(out_path), bbox_inches="tight")
        plt.close(fig)

        logger.info(f"Curvas de treinamento salvas em: {out_path}")
        return out_path

    @classmethod
    def plot_radar_comparison(
        cls,
        experiments: List[ExperimentRecord],
        output_path: str | Path,
        title: str = "Radar Comparativo de Modelos",
    ) -> Path:
        """
        Gera um gráfico radar (Spider Chart) comparando o perfil multidimensional dos modelos.
        """
        out_path = Path(output_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if not experiments:
            raise ValueError("Lista de experimentos vazia.")

        categories = ["Precisão", "Recall", "F1", "mAP50", "mAP50-95"]
        num_vars = len(categories)
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        angles += angles[:1]  # Fecha o polígono

        fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True), dpi=300)

        for idx, exp in enumerate(experiments[:5]):
            values = [exp.precision, exp.recall, exp.f1_score, exp.map50, exp.map50_95]
            values += values[:1]
            color = cls.PALETTE[idx % len(cls.PALETTE)]

            ax.plot(angles, values, color=color, linewidth=2, label=exp.name)
            ax.fill(angles, values, color=color, alpha=0.15)

        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_thetagrids(np.degrees(angles[:-1]), categories, fontsize=10, fontweight="bold")
        ax.set_ylim(0.0, 1.0)
        ax.set_title(title, fontsize=13, fontweight="bold", color="#0F172A", pad=20)
        ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=9)

        plt.tight_layout()
        fig.savefig(str(out_path), bbox_inches="tight")
        plt.close(fig)

        return out_path
