"""
Perfis de Calibração Radiométrica e Equações de Planck para Microbolômetros LWIR.
Implementa os modelos de conversão de contagem digital (Digital Count / Raw) para radiação física e temperatura (°C),
compatível com os sensores DJI Matrice 4T e câmeras radiométricas industriais.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict
import numpy as np


class SensorProfileType(str, Enum):
    """Perfis pré-configurados de sensores térmicos."""
    DJI_MATRICE_4T_HIGH_GAIN = "dji_m4t_high_gain"   # Faixa -20°C a 150°C (Alta sensibilidade - padrão solar)
    DJI_MATRICE_4T_LOW_GAIN = "dji_m4t_low_gain"     # Faixa 0°C a 500°C (Baixa sensibilidade - altas temperaturas)
    GENERIC_CENTIKELVIN = "generic_centikelvin"       # TIFF 16-bit em cK (K * 100)
    GENERIC_DECIKELVIN = "generic_decikelvin"         # TIFF 16-bit em dK (K * 10)
    CUSTOM = "custom"                                 # Parâmetros de calibração fornecidos manualmente


@dataclass
class CalibrationProfile:
    """
    Constantes de Calibração Radiométrica de Planck para sensores térmicos uncooled.
    
    Equação de Radiação direta (Temperatura K -> Radiação W):
        W(T) = R1 / (R2 * (exp(B / T) - F)) + O
        
    Equação inversa (Radiação W -> Temperatura K):
        T(W) = B / ln(R1 / (R2 * (W - O)) + F)
    """
    name: str
    r1: float
    r2: float
    b: float
    f: float
    o: float
    min_temp_celsius: float
    max_temp_celsius: float
    is_direct_kelvin: bool = False
    scale_factor: float = 1.0  # Fator divisor caso seja centi-kelvin (100.0) ou deci-kelvin (10.0)

    def temp_celsius_to_radiation(self, temp_celsius: float | np.ndarray) -> float | np.ndarray:
        """Converte temperatura em graus Celsius para radiação equivalente do corpo negro."""
        t_kelvin = np.maximum(100.0, np.array(temp_celsius, dtype=np.float64) + 273.15)
        
        if self.is_direct_kelvin:
            return t_kelvin

        denom = self.r2 * (np.exp(self.b / t_kelvin) - self.f)
        radiation = (self.r1 / denom) + self.o
        return radiation if isinstance(temp_celsius, np.ndarray) else float(radiation)

    def radiation_to_temp_celsius(self, radiation: float | np.ndarray) -> float | np.ndarray:
        """Converte radiação equivalente para temperatura física em graus Celsius."""
        if self.is_direct_kelvin:
            t_kelvin = np.array(radiation, dtype=np.float64)
            return t_kelvin - 273.15

        rad = np.array(radiation, dtype=np.float64)
        net_rad = np.maximum(1.0, rad - self.o)
        arg = (self.r1 / (self.r2 * net_rad)) + self.f
        arg = np.maximum(1.000001, arg)

        t_kelvin = self.b / np.log(arg)
        t_celsius = t_kelvin - 273.15
        return t_celsius if isinstance(radiation, np.ndarray) else float(t_celsius)


# Tabela oficial de perfis pré-calibrados
PROFILES: Dict[SensorProfileType, CalibrationProfile] = {
    # Constantes típicas da câmera LWIR do DJI Matrice 4T (modo High Gain para usinas fotovoltaicas)
    SensorProfileType.DJI_MATRICE_4T_HIGH_GAIN: CalibrationProfile(
        name="DJI Matrice 4T Thermal (High Gain)",
        r1=21106.77,
        r2=0.01254,
        b=1428.0,
        f=1.0,
        o=-100.0,
        min_temp_celsius=-20.0,
        max_temp_celsius=150.0,
    ),
    SensorProfileType.DJI_MATRICE_4T_LOW_GAIN: CalibrationProfile(
        name="DJI Matrice 4T Thermal (Low Gain)",
        r1=21106.77,
        r2=0.00285,
        b=1428.0,
        f=1.0,
        o=-50.0,
        min_temp_celsius=0.0,
        max_temp_celsius=500.0,
    ),
    SensorProfileType.GENERIC_CENTIKELVIN: CalibrationProfile(
        name="TIFF Radiométrico 16-bit (Centi-Kelvin)",
        r1=1.0, r2=1.0, b=1.0, f=1.0, o=0.0,
        min_temp_celsius=-40.0,
        max_temp_celsius=200.0,
        is_direct_kelvin=True,
        scale_factor=100.0,
    ),
    SensorProfileType.GENERIC_DECIKELVIN: CalibrationProfile(
        name="TIFF Radiométrico 16-bit (Deci-Kelvin)",
        r1=1.0, r2=1.0, b=1.0, f=1.0, o=0.0,
        min_temp_celsius=-40.0,
        max_temp_celsius=200.0,
        is_direct_kelvin=True,
        scale_factor=10.0,
    ),
}


class CalibrationProfileFactory:
    """Fábrica de obtenção e customização de perfis de calibração."""

    @staticmethod
    def get_profile(profile_type: SensorProfileType = SensorProfileType.DJI_MATRICE_4T_HIGH_GAIN) -> CalibrationProfile:
        return PROFILES.get(profile_type, PROFILES[SensorProfileType.DJI_MATRICE_4T_HIGH_GAIN])

    @staticmethod
    def create_custom_profile(
        name: str,
        r1: float,
        r2: float,
        b: float,
        f: float,
        o: float,
        min_temp: float = -20.0,
        max_temp: float = 150.0,
    ) -> CalibrationProfile:
        return CalibrationProfile(
            name=name,
            r1=r1,
            r2=r2,
            b=b,
            f=f,
            o=o,
            min_temp_celsius=min_temp,
            max_temp_celsius=max_temp,
            is_direct_kelvin=False,
        )
