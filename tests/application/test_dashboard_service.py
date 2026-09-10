"""
Testes integrados para o serviço DashboardService (Etapa 7).
Valida KPIs, agregação do histórico de inspeções e geração automática de gráficos com SQLite em memória.
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta

from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories import (
    SqliteProjectRepository,
    SqliteInspectionRepository,
    SqliteThermalImageRepository,
    SqliteThermalAnomalyRepository,
)
from src.domain.entities import Project, Inspection, ThermalImage, ThermalAnomaly
from src.domain.enums import AnomalyType, SeverityLevel, InspectionStatus
from src.domain.value_objects import BoundingBox, DeltaT
from src.infrastructure.visualization.chart_generator import ChartGenerator
from src.application.services.dashboard_service import DashboardService


@pytest.fixture
def in_memory_db() -> DatabaseManager:
    """Banco SQLite em memória para testes integrados do Dashboard."""
    db = DatabaseManager(":memory:")
    db.initialize_schema()
    yield db
    db.close()


@pytest.fixture
def populated_solar_plant(in_memory_db):
    """Popula o banco com usinas, inspeções e anomalias de teste."""
    proj_repo = SqliteProjectRepository(in_memory_db)
    insp_repo = SqliteInspectionRepository(in_memory_db)
    img_repo = SqliteThermalImageRepository(in_memory_db)
    anom_repo = SqliteThermalAnomalyRepository(in_memory_db)

    # 1. Projeto / Usina
    project = proj_repo.save(
        Project(name="UFV Solar Sol Nascente 5MW", client_name="EletroSolar", location_name="Petrolina - PE", capacity_kwp=5000.0)
    )

    # 2. Duas inspeções cronológicas
    date_past = datetime.now() - timedelta(days=45)
    date_recent = datetime.now() - timedelta(days=10)

    insp1 = insp_repo.save(
        Inspection(
            project_id=project.id,
            title="Inspeção Inicial Q1",
            inspector_name="Piloto Gabriel",
            status=InspectionStatus.COMPLETED,
            irradiance_w_m2=850.0,
            wind_speed_m_s=2.0,
            date=date_past,
        )
    )

    insp2 = insp_repo.save(
        Inspection(
            project_id=project.id,
            title="Inspeção Semestral Q2",
            inspector_name="Piloto Gabriel",
            status=InspectionStatus.COMPLETED,
            irradiance_w_m2=920.0,
            wind_speed_m_s=1.8,
            date=date_recent,
        )
    )

    # 3. Imagens Térmicas
    img1 = img_repo.save(ThermalImage(inspection_id=insp1.id, file_path="/p1.jpg", filename="p1.jpg", is_analyzed=True))
    img2 = img_repo.save(ThermalImage(inspection_id=insp2.id, file_path="/p2.jpg", filename="p2.jpg", is_analyzed=True))

    # 4. Falhas em Insp1: 1 Hotspot Crítico (74 °C, DeltaT=39 °C) e 1 Sujidade (40 °C, DeltaT=5 °C)
    anom_repo.save(
        ThermalAnomaly(
            anomaly_type=AnomalyType.HOTSPOT,
            severity=SeverityLevel.CRITICAL,
            confidence=0.95,
            bbox=BoundingBox(0.2, 0.2, 0.3, 0.3),
            max_temp_celsius=74.0,
            delta_t=DeltaT(74.0, 35.0),
        ),
        image_id=img1.id,
    )
    anom_repo.save(
        ThermalAnomaly(
            anomaly_type=AnomalyType.SOILING,
            severity=SeverityLevel.LOW,
            confidence=0.88,
            bbox=BoundingBox(0.5, 0.5, 0.6, 0.6),
            max_temp_celsius=40.0,
            delta_t=DeltaT(40.0, 35.0),
        ),
        image_id=img1.id,
    )

    # 5. Falhas em Insp2: 1 Módulo Desconectado (42 °C, DeltaT=7 °C)
    anom_repo.save(
        ThermalAnomaly(
            anomaly_type=AnomalyType.DISCONNECTED_MODULE,
            severity=SeverityLevel.LOW,
            confidence=0.91,
            bbox=BoundingBox(0.1, 0.1, 0.4, 0.4),
            max_temp_celsius=42.0,
            delta_t=DeltaT(42.0, 35.0),
        ),
        image_id=img2.id,
    )

    return project


class TestDashboardService:
    def test_dashboard_data_compilation_and_kpis(self, in_memory_db, populated_solar_plant, tmp_path):
        proj_repo = SqliteProjectRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)
        anom_repo = SqliteThermalAnomalyRepository(in_memory_db)

        chart_gen = ChartGenerator(output_dir=tmp_path / "dashboard_charts")
        service = DashboardService(
            project_repository=proj_repo,
            inspection_repository=insp_repo,
            thermal_image_repository=img_repo,
            thermal_anomaly_repository=anom_repo,
            chart_generator=chart_gen,
        )

        result = service.get_dashboard_data(generate_charts=True)

        assert result.is_success is True
        dashboard = result.value

        # Validação dos KPIs
        kpis = dashboard.kpis
        assert kpis.total_projects == 1
        assert kpis.total_inspections == 2
        assert kpis.total_faults == 3
        assert kpis.critical_faults == 1
        assert kpis.highest_temp_celsius == 74.0
        assert kpis.max_delta_t_celsius == 39.0
        assert kpis.total_images_analyzed == 2
        assert kpis.iec_compliance_rate_pct == 100.0

        # Validação do Histórico (ordenado do mais recente ao mais antigo)
        assert len(dashboard.history) == 2
        assert dashboard.history[0].title == "Inspeção Semestral Q2"
        assert dashboard.history[1].title == "Inspeção Inicial Q1"

        # Validação da Distribuição por tipo de falha
        assert dashboard.distribution.by_type["Hotspot"] == 1
        assert dashboard.distribution.by_type["Sujidade / Poeira"] == 1
        assert dashboard.distribution.by_type["Módulo Desconectado"] == 1
        assert dashboard.distribution.by_type["Degradação PID"] == 0

        # Validação dos arquivos de gráficos gerados pelo Matplotlib
        assert dashboard.chart_distribution_path is not None
        assert Path(dashboard.chart_distribution_path).exists()

        assert dashboard.chart_severity_path is not None
        assert Path(dashboard.chart_severity_path).exists()

        assert dashboard.chart_history_path is not None
        assert Path(dashboard.chart_history_path).exists()

        assert dashboard.chart_overview_path is not None
        assert Path(dashboard.chart_overview_path).exists()

    def test_dashboard_filtered_by_project(self, in_memory_db, populated_solar_plant):
        proj_repo = SqliteProjectRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)
        anom_repo = SqliteThermalAnomalyRepository(in_memory_db)

        service = DashboardService(
            project_repository=proj_repo,
            inspection_repository=insp_repo,
            thermal_image_repository=img_repo,
            thermal_anomaly_repository=anom_repo,
        )

        result = service.get_dashboard_data(project_id=populated_solar_plant.id, generate_charts=False)
        assert result.is_success is True
        assert result.value.kpis.total_inspections == 2
