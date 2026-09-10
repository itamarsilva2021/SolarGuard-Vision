"""
Analisador de balanceamento de classes para datasets de visão computacional YOLOv11.
Calcula Imbalance Ratio, Entropia de Shannon e gera recomendações de pesos e data augmentation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import math


class BalanceSeverity(str, Enum):
    """Classificação do grau de desbalanceamento do dataset."""
    BALANCED = "balanced"                     # Proporções equilibradas (IR <= 3.0, H_norm >= 0.85)
    MODERATE_IMBALANCE = "moderate_imbalance" # Desbalanceamento tolerável (3.0 < IR <= 10.0)
    SEVERE_IMBALANCE = "severe_imbalance"     # Desbalanceamento crítico (IR > 10.0 ou classes zeradas)

    @property
    def display_name(self) -> str:
        names = {
            BalanceSeverity.BALANCED: "Balanceado (Equilibrado)",
            BalanceSeverity.MODERATE_IMBALANCE: "Desbalanceamento Moderado",
            BalanceSeverity.SEVERE_IMBALANCE: "Desbalanceamento Severo / Crítico",
        }
        return names.get(self, self.value)


@dataclass
class BalanceAnalysisResult:
    """Diagnóstico consolidado de balanceamento entre as classes do dataset."""
    severity: BalanceSeverity
    imbalance_ratio: float
    shannon_entropy: float
    normalized_entropy: float  # Entre 0.0 e 1.0
    
    # Classes extremas
    majority_classes: List[str] = field(default_factory=list)
    minority_classes: List[str] = field(default_factory=list)
    empty_classes: List[str] = field(default_factory=list)
    
    # Fatores de peso recomendados para a função de perda (YOLO cls_pw)
    recommended_class_weights: Dict[str, float] = field(default_factory=dict)
    
    # Recomendações técnicas acionáveis
    recommendations: List[str] = field(default_factory=list)


class DatasetBalanceAnalyzer:
    """
    Avalia a dispersão e desigualdade entre as amostras de classes anotadas.
    """

    @classmethod
    def analyze(cls, counts_by_class: Dict[str, int]) -> BalanceAnalysisResult:
        """
        Executa a análise de balanceamento a partir do dicionário de contagens por classe.
        
        :param counts_by_class: Dicionário {nome_classe: contagem_total}.
        :return: BalanceAnalysisResult com diagnóstico estatístico.
        """
        total_samples = sum(counts_by_class.values())
        num_classes = len(counts_by_class)

        if total_samples == 0 or num_classes == 0:
            return BalanceAnalysisResult(
                severity=BalanceSeverity.SEVERE_IMBALANCE,
                imbalance_ratio=float("inf"),
                shannon_entropy=0.0,
                normalized_entropy=0.0,
                recommendations=["O dataset não possui anotações válidas para análise."],
            )

        # 1. Identificação de classes vazias e extremas
        empty_classes = [c for c, count in counts_by_class.items() if count == 0]
        non_zero_counts = [count for count in counts_by_class.values() if count > 0]

        max_count = max(counts_by_class.values())
        min_non_zero = min(non_zero_counts) if non_zero_counts else 0

        # Imbalance Ratio
        if empty_classes or min_non_zero == 0:
            ir = float("inf")
        else:
            ir = round(max_count / min_non_zero, 2)

        # 2. Entropia de Shannon
        # H = - sum(p_i * log2(p_i))
        entropy = 0.0
        for count in non_zero_counts:
            p_i = count / total_samples
            entropy -= p_i * math.log2(p_i)

        max_entropy = math.log2(num_classes) if num_classes > 1 else 1.0
        norm_entropy = round(entropy / max_entropy, 4) if max_entropy > 0 else 1.0

        # 3. Classificação de Severidade
        if empty_classes or ir > 10.0 or norm_entropy < 0.65:
            severity = BalanceSeverity.SEVERE_IMBALANCE
        elif ir > 3.0 or norm_entropy < 0.85:
            severity = BalanceSeverity.MODERATE_IMBALANCE
        else:
            severity = BalanceSeverity.BALANCED

        # Identificação de classes dominantes e minoritárias
        avg_count = total_samples / num_classes
        majority = [c for c, count in counts_by_class.items() if count > avg_count * 1.5]
        minority = [c for c, count in counts_by_class.items() if 0 < count < avg_count * 0.5]

        # 4. Cálculo de Pesos Balanceados Inversos para YOLOv11
        # w_i = total_samples / (num_classes * count_i)
        weights: Dict[str, float] = {}
        for c, count in counts_by_class.items():
            if count > 0:
                raw_w = total_samples / (num_classes * count)
                weights[c] = round(min(raw_w, 20.0), 3)  # Limita peso máximo a 20x
            else:
                weights[c] = 20.0

        # 5. Recomendações Técnicas
        recommendations: List[str] = []
        if empty_classes:
            recommendations.append(
                f"Crítico: As classes {empty_classes} não possuem nenhuma amostra anotada. Colete imagens para essas categorias antes do treinamento."
            )

        if severity == BalanceSeverity.SEVERE_IMBALANCE:
            recommendations.append(
                f"Desbalanceamento Crítico (IR={ir}x, Entropia={norm_entropy*100:.1f}%). "
                f"Recomenda-se aplicar Data Augmentation térmico agressivo nas classes minoritárias ({minority})."
            )
            recommendations.append(
                "Configurar 'cls_pw' ou ponderação inversa de perda no treinamento YOLOv11 para evitar viés em direção às classes majoritárias."
            )
        elif severity == BalanceSeverity.MODERATE_IMBALANCE:
            recommendations.append(
                f"Desbalanceamento Moderado (IR={ir}x). Considere aumentar amostras das classes {minority} com rotações e ruído térmico sintético."
            )
        else:
            recommendations.append(
                "Distribuição de classes bem equilibrada. Adequado para treinamento padrão com hiperparâmetros de fábrica do YOLOv11."
            )

        return BalanceAnalysisResult(
            severity=severity,
            imbalance_ratio=ir,
            shannon_entropy=round(entropy, 4),
            normalized_entropy=norm_entropy,
            majority_classes=majority,
            minority_classes=minority,
            empty_classes=empty_classes,
            recommended_class_weights=weights,
            recommendations=recommendations,
        )
