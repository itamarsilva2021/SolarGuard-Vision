"""
Contrato abstrato para o módulo de inferência e detecção por Inteligência Artificial (YOLOv11).
"""

from abc import ABC, abstractmethod
import numpy as np
from src.domain.entities.thermal_anomaly import ThermalAnomaly


class IAnomalyDetector(ABC):
    """
    Interface para modelos de detecção de anomalias baseados em YOLOv11 / PyTorch.
    """

    @abstractmethod
    def detect(
        self,
        image_bgr_or_rgb: np.ndarray,
        temperature_matrix: np.ndarray | None = None,
        confidence_threshold: float = 0.40,
    ) -> list[ThermalAnomaly]:
        """
        Executa a inferência na imagem e correlaciona as detecções com a matriz de temperatura
        para quantificar gradientes Delta T e classificar severidades segundo a IEC TS 62446-3.
        
        :param image_bgr_or_rgb: Imagem em array numpy (3 canais).
        :param temperature_matrix: Matriz radiométrica 2D de temperaturas em °C (se disponível).
        :param confidence_threshold: Limiar mínimo de probabilidade para retenção da caixa.
        :return: Lista de anomalias detectadas.
        """
        pass
