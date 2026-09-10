"""
Engine de Georreferenciamento e Projeção Fotogramétrica para Imagens Térmicas DJI.
Calcula a latitude e longitude exata de cada falha detectada com base no GPS do drone,
altitude de voo, orientação da aeronave (yaw) e parâmetros ópticos da câmera térmica DJI Matrice 4T.
"""

import math
from typing import Optional, Tuple
from src.domain.value_objects.geo_coordinate import GeoCoordinate
from src.domain.value_objects.bounding_box import BoundingBox
from src.core.logger import get_logger

logger = get_logger("ThermalGeoReferencer")


class ThermalGeoReferencer:
    """
    Calculador de coordenadas no solo a partir da projeção fotogramétrica aérea
    de sensores radiométricos DJI (especialmente DJI Matrice 4T).
    """

    # Parâmetros padrão do sensor térmico não-refrigerado VOx do DJI Matrice 4T:
    # Resolução: 640x512 | DFOV: 61° | HFOV: ~44° | VFOV: ~35°
    DEFAULT_HFOV_DEG: float = 44.0
    DEFAULT_VFOV_DEG: float = 35.0
    DEFAULT_FLIGHT_ALTITUDE_METERS: float = 25.0  # Altitude padrão regulamentar de inspeção fotovoltaica
    EARTH_RADIUS_METERS: float = 6378137.0       # WGS84 semi-eixo maior

    def __init__(
        self,
        hfov_deg: float = DEFAULT_HFOV_DEG,
        vfov_deg: float = DEFAULT_VFOV_DEG,
    ) -> None:
        self.hfov_deg = hfov_deg
        self.vfov_deg = vfov_deg
        self._hfov_rad = math.radians(hfov_deg)
        self._vfov_rad = math.radians(vfov_deg)

    def calculate_gsd(
        self,
        flight_altitude_m: float,
        image_width_px: int = 640,
        image_height_px: int = 512,
    ) -> Tuple[float, float]:
        """
        Calcula o Ground Sample Distance (GSD em metros por pixel) horizontal e vertical.
        
        :param flight_altitude_m: Altitude relativa de voo do drone sobre o terreno (metros).
        :param image_width_px: Largura da imagem em pixels.
        :param image_height_px: Altura da imagem em pixels.
        :return: Tupla (gsd_x_m, gsd_y_m).
        """
        alt = max(flight_altitude_m, 1.0)
        ground_width_m = 2.0 * alt * math.tan(self._hfov_rad / 2.0)
        ground_height_m = 2.0 * alt * math.tan(self._vfov_rad / 2.0)

        gsd_x = ground_width_m / max(image_width_px, 1)
        gsd_y = ground_height_m / max(image_height_px, 1)
        return gsd_x, gsd_y

    def project_anomaly_coordinate(
        self,
        drone_coordinate: GeoCoordinate,
        bbox: BoundingBox,
        image_width_px: int = 640,
        image_height_px: int = 512,
        flight_altitude_m: Optional[float] = None,
        yaw_deg: float = 0.0,
    ) -> GeoCoordinate:
        """
        Projeta o ponto central de uma BoundingBox no plano do solo para obter a coordenada geográfica exata.
        
        :param drone_coordinate: Coordenada GPS do drone no momento da captura.
        :param bbox: Caixa delimitadora da falha.
        :param image_width_px: Largura da imagem em pixels.
        :param image_height_px: Altura da imagem em pixels.
        :param flight_altitude_m: Altitude relativa em metros (se None, usa altitude do GPS ou padrão).
        :param yaw_deg: Ângulo de rumo do drone/gimbal (0° = Norte, 90° = Leste).
        :return: GeoCoordinate precisa do defeito no solo.
        """
        # Determinar altitude de voo sobre o painel
        alt = flight_altitude_m
        if alt is None or alt <= 0:
            alt = drone_coordinate.altitude if (drone_coordinate.altitude and drone_coordinate.altitude > 0) else self.DEFAULT_FLIGHT_ALTITUDE_METERS

        gsd_x, gsd_y = self.calculate_gsd(alt, image_width_px, image_height_px)

        # Centro do defeito na imagem
        cx_norm, cy_norm = bbox.center
        center_x_px = cx_norm * image_width_px if bbox.is_normalized else cx_norm
        center_y_px = cy_norm * image_height_px if bbox.is_normalized else cy_norm

        # Deslocamento em relação ao centro óptico da câmera
        center_opt_x = image_width_px / 2.0
        center_opt_y = image_height_px / 2.0

        delta_u = center_x_px - center_opt_x
        delta_v = center_y_px - center_opt_y

        # Deslocamento métrico no sistema de coordenadas do corpo do drone (Body Frame)
        # X: Direita / Asa Direita | Y: Frente / Nariz
        x_body_m = delta_u * gsd_x
        y_body_m = -delta_v * gsd_y  # Inverte pois o eixo Y da imagem aponta para baixo

        # Rotação para o sistema de coordenadas Norte-Leste pelo ângulo de rumo (Yaw)
        yaw_rad = math.radians(yaw_deg)
        # North = y_body * cos(yaw) - x_body * sin(yaw)
        # East  = y_body * sin(yaw) + x_body * cos(yaw)
        delta_north_m = y_body_m * math.cos(yaw_rad) - x_body_m * math.sin(yaw_rad)
        delta_east_m = y_body_m * math.sin(yaw_rad) + x_body_m * math.cos(yaw_rad)

        # Conversão métrica para deslocamento geodésico WGS84
        lat_rad = math.radians(drone_coordinate.latitude)
        delta_lat = (delta_north_m / self.EARTH_RADIUS_METERS) * (180.0 / math.pi)
        delta_lon = (delta_east_m / (self.EARTH_RADIUS_METERS * math.cos(lat_rad))) * (180.0 / math.pi)

        anomaly_lat = drone_coordinate.latitude + delta_lat
        anomaly_lon = drone_coordinate.longitude + delta_lon

        # Altitude do solo estimada
        ground_alt = (drone_coordinate.altitude - alt) if drone_coordinate.altitude else None

        return GeoCoordinate(
            latitude=anomaly_lat,
            longitude=anomaly_lon,
            altitude_meters=ground_alt,
        )

