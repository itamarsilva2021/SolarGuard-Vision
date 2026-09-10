"""
Serviço de Aplicação para Importação em Lote de Imagens Aéreas e Termográficas.
Suporta JPG, PNG, TIFF e R-JPEG do DJI Matrice 4T com geração de pré-visualizações.
"""

from pathlib import Path
from typing import Optional, Set
from PIL import Image

from src.core.result import Result, Success, Failure
from src.core.logger import get_logger
from src.domain.interfaces.repositories import IInspectionRepository, IThermalImageRepository
from src.domain.interfaces.thermal_parser import IThermalParser
from src.domain.entities.thermal_image import ThermalImage
from src.infrastructure.imaging.dji_thermal_parser import DjiThermalParser
from src.infrastructure.imaging.metadata_extractor import MetadataExtractor
from src.infrastructure.imaging.preview_generator import PreviewGenerator
from src.application.dtos.import_dtos import (
    ImportBatchRequest,
    ImportBatchResult,
    ImportedImageDTO,
)

logger = get_logger("ImageImportService")


class ImageImportService:
    """
    Orquestra a validação, extração radiométrica/EXIF, renderização de pré-visualização
    e persistência relacional de imagens importadas.
    """

    ALLOWED_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

    def __init__(
        self,
        inspection_repository: IInspectionRepository,
        thermal_image_repository: IThermalImageRepository,
        thermal_parser: Optional[IThermalParser] = None,
        preview_generator: Optional[PreviewGenerator] = None,
    ) -> None:
        self.inspection_repo = inspection_repository
        self.image_repo = thermal_image_repository
        self.thermal_parser = thermal_parser or DjiThermalParser()
        self.preview_generator = preview_generator or PreviewGenerator()

    def import_images(self, request: ImportBatchRequest) -> Result[ImportBatchResult, str]:
        """
        Executa a importação em lote com suporte a seleção múltipla de arquivos.
        
        :param request: Objeto com id da inspeção, lista de arquivos e configurações de prévia.
        :return: Result contendo ImportBatchResult ou mensagem de falha.
        """
        # 1. Validar existência da inspeção de destino
        inspection = self.inspection_repo.get_by_id(request.inspection_id)
        if not inspection:
            return Failure(f"Inspeção não encontrada com ID: {request.inspection_id}")

        if not request.file_paths:
            return Failure("Nenhum arquivo fornecido para importação.")

        total_files = len(request.file_paths)
        imported_dtos: list[ImportedImageDTO] = []
        errors: list[str] = []

        logger.info(f"Iniciando importação de {total_files} imagens para a inspeção '{inspection.title}'.")

        # 2. Processar cada arquivo individualmente (falha em um não interrompe os outros)
        for raw_path in request.file_paths:
            file_path = Path(raw_path)

            if not file_path.exists() or not file_path.is_file():
                errors.append(f"Arquivo inacessível ou inexistente: {file_path}")
                continue

            ext = file_path.suffix.lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                errors.append(
                    f"Extensão não suportada '{ext}' em {file_path.name}. Permitidos: JPG, PNG, TIFF."
                )
                continue

            try:
                # A. Extração de Metadados EXIF e XMP DJI
                exif_data = MetadataExtractor.extract_exif(file_path)
                xmp_data = MetadataExtractor.extract_dji_xmp(file_path)

                width = exif_data.get("width") or 640
                height = exif_data.get("height") or 512
                coord = exif_data.get("coordinate")
                captured_at = exif_data.get("captured_at")

                flight_alt = xmp_data.get("flight_altitude_meters")
                pitch = xmp_data.get("gimbal_pitch_degrees")
                yaw = xmp_data.get("gimbal_yaw_degrees")

                # B. Extração de Metadados Térmicos Radiométricos
                thermal_meta = None
                try:
                    thermal_meta = self.thermal_parser.extract_metadata(file_path)
                    if width == 640 and thermal_meta.sensor_width > 0:
                        width = thermal_meta.sensor_width
                        height = thermal_meta.sensor_height
                except Exception as th_err:
                    logger.debug(f"Metadados térmicos não disponíveis para {file_path.name}: {th_err}")

                # C. Geração de Pré-visualização (Thumbnail com Paleta)
                preview_path_str = None
                if request.generate_previews:
                    try:
                        prev_path = self.preview_generator.generate_preview(
                            file_path=file_path,
                            palette=request.palette,
                        )
                        preview_path_str = str(prev_path)
                    except Exception as prev_err:
                        logger.warning(f"Erro ao gerar pré-visualização de {file_path.name}: {prev_err}")

                # D. Criação da Entidade de Domínio
                image_entity = ThermalImage(
                    inspection_id=inspection.id,
                    file_path=str(file_path.resolve()),
                    filename=file_path.name,
                    width=width,
                    height=height,
                    coordinate=coord,
                    flight_altitude_meters=flight_alt,
                    gimbal_pitch_degrees=pitch,
                    gimbal_yaw_degrees=yaw,
                    thermal_meta=thermal_meta,
                    is_analyzed=False,
                    captured_at=captured_at,
                )

                # E. Persistência Relacional no Banco SQLite
                saved_entity = self.image_repo.save(image_entity)

                # F. Construção do DTO de Retorno
                dto = ImportedImageDTO(
                    id=saved_entity.id,
                    filename=saved_entity.filename,
                    file_path=saved_entity.file_path,
                    preview_path=preview_path_str,
                    width=saved_entity.width,
                    height=saved_entity.height,
                    has_gps=saved_entity.coordinate is not None,
                    latitude=saved_entity.coordinate.latitude if saved_entity.coordinate else None,
                    longitude=saved_entity.coordinate.longitude if saved_entity.coordinate else None,
                    flight_altitude_meters=saved_entity.flight_altitude_meters,
                    gimbal_pitch_degrees=saved_entity.gimbal_pitch_degrees,
                    min_temp_celsius=thermal_meta.min_temp_celsius if thermal_meta else None,
                    max_temp_celsius=thermal_meta.max_temp_celsius if thermal_meta else None,
                    avg_temp_celsius=thermal_meta.avg_temp_celsius if thermal_meta else None,
                )
                imported_dtos.append(dto)

            except Exception as file_err:
                msg = f"Falha ao processar {file_path.name}: {str(file_err)}"
                logger.error(msg)
                errors.append(msg)

        batch_result = ImportBatchResult(
            inspection_id=inspection.id,
            total_files=total_files,
            successful_count=len(imported_dtos),
            failed_count=len(errors),
            imported_images=imported_dtos,
            errors=errors,
        )

        logger.info(
            f"Importação finalizada: {batch_result.successful_count} sucessos, "
            f"{batch_result.failed_count} falhas."
        )
        return Success(batch_result)
