"""
Testes integrados para o serviço ReportService (Etapa 9).
Valida o fluxo completo de emissão de PDF técnico, integrando Cliente, Usina,
Inspeção, Imagens DJI, Anomalias Térmicas, cálculo de KPIs e persistência no SQLite.
"""

from pathlib import Path
from datetime import datetime
import pytest
import numpy as np
import cv2

from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories import (
    SqliteClientRepository,
    SqliteProjectRepository,
    SqliteInspectionRepository,
    SqliteThermalImageRepository,
    SqliteThermalAnomalyRepository,
    SqliteReportRepository,
)
from src.domain.entities import Client, Project, Inspection, ThermalImage, ThermalAnomaly
from src.domain.entities.report import ReportType
from src.domain.enums import AnomalyType, SeverityLevel, InspectionStatus
from src.domain.value_objects import GeoCoordinate, BoundingBox, DeltaT
from src.infrastructure.reporting.pdf_generator import PdfReportGenerator
from src.infrastructure.visualization.chart_generator import ChartGenerator
from src.application.services.report_service import ReportService


@pytest.fixture
def in_memory_db() -> DatabaseManager:
    db = DatabaseManager(":memory:")
    db.initialize_schema()
    yield db
    db.close()


@pytest.fixture
def populated_report_data(in_memory_db: DatabaseManager, tmp_path: Path):
    """Cria dados completos persistidos no SQLite com arquivos de imagem válidos."""
    client_repo = SqliteClientRepository(in_memory_db)
    proj_repo = SqliteProjectRepository(in_memory_db)
    insp_repo = SqliteInspectionRepository(in_memory_db)
    img_repo = SqliteThermalImageRepository(in_memory_db)
    anom_repo = SqliteThermalAnomalyRepository(in_memory_db)

    # 1. Cliente
    client = Client(name="VoltMax Geração Solar", email="contato@voltmax.com")
    client_repo.save(client)


    # 2. Usina / Projeto
    project = Project(
        client_id=client.id,
        name="Parque Fotovoltaico Sol Nascente 5MW",
        client_name=client.name,
        location_name="Bom Jesus da Lapa - BA",
        capacity_kwp=5000.0,
    )
    proj_repo.save(project)

    # 3. Inspeção
    inspection = Inspection(
        project_id=project.id,
        title="Inspeção Pericial com Drone DJI Matrice 4T",
        date=datetime(2026, 8, 20, 11, 30),
        inspector_name="Dr. Fernando Alves - CREA/BA 98765",
        status=InspectionStatus.COMPLETED,
    )
    insp_repo.save(inspection)

    # Criar imagens de teste no disco
    img_dir = tmp_path / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    img_file = img_dir / "termograma_01.jpg"
    blank_img = np.full((512, 640, 3), 50, dtype=np.uint8)
    cv2.putText(blank_img, "DJI M4T IR", (30, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.imwrite(str(img_file), blank_img)

    crop_file = img_dir / "crop_01.jpg"
    blank_crop = np.full((120, 120, 3), 70, dtype=np.uint8)
    cv2.circle(blank_crop, (60, 60), 25, (0, 0, 255), -1)
    cv2.imwrite(str(crop_file), blank_crop)

    # 4. Imagem Térmica
    thermal_img = ThermalImage(
        inspection_id=inspection.id,
        file_path=str(img_file),
        filename="termograma_01.jpg",
        width=640,
        height=512,
        coordinate=GeoCoordinate(latitude=-13.2541, longitude=-43.4125, altitude_meters=420.0),
        flight_altitude_meters=25.0,
        gimbal_pitch_degrees=-90.0,
        gimbal_yaw_degrees=0.0,
    )
    img_repo.save(thermal_img)

    # 5. Falha Térmica: Hotspot Crítico
    anom1 = ThermalAnomaly(
        image_id=thermal_img.id,
        anomaly_type=AnomalyType.HOTSPOT,
        severity=SeverityLevel.CRITICAL,
        confidence=0.97,
        bbox=BoundingBox(x_min=0.4, y_min=0.4, x_max=0.6, y_max=0.6, is_normalized=True),
        max_temp_celsius=76.2,
        delta_t=DeltaT(t_max_celsius=76.2, t_ref_celsius=38.0),
        crop_path=str(crop_file),
        notes="Ponto quente com superaquecimento severo (>30°C)",
    )
    anom_repo.save(anom1)

    return {
        "client": client,
        "project": project,
        "inspection": inspection,
        "image": thermal_img,
        "anomaly": anom1,
    }


class TestReportService:
    """Testes integrados do serviço de emissão e gravação de relatórios técnicos."""

    def test_generate_inspection_pdf_complete_flow(self, in_memory_db: DatabaseManager, populated_report_data: dict, tmp_path: Path):
        client_repo = SqliteClientRepository(in_memory_db)
        proj_repo = SqliteProjectRepository(in_memory_db)
        insp_repo = SqliteInspectionRepository(in_memory_db)
        img_repo = SqliteThermalImageRepository(in_memory_db)
        anom_repo = SqliteThermalAnomalyRepository(in_memory_db)
        rep_repo = SqliteReportRepository(in_memory_db)

        pdf_gen = PdfReportGenerator(output_dir=tmp_path / "reports")
        chart_gen = ChartGenerator(output_dir=tmp_path / "reports" / "charts")

        service = ReportService(
            project_repository=proj_repo,
            client_repository=client_repo,
            inspection_repository=insp_repo,
            thermal_image_repository=img_repo,
            thermal_anomaly_repository=anom_repo,
            report_repository=rep_repo,
            pdf_generator=pdf_gen,
            chart_generator=chart_gen,
        )

        insp_id = populated_report_data["inspection"].id
        result = service.generate_inspection_pdf(
            inspection_id=insp_id,
            inspector_name="Eng. Marcos Viana",
            include_charts=True,
            output_filename="relatorio_teste_integrado.pdf",
        )

        assert result.is_success is True
        report = result.value

        # Validações da Entidade Report
        assert report.id is not None
        assert report.inspection_id == insp_id
        assert report.report_type == ReportType.PDF_TECHNICAL
        assert "relatorio_teste_integrado.pdf" in report.file_path
        assert report.file_size_bytes > 5000
        assert Path(report.file_path).exists()

        # Validação da persistência no banco SQLite
        persisted_report = rep_repo.get_by_id(report.id)
        assert persisted_report is not None
        assert persisted_report.title == report.title
        assert persisted_report.file_size_bytes == report.file_size_bytes
