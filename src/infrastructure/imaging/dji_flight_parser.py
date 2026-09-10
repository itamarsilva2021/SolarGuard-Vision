"""
Parser de telemetria de voo, atitude espacial (Euler angles) e altitudes da aeronave DJI.
"""

from typing import Dict, Any, Optional, Tuple
from src.application.dtos.dji_metadata_dto import FlightOrientationDTO
from src.domain.value_objects.geo_coordinate import GeoCoordinate
from src.core.logger import get_logger

logger = get_logger("DjiFlightParser")


class DjiFlightParser:
    """
    Decodifica a orientação angular 3D do gimbal e do drone,
    distinguindo tipos de altitude e validando a geometria do disparo térmico.
    """

    @classmethod
    def parse_orientation(cls, xmp_data: Dict[str, Any]) -> FlightOrientationDTO:
        """
        Extrai os ângulos de atitude do gimbal e da aeronave em graus decimais [-180, +180].
        
        :param xmp_data: Dicionário retornado pelo DjiXmpParser.
        :return: FlightOrientationDTO.
        """
        def _get_float(k: str) -> Optional[float]:
            v = xmp_data.get(k)
            return float(v) if v is not None and isinstance(v, (int, float)) else None

        return FlightOrientationDTO(
            gimbal_pitch=_get_float("GimbalPitchDegree"),
            gimbal_roll=_get_float("GimbalRollDegree"),
            gimbal_yaw=_get_float("GimbalYawDegree"),
            flight_pitch=_get_float("FlightPitchDegree"),
            flight_roll=_get_float("FlightRollDegree"),
            flight_yaw=_get_float("FlightYawDegree"),
        )

    @classmethod
    def parse_altitudes(cls, xmp_data: Dict[str, Any], exif_gps_alt: Optional[float] = None) -> Tuple[Optional[float], Optional[float]]:
        """
        Extrai tanto a altitude relativa (em relação ao ponto de decolagem)
        quanto a altitude absoluta (MSL/Elipsoidal).
        
        :param xmp_data: Dicionário XMP decodificado.
        :param exif_gps_alt: Altitude obtida da tag GPS EXIF (fallback).
        :return: Tupla (relative_altitude_meters, absolute_altitude_meters).
        """
        rel_alt = xmp_data.get("RelativeAltitude")
        abs_alt = xmp_data.get("AbsoluteAltitude")
        rtk_alt = xmp_data.get("RtkAltitude")

        rel_alt_val = float(rel_alt) if rel_alt is not None else None
        
        # Prioriza RtkAltitude se disponível, depois AbsoluteAltitude, depois EXIF GPSAltitude
        if rtk_alt is not None:
            abs_alt_val = float(rtk_alt)
        elif abs_alt is not None:
            abs_alt_val = float(abs_alt)
        else:
            abs_alt_val = exif_gps_alt

        return rel_alt_val, abs_alt_val

    @classmethod
    def is_nadir_angle(cls, orientation: FlightOrientationDTO, tolerance_deg: float = 15.0) -> bool:
        """
        Verifica se a câmera térmica estava apontada para o nadir (prumo perpendicular ao solo, ~ -90°).
        Em inspeções solares IEC TS 62446-3, ângulos próximos de nadir minimizam distorções de perspectiva.
        """
        if orientation.gimbal_pitch is None:
            return False
        # Nadir perfeito é -90 graus
        return abs(orientation.gimbal_pitch - (-90.0)) <= tolerance_deg
