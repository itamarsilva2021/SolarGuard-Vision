"""
Objeto de Valor (Value Object) para coordenadas geográficas com suporte a cálculo de distância geodésica.
"""

from dataclasses import dataclass
import math
from typing import Optional
from src.domain.exceptions import InvalidCoordinateError


@dataclass(frozen=True)
class GeoCoordinate:
    """
    Representa uma coordenada geográfica WGS84 imutável.
    
    :param latitude: Latitude em graus decimais [-90.0, 90.0].
    :param longitude: Longitude em graus decimais [-180.0, 180.0].
    :param altitude_meters: Altitude acima do nível do mar em metros (opcional).
    """
    latitude: float
    longitude: float
    altitude_meters: Optional[float] = None

    @property
    def altitude(self) -> Optional[float]:
        """Alias para altitude_meters."""
        return self.altitude_meters


    def __post_init__(self) -> None:
        if not (-90.0 <= self.latitude <= 90.0):
            raise InvalidCoordinateError(
                f"Latitude inválida: {self.latitude}. Deve estar no intervalo [-90.0, 90.0]."
            )
        if not (-180.0 <= self.longitude <= 180.0):
            raise InvalidCoordinateError(
                f"Longitude inválida: {self.longitude}. Deve estar no intervalo [-180.0, 180.0]."
            )
        if self.altitude_meters is not None and self.altitude_meters < -500.0:
            raise InvalidCoordinateError(
                f"Altitude inválida: {self.altitude_meters}m. Deve ser fisicamente plausível."
            )

    def distance_to_meters(self, other: "GeoCoordinate") -> float:
        """
        Calcula a distância aproximada em metros entre dois pontos geográficos pela fórmula de Haversine.
        
        :param other: Outra coordenada geográfica.
        :return: Distância em metros.
        """
        earth_radius_m = 6_371_000.0  # Raio médio da Terra em metros

        phi1 = math.radians(self.latitude)
        phi2 = math.radians(other.latitude)
        delta_phi = math.radians(other.latitude - self.latitude)
        delta_lambda = math.radians(other.longitude - self.longitude)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

        return earth_radius_m * c

    def to_tuple(self) -> tuple[float, float]:
        """Retorna tupla (latitude, longitude)."""
        return self.latitude, self.longitude
