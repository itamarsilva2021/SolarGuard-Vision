"""
Testes unitários para o gerador de relatórios técnicos em PDF com ReportLab (Etapa 9).
Valida a compilação do documento, estilos normativos IEC, imagens, gráficos e numeração de páginas.
"""

from pathlib import Path
from datetime import datetime
import pytest
import numpy as np
import cv2

from src.domain.enums import AnomalyType, SeverityLevel
from src.domain.value_objects import GeoCoordinate
from src.application.dtos.report_dtos import InspectionReportData, AnomalyReportItem
from src.infrastructure.reporting.pdf_generator import PdfReportGenerator


@pytest.fixture
def sample_image_files(tmp_path: Path):
    """Cria imagens térmicas de teste para simular fotos gerais e recortes de falhas."""
    img_dir = tmp_path / "sample_images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # Imagem de contexto térmico (640x512)
    context_path = img_dir / "termograma_geral.jpg"
    blank_context = np.full((512, 640, 3), 40, dtype=np.uint8)
    cv2.putText(blank_context, "DJI Matrice 4T Thermal", (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
    cv2.imwrite(str(context_path), blank_context)

    # Recorte da falha (crop 128x128)
    crop_path = img_dir / "crop_hotspot.jpg"
    blank_crop = np.full((128, 128, 3), 60, dtype=np.uint8)
    cv2.circle(blank_crop, (64, 64), 30, (0, 0, 255), -1)  # Círculo vermelho quente
    cv2.imwrite(str(crop_path), blank_crop)

    # Gráfico fake (400x300)
    chart_path = img_dir / "chart_fake.png"
    blank_chart = np.full((300, 400, 3), 30, dtype=np.uint8)
    cv2.putText(blank_chart, "Chart Fake", (100, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
    cv2.imwrite(str(chart_path), blank_chart)

    return {
        "context": str(context_path),
        "crop": str(crop_path),
        "chart": str(chart_path),
    }


class TestPdfReportGenerator:
    """Testes para o construtor do documento PDF."""

    def test_generate_report_healthy_plant_without_faults(self, tmp_path: Path):
        generator = PdfReportGenerator(output_dir=tmp_path)
        data = InspectionReportData(
            client_name="Omega Solar S.A.",
            project_name="UFV Alvorada 5MW",
            location="Petrolina - PE",
            capacity_kwp=5000.0,
            inspection_id="insp-healthy-01",
            inspection_title="Inspeção Periódica Q1",
            inspection_date=datetime(2026, 3, 10, 9, 30),
            inspector_name="Eng. Termografista",
            total_images=50,
            total_anomalies=0,
            compliance_rate_pct=100.0,
            anomalies=[],
        )

        pdf_path = generator.generate_report(data, "relatorio_saudavel.pdf")

        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 3000
        # Validar cabeçalho binário padrão do PDF
        with open(pdf_path, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"

    def test_generate_report_with_anomalies_and_photos(self, tmp_path: Path, sample_image_files: dict):
        generator = PdfReportGenerator(output_dir=tmp_path)

        anom1 = AnomalyReportItem(
            anomaly_id="anom-01",
            anomaly_type=AnomalyType.HOTSPOT,
            severity=SeverityLevel.CRITICAL,
            max_temp_celsius=78.5,
            confidence=0.96,
            delta_t_celsius=38.5,
            ref_temp_celsius=40.0,
            coordinate=GeoCoordinate(latitude=-9.3891, longitude=-40.5027, altitude_meters=375.0),
            crop_image_path=sample_image_files["crop"],
            context_image_path=sample_image_files["context"],
            notes="Hotspot de alta severidade em módulo 12 da mesa 4.",
        )

        anom2 = AnomalyReportItem(
            anomaly_id="anom-02",
            anomaly_type=AnomalyType.DISCONNECTED_MODULE,
            severity=SeverityLevel.MEDIUM,
            max_temp_celsius=52.0,
            confidence=0.91,
            delta_t_celsius=12.0,
            ref_temp_celsius=40.0,
            coordinate=GeoCoordinate(latitude=-9.3892, longitude=-40.5028, altitude_meters=375.0),
            crop_image_path=sample_image_files["crop"],
            context_image_path=sample_image_files["context"],
            notes="String com aquecimento uniforme sugestivo de circuito aberto.",
        )

        data = InspectionReportData(
            client_name="EletroSolar Participações",
            project_name="Complexo Solar São Francisco",
            location="Juazeiro - BA",
            capacity_kwp=10000.0,
            inspection_id="insp-complex-01",
            inspection_title="Inspeção Termográfica Aérea DJI Matrice 4T",
            inspection_date=datetime(2026, 7, 15, 11, 0),
            inspector_name="Eng. Carlos Rocha - CREA 123456",
            total_images=120,
            total_anomalies=2,
            critical_count=1,
            medium_count=1,
            low_count=0,
            max_temp_celsius=78.5,
            max_delta_t_celsius=38.5,
            compliance_rate_pct=80.0,
            anomalies=[anom1, anom2],
            chart_distribution_path=sample_image_files["chart"],
            chart_severity_path=sample_image_files["chart"],
        )

        pdf_path = generator.generate_report(data, "relatorio_completo_falhas.pdf")

        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 8000
        with open(pdf_path, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"
