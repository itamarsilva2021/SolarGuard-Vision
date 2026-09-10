"""
Testes unitários para a estrutura de dados ScientificThermalMatrix.
"""

import pytest
import numpy as np
from src.infrastructure.thermal.thermal_matrix import (
    ScientificThermalMatrix,
    RadiometricMetadata,
)
from src.domain.enums.severity_level import SeverityLevel


@pytest.fixture
def sample_scientific_matrix() -> ScientificThermalMatrix:
    # Matriz 10x10 com distribuição típica de módulo solar com hotspot
    data = np.full((10, 10), 40.0, dtype=np.float32)
    data[2:4, 2:4] = 65.0  # Hotspot de 25°C acima da média
    data[8, 8] = 30.0      # Ponto mais frio

    metadata = RadiometricMetadata(
        emissivity=0.93,
        reflected_temp_celsius=15.0,
        ambient_temp_celsius=28.0,
        atmospheric_transmittance=0.98,
        distance_meters=25.0,
        relative_humidity=0.50,
        sensor_profile="DJI Matrice 4T Thermal (High Gain)",
    )
    return ScientificThermalMatrix(data, metadata)


class TestScientificThermalMatrix:
    def test_dimensions_and_properties(self, sample_scientific_matrix):
        m = sample_scientific_matrix
        assert m.shape == (10, 10)
        assert m.width == 10
        assert m.height == 10
        assert m.min_temp == 30.0
        assert m.max_temp == 65.0
        assert 40.0 <= m.mean_temp <= 45.0

    def test_pixel_access(self, sample_scientific_matrix):
        m = sample_scientific_matrix
        assert m.get_temperature_at(2, 2) == 65.0
        assert m.get_temperature_at(0, 0) == 40.0
        assert m.get_temperature_at(8, 8) == 30.0

        with pytest.raises(IndexError):
            m.get_temperature_at(15, 15)

    def test_roi_slicing_preserves_metadata(self, sample_scientific_matrix):
        m = sample_scientific_matrix
        roi = m.get_roi(2, 2, 5, 5)
        assert roi.shape == (3, 3)
        assert roi.max_temp == 65.0
        assert roi.metadata.emissivity == 0.93

    def test_metrics_calculation_and_iec_severity(self, sample_scientific_matrix):
        m = sample_scientific_matrix
        metrics = m.calculate_metrics(reference_temp=40.0)

        assert metrics.max_temp == 65.0
        assert metrics.min_temp == 30.0
        assert metrics.delta_t == 25.0  # 65 - 40 = 25°C
        assert metrics.severity == SeverityLevel.MEDIUM  # 10 <= DeltaT < 30 -> Média

    def test_numpy_compatibility(self, sample_scientific_matrix):
        m = sample_scientific_matrix
        # Deve funcionar como array numpy diretamente
        mean = np.mean(m)
        assert 40.0 <= mean <= 45.0

    def test_gradient_magnitude_calculation(self, sample_scientific_matrix):
        m = sample_scientific_matrix
        grad = m.calculate_gradient_magnitude()
        assert grad.shape == (10, 10)
        # O gradiente deve ser alto na borda do hotspot (x=2, y=2)
        assert np.max(grad) > 10.0
