"""
Testes de integração e unidade para a camada de Banco de Dados SQLite e Repositórios.
Valida o CRUD completo de Clientes, Projetos, Inspeções, Imagens, Falhas e Relatórios.
"""

import pytest
import sqlite3
from datetime import datetime

from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories import (
    SqliteClientRepository,
    SqliteProjectRepository,
    SqliteInspectionRepository,
    SqliteThermalImageRepository,
    SqliteThermalAnomalyRepository,
    SqliteReportRepository,
)
from src.domain.entities import (
    Client,
    Project,
    Inspection,
    ThermalImage,
    ThermalAnomaly,
    Report,
    ReportType,
)
from src.domain.enums import AnomalyType, SeverityLevel, InspectionStatus
from src.domain.value_objects import GeoCoordinate, BoundingBox, DeltaT, ThermalMatrixMeta


@pytest.fixture
def in_memory_db() -> DatabaseManager:
    """Retorna uma instância de DatabaseManager operando em memória SQLite (:memory:)."""
    db = DatabaseManager(":memory:")
    db.initialize_schema()
    yield db
    db.close()


class TestDatabaseInitialization:
    def test_schema_creation_and_pragmas(self, in_memory_db):
        conn = in_memory_db.get_connection()
        cursor = conn.execute("PRAGMA foreign_keys;")
        assert cursor.fetchone()[0] == 1

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        tables = [row["name"] for row in cursor.fetchall()]
        assert "clients" in tables
        assert "projects" in tables
        assert "inspections" in tables
        assert "thermal_images" in tables
        assert "thermal_anomalies" in tables
        assert "reports" in tables


class TestClientRepository:
    def test_client_crud(self, in_memory_db):
        repo = SqliteClientRepository(in_memory_db)

        # 1. Create
        client = Client(
            name="Energia Solar do Sertão Ltda",
            document="12.345.678/0001-90",
            email="contato@sertaosolar.com.br",
            phone="(74) 99999-8888",
            address="Av. Sol Nascente, 100 - Juazeiro, BA",
        )
        saved = repo.save(client)
        assert saved.id == client.id

        # 2. Read by ID
        fetched = repo.get_by_id(client.id)
        assert fetched is not None
        assert fetched.name == "Energia Solar do Sertão Ltda"
        assert fetched.document == "12.345.678/0001-90"
        assert fetched.email == "contato@sertaosolar.com.br"

        # 3. Update
        fetched.phone = "(74) 91111-2222"
        repo.save(fetched)
        updated = repo.get_by_id(client.id)
        assert updated.phone == "(74) 91111-2222"

        # 4. List All
        all_clients = repo.list_all()
        assert len(all_clients) == 1

        # 5. Delete
        assert repo.delete(client.id) is True
        assert repo.get_by_id(client.id) is None
        assert repo.delete(client.id) is False


class TestProjectRepository:
    def test_project_crud_and_client_relation(self, in_memory_db):
        client_repo = SqliteClientRepository(in_memory_db)
        project_repo = SqliteProjectRepository(in_memory_db)

        client = Client(name="Volt Capital")
        client_repo.save(client)

        # 1. Create Project
        coord = GeoCoordinate(latitude=-12.9714, longitude=-38.5014, altitude_meters=15.0)
        project = Project(
            name="UFV Salvador Solar 3MW",
            client_id=client.id,
            client_name=client.name,
            location_name="Salvador - BA",
            capacity_kwp=3000.0,
            coordinate=coord,
            module_manufacturer="Trina Solar",
            module_model="TSM-DE19",
        )
        project_repo.save(project)

        # 2. Read by ID
        fetched = project_repo.get_by_id(project.id)
        assert fetched is not None
        assert fetched.name == "UFV Salvador Solar 3MW"
        assert fetched.client_id == client.id
        assert fetched.coordinate.latitude == -12.9714
        assert fetched.capacity_kwp == 3000.0

        # 3. List by Client
        by_client = project_repo.list_by_client(client.id)
        assert len(by_client) == 1
        assert by_client[0].id == project.id

        # 4. Update
        fetched.capacity_kwp = 3500.0
        project_repo.save(fetched)
        assert project_repo.get_by_id(project.id).capacity_kwp == 3500.0

        # 5. Delete
        assert project_repo.delete(project.id) is True
        assert project_repo.get_by_id(project.id) is None


class TestInspectionRepository:
    def test_inspection_crud(self, in_memory_db):
        project_repo = SqliteProjectRepository(in_memory_db)
        inspection_repo = SqliteInspectionRepository(in_memory_db)

        project = Project(
            name="UFV Caetité 5MW",
            client_name="Sol Bahia",
            location_name="Caetité - BA",
            capacity_kwp=5000.0,
        )
        project_repo.save(project)

        # 1. Create Inspection
        inspection = Inspection(
            project_id=project.id,
            title="Inspeção Térmica Anual 2026",
            inspector_name="Eng. Laura Peixoto",
            drone_model="DJI Matrice 4T",
            status=InspectionStatus.CREATED,
            irradiance_w_m2=890.0,
            ambient_temp_celsius=31.5,
            wind_speed_m_s=2.1,
            notes="Céu limpo, excelente condição de voo.",
        )
        inspection_repo.save(inspection)

        # 2. Read
        fetched = inspection_repo.get_by_id(inspection.id)
        assert fetched is not None
        assert fetched.title == "Inspeção Térmica Anual 2026"
        assert fetched.irradiance_w_m2 == 890.0
        assert fetched.status == InspectionStatus.CREATED

        # 3. Update Status
        fetched.status = InspectionStatus.COMPLETED
        inspection_repo.save(fetched)
        assert inspection_repo.get_by_id(inspection.id).status == InspectionStatus.COMPLETED

        # 4. List by Project
        inspections = inspection_repo.list_by_project(project.id)
        assert len(inspections) == 1

        # 5. Delete
        assert inspection_repo.delete(inspection.id) is True
        assert inspection_repo.get_by_id(inspection.id) is None


class TestThermalImageAndAnomalyRepositories:
    def test_image_and_anomaly_crud(self, in_memory_db):
        project_repo = SqliteProjectRepository(in_memory_db)
        inspection_repo = SqliteInspectionRepository(in_memory_db)
        image_repo = SqliteThermalImageRepository(in_memory_db)
        anomaly_repo = SqliteThermalAnomalyRepository(in_memory_db)

        # Setup Projeto e Inspeção
        project = Project(
            name="UFV Bom Jesus 1MW",
            client_name="Solaris",
            location_name="Bom Jesus da Lapa - BA",
            capacity_kwp=1000.0,
        )
        project_repo.save(project)

        inspection = Inspection(
            project_id=project.id,
            title="Inspeção Piloto",
            inspector_name="Piloto Rodrigo",
        )
        inspection_repo.save(inspection)

        # 1. Salvar Imagem Térmica
        coord = GeoCoordinate(latitude=-13.2500, longitude=-43.4167, altitude_meters=450.0)
        thermal_meta = ThermalMatrixMeta(
            emissivity=0.95,
            reflected_temp_celsius=25.0,
            ambient_temp_celsius=32.0,
            min_temp_celsius=25.0,
            max_temp_celsius=75.0,
            avg_temp_celsius=40.0,
        )
        image = ThermalImage(
            inspection_id=inspection.id,
            file_path="C:/UFV/DJI_0001_T.JPG",
            filename="DJI_0001_T.JPG",
            width=640,
            height=512,
            coordinate=coord,
            flight_altitude_meters=25.0,
            gimbal_pitch_degrees=-90.0,
            gimbal_yaw_degrees=180.0,
            thermal_meta=thermal_meta,
            is_analyzed=True,
            captured_at=datetime.now(),
        )
        image_repo.save(image)

        fetched_img = image_repo.get_by_id(image.id)
        assert fetched_img is not None
        assert fetched_img.filename == "DJI_0001_T.JPG"
        assert fetched_img.thermal_meta.emissivity == 0.95
        assert fetched_img.thermal_meta.max_temp_celsius == 75.0

        # 2. Salvar Falha / Anomalia
        bbox = BoundingBox(x_min=0.25, y_min=0.30, x_max=0.35, y_max=0.45)
        anomaly = ThermalAnomaly(
            anomaly_type=AnomalyType.HOTSPOT,
            severity=SeverityLevel.CRITICAL,
            confidence=0.96,
            bbox=bbox,
            max_temp_celsius=74.5,
            delta_t=DeltaT(t_max_celsius=74.5, t_ref_celsius=39.5),
            min_temp_celsius=42.0,
            avg_temp_celsius=62.0,
            crop_path="C:/crops/hotspot_01.jpg",
            notes="Hotspot severo no canto superior esquerdo da célula",
        )
        anomaly_repo.save(anomaly, image_id=image.id)

        # 3. Consultar Anomalia
        fetched_anom = anomaly_repo.get_by_id(anomaly.id)
        assert fetched_anom is not None
        assert fetched_anom.anomaly_type == AnomalyType.HOTSPOT
        assert fetched_anom.severity == SeverityLevel.CRITICAL
        assert fetched_anom.delta_t.value == 35.0
        assert fetched_anom.confidence == 0.96

        # 4. Listar anomalias por imagem e por inspeção
        by_image = anomaly_repo.list_by_image(image.id)
        assert len(by_image) == 1
        assert by_image[0].id == anomaly.id

        by_inspection = anomaly_repo.list_by_inspection(inspection.id)
        assert len(by_inspection) == 1
        assert by_inspection[0].id == anomaly.id

        # 5. Delete anomalia
        assert anomaly_repo.delete(anomaly.id) is True
        assert anomaly_repo.get_by_id(anomaly.id) is None


class TestReportRepository:
    def test_report_crud(self, in_memory_db):
        project_repo = SqliteProjectRepository(in_memory_db)
        inspection_repo = SqliteInspectionRepository(in_memory_db)
        report_repo = SqliteReportRepository(in_memory_db)

        project = Project(name="UFV 1", client_name="C1", location_name="L1", capacity_kwp=100.0)
        project_repo.save(project)

        inspection = Inspection(project_id=project.id, title="Insp 1", inspector_name="Insp")
        inspection_repo.save(inspection)

        # 1. Salvar Relatório
        report = Report(
            inspection_id=inspection.id,
            title="Dossiê Técnico Termográfico - UFV 1",
            report_type=ReportType.PDF_TECHNICAL,
            file_path="C:/reports/dossie_ufv1.pdf",
            file_size_bytes=2_450_100,
            generated_by="Eng. Marcos",
        )
        report_repo.save(report)

        # 2. Consultar
        fetched = report_repo.get_by_id(report.id)
        assert fetched is not None
        assert fetched.title == "Dossiê Técnico Termográfico - UFV 1"
        assert fetched.report_type == ReportType.PDF_TECHNICAL
        assert fetched.file_size_bytes == 2_450_100

        # 3. Listar por Inspeção
        reports = report_repo.list_by_inspection(inspection.id)
        assert len(reports) == 1

        # 4. Delete
        assert report_repo.delete(report.id) is True
        assert report_repo.get_by_id(report.id) is None


class TestCascadeDeleteIntegrity:
    def test_cascade_delete_from_project(self, in_memory_db):
        """Valida se ao excluir um projeto, suas inspeções, imagens, anomalias e relatórios são excluídos em cascata."""
        project_repo = SqliteProjectRepository(in_memory_db)
        inspection_repo = SqliteInspectionRepository(in_memory_db)
        image_repo = SqliteThermalImageRepository(in_memory_db)
        anomaly_repo = SqliteThermalAnomalyRepository(in_memory_db)
        report_repo = SqliteReportRepository(in_memory_db)

        # Inserção da cadeia relacional completa
        project = project_repo.save(
            Project(name="Usina Cascata", client_name="Cliente", location_name="Cidade", capacity_kwp=500.0)
        )
        inspection = inspection_repo.save(
            Inspection(project_id=project.id, title="Inspeção Cascata", inspector_name="Técnico")
        )
        image = image_repo.save(
            ThermalImage(inspection_id=inspection.id, file_path="/img.jpg", filename="img.jpg")
        )
        anomaly = anomaly_repo.save(
            ThermalAnomaly(
                anomaly_type=AnomalyType.HOTSPOT,
                severity=SeverityLevel.CRITICAL,
                confidence=0.9,
                bbox=BoundingBox(0.1, 0.1, 0.2, 0.2),
                max_temp_celsius=65.0,
            ),
            image_id=image.id,
        )
        report = report_repo.save(
            Report(
                inspection_id=inspection.id,
                title="Relatório",
                report_type=ReportType.PDF_EXECUTIVE,
                file_path="/rep.pdf",
            )
        )

        # Garantir que todos existem
        assert project_repo.get_by_id(project.id) is not None
        assert inspection_repo.get_by_id(inspection.id) is not None
        assert image_repo.get_by_id(image.id) is not None
        assert anomaly_repo.get_by_id(anomaly.id) is not None
        assert report_repo.get_by_id(report.id) is not None

        # Excluir o Projeto Raiz
        project_repo.delete(project.id)

        # Verificar cascata completa (ON DELETE CASCADE)
        assert project_repo.get_by_id(project.id) is None
        assert inspection_repo.get_by_id(inspection.id) is None
        assert image_repo.get_by_id(image.id) is None
        assert anomaly_repo.get_by_id(anomaly.id) is None
        assert report_repo.get_by_id(report.id) is None

    def test_foreign_key_violation_raises_error(self, in_memory_db):
        """Valida que tentar inserir uma inspeção para um project_id inexistente lança IntegrityError."""
        inspection_repo = SqliteInspectionRepository(in_memory_db)
        invalid_inspection = Inspection(
            project_id="non-existent-project-id",
            title="Inspeção Inválida",
            inspector_name="Piloto",
        )
        with pytest.raises(sqlite3.IntegrityError):
            inspection_repo.save(invalid_inspection)
