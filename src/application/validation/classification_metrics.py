"""
Módulo de cálculo de métricas de classificação científica para modelos de IA do SolarGuard Vision.
Fornece métricas por classe e agregadas (Accuracy, Precision, Recall, Specificity, F1-Score, Balanced Accuracy).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
import numpy as np


@dataclass
class ClassMetrics:
    """Métricas de desempenho para uma classe individual (estratégia One-vs-Rest)."""
    class_name: str
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    total_samples: int
    precision: float
    recall: float
    specificity: float
    f1_score: float
    balanced_accuracy: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_name": self.class_name,
            "tp": self.true_positives,
            "fp": self.false_positives,
            "tn": self.true_negatives,
            "fn": self.false_negatives,
            "total": self.total_samples,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "specificity": round(self.specificity, 4),
            "f1_score": round(self.f1_score, 4),
            "balanced_accuracy": round(self.balanced_accuracy, 4),
        }


@dataclass
class GlobalClassificationMetrics:
    """Métricas consolidadas de classificação em nível global de dataset/modelo."""
    total_samples: int
    accuracy: float
    balanced_accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    weighted_precision: float
    weighted_recall: float
    weighted_f1: float
    per_class_metrics: Dict[str, ClassMetrics] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "accuracy": round(self.accuracy, 4),
            "balanced_accuracy": round(self.balanced_accuracy, 4),
            "macro_precision": round(self.macro_precision, 4),
            "macro_recall": round(self.macro_recall, 4),
            "macro_f1": round(self.macro_f1, 4),
            "weighted_precision": round(self.weighted_precision, 4),
            "weighted_recall": round(self.weighted_recall, 4),
            "weighted_f1": round(self.weighted_f1, 4),
            "classes": {k: v.to_dict() for k, v in self.per_class_metrics.items()},
        }


class ClassificationMetricsCalculator:
    """
    Calculadora científica de métricas de classificação para SolarGuard Vision.
    Suporta rótulos textuais e numéricos, com tratamento estrito de divisões por zero.
    """

    @staticmethod
    def calculate_from_labels(
        y_true: List[Union[str, int]],
        y_pred: List[Union[str, int]],
        labels: Optional[List[Union[str, int]]] = None,
        target_classes: Optional[List[Union[str, int]]] = None,
    ) -> GlobalClassificationMetrics:
        """
        Calcula as métricas globais e por classe a partir de listas de ground-truth e predições.
        
        :param y_true: Lista de rótulos reais.
        :param y_pred: Lista de rótulos preditos.
        :param labels: Rótulos a incluir na análise detalhada por classe.
        :param target_classes: Subconjunto de classes de interesse para métricas agregadas macro/weighted.
        """
        if len(y_true) != len(y_pred):
            raise ValueError(f"Tamanhos incompatíveis: y_true ({len(y_true)}) != y_pred ({len(y_pred)})")

        if len(y_true) == 0:
            return GlobalClassificationMetrics(
                total_samples=0,
                accuracy=0.0,
                balanced_accuracy=0.0,
                macro_precision=0.0,
                macro_recall=0.0,
                macro_f1=0.0,
                weighted_precision=0.0,
                weighted_recall=0.0,
                weighted_f1=0.0,
                per_class_metrics={},
            )

        str_y_true = [str(x) for x in y_true]
        str_y_pred = [str(x) for x in y_pred]

        if labels is None:
            unique_labels = sorted(list(set(str_y_true) | set(str_y_pred)))
        else:
            unique_labels = [str(lbl) for lbl in labels]

        total_samples = len(str_y_true)
        correct_predictions = sum(1 for yt, yp in zip(str_y_true, str_y_pred) if yt == yp)
        accuracy = correct_predictions / total_samples if total_samples > 0 else 0.0

        per_class: Dict[str, ClassMetrics] = {}
        for cls_name in unique_labels:
            tp = sum(1 for yt, yp in zip(str_y_true, str_y_pred) if yt == cls_name and yp == cls_name)
            fp = sum(1 for yt, yp in zip(str_y_true, str_y_pred) if yt != cls_name and yp == cls_name)
            fn = sum(1 for yt, yp in zip(str_y_true, str_y_pred) if yt == cls_name and yp != cls_name)
            tn = sum(1 for yt, yp in zip(str_y_true, str_y_pred) if yt != cls_name and yp != cls_name)
            cls_total = tp + fn

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
            bal_acc = (rec + spec) / 2.0

            per_class[cls_name] = ClassMetrics(
                class_name=cls_name,
                true_positives=tp,
                false_positives=fp,
                true_negatives=tn,
                false_negatives=fn,
                total_samples=cls_total,
                precision=prec,
                recall=rec,
                specificity=spec,
                f1_score=f1,
                balanced_accuracy=bal_acc,
            )

        # Classes consideradas para a agregação macro
        if target_classes is not None:
            macro_class_names = [str(c) for c in target_classes if str(c) in per_class]
        else:
            macro_class_names = list(unique_labels)

        num_classes = len(macro_class_names)
        if num_classes > 0:
            macro_prec = sum(per_class[c].precision for c in macro_class_names) / num_classes
            macro_rec = sum(per_class[c].recall for c in macro_class_names) / num_classes
            macro_f1 = sum(per_class[c].f1_score for c in macro_class_names) / num_classes
            macro_bal_acc = sum(per_class[c].balanced_accuracy for c in macro_class_names) / num_classes

            # Médias ponderadas pelo suporte
            total_ground_truth = sum(per_class[c].total_samples for c in macro_class_names)
            if total_ground_truth > 0:
                weighted_prec = sum(per_class[c].precision * per_class[c].total_samples for c in macro_class_names) / total_ground_truth
                weighted_rec = sum(per_class[c].recall * per_class[c].total_samples for c in macro_class_names) / total_ground_truth
                weighted_f1 = sum(per_class[c].f1_score * per_class[c].total_samples for c in macro_class_names) / total_ground_truth
            else:
                weighted_prec = macro_prec
                weighted_rec = macro_rec
                weighted_f1 = macro_f1
        else:
            macro_prec = macro_rec = macro_f1 = macro_bal_acc = 0.0
            weighted_prec = weighted_rec = weighted_f1 = 0.0

        return GlobalClassificationMetrics(
            total_samples=total_samples,
            accuracy=accuracy,
            balanced_accuracy=macro_bal_acc,
            macro_precision=macro_prec,
            macro_recall=macro_rec,
            macro_f1=macro_f1,
            weighted_precision=weighted_prec,
            weighted_recall=weighted_rec,
            weighted_f1=weighted_f1,
            per_class_metrics=per_class,
        )
