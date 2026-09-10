"""
Testes unitários para compensação atmosférica e cálculo de transmitância.
"""

import pytest
from src.infrastructure.thermal.atmospheric_compensation import AtmosphericCompensation


class TestAtmosphericCompensation:
    def test_water_vapor_content_calculation(self):
        # Ar a 30°C com 60% de umidade deve ter densidade de vapor plausível (~18 g/m³)
        omega = AtmosphericCompensation.calculate_water_vapor_content(
            ambient_temp_celsius=30.0,
            relative_humidity=0.60,
        )
        assert 10.0 <= omega <= 25.0

    def test_transmittance_decreases_with_distance(self):
        # Transmitância deve cair monotonamente com a distância
        tau_10m = AtmosphericCompensation.calculate_transmittance(distance_meters=10.0)
        tau_30m = AtmosphericCompensation.calculate_transmittance(distance_meters=30.0)
        tau_70m = AtmosphericCompensation.calculate_transmittance(distance_meters=70.0)

        assert 0.90 <= tau_10m <= 1.0
        assert tau_30m < tau_10m
        assert tau_70m < tau_30m
        assert tau_70m > 0.70

    def test_transmittance_decreases_with_higher_humidity(self):
        # Umidade maior aumenta absorção por vapor de água
        tau_dry = AtmosphericCompensation.calculate_transmittance(
            distance_meters=50.0,
            ambient_temp_celsius=30.0,
            relative_humidity=0.20,
        )
        tau_humid = AtmosphericCompensation.calculate_transmittance(
            distance_meters=50.0,
            ambient_temp_celsius=30.0,
            relative_humidity=0.90,
        )

        assert tau_humid < tau_dry

    def test_get_atmospheric_parameters_tuple(self):
        tau, t_atm = AtmosphericCompensation.get_atmospheric_parameters(
            distance_meters=25.0,
            ambient_temp_celsius=29.5,
            relative_humidity=0.55,
        )
        assert 0.90 <= tau <= 1.0
        assert t_atm == 29.5
