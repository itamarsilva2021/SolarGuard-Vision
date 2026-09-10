"""
Serviço de cálculo de Curva ROC (Receiver Operating Characteristic) e AUC (Area Under the Curve).
Suporta classificação binária e multiclasse (One-vs-Rest) com determinação do limiar ótimo de Youden.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union, Tuple
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.core.logger import get_logger

logger = get_logger("RocCurveService")


@dataclass
class RocCurveData:
    """Estrutura com os pontos da curva ROC e métricas associadas para uma classe ou modelo."""
    class_name: str
    thresholds: List[float]
    fpr: List[float]  # False Positive Rate
    tpr: List[float]  # True Positive Rate
    auc: float        # Area Under the ROC Curve
    optimal_threshold: float
    optimal_tpr: float
    optimal_fpr: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_name": self.class_name,
            "auc": round(self.auc, 4),
            "optimal_threshold": round(self.optimal_threshold, 4),
            "optimal_tpr": round(self.optimal_tpr, 4),
            "optimal_fpr": round(self.optimal_fpr, 4),
            "points_count": len(self.fpr),
        }


class RocCurveService:
    """
    Calculadora e renderizadora científica de Curvas ROC e métricas AUC para SolarGuard Vision.
    """

    @staticmethod
    def _trapezoidal_auc(x: np.ndarray, y: np.ndarray) -> float:
        """
        Calcula a integral trapezoidal numérica.
        Garante ordenação monotônica crescente de x.
        """
        order = np.argsort(x)
        x_sorted = x[order]
        y_sorted = y[order]
        
        # Regra do trapézio pura sem depender de versão de np.trapz / trapezoid
        auc_val = 0.0
        for i in range(len(x_sorted) - 1):
            dx = x_sorted[i + 1] - x_sorted[i]
            avg_y = (y_sorted[i + 1] + y_sorted[i]) / 2.0
            auc_val += dx * avg_y
        return float(np.clip(auc_val, 0.0, 1.0))

    def compute_binary_roc(
        self,
        y_true: List[int],
        y_scores: List[float],
        class_name: str = "Positive",
        num_thresholds: int = 100,
    ) -> RocCurveData:
        """
        Calcula os pontos da curva ROC, AUC e limiar ótimo para um problema binário (y_true in {0, 1}).
        """
        if len(y_true) != len(y_scores):
            raise ValueError(f"Comprimento divergente: y_true ({len(y_true)}) != y_scores ({len(y_scores)})")

        y_true_arr = np.array(y_true, dtype=int)
        y_scores_arr = np.array(y_scores, dtype=float)

        total_positives = int(np.sum(y_true_arr == 1))
        total_negatives = int(np.sum(y_true_arr == 0))

        if total_positives == 0 or total_negatives == 0:
            # Caso degenerado: todas amostras da mesma classe
            return RocCurveData(
                class_name=class_name,
                thresholds=[0.0, 1.0],
                fpr=[0.0, 1.0],
                tpr=[0.0, 1.0],
                auc=0.5,
                optimal_threshold=0.5,
                optimal_tpr=0.0,
                optimal_fpr=0.0,
            )

        # Gera thresholds ordenados de forma decrescente
        sorted_scores = np.sort(np.unique(y_scores_arr))[::-1]
        if len(sorted_scores) > num_thresholds:
            indices = np.linspace(0, len(sorted_scores) - 1, num_thresholds, dtype=int)
            thresholds = sorted_scores[indices].tolist()
        else:
            thresholds = sorted_scores.tolist()

        # Inclui limites extremos
        thresholds = [thresholds[0] + 1e-5] + thresholds + [-1e-5]

        fpr_list: List[float] = []
        tpr_list: List[float] = []
        threshold_list: List[float] = []

        best_youden_j = -1.0
        best_threshold = 0.5
        best_tpr = 0.0
        best_fpr = 0.0

        for thresh in thresholds:
            y_pred = (y_scores_arr >= thresh).astype(int)
            tp = int(np.sum((y_pred == 1) & (y_true_arr == 1)))
            fp = int(np.sum((y_pred == 1) & (y_true_arr == 0)))
            
            tpr = tp / total_positives
            fpr = fp / total_negatives

            tpr_list.append(tpr)
            fpr_list.append(fpr)
            threshold_list.append(thresh)

            # Youden's J statistic: J = sensitivity + specificity - 1 = TPR - FPR
            youden_j = tpr - fpr
            if youden_j > best_youden_j:
                best_youden_j = youden_j
                best_threshold = thresh
                best_tpr = tpr
                best_fpr = fpr

        auc = self._trapezoidal_auc(np.array(fpr_list), np.array(tpr_list))

        return RocCurveData(
            class_name=class_name,
            thresholds=threshold_list,
            fpr=fpr_list,
            tpr=tpr_list,
            auc=auc,
            optimal_threshold=best_threshold,
            optimal_tpr=best_tpr,
            optimal_fpr=best_fpr,
        )

    def compute_multiclass_ovr_roc(
        self,
        y_true: List[str],
        y_scores_dict: Dict[str, List[float]],
        labels: Optional[List[str]] = None,
    ) -> Dict[str, RocCurveData]:
        """
        Calcula a curva ROC e AUC para múltiplas classes utilizando a estratégia One-vs-Rest (OvR).
        :param y_true: Lista com a classe verdadeira de cada amostra.
        :param y_scores_dict: Dicionário mapeando cada classe para a lista de scores de probabilidade de cada amostra.
        """
        resolved_labels = labels or list(y_scores_dict.keys())
        results: Dict[str, RocCurveData] = {}

        for cls_name in resolved_labels:
            if cls_name not in y_scores_dict:
                continue
            scores = y_scores_dict[cls_name]
            binary_true = [1 if yt == cls_name else 0 for yt in y_true]
            roc_data = self.compute_binary_roc(binary_true, scores, class_name=cls_name)
            results[cls_name] = roc_data

        return results

    def plot_roc_curves(
        self,
        roc_dict: Union[Dict[str, RocCurveData], RocCurveData],
        output_path: Union[str, Path],
        title: str = "SolarGuard Vision - Curva ROC e Desempenho AUC",
    ) -> Path:
        """
        Plota as curvas ROC comparativas e exporta imagem em alta definição.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(roc_dict, RocCurveData):
            curves = {roc_dict.class_name: roc_dict}
        else:
            curves = roc_dict

        fig, ax = plt.subplots(figsize=(8, 6), dpi=300)

        # Linha diagonal de classificação puramente aleatória (AUC = 0.5)
        ax.plot([0, 1], [0, 1], linestyle="--", lw=1.5, color="#94A3B8", label="Aleatório (AUC = 0.5000)")

        colors = ["#2563EB", "#DC2626", "#16A34A", "#D97706", "#9333EA", "#0891B2", "#4F46E5"]
        for idx, (cls_name, data) in enumerate(curves.items()):
            color = colors[idx % len(colors)]
            ax.plot(
                data.fpr,
                data.tpr,
                lw=2,
                color=color,
                label=f"{cls_name} (AUC = {data.auc:.4f})",
            )
            # Marca o ponto de corte ótimo de Youden
            ax.scatter(
                [data.optimal_fpr],
                [data.optimal_tpr],
                color=color,
                edgecolor="black",
                zorder=5,
                s=40,
            )

        ax.set_xlim([-0.02, 1.02])
        ax.set_ylim([-0.02, 1.02])
        ax.set_xlabel("Taxa de Falsos Positivos (1 - Especificidade)", fontsize=11, fontweight="bold")
        ax.set_ylabel("Taxa de Verdadeiros Positivos (Sensibilidade / Recall)", fontsize=11, fontweight="bold")
        ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="lower right", fontsize=9, framealpha=0.9)

        fig.tight_layout()
        plt.savefig(out, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Gráfico de curvas ROC exportado com sucesso: {out}")
        return out
