"""
Objetos de Transferência de Dados (DTOs) para o fluxo de importação de imagens.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from src.domain.enums.palette_type import PaletteType


@dataclass
class ImportedImageDTO:
    """Informações resumidas de uma imagem importada com sucesso."""
    id: str
    filename: str
    file_path: str
    preview_path: Optional[str] = None
    width: int = 640
    height: int = 512
    has_gps: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    flight_altitude_meters: Optional[float] = None
    gimbal_pitch_degrees: Optional[float] = None
    min_temp_celsius: Optional[float] = None
    max_temp_celsius: Optional[float] = None
    avg_temp_celsius: Optional[float] = None


@dataclass
class ImportBatchRequest:
    """Requisição de importação de lote de arquivos (seleção múltipla)."""
    inspection_id: str
    file_paths: list[str | Path]
    generate_previews: bool = True
    palette: PaletteType = PaletteType.IRONBOW


@dataclass
class ImportBatchResult:
    """Resultado detalhado do processamento da importação em lote."""
    inspection_id: str
    total_files: int
    successful_count: int
    failed_count: int
    imported_images: list[ImportedImageDTO] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_fully_successful(self) -> bool:
        return self.failed_count == 0 and self.successful_count > 0
