"""
Testes integrados para o GeoReferencingService (Etapa 8).
Valida o georreferenciamento completo de inspeções e usinas fotovoltaicas
com imagens contendo metadados GPS DJI e geração de arquivos HTML (Folium) e GeoJSON.
"""

import json
from pathlib import Path
from datetime import datetime
import pytest

from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories import (
    SqliteProjectRepository,
    SqliteInspectionRepository,
    SqliteThermalImageRepository,
    SqliteThermalAnomalyRepository,
)
from src.domain.entities import Project, Inspection, ThermalImage, ThermalAnomaly
from src.domain.enums import AnomalyType, SeverityLevel, InspectionStatus
from src.domain.value_objects import GeoCoordinate, BoundingBox, DeltaT
from src.infrastructure.gis.thermal_georeferencer import ThermalGeoReferencer
from src.infrastructure.gis.map_generator import MapGenerator
from src.infrastructure.gis.geojson_exporter import GeoJsonExporter
from src.application.services.georeferencing_service import GeoReferencingService


@pytest.fixture
def in_memory_db() -> DatabaseManager:
    db = DatabaseManager(":memory:")
    db.initialize_schema()
    yield db
    db.close()


@pytest.fixture
def populated_gis_data(in_memory_db: DatabaseManager):
    """Cria um cenário realista com Usina, Inspeção, Imagens DJI com GPS e Anomalias."""
    proj_repo = SqliteProjectRepository(in_memory_db)
    insp_repo = SqliteInspectionRepository(in_memory_db)
    img_repo = SqliteThermalImageRepository(in_memory_db)
    anom_repo = SqliteThermalAnomalyRepository(in_memory_db)

    # 1. Usina Fotovoltaica
    project = Project(
        name="Complexo Solar São Francisco 10MW",
        client_name="SolBrasil Energia",
        location_name="Juazeiro - BA",
        capacity_kwp=10000.0,
    )
    proj_repo.save(project)

    # 2. Inspeção de Voo
    inspection = Inspection(
        project_id=project.id,
        title="Voo Termográfico Drone DJI Matrice 4T - Faixa A",
        date=datetime(2026, 7, 10, 10, 0),
        inspector_name="Eng. Termografista Nível 2",
        status=InspectionStatus.COMPLETED,
    )
    insp_repo.save(inspection)

    # 3. Imagem Térmica DJI com GPS no Vale do São Francisco
    dji_gps = GeoCoordinate(latitude=-9.412345, longitude=-40.498765, altitude_meters=385.0)

    image1 = ThermalImage(
        inspection_id=inspection.id,
        file_path="/drones/DJI_001_T.JPG",
        filename="DJI_001_T.JPG",
        width=640,
        height=512,
        coordinate=dji_gps,
        flight_altitude_meters=28.0,
        gimbal_pitch_degrees=-90.0,  # Nadir
        gimbal_yaw_degrees=45.0,     # Rumo Nordeste
        captured_at=datetime(2026, 7, 10, 10, 15),
    )
    img_repo.save(image1)

    # 4. Falha Térmica 1: Hotspot Crítico (canto superior da imagem)
    anom1 = ThermalAnomaly(
        image_id=image1.id,
        anomaly_type=AnomalyType.HOTSPOT,
        severity=SeverityLevel.CRITICAL,
        confidence=0.96,
        bbox=BoundingBox(x_min=0.6, y_min=0.2, x_max=0.7, y_max=0.3, is_normalized=True),
        max_temp_celsius=78.5,
        delta_t=DeltaT(t_max_celsius=78.5, t_ref_celsius=40.0),  # Delta T = 38.5°C -> Classe 3
        notes="Ponto quente severo em célula central da string 4",
    )
    anom_repo.save(anom1)

    # 5. Falha Térmica 2: Módulo Desconectado (centro da imagem)
    anom2 = ThermalAnomaly(
        image_id=image1.id,
        anomaly_type=AnomalyType.DISCONNECTED_MODULE,
        severity=SeverityLevel.MEDIUM,
        confidence=0.92,
        bbox=BoundingBox(x_min=0.45, y_min=0.45, x_max=0.55, y_max=0.55, is_normalized=True),
        max_temp_celsius=52.0,
        delta_t=DeltaT(t_max_celsius=52.0, t_ref_celsius=40.0),  # Delta T = 12.0°C -> Classe 2
        notes="Módulo inteiro com aquecimento uniforme",
    )
    anom_repo.save(anom2)

    return {
        "project": project,
        "inspection": inspection,
        "image": image1,
        "anomalies": [anom1, anom2],
    }


class TestGeoReferencingService:
    """Testes para o fluxo integrado de GIS."""

    def test_process_inspection_gis(self, in_memory_db, populated_gis_data, tmp_path):
        proj_repo = SqliteProjectRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)
        anom_repo = SqliteThermalAnomalyRepository(in_memory_db)

        map_gen = MapGenerator(output_dir=tmp_path / "maps")
        exporter = GeoJsonExporter()
        georef = ThermalGeoReferencer()

        service = GeoReferencingService(
            project_repository=proj_repo,
            inspection_repository=insp_repo,
            thermal_image_repository=img_repo,
            thermal_anomaly_repository=anom_repo,
            georeferencer=georef,
            map_generator=map_gen,
            geojson_exporter=exporter,
        )

        insp_id = populated_gis_data["inspection"].id
        result = service.process_inspection_gis(
            inspection_id=insp_id,
            generate_map=True,
            export_geojson=True,
        )

        assert result.is_success is True
        gis_res = result.value

        # Validações dos totais
        assert gis_res.total_anomalies == 2
        assert gis_res.critical_count == 1
        assert gis_res.medium_count == 1
        assert gis_res.low_count == 0

        # Validação das coordenadas calculadas para os defeitos
        anom_list = gis_res.anomalies
        assert len(anom_list) == 2
        for anom in anom_list:
            assert isinstance(anom.coordinate, GeoCoordinate)
            assert -10.0 < anom.coordinate.latitude < -9.0
            assert -41.0 < anom.coordinate.longitude < -40.0

        # Validação da existência do Mapa HTML gerado com Folium
        assert gis_res.map_html_path is not None
        assert gis_res.map_html_path.exists()
        map_content = gis_res.map_html_path.read_text(encoding="utf-8")
        assert "folium" in map_content.lower()
        assert "Complexo Solar São Francisco" in map_content

        # Validação da existência e integridade do arquivo GeoJSON
        assert gis_res.geojson_path is not None
        assert gis_res.geojson_path.exists()
        geojson_data = json.loads(gis_res.geojson_path.read_text(encoding="utf-8"))
        assert geojson_data["type"] == "FeatureCollection"
        assert len(geojson_data["features"]) == 2
        assert geojson_data["metadata"]["total_features"] == 2

    def test_process_project_gis(self, in_memory_db, populated_gis_data, tmp_path):
        proj_repo = SqliteProjectRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)
        anom_repo = SqliteThermalAnomalyRepository(in_memory_db)

        map_gen = MapGenerator(output_dir=tmp_path / "maps")
        service = GeoReferencingService(
            project_repository=proj_repo,
            inspection_repository=insp_repo,
            thermal_image_repository=img_repo,
            thermal_anomaly_repository=anom_repo,
            map_generator=map_gen,
        )

        proj_id = populated_gis_data["project"].id
        result = service.process_project_gis(proj_id, generate_map=True, export_geojson=True)

        assert result.is_success is True
        assert result.value.total_anomalies == 2
        assert result.value.map_html_path.exists()
        assert result.value.geojson_path.exists()
