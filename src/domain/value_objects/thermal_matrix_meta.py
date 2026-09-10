"""
Objeto de Valor para metadados radiométricos de imagens térmicas do drone DJI Matrice 4T.
"""

from dataclasses import dataclass
from typing import Optional
from src.domain.exceptions import ThermalDataCorruptedError


@dataclass(frozen=True)
class ThermalMatrixMeta:
    """
    Metadados do sensor termográfico do DJI Matrice 4T.
    
    :param emissivity: Coeficiente de emissividade da superfície (padrão 0.85-0.95 para vidro solar).
    :param reflected_temp_celsius: Temperatura aparente refletida (°C).
    :param ambient_temp_celsius: Temperatura do ar ambiente (°C).
    :param relative_humidity: Umidade relativa do ar (0.0 a 1.0 ou percentual).
    :param distance_meters: Distância do sensor ao objeto (altitude relativa de voo em metros).
    :param min_temp_celsius: Temperatura mínima absoluta medida na cena (°C).
    :param max_temp_celsius: Temperatura máxima absoluta medida na cena (°C).
    :param avg_temp_celsius: Temperatura média da cena (°C).
    :param sensor_width: Resolução horizontal nativa do sensor térmico (640 para DJI M4T).
    :param sensor_height: Resolução vertical nativa do sensor térmico (512 para DJI M4T).
    """
    emissivity: float = 0.95
    reflected_temp_celsius: float = 25.0
    ambient_temp_celsius: float = 28.0
    relative_humidity: float = 0.50
    distance_meters: float = 25.0
    min_temp_celsius: float = 20.0
    max_temp_celsius: float = 65.0
    avg_temp_celsius: float = 38.0
    sensor_width: int = 640
    sensor_height: int = 512

    def __post_init__(self) -> None:
        if not (0.0 < self.emissivity <= 1.0):
            raise ThermalDataCorruptedError(
                f"Emissividade inválida: {self.emissivity}. Deve estar no intervalo (0.0, 1.0]."
            )
        if self.min_temp_celsius > self.max_temp_celsius:
            raise ThermalDataCorruptedError(
                f"min_temp ({self.min_temp_celsius}°C) não pode ser maior que max_temp ({self.max_temp_celsius}°C)."
            )
        if self.sensor_width <= 0 or self.sensor_height <= 0:
            raise ThermalDataCorruptedError(
                f"Resolução de sensor inválida: {self.sensor_width}x{self.sensor_height}."
            )

    @property
    def dynamic_range(self) -> float:
        """Amplitude térmica (span) da imagem em graus Celsius."""
        return round(self.max_temp_celsius - self.min_temp_celsius, 2)
