"""
Fachada e orquestrador unificado para extração, validação e padronização
de metadados de imagens capturadas por drones DJI Enterprise (Matrice 4T).
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import numpy as np

from src.application.dtos.dji_metadata_dto import (
    DjiParsedMetadataDTO,
    RtkTelemetryDTO,
    FlightOrientationDTO,
    RadiometricFlightParamsDTO,
    CameraSensorDTO,
    RtkStatus,
    ThermalGainMode,
)
from src.domain.value_objects.geo_coordinate import GeoCoordinate
from src.domain.value_objects.thermal_matrix_meta import ThermalMatrixMeta
from src.infrastructure.imaging.metadata_extractor import MetadataExtractor
from src.infrastructure.imaging.dji_xmp_parser import DjiXmpParser
from src.infrastructure.imaging.dji_rtk_parser import DjiRtkParser
from src.infrastructure.imaging.dji_flight_parser import DjiFlightParser
from src.infrastructure.imaging.dji_validators import DjiImageValidator
from src.core.logger import get_logger

logger = get_logger("DjiMetadataParser")


class DjiMetadataParser:
    """
    Fachada unificada para análise e consolidação de metadados EXIF, XMP, RTK,
    orientação de voo e parâmetros radiométricos de imagens térmicas DJI Matrice 4T.
    """

    @classmethod
    def parse(cls, file_path: str | Path) -> DjiParsedMetadataDTO:
        """
        Executa a extração completa e validação de metadados a partir do arquivo.
        
        :param file_path: Caminho para a imagem (R-JPEG ou TIFF).
        :return: DjiParsedMetadataDTO consolidado.
        """
        path = Path(file_path)
        warnings: List[str] = []

        # 1. Validação física e integridade do arquivo
        is_intact, integrity_errors = DjiImageValidator.validate_file_integrity(path)
        if not is_intact:
            warnings.extend(integrity_errors)

        # 2. Extração de Metadados EXIF Padrão
        exif_data = MetadataExtractor.extract_exif(path)
        width = exif_data.get("width") or 640
        height = exif_data.get("height") or 512
        captured_at = exif_data.get("captured_at")
        geo_coord: Optional[GeoCoordinate] = exif_data.get("coordinate")

        # 3. Extração de Metadados XMP DJI Avançados
        xmp_data = DjiXmpParser.parse_xmp(path)
        raw_xmp_found = len(xmp_data) > 0

        # Validação do canal térmico (evita fotos Wide / Zoom no pipeline térmico)
        is_thermal, thermal_warnings = DjiImageValidator.validate_thermal_channel(path, xmp_data)
        warnings.extend(thermal_warnings)

        # 4. Mapeamento de RTK
        rtk_dto = DjiRtkParser.parse_rtk_data(xmp_data)

        # 5. Mapeamento de Atitude Angular (Gimbal e Drone)
        orientation_dto = DjiFlightParser.parse_orientation(xmp_data)

        # 6. Mapeamento de Altitudes Diferenciadas
        exif_alt = geo_coord.altitude_meters if geo_coord else None
        rel_alt, abs_alt = DjiFlightParser.parse_altitudes(xmp_data, exif_gps_alt=exif_alt)

        # 7. Mapeamento de Parâmetros Radiométricos do DJI Pilot 2
        emissivity = xmp_data.get("Emissivity", 0.95)
        refl_temp = xmp_data.get("ReflectedTemperature", 25.0)
        target_dist = xmp_data.get("Distance", rel_alt or 25.0)
        humidity = xmp_data.get("RelativeHumidity", 0.50)

        # Normalização de umidade relativa (DJI Pilot às vezes grava em % 50.0 ou decimal 0.50)
        if humidity is not None and humidity > 1.0:
            humidity = round(humidity / 100.0, 3)

        raw_gain = str(xmp_data.get("ThermalGainMode", "")).lower()
        if "high" in raw_gain:
            gain_mode = ThermalGainMode.HIGH_GAIN
        elif "low" in raw_gain:
            gain_mode = ThermalGainMode.LOW_GAIN
        else:
            gain_mode = ThermalGainMode.HIGH_GAIN  # Padrão típico para termografia fotovoltaica

        radiometry_dto = RadiometricFlightParamsDTO(
            emissivity=float(emissivity),
            reflected_temp_celsius=float(refl_temp),
            ambient_temp_celsius=28.0,  # Estimativa ou sensor meteorológico externo
            relative_humidity=float(humidity) if humidity is not None else 0.50,
            target_distance_meters=float(target_dist) if target_dist is not None else 25.0,
            gain_mode=gain_mode,
        )

        # 8. Mapeamento de Hardware e Sensor
        camera_dto = CameraSensorDTO(
            drone_model=xmp_data.get("Model", "Matrice 4T"),
            drone_serial_number=xmp_data.get("DroneSerialNumber"),
            camera_serial_number=xmp_data.get("CameraSerialNumber"),
            camera_type=xmp_data.get("CameraType", "Thermal"),
            is_thermal_lens=is_thermal,
            focal_length_mm=xmp_data.get("FocalLength"),
            focal_length_35mm=xmp_data.get("FocalLengthIn35mmFilm"),
            calibrated_focal_length_px=xmp_data.get("CalibratedFocalLength"),
            optical_center_x=xmp_data.get("CalibratedOpticalCenterX"),
            optical_center_y=xmp_data.get("CalibratedOpticalCenterY"),
            dewarp_data=xmp_data.get("DewarpData"),
        )

        # 9. Validação de Limites Físicos
        lat_val = geo_coord.latitude if geo_coord else None
        lon_val = geo_coord.longitude if geo_coord else None
        _, telemetry_warnings = DjiImageValidator.validate_physical_telemetry(
            latitude=lat_val,
            longitude=lon_val,
            altitude_rel=rel_alt,
            emissivity=emissivity,
        )
        warnings.extend(telemetry_warnings)

        return DjiParsedMetadataDTO(
            file_name=path.name,
            file_path=str(path.resolve()),
            width=width,
            height=height,
            captured_at=captured_at,
            latitude=lat_val,
            longitude=lon_val,
            relative_altitude_meters=rel_alt,
            absolute_altitude_meters=abs_alt,
            rtk=rtk_dto,
            orientation=orientation_dto,
            radiometry=radiometry_dto,
            camera=camera_dto,
            is_valid=is_intact and (len(integrity_errors) == 0),
            validation_warnings=warnings,
            raw_xmp_found=raw_xmp_found,
        )

    @classmethod
    def to_geo_coordinate(cls, dto: DjiParsedMetadataDTO) -> Optional[GeoCoordinate]:
        """Converte as coordenadas do DTO no Value Object de domínio GeoCoordinate."""
        if dto.latitude is not None and dto.longitude is not None:
            return GeoCoordinate(
                latitude=dto.latitude,
                longitude=dto.longitude,
                altitude_meters=dto.absolute_altitude_meters or dto.relative_altitude_meters,
            )
        return None

    @classmethod
    def to_thermal_matrix_meta(
        cls,
        dto: DjiParsedMetadataDTO,
        matrix: Optional[np.ndarray] = None,
    ) -> ThermalMatrixMeta:
        """
        Converte o DTO no Value Object ThermalMatrixMeta,
        calculando temperaturas mínima, máxima e média a partir da matriz se fornecida.
        """
        if matrix is not None and matrix.size > 0:
            min_temp = float(np.min(matrix))
            max_temp = float(np.max(matrix))
            avg_temp = float(np.mean(matrix))
            h, w = matrix.shape[:2]
        else:
            min_temp = 20.0
            max_temp = 65.0
            avg_temp = 38.0
            h = dto.height or 512
            w = dto.width or 640

        return ThermalMatrixMeta(
            emissivity=dto.radiometry.emissivity,
            reflected_temp_celsius=dto.radiometry.reflected_temp_celsius,
            ambient_temp_celsius=dto.radiometry.ambient_temp_celsius,
            relative_humidity=dto.radiometry.relative_humidity,
            distance_meters=dto.radiometry.target_distance_meters,
            min_temp_celsius=round(min_temp, 2),
            max_temp_celsius=round(max_temp, 2),
            avg_temp_celsius=round(avg_temp, 2),
            sensor_width=w,
            sensor_height=h,
        )
