"""
Serviço de cálculo, normalização e renderização gráfica de Matriz de Confusão para SolarGuard Vision.
"""

from typing import List, Optional, Union, Dict, Tuple
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.core.logger import get_logger

logger = get_logger("ConfusionMatrixService")


class ConfusionMatrixService:
    """
    Constrói matrizes de confusão quantitativas e gera visualizações científicas de alta resolução.
    """

    def __init__(self, labels: Optional[List[str]] = None) -> None:
        self.labels = labels or []

    def compute(
        self,
        y_true: List[Union[str, int]],
        y_pred: List[Union[str, int]],
        labels: Optional[List[str]] = None,
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Calcula a matriz de confusão absoluta N x N onde as linhas representam
        as classes reais (Ground Truth) e as colunas as classes preditas (Predicted).
        """
        if len(y_true) != len(y_pred):
            raise ValueError(f"Dimensões incompatíveis: len(y_true)={len(y_true)} != len(y_pred)={len(y_pred)}")

        str_y_true = [str(x) for x in y_true]
        str_y_pred = [str(x) for x in y_pred]

        if labels is not None:
            resolved_labels = [str(l) for l in labels]
        elif self.labels:
            resolved_labels = [str(l) for l in self.labels]
        else:
            resolved_labels = sorted(list(set(str_y_true) | set(str_y_pred)))

        label_to_idx = {lbl: idx for idx, lbl in enumerate(resolved_labels)}
        n = len(resolved_labels)
        matrix = np.zeros((n, n), dtype=int)

        for yt, yp in zip(str_y_true, str_y_pred):
            if yt in label_to_idx and yp in label_to_idx:
                r = label_to_idx[yt]
                c = label_to_idx[yp]
                matrix[r, c] += 1

        return matrix, resolved_labels

    def normalize(
        self,
        matrix: np.ndarray,
        mode: str = "true",
    ) -> np.ndarray:
        """
        Normaliza a matriz de confusão:
        - 'true': normaliza pelas somas das linhas (Recall por classe).
        - 'pred': normaliza pelas somas das colunas (Precision por classe).
        - 'all': normaliza pelo total geral de amostras.
        """
        mat = matrix.astype(float)
        if mode == "true":
            row_sums = mat.sum(axis=1, keepdims=True)
            row_sums[row_sums == 0] = 1.0
            return np.round(mat / row_sums, 4)
        elif mode == "pred":
            col_sums = mat.sum(axis=0, keepdims=True)
            col_sums[col_sums == 0] = 1.0
            return np.round(mat / col_sums, 4)
        elif mode == "all":
            total = mat.sum()
            return np.round(mat / total, 4) if total > 0 else mat
        else:
            raise ValueError(f"Modo de normalização inválido: '{mode}'. Use 'true', 'pred' ou 'all'.")

    def plot(
        self,
        matrix: np.ndarray,
        labels: List[str],
        output_path: Union[str, Path],
        normalize_mode: Optional[str] = None,
        title: str = "SolarGuard Vision - Matriz de Confusão",
        cmap: str = "Blues",
    ) -> Path:
        """
        Gera uma representação gráfica da matriz de confusão em formato PNG.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        display_matrix = matrix
        if normalize_mode:
            display_matrix = self.normalize(matrix, mode=normalize_mode)

        n = len(labels)
        fig_size = max(6, n * 1.2)
        fig, ax = plt.subplots(figsize=(fig_size, fig_size), dpi=300)

        im = ax.imshow(display_matrix, interpolation="nearest", cmap=cmap)
        ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        ax.set(
            xticks=np.arange(n),
            yticks=np.arange(n),
            xticklabels=labels,
            yticklabels=labels,
            title=title,
            ylabel="Classe Real (Ground Truth)",
            xlabel="Classe Predita (Predicted)",
        )

        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

        # Texto anotado em cada célula
        thresh = display_matrix.max() / 2.0 if display_matrix.size > 0 else 0.5
        for i in range(n):
            for j in range(n):
                val = display_matrix[i, j]
                val_str = f"{val:.2%}" if normalize_mode else f"{int(val)}"
                color = "white" if val > thresh else "black"
                ax.text(j, i, val_str, ha="center", va="center", color=color, fontsize=9, fontweight="bold")

        fig.tight_layout()
        plt.savefig(out, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Matriz de confusão exportada com sucesso: {out}")
        return out
