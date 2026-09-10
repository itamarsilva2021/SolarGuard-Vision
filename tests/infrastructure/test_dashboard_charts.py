"""
Testes unitários para o gerador de gráficos Matplotlib do Dashboard (Etapa 7).
Valida a geração de gráficos de rosca, barras de severidade, linha temporal e painel 2x2.
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
import cv2

from src.infrastructure.visualization.chart_generator import ChartGenerator
from src.application.dtos.dashboard_dtos import DashboardData, DashboardKPIs, FaultDistribution


@pytest.fixture
def chart_generator(tmp_path) -> ChartGenerator:
    """Instância do gerador apontando para pasta temporária de saída."""
    out_dir = tmp_path / "test_charts"
    return ChartGenerator(output_dir=out_dir)


class TestChartGenerator:
    def test_generate_fault_distribution_pie(self, chart_generator):
        data = {
            "Hotspot": 12,
            "Módulo Desconectado": 4,
            "Degradação PID": 2,
            "Sujidade / Poeira": 8,
            "Sombreamento Parcial": 3,
        }
        chart_path = chart_generator.generate_fault_distribution_pie(data, "pie_test.png")

        assert chart_path.exists()
        assert chart_path.stat().st_size > 1000

        # Verifica legibilidade da imagem gerada com OpenCV
        img = cv2.imread(str(chart_path))
        assert img is not None
        assert img.ndim == 3

    def test_generate_severity_bar_chart(self, chart_generator):
        data = {
            "Crítico (Classe 3 - IEC)": 6,
            "Médio (Classe 2 - IEC)": 14,
            "Baixo (Classe 1 - IEC)": 9,
            "Informativo / Normal": 35,
        }
        chart_path = chart_generator.generate_severity_bar_chart(data, "bar_test.png")

        assert chart_path.exists()
        assert chart_path.stat().st_size > 1000

        img = cv2.imread(str(chart_path))
        assert img is not None

    def test_generate_historical_trend_chart(self, chart_generator):
        now = datetime.now()
        timeline = [
            {"date": now - timedelta(days=60), "faults": 15, "inspections": 1},
            {"date": now - timedelta(days=30), "faults": 8, "inspections": 1},
            {"date": now, "faults": 3, "inspections": 1},
        ]
        chart_path = chart_generator.generate_historical_trend_chart(timeline, "trend_test.png")

        assert chart_path.exists()
        assert chart_path.stat().st_size > 1000

        img = cv2.imread(str(chart_path))
        assert img is not None

    def test_generate_consolidated_dashboard_figure(self, chart_generator):
        kpis = DashboardKPIs(
            total_inspections=5,
            total_faults=25,
            critical_faults=4,
            total_projects=2,
            total_images_analyzed=120,
            max_delta_t_celsius=38.5,
            highest_temp_celsius=74.2,
            iec_compliance_rate_pct=100.0,
        )
        dist = FaultDistribution(
            by_type={"Hotspot": 10, "Sujidade / Poeira": 15},
            by_severity={"Crítico (Classe 3 - IEC)": 4, "Médio (Classe 2 - IEC)": 21},
            timeline_series=[
                {"date": datetime(2026, 1, 15), "faults": 12},
                {"date": datetime(2026, 6, 20), "faults": 13},
            ],
        )
        data = DashboardData(kpis=kpis, distribution=dist)

        overview_path = chart_generator.generate_consolidated_dashboard_figure(data, "overview_test.png")

        assert overview_path.exists()
        assert overview_path.stat().st_size > 5000

        img = cv2.imread(str(overview_path))
        assert img is not None
        h, w = img.shape[:2]
        # Painel consolidado deve ser de alta resolução
        assert w >= 1800 and h >= 1000
