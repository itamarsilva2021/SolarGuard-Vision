"""
Testes unitários e de integração para a Engine Térmica do SolarGuard Vision.
Valida ThermalProcessor, ThermalAnalyzer e ThermalMetrics.
"""

import pytest
import numpy as np
import cv2

from src.domain.enums.palette_type import PaletteType
from src.domain.enums.severity_level import SeverityLevel
from src.domain.value_objects.bounding_box import BoundingBox
from src.domain.value_objects.thermal_metrics import ThermalMetrics
from src.infrastructure.thermal.thermal_processor import ThermalProcessor
from src.infrastructure.thermal.thermal_analyzer import ThermalAnalyzer


@pytest.fixture
def synthetic_thermal_scene() -> np.ndarray:
    """
    Cria uma matriz térmica 2D float32 [120 x 160] simulando uma usina solar:
    - Fundo / módulos normais em ~35.0 °C
    - Ruído leve gaussiano (+- 0.5 °C)
    - Hotspot severo em (80, 50) com pico de 72.5 °C (Delta T = 37.5 °C -> Crítico)
    - Sujidade / ponto morno em (30, 90) com pico de 42.0 °C (Delta T = 7.0 °C -> Baixo)
    """
    np.random.seed(42)
    scene = np.full((120, 160), 35.0, dtype=np.float32)
    noise = np.random.normal(0, 0.3, (120, 160)).astype(np.float32)
    scene += noise

    # Hotspot severo (Classe 3 - Crítico)
    scene[45:55, 75:85] = 70.0
    scene[50, 80] = 72.5  # Pico exato

    # Ponto morno (Classe 1 - Baixo)
    scene[88:93, 28:33] = 42.0

    return np.round(scene, 2)


class TestThermalMetrics:
    def test_thermal_metrics_properties(self):
        metrics = ThermalMetrics(
            min_temp=25.0,
            max_temp=70.0,
            avg_temp=36.0,
            median_temp=35.0,
            std_temp=4.5,
            delta_t=35.0,
            max_location=(80, 50),
            min_location=(10, 10),
            ref_temp=35.0,
            severity=SeverityLevel.CRITICAL,
        )

        assert metrics.dynamic_range == 45.0
        assert metrics.is_critical is True
        assert metrics.to_dict()["delta_t_celsius"] == 35.0
        assert metrics.to_dict()["max_location_pixel"] == (80, 50)

        delta_t_obj = metrics.to_delta_t_object()
        assert delta_t_obj.value == 35.0
        assert delta_t_obj.classify_iec_62446_3() == SeverityLevel.CRITICAL


class TestThermalProcessor:
    def test_load_matrix_valid_and_invalid(self, synthetic_thermal_scene):
        processor = ThermalProcessor()
        loaded = processor.load_matrix(synthetic_thermal_scene)
        assert loaded.shape == (120, 160)
        assert loaded.dtype == np.float32

        # Matriz não 2D deve falhar
        with pytest.raises(ValueError):
            processor.load_matrix(np.zeros((10, 10, 3)))

    def test_normalization_methods(self, synthetic_thermal_scene):
        processor = ThermalProcessor()

        # Percentile normalization
        norm_perc = processor.normalize(synthetic_thermal_scene, method="percentile")
        assert norm_perc.shape == (120, 160)
        assert norm_perc.dtype == np.uint8
        assert 0 <= np.min(norm_perc) <= np.max(norm_perc) <= 255

        # MinMax normalization
        norm_minmax = processor.normalize(synthetic_thermal_scene, method="minmax")
        assert norm_minmax.shape == (120, 160)
        assert norm_minmax.dtype == np.uint8

        # Matriz uniforme não causa divisão por zero
        flat = np.full((50, 50), 30.0, dtype=np.float32)
        norm_flat = processor.normalize(flat)
        assert norm_flat.shape == (50, 50)
        assert np.all(norm_flat == 0)

    def test_generate_heatmap_palettes(self, synthetic_thermal_scene):
        processor = ThermalProcessor()

        # Teste Ironbow
        hm_iron = processor.generate_heatmap(synthetic_thermal_scene, palette=PaletteType.IRONBOW)
        assert hm_iron.shape == (120, 160, 3)
        assert hm_iron.dtype == np.uint8

        # Teste Rainbow
        hm_rain = processor.generate_heatmap(synthetic_thermal_scene, palette=PaletteType.RAINBOW)
        assert hm_rain.shape == (120, 160, 3)

        # Teste White Hot
        hm_white = processor.generate_heatmap(synthetic_thermal_scene, palette=PaletteType.WHITE_HOT)
        assert hm_white.shape == (120, 160, 3)

        # Teste Black Hot
        hm_black = processor.generate_heatmap(synthetic_thermal_scene, palette=PaletteType.BLACK_HOT)
        assert hm_black.shape == (120, 160, 3)

    def test_overlay_colorbar(self, synthetic_thermal_scene):
        processor = ThermalProcessor()
        heatmap = processor.generate_heatmap(synthetic_thermal_scene)
        with_bar = processor.overlay_colorbar(heatmap, min_temp=25.0, max_temp=75.0, bar_width=40)

        # Altura deve ser a mesma, largura deve ser maior
        assert with_bar.shape[0] == 120
        assert with_bar.shape[1] > 160
        assert with_bar.shape[2] == 3

    def test_mark_hotspots(self, synthetic_thermal_scene):
        processor = ThermalProcessor()
        heatmap = processor.generate_heatmap(synthetic_thermal_scene)
        marked = processor.mark_hotspots(heatmap, points=[(80, 50)], temps=[72.5])
        assert marked.shape == heatmap.shape

    def test_apply_isotherm(self, synthetic_thermal_scene):
        processor = ThermalProcessor()
        heatmap = processor.generate_heatmap(synthetic_thermal_scene)
        # Destaca pixels acima de 65 °C
        isotherm = processor.apply_isotherm(heatmap, synthetic_thermal_scene, min_celsius=65.0, max_celsius=80.0)
        assert isotherm.shape == heatmap.shape

    def test_get_temperature_at(self, synthetic_thermal_scene):
        processor = ThermalProcessor()
        temp_hotspot = processor.get_temperature_at(synthetic_thermal_scene, x=80, y=50)
        assert pytest.approx(temp_hotspot, abs=0.1) == 72.5

        # Proteção contra coordenadas fora dos limites
        safe_temp = processor.get_temperature_at(synthetic_thermal_scene, x=9999, y=9999)
        assert isinstance(safe_temp, float)


class TestThermalAnalyzer:
    def test_calculate_delta_t_and_severity(self):
        analyzer = ThermalAnalyzer()

        # Caso crítico IEC (Delta >= 30 °C)
        dt_crit = analyzer.calculate_delta_t(t_target=72.0, t_reference=35.0)
        assert dt_crit.value == 37.0
        assert dt_crit.classify_iec_62446_3() == SeverityLevel.CRITICAL

        # Caso médio IEC (10 <= Delta < 30 °C)
        dt_med = analyzer.calculate_delta_t(t_target=50.0, t_reference=35.0)
        assert dt_med.value == 15.0
        assert dt_med.classify_iec_62446_3() == SeverityLevel.MEDIUM

        # Caso baixo IEC (3 <= Delta < 10 °C)
        dt_low = analyzer.calculate_delta_t(t_target=40.0, t_reference=35.0)
        assert dt_low.value == 5.0
        assert dt_low.classify_iec_62446_3() == SeverityLevel.LOW

    def test_analyze_full_matrix(self, synthetic_thermal_scene):
        analyzer = ThermalAnalyzer()
        metrics = analyzer.analyze_matrix(synthetic_thermal_scene)

        assert pytest.approx(metrics.max_temp, abs=0.1) == 72.5
        assert metrics.max_location == (80, 50)
        assert pytest.approx(metrics.median_temp, abs=0.5) == 35.0
        assert metrics.delta_t > 35.0
        assert metrics.severity == SeverityLevel.CRITICAL

    def test_analyze_region_with_bounding_box(self, synthetic_thermal_scene):
        analyzer = ThermalAnalyzer()

        # Bounding box ao redor do hotspot (normalizada [0, 1])
        # x em [70, 90] de 160 -> [0.4375, 0.5625]
        # y em [40, 60] de 120 -> [0.3333, 0.5000]
        bbox = BoundingBox(x_min=0.40, y_min=0.30, x_max=0.60, y_max=0.55, is_normalized=True)

        metrics = analyzer.analyze_region(synthetic_thermal_scene, bbox=bbox, ref_temp=35.0)
        assert pytest.approx(metrics.max_temp, abs=0.1) == 72.5
        assert metrics.max_location == (80, 50)  # Mapeado de volta para as coordenadas globais
        assert metrics.delta_t == 37.5
        assert metrics.severity == SeverityLevel.CRITICAL

    def test_find_hotspots_heuristics(self, synthetic_thermal_scene):
        analyzer = ThermalAnalyzer()
        hotspots = analyzer.find_hotspots(synthetic_thermal_scene, min_delta_celsius=6.0)

        assert len(hotspots) >= 1
        top_hotspot = hotspots[0]

        assert pytest.approx(top_hotspot["peak_temperature"], abs=0.5) == 72.5
        assert top_hotspot["severity"] == SeverityLevel.CRITICAL
        assert top_hotspot["peak_location"] == (80, 50)

    def test_compare_modules(self):
        analyzer = ThermalAnalyzer()
        # Módulo normal operando a 38 °C
        mod_normal = np.full((40, 40), 38.0, dtype=np.float32)
        # Módulo desconectado operando a 44 °C (+6 °C uniforme)
        mod_disconnected = np.full((40, 40), 44.0, dtype=np.float32)

        comparison = analyzer.compare_modules(mod_disconnected, mod_normal)
        assert comparison["delta_avg_celsius"] == 6.0
        assert comparison["possible_disconnected_module"] is True
        assert comparison["severity"] == SeverityLevel.LOW
