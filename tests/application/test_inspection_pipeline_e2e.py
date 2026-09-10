"""
Testes de Integração End-to-End para o InspectionPipelineService (ETAPA 18).
Simula o fluxo industrial autônomo completo:
Pasta DJI -> Importação -> Radiometria -> Análise Térmica -> YOLO -> Validação IEC ->
Classificação -> Persistência Científica -> Dashboard -> Mapa Folium -> Relatório PDF.
"""

import pytest
from pathlib import Path
from datetime import datetime
import uuid
import numpy as np
from PIL import Image

from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories.sqlite_client_repository import SqliteClientRepository
from src.infrastructure.database.repositories.sqlite_project_repository import SqliteProjectRepository
from src.infrastructure.database.repositories.sqlite_inspection_repository import SqliteInspectionRepository
from src.infrastructure.database.repositories.sqlite_thermal_image_repository import SqliteThermalImageRepository
from src.infrastructure.database.repositories.sqlite_thermal_anomaly_repository import SqliteThermalAnomalyRepository
from src.infrastructure.database.repositories.sqlite_detection_repository import SqliteDetectionRepository
from src.infrastructure.database.repositories.sqlite_panel_repository import SqlitePanelRepository
from src.infrastructure.database.repositories.sqlite_report_repository import SqliteReportRepository

from src.domain.entities.client import Client
from src.domain.entities.project import Project
from src.domain.enums.inspection_status import InspectionStatus

from src.application.services.image_import_service import ImageImportService
from src.application.services.detection_persistence_service import DetectionPersistenceService
from src.application.services.dashboard_service import DashboardService
from src.application.services.georeferencing_service import GeoReferencingService
from src.application.services.report_service import ReportService
from src.application.services.inspection_pipeline_service import InspectionPipelineService
from src.application.dtos.pipeline_dtos import InspectionPipelineRequest

from src.infrastructure.gis.panel_mapper import PanelMapper
from src.infrastructure.thermal.radiometry_engine import RadiometryEngine


@pytest.fixture
def in_memory_db():
    db = DatabaseManager(db_path=":memory:")
    db.initialize_schema()
    return db


@pytest.fixture
def setup_environment(in_memory_db, tmp_path):
    client_repo = SqliteClientRepository(in_memory_db)
    project_repo = SqliteProjectRepository(in_memory_db)

    # 1. Cria Cliente e Projeto
    client = Client(name="Solar Enterprise S.A.", email="engenharia@solarenterprise.com")
    client_repo.save(client)

    project = Project(
        name="Complexo Solar São Francisco",
        client_name=client.name,
        location_name="Petrolina - PE",
        capacity_kwp=2500.0,
        client_id=client.id,
    )
    project_repo.save(project)

    # 2. Cria pasta de voo com imagens térmicas sintéticas (640x512)
    flight_folder = tmp_path / "DJI_FLIGHT_2026_09_10"
    flight_folder.mkdir(parents=True, exist_ok=True)

    for i in range(1, 4):
        img_array = np.zeros((512, 640, 3), dtype=np.uint8)
        # Desenha região clara representando módulo aquecido
        img_array[100:400, 100:540] = [180, 120, 60]
        # Ponto quente representando hotspot
        img_array[200:250, 250:300] = [255, 255, 200]

        img = Image.fromarray(img_array)
        img_path = flight_folder / f"DJI_{i:04d}_T.JPG"
        img.save(img_path, format="JPEG")

    return project, flight_folder


class TestInspectionPipelineServiceE2E:
    """Testes End-to-End da orquestração autônoma de vistorias."""

    def test_full_pipeline_execution_end_to_end(self, in_memory_db, setup_environment, tmp_path):
        project, flight_folder = setup_environment

        # Repositórios
        inspection_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)
        project_repo = SqliteProjectRepository(in_memory_db)
        client_repo = SqliteClientRepository(in_memory_db)
        anomaly_repo = SqliteThermalAnomalyRepository(in_memory_db)
        detection_repo = SqliteDetectionRepository(in_memory_db)
        panel_repo = SqlitePanelRepository(in_memory_db)
        report_repo = SqliteReportRepository(in_memory_db)

        # Serviços
        import_service = ImageImportService(
            inspection_repository=inspection_repo,
            thermal_image_repository=img_repo,
        )
        persistence_service = DetectionPersistenceService(
            detection_repo=detection_repo,
            image_repo=img_repo,
            anomaly_repo=anomaly_repo,
        )
        panel_mapper = PanelMapper(panel_repo=panel_repo)
        dashboard_service = DashboardService(
            project_repository=project_repo,
            inspection_repository=inspection_repo,
            thermal_image_repository=img_repo,
            thermal_anomaly_repository=anomaly_repo,
        )
        georeferencing_service = GeoReferencingService(
            project_repository=project_repo,
            inspection_repository=inspection_repo,
            thermal_image_repository=img_repo,
            thermal_anomaly_repository=anomaly_repo,
        )
        report_service = ReportService(
            project_repository=project_repo,
            client_repository=client_repo,
            inspection_repository=inspection_repo,
            thermal_image_repository=img_repo,
            thermal_anomaly_repository=anomaly_repo,
            report_repository=report_repo,
        )

        pipeline_service = InspectionPipelineService(
            inspection_repository=inspection_repo,
            image_repository=img_repo,
            project_repository=project_repo,
            import_service=import_service,
            detection_persistence_service=persistence_service,
            panel_mapper=panel_mapper,
            dashboard_service=dashboard_service,
            georeferencing_service=georeferencing_service,
            report_service=report_service,
        )

        request = InspectionPipelineRequest(
            flight_folder=flight_folder,
            project_id=project.id,
            inspection_title="Inspeção Automatizada Completa - E2E",
            inspector_name="Eng. Termografista Solar",
            ambient_temp_celsius=26.0,
            emissivity=0.93,
            generate_map=True,
            generate_report=True,
        )

        # 1. Executa o pipeline
        result = pipeline_service.run_pipeline(request)
        assert result.is_success is True

        val = result.value
        assert val.status == "completed"
        assert val.total_images_processed == 3
        assert val.total_anomalies_detected >= 3
        assert val.duration_seconds > 0

        # 2. Valida persistência da inspeção no SQLite
        saved_insp = inspection_repo.get_by_id(val.inspection_id)
        assert saved_insp is not None
        assert saved_insp.status == InspectionStatus.COMPLETED

        # 3. Valida persistência de detecções e análises térmicas
        detections = detection_repo.get_detections_by_inspection_id(val.inspection_id)
        assert len(detections) >= 3

        # 4. Valida persistência de painéis físicos segmentados
        images = img_repo.list_by_inspection(val.inspection_id)
        for img in images:
            assert img.is_analyzed is True
            panels = panel_repo.get_panels_by_image_id(img.id)
            assert len(panels) == 8  # Grade 2x4

        # 5. Valida geração de Mapa Folium no disco
        assert val.map_file_path is not None
        assert Path(val.map_file_path).exists()
        assert Path(val.map_file_path).stat().st_size > 100

        # 6. Valida geração de Relatório PDF no disco
        assert val.report_file_path is not None
        assert Path(val.report_file_path).exists()
        assert Path(val.report_file_path).stat().st_size > 1000

    def test_pipeline_nonexistent_folder_fails_gracefully(self, in_memory_db, setup_environment, tmp_path):
        project, _ = setup_environment
        inspection_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)
        project_repo = SqliteProjectRepository(in_memory_db)

        import_service = ImageImportService(inspection_repo, img_repo)
        persistence_service = DetectionPersistenceService(
            detection_repo=SqliteDetectionRepository(in_memory_db),
            image_repo=img_repo,
        )

        service = InspectionPipelineService(
            inspection_repository=inspection_repo,
            image_repository=img_repo,
            project_repository=project_repo,
            import_service=import_service,
            detection_persistence_service=persistence_service,
        )

        req = InspectionPipelineRequest(
            flight_folder=tmp_path / "PASTA_INEXISTENTE_XYZ",
            project_id=project.id,
        )
        res = service.run_pipeline(req)
        assert res.is_failure is True
        assert "não existe" in res.error

    def test_pipeline_invalid_project_fails_gracefully(self, in_memory_db, setup_environment):
        _, flight_folder = setup_environment
        inspection_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)
        project_repo = SqliteProjectRepository(in_memory_db)

        import_service = ImageImportService(inspection_repo, img_repo)
        persistence_service = DetectionPersistenceService(
            detection_repo=SqliteDetectionRepository(in_memory_db),
            image_repo=img_repo,
        )

        service = InspectionPipelineService(
            inspection_repository=inspection_repo,
            image_repository=img_repo,
            project_repository=project_repo,
            import_service=import_service,
            detection_persistence_service=persistence_service,
        )

        req = InspectionPipelineRequest(
            flight_folder=flight_folder,
            project_id="PROJETO_NAO_EXISTE_123",
        )
        res = service.run_pipeline(req)
        assert res.is_failure is True
        assert "Projeto/Usina não encontrada" in res.error
