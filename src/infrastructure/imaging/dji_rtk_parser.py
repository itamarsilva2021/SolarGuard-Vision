"""
Parser e analisador de posicionamento e acurácia RTK para drones DJI Enterprise.
Avalia a fixação da solução e calcula métricas de incerteza para inspeção fotovoltaica.
"""

from typing import Dict, Any, Optional
from src.application.dtos.dji_metadata_dto import RtkStatus, RtkTelemetryDTO
from src.core.logger import get_logger

logger = get_logger("DjiRtkParser")


class DjiRtkParser:
    """
    Interpreta os metadados RTK do DJI Matrice 4T e fornece métricas de qualidade
    cartográfica para correlação com coordenadas de painéis solares.
    """

    # Limiares de precisão em metros para inspeções solares IEC TS 62446-3
    IEC_RECOMMENDED_MAX_HORIZ_ACCURACY_M = 0.15  # 15 cm para identificação unívoca de célula/string

    @classmethod
    def parse_rtk_data(cls, xmp_data: Dict[str, Any]) -> RtkTelemetryDTO:
        """
        Extrai e formata os dados RTK a partir de um dicionário de metadados XMP.
        
        :param xmp_data: Dicionário retornado pelo DjiXmpParser.
        :return: RtkTelemetryDTO preenchido.
        """
        raw_flag = xmp_data.get("RtkFlag")
        flag_val = int(raw_flag) if raw_flag is not None and isinstance(raw_flag, (int, float)) else 0

        # Mapeamento do status RTK oficial da DJI
        if flag_val == 50:
            status = RtkStatus.FIXED
        elif flag_val == 16 or (1 <= flag_val < 50):
            status = RtkStatus.FLOAT
        else:
            status = RtkStatus.NONE

        std_lat = xmp_data.get("RtkStdLat")
        std_lon = xmp_data.get("RtkStdLon")
        std_hgt = xmp_data.get("RtkStdHgt")
        diff_age = xmp_data.get("RtkDiffAge")

        dto = RtkTelemetryDTO(
            status=status,
            flag=flag_val,
            std_latitude_meters=float(std_lat) if std_lat is not None else None,
            std_longitude_meters=float(std_lon) if std_lon is not None else None,
            std_altitude_meters=float(std_hgt) if std_hgt is not None else None,
            diff_age_seconds=float(diff_age) if diff_age is not None else None,
        )

        return dto

    @classmethod
    def is_suitable_for_photogrammetry(cls, rtk_dto: RtkTelemetryDTO) -> tuple[bool, str]:
        """
        Verifica se a precisão RTK é suficiente para ortorretificação e georreferenciamento
        de módulos fotovoltaicos sem necessidade de pontos de controle terrestres (GCPs).
        
        :param rtk_dto: DTO de telemetria RTK.
        :return: Tupla (is_suitable, justificativa).
        """
        if rtk_dto.status == RtkStatus.FIXED:
            h_acc = rtk_dto.horizontal_accuracy_meters
            if h_acc is not None and h_acc <= cls.IEC_RECOMMENDED_MAX_HORIZ_ACCURACY_M:
                return True, f"RTK Fixed com precisão horizontal excelente ({h_acc * 100:.1f} cm)."
            return True, "RTK Fixed convergido com sucesso."

        if rtk_dto.status == RtkStatus.FLOAT:
            return False, "RTK Float (solução ambígua, acurácia submétrica insuficiente para nível de módulo)."

        return False, "Sem correção RTK ativa (GPS comum autônomo com incerteza típica de 1 a 3 metros)."
