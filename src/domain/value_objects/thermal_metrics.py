"""
Objeto de Valor contendo métricas térmicas quantitativas de uma cena, módulo ou anomalia.
Inclui temperaturas extremas, médias, gradientes Delta T e classificação normativa IEC TS 62446-3.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple
from src.domain.enums.severity_level import SeverityLevel
from src.domain.value_objects.delta_t import DeltaT


@dataclass(frozen=True)
class ThermalMetrics:
    """
    Conjunto de métricas térmicas quantitativas extraídas de uma matriz radiométrica.
    
    :param min_temp: Temperatura mínima medida (°C).
    :param max_temp: Temperatura máxima absoluta de pico (°C).
    :param avg_temp: Temperatura média (°C).
    :param median_temp: Temperatura mediana (°C).
    :param std_temp: Desvio padrão térmico (°C) - mede a dispersão de calor.
    :param delta_t: Gradiente térmico em relação à referência (°C).
    :param max_location: Coordenadas de pixel (x, y) do ponto mais quente.
    :param min_location: Coordenadas de pixel (x, y) do ponto mais frio.
    :param ref_temp: Temperatura de referência utilizada para o cálculo do Delta T (°C).
    :param severity: Classificação de severidade segundo a norma IEC TS 62446-3.
    """
    min_temp: float
    max_temp: float
    avg_temp: float
    median_temp: float
    std_temp: float
    delta_t: float
    max_location: tuple[int, int]
    min_location: tuple[int, int]
    ref_temp: float
    severity: SeverityLevel = SeverityLevel.INFORMATIVE

    @property
    def dynamic_range(self) -> float:
        """Amplitude térmica (span) da região analisada (°C)."""
        return round(self.max_temp - self.min_temp, 2)

    @property
    def is_critical(self) -> bool:
        """Indica se a severidade atingiu a Classe 3 da IEC (Crítico)."""
        return self.severity == SeverityLevel.CRITICAL

    def to_delta_t_object(self) -> DeltaT:
        """Converte para a entidade de valor DeltaT do domínio."""
        return DeltaT(t_max_celsius=self.max_temp, t_ref_celsius=self.ref_temp)

    def to_dict(self) -> dict:
        """Serializa as métricas em formato legível de dicionário."""
        return {
            "min_temp_celsius": self.min_temp,
            "max_temp_celsius": self.max_temp,
            "avg_temp_celsius": self.avg_temp,
            "median_temp_celsius": self.median_temp,
            "std_temp_celsius": self.std_temp,
            "delta_t_celsius": self.delta_t,
            "dynamic_range_celsius": self.dynamic_range,
            "ref_temp_celsius": self.ref_temp,
            "max_location_pixel": self.max_location,
            "min_location_pixel": self.min_location,
            "severity": self.severity.value,
            "severity_display": self.severity.display_name,
        }
