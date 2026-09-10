"""
Validadores de integridade estrutural de arquivos, identificação de sensor e
consistência física de telemetria para o DJI Matrice 4T.
"""

from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import os
from src.core.logger import get_logger

logger = get_logger("DjiValidators")


class DjiImageValidator:
    """
    Executa testes de integridade e plausibilidade física em imagens e metadados
    capturados por drones DJI Matrice 4T.
    """

    JPEG_SOI = b"\xff\xd8"
    JPEG_EOI = b"\xff\xd9"
    TIFF_LE_HEADER = b"II*\x00"
    TIFF_BE_HEADER = b"MM\x00*"

    @classmethod
    def validate_file_integrity(cls, file_path: str | Path) -> Tuple[bool, List[str]]:
        """
        Verifica a integridade física do arquivo no disco (existência, tamanho e integridade de container).
        
        :param file_path: Caminho do arquivo a verificar.
        :return: (is_valid, lista de mensagens de erro).
        """
        path = Path(file_path)
        errors: List[str] = []

        if not path.exists():
            return False, [f"Arquivo não existe: {path}"]

        if not path.is_file():
            return False, [f"O caminho especificado não é um arquivo: {path}"]

        file_size = os.path.getsize(path)
        if file_size < 1024:
            return False, [f"Arquivo corrompido ou vazio (tamanho: {file_size} bytes)."]

        ext = path.suffix.lower()

        # Validação de cabeçalho e terminador JPEG
        if ext in [".jpg", ".jpeg"]:
            try:
                with open(path, "rb") as f:
                    header = f.read(2)
                    if header != cls.JPEG_SOI:
                        errors.append(f"Cabeçalho SOI JPEG inválido ({header.hex()}). Arquivo não é um JPEG válido.")
                    
                    # Checagem de terminador EOI nos últimos 128 bytes
                    f.seek(max(0, file_size - 128))
                    tail = f.read()
                    if cls.JPEG_EOI not in tail:
                        errors.append("Terminador EOI (0xFFD9) ausente. Imagem JPEG corrompida ou truncada.")
            except Exception as ex:
                errors.append(f"Erro de leitura de arquivo binário: {ex}")

        # Validação de cabeçalho TIFF
        elif ext in [".tif", ".tiff"]:
            try:
                with open(path, "rb") as f:
                    header = f.read(4)
                    if header not in [cls.TIFF_LE_HEADER, cls.TIFF_BE_HEADER]:
                        errors.append(f"Cabeçalho TIFF inválido ({header.hex()}).")
            except Exception as ex:
                errors.append(f"Erro ao ler cabeçalho TIFF: {ex}")

        return (len(errors) == 0, errors)

    @classmethod
    def validate_thermal_channel(cls, file_path: str | Path, xmp_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[str]]:
        """
        Verifica se o arquivo corresponde ao canal térmico (LWIR) do DJI Matrice 4T,
        evitando o processamento acidental de imagens dos sensores Wide ou Zoom.
        
        :param file_path: Caminho do arquivo.
        :param xmp_data: Dicionário XMP (opcional).
        :return: (is_thermal, lista de alertas).
        """
        path = Path(file_path)
        stem = path.stem.upper()
        warnings: List[str] = []

        # Convenção de nomenclatura de arquivo DJI:
        # _T = Thermal, _W = Wide, _Z = Zoom, _V = Visual
        if stem.endswith("_W"):
            warnings.append(
                f"O arquivo {path.name} parece ser do canal Grande Angular (Wide - RGB), não do sensor térmico."
            )
            return False, warnings
        elif stem.endswith("_Z"):
            warnings.append(
                f"O arquivo {path.name} parece ser do canal Teleobjetiva (Zoom - RGB), não do sensor térmico."
            )
            return False, warnings

        # Validação via metadados XMP
        if xmp_data:
            cam_type = str(xmp_data.get("CameraType", "")).lower()
            if cam_type and cam_type not in ["thermal", "ir", "infrared"]:
                warnings.append(
                    f"Tipo de câmera declarado no XMP é '{xmp_data.get('CameraType')}', esperado 'Thermal'."
                )
                return False, warnings

        return True, warnings

    @classmethod
    def validate_physical_telemetry(
        cls,
        latitude: Optional[float],
        longitude: Optional[float],
        altitude_rel: Optional[float],
        emissivity: Optional[float] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Valida se os valores de telemetria e parâmetros radiométricos obedecem a limites físicos.
        """
        warnings: List[str] = []

        if latitude is not None and not (-90.0 <= latitude <= 90.0):
            warnings.append(f"Latitude fora da faixa física válida: {latitude}")

        if longitude is not None and not (-180.0 <= longitude <= 180.0):
            warnings.append(f"Longitude fora da faixa física válida: {longitude}")

        if altitude_rel is not None:
            if altitude_rel < 0.5:
                warnings.append(f"Altitude relativa muito baixa para voo de inspeção: {altitude_rel} m.")
            elif altitude_rel > 500.0:
                warnings.append(f"Altitude relativa excepcionalmente alta ({altitude_rel} m), risco de GSD degradado.")

        if emissivity is not None:
            if not (0.10 <= emissivity <= 1.00):
                warnings.append(f"Emissividade configurada fora do intervalo plausível (0.1 a 1.0): {emissivity}")

        return (len(warnings) == 0, warnings)
