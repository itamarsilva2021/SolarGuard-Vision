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

    def test_import_rejects_oversized_file(self, in_memory_db, sample_test_files, tmp_path, monkeypatch):
        """Valida que arquivo excedendo MAX_FILE_SIZE_MB é rejeitado com mensagem clara."""
        proj_repo = SqliteProjectRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)

        project = proj_repo.save(Project(name="UFV MaxSize", client_name="C", location_name="L", capacity_kwp=100.0))
        inspection = insp_repo.save(Inspection(project_id=project.id, title="Insp MaxSize", inspector_name="Insp"))

        service = ImageImportService(inspection_repository=insp_repo, thermal_image_repository=img_repo)

        # Ajusta o limite para um valor estritamente menor que o arquivo existente
        actual_size_bytes = sample_test_files[0].stat().st_size
        monkeypatch.setattr(service, "MAX_FILE_SIZE_MB", (actual_size_bytes / 2) / (1024 * 1024))

        request = ImportBatchRequest(
            inspection_id=inspection.id,
            file_paths=[sample_test_files[0]],  # JPG válido, mas cujo tamanho excede o limite configurado
            generate_previews=False,
        )

        res = service.import_images(request)
        assert res.is_success is True
        batch = res.value
        assert batch.successful_count == 0
        assert batch.failed_count == 1
        assert any("excede o tamanho máximo permitido" in err for err in batch.errors)

    def test_import_rejects_non_image_content_with_image_extension(self, in_memory_db, tmp_path):
        """Valida que arquivo com extensão .jpg mas conteúdo texto/não-imagem é rejeitado por magic bytes."""
        proj_repo = SqliteProjectRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)

        project = proj_repo.save(Project(name="UFV Fake", client_name="C", location_name="L", capacity_kwp=100.0))
        inspection = insp_repo.save(Inspection(project_id=project.id, title="Insp Fake", inspector_name="Insp"))

        fake_file = tmp_path / "fake_image.jpg"
        fake_file.write_text("ISTO_NAO_E_UMA_IMAGEM_E_TEXTO_PURO")

        service = ImageImportService(inspection_repository=insp_repo, thermal_image_repository=img_repo)
        request = ImportBatchRequest(
            inspection_id=inspection.id,
            file_paths=[fake_file],
            generate_previews=False,
        )

        res = service.import_images(request)
        assert res.is_success is True
        batch = res.value
        assert batch.successful_count == 0
        assert batch.failed_count == 1
        assert any("Assinatura (magic bytes) inválida" in err or "não é uma imagem válida" in err for err in batch.errors)

    def test_import_rejects_image_exceeding_max_dimensions(self, in_memory_db, tmp_path, monkeypatch):
        """Valida que imagem com largura ou altura superior a MAX_IMAGE_DIMENSION é rejeitada."""
        proj_repo = SqliteProjectRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)

        project = proj_repo.save(Project(name="UFV Dim", client_name="C", location_name="L", capacity_kwp=100.0))
        inspection = insp_repo.save(Inspection(project_id=project.id, title="Insp Dim", inspector_name="Insp"))

        service = ImageImportService(inspection_repository=insp_repo, thermal_image_repository=img_repo)

        # Ajusta limite para 100 pixels para testar sem precisar alocar imagem gigante em memória
        monkeypatch.setattr(service, "MAX_IMAGE_DIMENSION", 100)

        # sample_test_files[0] tem dimensões 120x160 (ambas > 100)
        from PIL import Image as PILImage
        img_oversized = tmp_path / "oversized.png"
        PILImage.new("RGB", (150, 80)).save(img_oversized)

        request = ImportBatchRequest(
            inspection_id=inspection.id,
            file_paths=[img_oversized],
            generate_previews=False,
        )

        res = service.import_images(request)
        assert res.is_success is True
        batch = res.value
        assert batch.successful_count == 0
        assert batch.failed_count == 1
        assert any("excedem o limite máximo permitido de 100 pixels" in err for err in batch.errors)

    def test_import_batch_with_valid_and_invalid_files_does_not_halt(self, in_memory_db, sample_test_files, tmp_path, monkeypatch):
        """
        Valida que imagens válidas continuam sendo importadas com sucesso mesmo se
        o lote contiver arquivos acima do limite de tamanho, fake jpg e dimensões excessivas.
        """
        proj_repo = SqliteProjectRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)

        project = proj_repo.save(Project(name="UFV MixedSec", client_name="C", location_name="L", capacity_kwp=100.0))
        inspection = insp_repo.save(Inspection(project_id=project.id, title="Insp MixedSec", inspector_name="Insp"))

        service = ImageImportService(inspection_repository=insp_repo, thermal_image_repository=img_repo)

        # 1. Arquivo não-imagem com extensão .jpg
        fake_jpg = tmp_path / "corrupto.jpg"
        fake_jpg.write_bytes(b"dados_binarios_aleatorios_sem_magic_bytes")

        # 2. Imagem com dimensões reais acima do limite padrão (ex.: 12001 x 10)
        from PIL import Image as PILImage
        oversized_img = tmp_path / "gigante.png"
        PILImage.new("RGB", (12001, 10)).save(oversized_img)

        # Lote misto: 2 imagens normais válidas + 2 imagens inválidas por segurança
        mixed_batch = [
            sample_test_files[0],  # Válido JPG
            fake_jpg,              # Inválido (conteúdo falso)
            sample_test_files[1],  # Válido PNG
            oversized_img,         # Inválido (dimensões > 12000)
        ]

        request = ImportBatchRequest(
            inspection_id=inspection.id,
            file_paths=mixed_batch,
            generate_previews=False,
        )

        res = service.import_images(request)
        assert res.is_success is True
        batch = res.value
        assert batch.total_files == 4
        assert batch.successful_count == 2
        assert batch.failed_count == 2
        assert len(batch.errors) == 2

        # As 2 imagens válidas foram persistidas no repositório
        stored = img_repo.list_by_inspection(inspection.id)
        assert len(stored) == 2

    def test_import_valid_image_with_exif_and_gps_metadata_persisted_correctly(self, in_memory_db, tmp_path):
        """
        Garante que após a validação estrutural com img.verify(),
        a extração de EXIF e metadados GPS é realizada com sucesso a partir de uma imagem real,
        provando que os descritores e dados do arquivo não são corrompidos nem invalidados.
        """
        import piexif
        from PIL import Image as PILImage
        from datetime import datetime

        proj_repo = SqliteProjectRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)

        project = proj_repo.save(Project(name="UFV ExifCheck", client_name="Cliente Exif", location_name="Nordeste", capacity_kwp=500.0))
        inspection = insp_repo.save(Inspection(project_id=project.id, title="Voo Verificacao EXIF", inspector_name="Inspetor Drone"))

        # Cria uma imagem JPG real com tags EXIF e GPS embutidas via piexif
        exif_jpg_path = tmp_path / "DJI_EXIF_TEST.JPG"
        img = PILImage.fromarray(np.zeros((120, 160, 3), dtype=np.uint8))

        exif_dict = {
            "0th": {},
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: b"2026:09:13 10:30:00",
            },
            "GPS": {
                piexif.GPSIFD.GPSLatitude: ((12, 1), (58, 1), (1704, 100)),
                piexif.GPSIFD.GPSLatitudeRef: "S",
                piexif.GPSIFD.GPSLongitude: ((38, 1), (30, 1), (504, 100)),
                piexif.GPSIFD.GPSLongitudeRef: "W",
            },
            "1st": {},
            "thumbnail": None,
        }
        exif_bytes = piexif.dump(exif_dict)
        img.save(exif_jpg_path, exif=exif_bytes)

        service = ImageImportService(inspection_repository=insp_repo, thermal_image_repository=img_repo)

        request = ImportBatchRequest(
            inspection_id=inspection.id,
            file_paths=[exif_jpg_path],
            generate_previews=False,
        )

        res = service.import_images(request)
        assert res.is_success is True
        batch = res.value
        assert batch.successful_count == 1
        assert batch.failed_count == 0
        assert len(batch.errors) == 0

        # Validação do DTO retornado
        imported_dto = batch.imported_images[0]
        assert imported_dto.filename == "DJI_EXIF_TEST.JPG"
        assert imported_dto.width == 160
        assert imported_dto.height == 120
        assert imported_dto.has_gps is True
        assert pytest.approx(imported_dto.latitude, abs=0.0001) == -12.9714
        assert pytest.approx(imported_dto.longitude, abs=0.0001) == -38.5014

        # Validação da Entidade no Repositório SQLite
        stored_images = img_repo.list_by_inspection(inspection.id)
        assert len(stored_images) == 1
        entity = stored_images[0]
        assert entity.captured_at == datetime(2026, 9, 13, 10, 30)
        assert entity.coordinate is not None
        assert pytest.approx(entity.coordinate.latitude, abs=0.0001) == -12.9714
        assert pytest.approx(entity.coordinate.longitude, abs=0.0001) == -38.5014


