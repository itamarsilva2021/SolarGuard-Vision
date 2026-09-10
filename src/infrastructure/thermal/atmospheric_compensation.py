"""
Módulo de Compensação Atmosférica para Termografia Aérea com Drones (LWIR 8 - 14 um).
Calcula a transmitância atmosférica (tau_atm) e a emissão do ar ao longo do caminho óptico entre o drone e o módulo fotovoltaico.
Em conformidade com os modelos radiométricos de Passman-Larmore e FLIR/DJI.
"""

import math
from typing import Tuple


class AtmosphericCompensation:
    """
    Calcula a transmitância da atmosfera (tau) e a contribuição radiativa do ar em função de:
    - Distância do voo (altitude relativa / distância oblíqua em metros).
    - Temperatura do ar ambiente (°C).
    - Umidade relativa do ar (0.0 a 1.0).
    """

    @staticmethod
    def calculate_water_vapor_content(ambient_temp_celsius: float, relative_humidity: float) -> float:
        """
        Calcula a densidade absoluta de vapor d'água na atmosfera (omega em g/m³).
        Utiliza a equação de Magnus-Tetens para pressão de saturação.
        
        :param ambient_temp_celsius: Temperatura ambiente (°C).
        :param relative_humidity: Umidade relativa (0.0 a 1.0).
        :return: Massa de vapor de água por volume de ar (g/m³).
        """
        t = ambient_temp_celsius
        rh = max(0.01, min(1.0, relative_humidity))

        # Pressão de vapor saturado (hPa / mbar)
        p_sat = 6.1078 * (10.0 ** ((7.5 * t) / (237.3 + t)))

        # Pressão parcial de vapor real
        p_v = rh * p_sat

        # Densidade de vapor (g/m³) pela equação de estado dos gases ideais
        t_kelvin = t + 273.15
        omega = (p_v * 216.7) / t_kelvin
        return max(0.1, float(omega))

    @classmethod
    def calculate_transmittance(
        cls,
        distance_meters: float,
        ambient_temp_celsius: float = 28.0,
        relative_humidity: float = 0.50,
    ) -> float:
        """
        Calcula o fator de transmitância da atmosfera (tau_atm) na banda LWIR (8 - 14 um).
        
        Para voos de drone (distâncias típicas de 10m a 100m):
        A transmitância situa-se tipicamente entre 0.94 e 0.99, variando conforme a umidade e temperatura.
        
        :param distance_meters: Distância entre o sensor do drone e a usina solar (m).
        :param ambient_temp_celsius: Temperatura ambiente (°C).
        :param relative_humidity: Umidade relativa do ar (0.0 a 1.0).
        :return: Coeficiente de transmitância atmosférica no intervalo (0.0, 1.0].
        """
        d = max(0.5, float(distance_meters))
        omega = cls.calculate_water_vapor_content(ambient_temp_celsius, relative_humidity)

        # Coeficientes empíricos calibrados para a janela espectral LWIR de 8 - 14 um
        k_path = 0.0065
        k_vapor = 0.0035

        # Modelo exponencial de extinção óptica por dispersão e absorção de vapor
        exponent = -math.sqrt(d) * (k_path + k_vapor * math.sqrt(omega))
        tau = math.exp(exponent)

        # Garante limites físicos estáveis
        return round(float(max(0.70, min(1.0, tau))), 4)

    @classmethod
    def get_atmospheric_parameters(
        cls,
        distance_meters: float,
        ambient_temp_celsius: float,
        relative_humidity: float,
    ) -> Tuple[float, float]:
        """
        Retorna tanto a transmitância calculada quanto a temperatura radiante da atmosfera.
        
        :return: Tupla (tau_atm, t_atm_celsius).
        """
        tau = cls.calculate_transmittance(distance_meters, ambient_temp_celsius, relative_humidity)
        # A atmosfera próxima emite em equilíbrio com a temperatura do ar ambiente
        return tau, round(float(ambient_temp_celsius), 2)
