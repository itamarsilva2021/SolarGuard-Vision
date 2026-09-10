"""
Testes unitários para perfis de calibração e equações de Planck.
"""

import pytest
import numpy as np
from src.infrastructure.thermal.calibration_profiles import (
    CalibrationProfileFactory,
    SensorProfileType,
)


class TestCalibrationProfiles:
    def test_default_profiles_exist(self):
        m4t_high = CalibrationProfileFactory.get_profile(SensorProfileType.DJI_MATRICE_4T_HIGH_GAIN)
        assert m4t_high.min_temp_celsius == -20.0
        assert m4t_high.max_temp_celsius == 150.0

        m4t_low = CalibrationProfileFactory.get_profile(SensorProfileType.DJI_MATRICE_4T_LOW_GAIN)
        assert m4t_low.max_temp_celsius == 500.0

    def test_planck_roundtrip_precision_scalar(self):
        # A transformação T -> Radiação -> T deve ter precisão sub-miliKelvin
        profile = CalibrationProfileFactory.get_profile(SensorProfileType.DJI_MATRICE_4T_HIGH_GAIN)

        test_temperatures = [-10.0, 0.0, 25.0, 45.0, 75.0, 110.0]
        for original_t in test_temperatures:
            rad = profile.temp_celsius_to_radiation(original_t)
            recovered_t = profile.radiation_to_temp_celsius(rad)
            assert abs(original_t - recovered_t) < 0.001

    def test_planck_roundtrip_precision_array(self):
        profile = CalibrationProfileFactory.get_profile(SensorProfileType.DJI_MATRICE_4T_HIGH_GAIN)
        matrix = np.array([
            [25.0, 30.0, 45.5],
            [50.0, 65.2, 80.0],
        ], dtype=np.float32)

        rad_matrix = profile.temp_celsius_to_radiation(matrix)
        recovered = profile.radiation_to_temp_celsius(rad_matrix)

        np.testing.assert_allclose(matrix, recovered, atol=0.001)

    def test_custom_profile_creation(self):
        custom = CalibrationProfileFactory.create_custom_profile(
            name="Custom Sensor Test",
            r1=20000.0,
            r2=0.01,
            b=1400.0,
            f=1.0,
            o=-50.0,
        )
        assert custom.name == "Custom Sensor Test"
        rad = custom.temp_celsius_to_radiation(50.0)
        rec = custom.radiation_to_temp_celsius(rad)
        assert abs(50.0 - rec) < 0.001
