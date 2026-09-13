"""
Configurações e fixtures globais do Pytest para a suíte de testes do SolarGuard Vision.
"""

from pathlib import Path
import pytest
from datetime import datetime

from src.core.config import settings
from src.domain.enums import AnomalyType, SeverityLevel, InspectionStatus
from src.domain.value_objects import GeoCoordinate, DeltaT, BoundingBox, ThermalMatrixMeta
from src.domain.entities import ThermalAnomaly, PVModule, ThermalImage, Inspection, Project


@pytest.fixture(autouse=True)
def isolate_settings_directories(tmp_path: Path):
    """
    Garante que os testes não poluam o diretório de dados real (%APPDATA% do usuário),
    redirecionando todos os caminhos do singleton settings para pastas temporárias limpas.
    """
    orig_base = settings.base_dir
    orig_data = settings.data_dir
    orig_db = settings.db_path
    orig_models = settings.models_dir
    orig_reports = settings.reports_dir
    orig_cache = settings.cache_dir
    orig_logs = settings.logs_dir

    test_base = tmp_path / "sg_test_env"
    test_data = test_base / "data"
    test_db = test_data / "solarguard.sqlite3"
    test_models = test_base / "models"
    test_reports = test_base / "reports"
    test_cache = test_base / "cache"
    test_logs = test_base / "logs"

    settings.base_dir = test_base
    settings.data_dir = test_data
    settings.db_path = test_db
    settings.models_dir = test_models
    settings.reports_dir = test_reports
    settings.cache_dir = test_cache
    settings.logs_dir = test_logs
    settings.ensure_directories()

    yield

    settings.base_dir = orig_base
    settings.data_dir = orig_data
    settings.db_path = orig_db
    settings.models_dir = orig_models
    settings.reports_dir = orig_reports
    settings.cache_dir = orig_cache
    settings.logs_dir = orig_logs


@pytest.fixture
def sample_coordinate() -> GeoCoordinate:
    """Retorna uma coordenada de exemplo (região do Nordeste brasileiro com alta irradiação)."""
    return GeoCoordinate(latitude=-9.3889, longitude=-40.5008, altitude_meters=376.0)


@pytest.fixture
def sample_bounding_box() -> BoundingBox:
    """Retorna uma bounding box normalizada de exemplo."""
    return BoundingBox(x_min=0.2, y_min=0.3, x_max=0.5, y_max=0.7, is_normalized=True)


@pytest.fixture
def sample_thermal_meta() -> ThermalMatrixMeta:
    """Retorna metadados radiométricos de exemplo do DJI Matrice 4T."""
    return ThermalMatrixMeta(
        emissivity=0.95,
        reflected_temp_celsius=25.0,
        ambient_temp_celsius=32.0,
        relative_humidity=0.45,
        distance_meters=20.0,
        min_temp_celsius=28.5,
        max_temp_celsius=72.3,
        avg_temp_celsius=41.2,
        sensor_width=640,
        sensor_height=512,
    )


@pytest.fixture
def sample_hotspot_anomaly(sample_bounding_box) -> ThermalAnomaly:
    """Retorna uma anomalia de Hotspot crítico de teste."""
    return ThermalAnomaly(
        anomaly_type=AnomalyType.HOTSPOT,
        severity=SeverityLevel.CRITICAL,
        confidence=0.94,
        bbox=sample_bounding_box,
        max_temp_celsius=72.0,
        delta_t=DeltaT(t_max_celsius=72.0, t_ref_celsius=40.0),
        min_temp_celsius=42.0,
        avg_temp_celsius=58.0,
    )


@pytest.fixture
def sample_project(sample_coordinate) -> Project:
    """Retorna um projeto completo de exemplo com inspeção agregada."""
    project = Project(
        name="Usina Solar Juazeiro 10MW",
        client_name="Solar Energy Brasil",
        location_name="Juazeiro - BA",
        capacity_kwp=10000.0,
        coordinate=sample_coordinate,
        module_manufacturer="Canadian Solar",
        module_model="CS3W-450MS",
    )
    return project
