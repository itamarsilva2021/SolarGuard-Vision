"""
Modelo de Temperatura Aparente Refletida (T_refl) para Termografia Solar Fotovoltaica.
Em conformidade com as normas ISO 18434-1, ASTM E1862 e IEC TS 62446-3.
Permite compensar a radiação de fundo refletida pelo vidro fotovoltaico (especialmente a abóbada celeste).
"""

from enum import Enum
from typing import Optional
import math


class SkyCondition(str, Enum):
    """Condições da abóbada celeste e de fundo durante a captura termográfica."""
    CLEAR_SKY = "clear_sky"              # Céu limpo / sem nuvens (forte depressão térmica do céu)
    PARTLY_CLOUDY = "partly_cloudy"      # Parcialmente nublado
    OVERCAST = "overcast"                # Céu totalmente encoberto (nuvens baixas e densas)
    MEASURED_REFLECTOR = "measured"      # Medição direta via método do refletor difuso (folha de alumínio corrugada)


class ReflectedTemperatureModel:
    """
    Calcula e compensa a Temperatura Aparente Refletida (T_refl / Background Temperature).
    
    Como o vidro fotovoltaico tem refletância térmica de aproximadamente 7% a 10% (1 - emissividade),
    a câmera termográfica recebe parte da radiação refletida do céu. Em dias de céu limpo,
    a temperatura aparente do céu (T_sky) pode ser de 15°C a 30°C inferior à temperatura ambiente,
    o que subestima a temperatura real do módulo se não for compensada adequadamente.
    """

    @staticmethod
    def estimate_sky_temperature(
        ambient_temp_celsius: float,
        sky_condition: SkyCondition = SkyCondition.CLEAR_SKY,
        relative_humidity: float = 0.50,
    ) -> float:
        """
        Estima a temperatura radiométrica aparente do céu (T_sky) com base em modelos atmosféricos
        (Swinbank / Idso-Jackson adaptados para termografia em 8 - 14 um).
        
        :param ambient_temp_celsius: Temperatura do ar ambiente no local do voo (°C).
        :param sky_condition: Condição da cobertura de nuvens.
        :param relative_humidity: Umidade relativa do ar (0.0 a 1.0).
        :return: Temperatura refletida estimada em °C.
        """
        t_amb_k = ambient_temp_celsius + 273.15

        if sky_condition == SkyCondition.OVERCAST:
            # Em céu encoberto, a base das nuvens atua como um corpo negro próximo da temperatura do ar
            # T_refl fica apenas de 2°C a 4°C abaixo da temperatura ambiente
            t_refl_celsius = ambient_temp_celsius - 3.0

        elif sky_condition == SkyCondition.PARTLY_CLOUDY:
            # Mistura de céu limpo com nuvens
            t_refl_celsius = ambient_temp_celsius - 12.0

        elif sky_condition == SkyCondition.CLEAR_SKY:
            # Modelo de Swinbank para céu limpo com correção por umidade
            # Emissividade efetiva da atmosfera clara: eps_sky ~ 0.72 + 0.005 * (RH * 100)
            eps_sky = min(0.85, max(0.65, 0.70 + 0.002 * (relative_humidity * 100.0)))
            t_sky_k = t_amb_k * (eps_sky ** 0.25)
            t_refl_celsius = t_sky_k - 273.15

        else:
            t_refl_celsius = ambient_temp_celsius

        return round(float(t_refl_celsius), 2)

    @classmethod
    def resolve_reflected_temperature(
        cls,
        ambient_temp_celsius: float,
        custom_reflected_celsius: Optional[float] = None,
        sky_condition: SkyCondition = SkyCondition.CLEAR_SKY,
        relative_humidity: float = 0.50,
    ) -> float:
        """
        Resolve a temperatura refletida final: utiliza o valor medido manualmente se fornecido,
        caso contrário aplica a estimativa científica pelo modelo de céu.
        
        :param ambient_temp_celsius: Temperatura do ar ambiente (°C).
        :param custom_reflected_celsius: Valor obtido pelo método do refletor calibrado (°C).
        :param sky_condition: Condição do céu.
        :param relative_humidity: Umidade relativa (0.0 a 1.0).
        :return: Temperatura refletida a ser empregada na equação de calibração radiométrica (°C).
        """
        if custom_reflected_celsius is not None:
            if not (-50.0 <= custom_reflected_celsius <= 150.0):
                raise ValueError(f"Temperatura refletida customizada inválida: {custom_reflected_celsius}°C")
            return round(float(custom_reflected_celsius), 2)

        return cls.estimate_sky_temperature(
            ambient_temp_celsius=ambient_temp_celsius,
            sky_condition=sky_condition,
            relative_humidity=relative_humidity,
        )
