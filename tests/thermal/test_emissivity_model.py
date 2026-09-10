"""
Testes unitários para o modelo de emissividade com correção angular.
"""

import pytest
from src.infrastructure.thermal.emissivity_model import (
    EmissivityModel,
    MaterialType,
    DEFAULT_EMISSIVITIES,
)


class TestEmissivityModel:
    def test_default_emissivities_exist_for_all_materials(self):
        for mat in MaterialType:
            if mat != MaterialType.CUSTOM:
                eps = EmissivityModel.get_base_emissivity(mat)
                assert 0.5 <= eps <= 1.0
                assert eps == DEFAULT_EMISSIVITIES[mat]

    def test_custom_emissivity_validation(self):
        custom_eps = EmissivityModel.get_base_emissivity(MaterialType.CUSTOM, custom_value=0.88)
        assert custom_eps == 0.88

        with pytest.raises(ValueError):
            EmissivityModel.get_base_emissivity(MaterialType.CUSTOM, custom_value=None)

        with pytest.raises(ValueError):
            EmissivityModel.get_base_emissivity(MaterialType.CUSTOM, custom_value=1.5)

    def test_angular_correction_near_normal(self):
        # Ângulos de 0° a 30° praticamente não devem alterar a emissividade do vidro
        eps_0 = EmissivityModel.calculate_angular_emissivity(0.93, angle_degrees=0.0)
        eps_15 = EmissivityModel.calculate_angular_emissivity(0.93, angle_degrees=15.0)
        eps_30 = EmissivityModel.calculate_angular_emissivity(0.93, angle_degrees=30.0)

        assert eps_0 == 0.93
        assert abs(eps_0 - eps_15) < 0.01
        assert abs(eps_0 - eps_30) < 0.02

    def test_angular_correction_steep_angles(self):
        # Ângulos superiores a 45° devem reduzir a emissividade devido à reflexão de Fresnel
        eps_normal = EmissivityModel.calculate_angular_emissivity(0.93, angle_degrees=0.0)
        eps_60 = EmissivityModel.calculate_angular_emissivity(0.93, angle_degrees=60.0)
        eps_75 = EmissivityModel.calculate_angular_emissivity(0.93, angle_degrees=75.0)

        assert eps_60 < eps_normal
        assert eps_75 < eps_60
        assert eps_75 > 0.40  # Limite físico

    def test_evaluate_helper(self):
        result = EmissivityModel.evaluate(
            material=MaterialType.PV_GLASS_CLEAN,
            view_angle_degrees=20.0,
        )
        assert 0.90 <= result <= 0.93
