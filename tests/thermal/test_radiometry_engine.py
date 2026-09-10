"""
Testes unitários e de integração para o motor radiométrico RadiometryEngine.
"""

import pytest
import numpy as np
from src.infrastructure.thermal.radiometry_engine import RadiometryEngine
from src.infrastructure.thermal.emissivity_model import MaterialType
from src.infrastructure.thermal.reflected_temperature import SkyCondition
from src.infrastructure.thermal.thermal_processor import ThermalProcessor
from src.infrastructure.thermal.thermal_analyzer import ThermalAnalyzer
from src.domain.enums.severity_level import SeverityLevel


class TestRadiometryEngine:
    def test_full_calibration_pipeline(self):
        engine = RadiometryEngine()
        raw_matrix = np.full((20, 20), 45.0, dtype=np.float32)
        raw_matrix[5:8, 5:8] = 72.0  # Ponto quente

        res = engine.calibrate_matrix(
            raw_apparent_matrix=raw_matrix,
            distance_meters=30.0,
            ambient_temp_celsius=30.0,
            relative_humidity=0.60,
            material=MaterialType.PV_GLASS_CLEAN,
            sky_condition=SkyCondition.CLEAR_SKY,
        )

        assert res.is_success is True
        sci_matrix = res.value
        assert sci_matrix.shape == (20, 20)
        assert sci_matrix.metadata.emissivity > 0.90
        assert sci_matrix.metadata.atmospheric_transmittance < 1.0

        # Temperatura corrigida deve ser fisicamente plausível
        assert 40.0 <= sci_matrix.min_temp <= 50.0
        assert sci_matrix.max_temp >= 70.0

    def test_emissivity_physical_effect(self):
        """
        Física da radiação: Para a mesma leitura aparente com céu frio,
        um material com menor emissividade necessita de temperatura real MAIOR
        para gerar a mesma radiância aparente total.
        """
        engine = RadiometryEngine()
        apparent = np.full((5, 5), 50.0, dtype=np.float32)

        # 1. Com alta emissividade (0.98)
        res_high_eps = engine.calibrate_matrix(
            raw_apparent_matrix=apparent,
            ambient_temp_celsius=25.0,
            custom_emissivity=0.98,
            custom_reflected_celsius=10.0,  # Céu frio
        )
        assert res_high_eps.is_success is True

        # 2. Com menor emissividade (0.85)
        res_low_eps = engine.calibrate_matrix(
            raw_apparent_matrix=apparent,
            ambient_temp_celsius=25.0,
            custom_emissivity=0.85,
            custom_reflected_celsius=10.0,  # Céu frio
        )
        assert res_low_eps.is_success is True

        t_obj_high_eps = res_high_eps.value.mean_temp
        t_obj_low_eps = res_low_eps.value.mean_temp

        # A temperatura corrigida para baixa emissividade deve ser maior que para alta emissividade
        assert t_obj_low_eps > t_obj_high_eps

    def test_raw_16bit_tiff_calibration(self):
        engine = RadiometryEngine()
        # Matriz 16-bit simulando centi-Kelvin (30315 cK = 303.15 K = 30.0 °C)
        raw_16bit = np.full((15, 15), 30315, dtype=np.uint16)
        raw_16bit[3, 3] = 34315  # 343.15 K = 70.0 °C

        res = engine.calibrate_raw_16bit_tiff(
            raw_16bit=raw_16bit,
            distance_meters=20.0,
            ambient_temp_celsius=25.0,
        )

        assert res.is_success is True
        sci_matrix = res.value
        assert abs(sci_matrix.get_temperature_at(0, 0) - 30.0) < 5.0
        assert sci_matrix.get_temperature_at(3, 3) > 65.0

    def test_compatibility_with_existing_thermal_processor_and_analyzer(self):
        """
        Garante que a nova ScientificThermalMatrix se integra sem atrito
        com os módulos estáveis ThermalProcessor e ThermalAnalyzer.
        """
        engine = RadiometryEngine()
        raw = np.full((12, 12), 40.0, dtype=np.float32)
        raw[2:5, 2:5] = 75.0  # Defeito

        res = engine.calibrate_matrix(raw)
        assert res.is_success is True
        sci_matrix = res.value

        # 1. Compatibilidade com ThermalProcessor (passando o objeto diretamente como ndarray)
        processor = ThermalProcessor()
        loaded = processor.load_matrix(sci_matrix)
        assert loaded.shape == (12, 12)

        # Normalização
        normalized = processor.normalize(sci_matrix, method="minmax")
        assert normalized.dtype == np.uint8
        assert normalized.shape == (12, 12)

        # 2. Compatibilidade com ThermalAnalyzer
        analyzer = ThermalAnalyzer()
        metrics = analyzer.analyze_matrix(sci_matrix)
        assert metrics.max_temp >= 70.0
        assert metrics.severity == SeverityLevel.CRITICAL
