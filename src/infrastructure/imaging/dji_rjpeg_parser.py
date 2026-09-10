"""
Parser de containers R-JPEG (Radiometric JPEG) para câmeras térmicas DJI Enterprise.
Analisa segmentos de aplicação JPEG (APP1, APP3, APP4) e extrai o fluxo térmico bruto.
"""

from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import struct
import numpy as np
from src.core.logger import get_logger

logger = get_logger("DjiRjpegParser")


class DjiRjpegParser:
    """
    Decodifica a estrutura interna de arquivos R-JPEG do DJI Matrice 4T,
    inspecionando marcadores JPEG e extraindo o fluxo radiométrico de 16 bits.
    """

    # Resolução nativa do sensor microbolômetro LWIR do DJI Matrice 4T
    SENSOR_WIDTH = 640
    SENSOR_HEIGHT = 512
    EXPECTED_RAW_BYTES = SENSOR_WIDTH * SENSOR_HEIGHT * 2  # 655.360 bytes (16-bit uint16)

    @classmethod
    def is_rjpeg(cls, file_path: str | Path) -> bool:
        """
        Verifica se o arquivo JPEG possui assinaturas de radiometria DJI nos segmentos APP.
        """
        path = Path(file_path)
        if not path.exists() or path.suffix.lower() not in [".jpg", ".jpeg"]:
            return False

        try:
            with open(path, "rb") as f:
                header = f.read(1024 * 64)  # Primeiros 64 KB cobrem os cabeçalhos APP

            # Assinaturas conhecidas de termografia DJI
            dji_signatures = [
                b"http://www.dji.com/drone-dji/1.0/",
                b"drone-dji:Thermal",
                b"DJI_DIRP",
                b"DJI_THERMAL",
                b"ThermalGainMode",
            ]
            return any(sig in header for sig in dji_signatures)
        except Exception as ex:
            logger.debug(f"Erro ao verificar assinatura R-JPEG de {path.name}: {ex}")
            return False

    @classmethod
    def extract_raw_thermal_stream(cls, file_path: str | Path) -> Optional[np.ndarray]:
        """
        Inspeciona os segmentos binários do JPEG e procura o bloco de digital counts (16 bits).
        
        :param file_path: Caminho para a imagem R-JPEG.
        :return: Array numpy 2D (512, 640) uint16 com os digital counts ou None.
        """
        path = Path(file_path)
        if not path.exists():
            return None

        try:
            with open(path, "rb") as f:
                content = f.read()

            file_len = len(content)
            idx = 2  # Pula o SOI (0xFF, 0xD8)

            # Varredura dos marcadores de segmento JPEG
            while idx < file_len - 4:
                if content[idx] != 0xFF:
                    idx += 1
                    continue

                marker = content[idx + 1]

                # Marcadores de parada ou sem comprimento
                if marker in [0xD8, 0xD9, 0x00]:  # SOI, EOI, preenchimento de byte
                    idx += 2
                    continue

                # Marcadores com comprimento definido de 2 bytes
                seg_len = struct.unpack(">H", content[idx + 2 : idx + 4])[0]
                seg_data_start = idx + 4
                seg_data_end = idx + 2 + seg_len

                if seg_data_end > file_len:
                    break

                # Segmentos APP3 (0xE3) ou APP4 (0xE4) onde a DJI armazena metadados e streams térmicos
                if marker in [0xE3, 0xE4, 0xE1]:
                    seg_data = content[seg_data_start:seg_data_end]

                    # 1. Verifica se o segmento contém o bloco exato de 655.360 bytes ou cabeçalho DIRP
                    if b"DJI_DIRP" in seg_data or b"DJI" in seg_data[:16]:
                        # Busca por payload térmico contíguo de tamanho de sensor
                        raw_offset = cls._find_thermal_payload_offset(content, seg_data_start)
                        if raw_offset:
                            raw_slice = content[raw_offset : raw_offset + cls.EXPECTED_RAW_BYTES]
                            if len(raw_slice) == cls.EXPECTED_RAW_BYTES:
                                arr = np.frombuffer(raw_slice, dtype=np.uint16)
                                return arr.reshape((cls.SENSOR_HEIGHT, cls.SENSOR_WIDTH))

                idx += 2 + seg_len

            # 2. Busca de emergência por bloco contíguo de 655.360 bytes com assinatura DJI
            raw_offset = cls._find_thermal_payload_offset(content, 0)
            if raw_offset:
                raw_slice = content[raw_offset : raw_offset + cls.EXPECTED_RAW_BYTES]
                if len(raw_slice) == cls.EXPECTED_RAW_BYTES:
                    arr = np.frombuffer(raw_slice, dtype=np.uint16)
                    return arr.reshape((cls.SENSOR_HEIGHT, cls.SENSOR_WIDTH))

        except Exception as ex:
            logger.warning(f"Exceção ao extrair fluxo térmico bruto de {path.name}: {ex}")

        return None

    @classmethod
    def _find_thermal_payload_offset(cls, data: bytes, search_start: int) -> Optional[int]:
        """Localiza o offset de início do bloco de bytes de contagens digitais."""
        magic_headers = [b"DJI_DIRP", b"DIRP\x00", b"RAW_THERMAL"]
        for magic in magic_headers:
            pos = data.find(magic, search_start)
            if pos != -1:
                # O payload geralmente inicia imediatamente após o cabeçalho de tamanho fixo
                payload_start = pos + len(magic) + 16  # Offset padrão de metadados DIRP
                if payload_start + cls.EXPECTED_RAW_BYTES <= len(data):
                    return payload_start
        return None
