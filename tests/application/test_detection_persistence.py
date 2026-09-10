"""
Suíte de testes para persistência científica de inferências (Etapa 15).
Valida gravação e consultas nas tabelas thermal_analysis, delta_t_results,
yolo_predictions e detections com rigor normativo IEC TS 62446-3.
"""

import pytest
from datetime import datetime
import uuid

from src.domain.entities.thermal_anomaly import ThermalAnomaly
from src.domain.entities.thermal_image import ThermalImage
from src.domain.enums.anomaly_type import AnomalyType
from src.domain.enums.severity_level import SeverityLevel
from src.domain.value_objects.bounding_box import BoundingBox
from src.domain.value_objects.delta_t import DeltaT
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories.sqlite_thermal_image_repository import SqliteThermalImageRepository
from src.infrastructure.database.repositories.sqlite_thermal_anomaly_repository import SqliteThermalAnomalyRepository
from src.infrastructure.database.repositories.sqlite_detection_repository import SqliteDetectionRepository
from src.application.dtos.scientific_detection_dtos import DetectionPersistenceRequest
from src.application.services.detection_persistence_service import DetectionPersistenceService


@pytest.fixture
def in_memory_db():
    """Fornece uma conexão SQLite em memória com o schema completo inicializado."""
    db = DatabaseManager(db_path=":memory:")
    db.initialize_schema()
    return db


@pytest.fixture
def image_and_inspection(in_memory_db):
    """Cria uma inspeção e uma imagem térmica no banco para servir de âncora relacional."""
    img_repo = SqliteThermalImageRepository(in_memory_db)
    inspection_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())

    with in_memory_db.transaction() as conn:
        # Cria projeto e inspeção mínimos para respeitar foreign keys
        conn.execute(
            "INSERT INTO projects (id, name, client_name, location_name, capacity_kwp, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?);",
            (project_id, "Planta Solar Teste", "Cliente Teste", "São Paulo", 500.0, datetime.now().isoformat()),
        )
        conn.execute(
            "INSERT INTO inspections (id, project_id, title, inspector_name, drone_model, status, date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?);",
            (inspection_id, project_id, "Inspeção Termográfica #1", "Inspetor Silva", "DJI Matrice 4T", "completed", datetime.now().isoformat()),
        )

    # Cria imagem térmica
    image = ThermalImage(
        id=str(uuid.uuid4()),
        inspection_id=inspection_id,
        file_path="C:/photos/DJI_0001_T.JPG",
        filename="DJI_0001_T.JPG",
        width=640,
        height=512,
        is_analyzed=False,
    )
    saved_img = img_repo.save(image)
    return saved_img, inspection_id


class TestDetectionPersistenceService:
    """Testes para o DetectionPersistenceService e repositório de inferências."""

    def test_persist_complete_scientific_inference(self, in_memory_db, image_and_inspection):
        image, inspection_id = image_and_inspection
        detection_repo = SqliteDetectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)
        anomaly_repo = SqliteThermalAnomalyRepository(in_memory_db)

        service = DetectionPersistenceService(
            detection_repo=detection_repo,
            image_repo=img_repo,
            anomaly_repo=anomaly_repo,
        )

        # 1. Cria 3 anomalias térmicas com severidades distintas
        # Anomalia 1: Hotspot Crítico (Delta T = 75 - 40 = 35°C >= 30°C -> Critical)
        a1 = ThermalAnomaly(
            anomaly_type=AnomalyType.HOTSPOT,
            severity=SeverityLevel.CRITICAL,
            confidence=0.94,
            bbox=BoundingBox(xmin=0.1, ymin=0.1, xmax=0.2, ymax=0.2),
            max_temp_celsius=75.0,
            min_temp_celsius=38.0,
            avg_temp_celsius=68.0,
            delta_t=DeltaT(t_max_celsius=75.0, t_ref_celsius=40.0),
        )

        # Anomalia 2: Módulo Desconectado Medium (Delta T = 55 - 40 = 15°C -> Medium)
        a2 = ThermalAnomaly(
            anomaly_type=AnomalyType.DISCONNECTED_MODULE,
            severity=SeverityLevel.MEDIUM,
            confidence=0.88,
            bbox=BoundingBox(xmin=0.3, ymin=0.3, xmax=0.6, ymax=0.6),
            max_temp_celsius=55.0,
            min_temp_celsius=35.0,
            avg_temp_celsius=50.0,
            delta_t=DeltaT(t_max_celsius=55.0, t_ref_celsius=40.0),
        )

        # Anomalia 3: Soiling Low (Delta T = 45 - 40 = 5°C -> Low)
        a3 = ThermalAnomaly(
            anomaly_type=AnomalyType.SOILING,
            severity=SeverityLevel.LOW,
            confidence=0.81,
            bbox=BoundingBox(xmin=0.7, ymin=0.7, xmax=0.85, ymax=0.85),
            max_temp_celsius=45.0,
            min_temp_celsius=32.0,
            avg_temp_celsius=42.0,
            delta_t=DeltaT(t_max_celsius=45.0, t_ref_celsius=40.0),
        )

        request = DetectionPersistenceRequest(
            image_id=image.id,
            anomalies=[a1, a2, a3],
            emissivity=0.92,
            reflected_temp_celsius=22.0,
            ambient_temp_celsius=27.5,
            relative_humidity=0.55,
            distance_meters=24.0,
            reference_temp_celsius=40.0,
            notes="Sessão de auditoria científica",
        )

        # 2. Executa persistência
        result = service.persist_inference(request)
        assert result.is_success is True

        payload = result.value
        assert payload.saved_detections_count == 3
        assert payload.saved_predictions_count == 3
        assert payload.saved_delta_t_count == 3
        assert payload.critical_anomalies_count == 1

        # 3. Validação de dados na tabela 'thermal_analysis'
        analysis = service.get_thermal_analysis(image.id)
        assert analysis is not None
        assert analysis.emissivity == pytest.approx(0.92)
        assert analysis.reflected_temp_celsius == pytest.approx(22.0)
        assert analysis.max_temp_celsius == pytest.approx(75.0)

        # 4. Validação de dados na tabela 'detections'
        detections = service.get_detections_for_image(image.id)
        assert len(detections) == 3

        # Ordenado por max_temp DESC: a1 (75°C), a2 (55°C), a3 (45°C)
        d1 = detections[0]
        assert d1.class_name == "hotspot"
        assert d1.confidence == pytest.approx(0.94)
        assert d1.bbox.xmin == pytest.approx(0.1)
        assert d1.delta_t == pytest.approx(35.0)
        assert d1.max_temp_celsius == pytest.approx(75.0)
        assert d1.avg_temp_celsius == pytest.approx(68.0)
        assert d1.severity == "critical"

        d2 = detections[1]
        assert d2.class_name == "disconnected_module"
        assert d2.delta_t == pytest.approx(15.0)
        assert d2.severity == "medium"

        d3 = detections[2]
        assert d3.class_name == "soiling"
        assert d3.delta_t == pytest.approx(5.0)
        assert d3.severity == "low"

        # 5. Validação da consulta por inspeção
        inspection_detections = service.get_detections_for_inspection(inspection_id)
        assert len(inspection_detections) == 3

        # 6. Validação de que a imagem foi marcada como analisada (is_analyzed = 1)
        updated_img = img_repo.get_by_id(image.id)
        assert updated_img.is_analyzed is True

    def test_cascade_deletion_cleans_scientific_tables(self, in_memory_db, image_and_inspection):
        image, _ = image_and_inspection
        detection_repo = SqliteDetectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)

        service = DetectionPersistenceService(detection_repo=detection_repo, image_repo=img_repo)

        a = ThermalAnomaly(
            anomaly_type=AnomalyType.HOTSPOT,
            severity=SeverityLevel.MEDIUM,
            confidence=0.90,
            bbox=BoundingBox(xmin=0.2, ymin=0.2, xmax=0.3, ymax=0.3),
            max_temp_celsius=60.0,
        )

        req = DetectionPersistenceRequest(image_id=image.id, anomalies=[a])
        res = service.persist_inference(req)
        assert res.is_success is True

        # Verifica existência
        assert len(service.get_detections_for_image(image.id)) == 1

        # Ao remover a imagem, todas as tabelas filhas devem ser limpas em cascata
        img_repo.delete(image.id)
        assert len(service.get_detections_for_image(image.id)) == 0
        assert service.get_thermal_analysis(image.id) is None
