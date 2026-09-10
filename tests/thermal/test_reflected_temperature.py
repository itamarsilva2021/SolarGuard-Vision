"""
Testes unitários para o modelo de temperatura aparente refletida.
"""

import pytest
from src.infrastructure.thermal.reflected_temperature import (
    ReflectedTemperatureModel,
    SkyCondition,
)


class TestReflectedTemperatureModel:
    def test_clear_sky_temperature_depression(self):
        # Em céu limpo, T_refl deve ser significativamente menor que a temperatura ambiente
        t_amb = 30.0
        t_refl = ReflectedTemperatureModel.estimate_sky_temperature(
            ambient_temp_celsius=t_amb,
            sky_condition=SkyCondition.CLEAR_SKY,
            relative_humidity=0.50,
        )

        assert t_refl < t_amb
        # Depressão térmica do céu limpo típica: entre 10°C e 30°C
        depression = t_amb - t_refl
        assert 10.0 <= depression <= 35.0

    def test_overcast_sky_temperature(self):
        # Em dia totalmente encoberto, a base das nuvens emite próximo à temperatura do ar
        t_amb = 25.0
        t_refl = ReflectedTemperatureModel.estimate_sky_temperature(
            ambient_temp_celsius=t_amb,
            sky_condition=SkyCondition.OVERCAST,
        )

        assert t_refl < t_amb
        assert abs(t_amb - t_refl) <= 5.0

    def test_resolve_reflected_temperature_with_custom_override(self):
        # Quando o operador fornece a medição direta com refletor, o modelo deve honrar exatamente
        resolved = ReflectedTemperatureModel.resolve_reflected_temperature(
            ambient_temp_celsius=30.0,
            custom_reflected_celsius=14.5,
        )
        assert resolved == 14.5

    def test_invalid_custom_reflected_temperature_raises_error(self):
        with pytest.raises(ValueError):
            ReflectedTemperatureModel.resolve_reflected_temperature(
                ambient_temp_celsius=30.0,
                custom_reflected_celsius=250.0,  # Valor fisicamente absurdo
            )
