"""
Contrato abstrato para decodificação e processamento radiométrico de imagens do drone DJI Matrice 4T.
"""

from abc import ABC, abstractmethod
from typing import Any
import numpy as np

from src.domain.value_objects.thermal_matrix_meta import ThermalMatrixMeta
from src.domain.value_objects.geo_coordinate import GeoCoordinate


class IThermalParser(ABC):
    """
    Interface para o motor radiométrico de extração de dados brutos de temperatura.
    Lida com imagens R-JPEG capturadas pela câmera térmica do DJI Matrice 4T.
    """

    @abstractmethod
    def extract_temperature_matrix(self, file_path: str) -> np.ndarray:
        """
        Decodifica o payload térmico radiométrico do R-JPEG e retorna
        uma matriz 2D numpy de float32 com os valores absolutos de temperatura em graus Celsius (°C).
        
        :param file_path: Caminho do arquivo R-JPEG em disco.
        :return: Array 2D float32 [altura x largura] com as temperaturas em °C.
        """
        pass

    @abstractmethod
    def extract_metadata(self, file_path: str) -> ThermalMatrixMeta:
        """
        Extrai parâmetros do sensor e ambientais (emissividade, temperatura ambiente, umidade, distâncias).
        """
        pass

    @abstractmethod
    def extract_gps_and_gimbal(self, file_path: str) -> tuple[GeoCoordinate | None, float | None, float | None]:
        """
        Extrai coordenadas geodésicas (GPS WGS84) e ângulos de orientação do Gimbal (pitch, yaw).
        
        :return: Tupla contendo (GeoCoordinate, gimbal_pitch, gimbal_yaw).
        """
        pass
