"""
Testes de integração para o serviço de aplicação ImageImportService.
Valida o fluxo completo de seleção múltipla, geração de prévias e armazenamento no SQLite.
"""

import pytest
import numpy as np
import cv2
from pathlib import Path

from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories import (
    SqliteProjectRepository,
    SqliteInspectionRepository,
    SqliteThermalImageRepository,
)
from src.domain.entities import Project, Inspection
from src.domain.enums.palette_type import PaletteType
from src.application.services.image_import_service import ImageImportService
from src.application.dtos import ImportBatchRequest
from src.infrastructure.imaging.preview_generator import PreviewGenerator


@pytest.fixture
def in_memory_db() -> DatabaseManager:
    """Banco em memória para testes."""
    db = DatabaseManager(":memory:")
    db.initialize_schema()
    yield db
    db.close()


@pytest.fixture
def sample_test_files(tmp_path) -> list[Path]:
    """Cria arquivos de teste em disco nos formatos JPG, PNG e TIFF."""
    img_dir = tmp_path / "drone_flight_01"
    img_dir.mkdir(parents=True, exist_ok=True)

    # 1. Arquivo JPG
    jpg_file = img_dir / "DJI_0001_T.JPG"
    jpg_data = np.full((120, 160, 3), 128, dtype=np.uint8)
    cv2.imwrite(str(jpg_file), jpg_data)

    # 2. Arquivo PNG
    png_file = img_dir / "DJI_0002_W.PNG"
    png_data = np.full((100, 150, 3), 200, dtype=np.uint8)
    cv2.imwrite(str(png_file), png_data)

    # 3. Arquivo TIFF Radiométrico 16-bit
    tiff_file = img_dir / "DJI_0003_RAW.TIFF"
    tiff_data = np.full((100, 100), 30500, dtype=np.uint16)  # ~31.85 °C
    cv2.imwrite(str(tiff_file), tiff_data)

    return [jpg_file, png_file, tiff_file]


class TestImageImportService:
    def test_successful_multi_selection_import(self, in_memory_db, sample_test_files, tmp_path):
        proj_repo = SqliteProjectRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)

        # Setup Projeto e Inspeção no banco
        project = proj_repo.save(
            Project(name="UFV Alvorada", client_name="Cliente A", location_name="Cidade A", capacity_kwp=2000.0)
        )
        inspection = insp_repo.save(
            Inspection(project_id=project.id, title="Voo Matrice 4T Lote 1", inspector_name="Inspetor Drone")
        )

        preview_gen = PreviewGenerator(cache_dir=tmp_path / "previews")
        service = ImageImportService(
            inspection_repository=insp_repo,
            thermal_image_repository=img_repo,
            preview_generator=preview_gen,
        )

        # Executa importação de múltiplos arquivos (JPG, PNG, TIFF)
        request = ImportBatchRequest(
            inspection_id=inspection.id,
            file_paths=sample_test_files,
            generate_previews=True,
            palette=PaletteType.IRONBOW,
        )

        result = service.import_images(request)

        # Asserts de Sucesso
        assert result.is_success is True
        batch_res = result.value
        assert batch_res.total_files == 3
        assert batch_res.successful_count == 3
        assert batch_res.failed_count == 0
        assert batch_res.is_fully_successful is True

        # Validação do Armazenamento no Banco SQLite
        stored_images = img_repo.list_by_inspection(inspection.id)
        assert len(stored_images) == 3

        filenames = [img.filename for img in stored_images]
        assert "DJI_0001_T.JPG" in filenames
        assert "DJI_0002_W.PNG" in filenames
        assert "DJI_0003_RAW.TIFF" in filenames

        # Validação das pré-visualizações geradas
        for dto in batch_res.imported_images:
            assert dto.preview_path is not None
            assert Path(dto.preview_path).exists()

    def test_import_with_unsupported_and_missing_files(self, in_memory_db, sample_test_files):
        proj_repo = SqliteProjectRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)

        project = proj_repo.save(
            Project(name="UFV Test", client_name="C", location_name="L", capacity_kwp=100.0)
        )
        inspection = insp_repo.save(
            Inspection(project_id=project.id, title="Insp", inspector_name="Insp")
        )

        service = ImageImportService(
            inspection_repository=insp_repo,
            thermal_image_repository=img_repo,
        )

        # Lista mista: 2 válidos + 1 arquivo inexistente + 1 arquivo de extensão inválida (.pdf)
        txt_invalid = sample_test_files[0].parent / "flight_log.pdf"
        txt_invalid.write_text("dummy")

        non_existent = sample_test_files[0].parent / "missing_file.jpg"

        mixed_paths = [
            sample_test_files[0],  # Válido JPG
            sample_test_files[2],  # Válido TIFF
            txt_invalid,           # Inválido (extensão não suportada)
            non_existent,          # Inválido (não existe)
        ]

        request = ImportBatchRequest(
            inspection_id=inspection.id,
            file_paths=mixed_paths,
            generate_previews=False,
        )

        result = service.import_images(request)
        assert result.is_success is True

        batch_res = result.value
        assert batch_res.total_files == 4
        assert batch_res.successful_count == 2
        assert batch_res.failed_count == 2
        assert len(batch_res.errors) == 2

        # 2 imagens foram salvas com sucesso no banco
        stored = img_repo.list_by_inspection(inspection.id)
        assert len(stored) == 2

    def test_import_fails_if_inspection_does_not_exist(self, in_memory_db, sample_test_files):
        img_repo = SqliteThermalImageRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)

        service = ImageImportService(
            inspection_repository=insp_repo,
            thermal_image_repository=img_repo,
        )

        request = ImportBatchRequest(
            inspection_id="inexistent-id-999",
            file_paths=sample_test_files,
        )

        result = service.import_images(request)
        assert result.is_failure is True
        assert "Inspeção não encontrada" in result.error
