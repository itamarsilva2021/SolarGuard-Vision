"""
Módulo de extração de metadados EXIF e XMP (DJI Matrice 4T).
Suporta leitura de coordenadas GPS WGS84, altitude de voo e ângulos do Gimbal.
"""

from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
import re
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import piexif

from src.domain.value_objects.geo_coordinate import GeoCoordinate
from src.core.logger import get_logger

logger = get_logger("MetadataExtractor")


class MetadataExtractor:
    """
    Extrator de metadados para imagens aéreas capturadas por drones,
    com suporte especializado para tags proprietárias do DJI Matrice 4T.
    """

    @staticmethod
    def _convert_gps_coordinate(coord_tuple, ref: str) -> Optional[float]:
        """Converte coordenadas GPS em graus, minutos e segundos (DMS) para graus decimais."""
        if not coord_tuple or len(coord_tuple) < 3:
            return None
        try:
            degrees = float(coord_tuple[0])
            minutes = float(coord_tuple[1])
            seconds = float(coord_tuple[2])

            decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
            if ref in ["S", "W"]:
                decimal = -decimal
            return round(decimal, 6)
        except Exception as ex:
            logger.warning(f"Erro ao converter coordenada GPS DMS: {ex}")
            return None

    @classmethod
    def extract_exif(cls, file_path: str | Path) -> dict:
        """
        Extrai metadados EXIF padrão e GPS da imagem.
        
        :param file_path: Caminho do arquivo da imagem.
        :return: Dicionário contendo coordinate (GeoCoordinate), captured_at, width, height.
        """
        file_path = Path(file_path)
        data: dict = {
            "coordinate": None,
            "captured_at": None,
            "width": 0,
            "height": 0,
        }

        if not file_path.exists():
            return data

        try:
            with Image.open(file_path) as img:
                data["width"], data["height"] = img.size
                exif_raw = img._getexif()

                if not exif_raw:
                    return data

                exif = {TAGS.get(k, k): v for k, v in exif_raw.items()}

                # Extração da Data/Hora de Captura
                date_str = exif.get("DateTimeOriginal") or exif.get("DateTime")
                if date_str and isinstance(date_str, str):
                    try:
                        data["captured_at"] = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        pass

                # Extração do bloco GPS
                gps_info_raw = exif.get("GPSInfo")
                if gps_info_raw and isinstance(gps_info_raw, dict):
                    gps_info = {GPSTAGS.get(k, k): v for k, v in gps_info_raw.items()}

                    lat_tuple = gps_info.get("GPSLatitude")
                    lat_ref = gps_info.get("GPSLatitudeRef", "N")
                    lon_tuple = gps_info.get("GPSLongitude")
                    lon_ref = gps_info.get("GPSLongitudeRef", "E")
                    alt_val = gps_info.get("GPSAltitude")

                    lat = cls._convert_gps_coordinate(lat_tuple, lat_ref)
                    lon = cls._convert_gps_coordinate(lon_tuple, lon_ref)
                    alt = float(alt_val) if alt_val is not None else None

                    if lat is not None and lon is not None:
                        try:
                            data["coordinate"] = GeoCoordinate(
                                latitude=lat,
                                longitude=lon,
                                altitude_meters=alt,
                            )
                        except Exception as e:
                            logger.warning(f"Coordenada inválida ignorada em {file_path.name}: {e}")

        except Exception as ex:
            logger.error(f"Erro ao processar EXIF de {file_path}: {ex}")

        return data

    @classmethod
    def extract_dji_xmp(cls, file_path: str | Path) -> dict:
        """
        Extrai metadados do pacote XMP proprietário do DJI Matrice 4T
        (ângulos do gimbal, altitude relativa, modelo do drone).
        
        :param file_path: Caminho do arquivo da imagem.
        :return: Dicionário contendo flight_altitude, gimbal_pitch, gimbal_yaw, drone_model.
        """
        file_path = Path(file_path)
        dji_data: dict = {
            "flight_altitude_meters": None,
            "gimbal_pitch_degrees": None,
            "gimbal_yaw_degrees": None,
            "drone_model": None,
        }

        if not file_path.exists():
            return dji_data

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            # Busca por bloco XMP no binário do arquivo
            xmp_start = content.find(b"<x:xmpmeta")
            xmp_end = content.find(b"</x:xmpmeta>")

            if xmp_start != -1 and xmp_end != -1:
                xmp_str = content[xmp_start : xmp_end + 12].decode("utf-8", errors="ignore")

                # Padrões regex para tags XMP da DJI
                pitch_match = re.search(r'drone-dji:GimbalPitchDegree="?([+-]?\d+\.?\d*)"?', xmp_str)
                yaw_match = re.search(r'drone-dji:GimbalYawDegree="?([+-]?\d+\.?\d*)"?', xmp_str)
                alt_match = re.search(r'drone-dji:RelativeAltitude="?([+-]?\d+\.?\d*)"?', xmp_str)
                model_match = re.search(r'drone-dji:Model="?([^"\s>]+)"?', xmp_str)

                if pitch_match:
                    dji_data["gimbal_pitch_degrees"] = float(pitch_match.group(1))
                if yaw_match:
                    dji_data["gimbal_yaw_degrees"] = float(yaw_match.group(1))
                if alt_match:
                    dji_data["flight_altitude_meters"] = float(alt_match.group(1))
                if model_match:
                    dji_data["drone_model"] = model_match.group(1)

        except Exception as ex:
            logger.warning(f"Erro ao extrair XMP da DJI em {file_path.name}: {ex}")

        return dji_data
