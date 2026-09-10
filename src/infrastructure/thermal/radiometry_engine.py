"""
Motor Científico de Radiometria e Compensação Térmica (RadiometryEngine).
Implementa a resolução completa da equação fundamental da termografia:
    W_tot = eps * tau * W_obj + (1 - eps) * tau * W_refl + (1 - tau) * W_atm
Isolando a radiação e temperatura reais da célula/módulo fotovoltaico:
    W_obj = [W_tot - (1 - eps) * tau * W_refl - (1 - tau) * W_atm] / (eps * tau)
"""

from typing import Optional, Union, Tuple
from pathlib import Path
import numpy as np

from src.core.result import Result, Success, Failure
from src.core.logger import get_logger
from src.infrastructure.thermal.emissivity_model import EmissivityModel, MaterialType
from src.infrastructure.thermal.reflected_temperature import ReflectedTemperatureModel, SkyCondition
from src.infrastructure.thermal.atmospheric_compensation import AtmosphericCompensation
from src.infrastructure.thermal.calibration_profiles import (
    CalibrationProfile,
    CalibrationProfileFactory,
    SensorProfileType,
)
from src.infrastructure.thermal.thermal_matrix import ScientificThermalMatrix, RadiometricMetadata

logger = get_logger("RadiometryEngine")


class RadiometryEngine:
    """
    Motor radiométrico de alta precisão para correção atmosférica, reflexão e emissividade.
    Processa matrizes brutas do DJI Matrice 4T e arquivos TIFF radiométricos de 16-bits.
    """

    def __init__(
        self,
        default_profile_type: SensorProfileType = SensorProfileType.DJI_MATRICE_4T_HIGH_GAIN,
        emissivity_model: Optional[EmissivityModel] = None,
        reflected_model: Optional[ReflectedTemperatureModel] = None,
        atmospheric_model: Optional[AtmosphericCompensation] = None,
    ) -> None:
        self.profile = CalibrationProfileFactory.get_profile(default_profile_type)
        self.emissivity_model = emissivity_model or EmissivityModel()
        self.reflected_model = reflected_model or ReflectedTemperatureModel()
        self.atmospheric_model = atmospheric_model or AtmosphericCompensation()

    def set_sensor_profile(self, profile: Union[SensorProfileType, CalibrationProfile]) -> None:
        """Configura o perfil do sensor de aquisição."""
        if isinstance(profile, SensorProfileType):
            self.profile = CalibrationProfileFactory.get_profile(profile)
        else:
            self.profile = profile
        logger.info(f"Perfil radiométrico ativo: {self.profile.name}")

    def calibrate_matrix(
        self,
        raw_apparent_matrix: np.ndarray,
        distance_meters: float = 25.0,
        ambient_temp_celsius: float = 28.0,
        relative_humidity: float = 0.50,
        material: MaterialType = MaterialType.PV_GLASS_CLEAN,
        view_angle_degrees: float = 0.0,
        custom_emissivity: Optional[float] = None,
        custom_reflected_celsius: Optional[float] = None,
        sky_condition: SkyCondition = SkyCondition.CLEAR_SKY,
    ) -> Result[ScientificThermalMatrix, str]:
        """
        Executa a calibração radiométrica completa de uma matriz térmica 2D.
        
        :param raw_apparent_matrix: Matriz 2D float32 de temperaturas aparentes ou valores de sensor (°C).
        :param distance_meters: Distância entre a câmera e o painel solar (altitude/slant range).
        :param ambient_temp_celsius: Temperatura ambiente do ar (°C).
        :param relative_humidity: Umidade relativa do ar (0.0 a 1.0).
        :param material: Material da superfície para cálculo de emissividade.
        :param view_angle_degrees: Ângulo de inclinação da visada do drone em relação à normal.
        :param custom_emissivity: Emissividade manual opcional (sobrepõe cálculo por material).
        :param custom_reflected_celsius: Temperatura refletida manual opcional (método do refletor).
        :param sky_condition: Condição do céu para cálculo da temperatura aparente refletida.
        :return: Result contendo a ScientificThermalMatrix calibrada ou mensagem de falha.
        """
        if raw_apparent_matrix is None or raw_apparent_matrix.ndim != 2:
            return Failure("A matriz de entrada deve ser um array bidimensional (2D) não-nulo.")

        try:
            # 1. Avaliação da Emissividade Efetiva com Correção Angular
            if custom_emissivity is not None:
                eps = float(custom_emissivity)
                if not (0.01 <= eps <= 1.0):
                    return Failure(f"Emissividade customizada inválida: {custom_emissivity}")
            else:
                eps = self.emissivity_model.evaluate(
                    material=material,
                    view_angle_degrees=view_angle_degrees,
                )

            # 2. Resolução da Temperatura Aparente Refletida (T_refl)
            t_refl = self.reflected_model.resolve_reflected_temperature(
                ambient_temp_celsius=ambient_temp_celsius,
                custom_reflected_celsius=custom_reflected_celsius,
                sky_condition=sky_condition,
                relative_humidity=relative_humidity,
            )

            # 3. Cálculo da Transmitância Atmosférica (tau_atm)
            tau, t_atm = self.atmospheric_model.get_atmospheric_parameters(
                distance_meters=distance_meters,
                ambient_temp_celsius=ambient_temp_celsius,
                relative_humidity=relative_humidity,
            )

            # 4. Solução da Equação Radiométrica Inversa de Radiação
            # Converte as temperaturas componentes para fluxos radiativos equivalentes
            w_tot = self.profile.temp_celsius_to_radiation(raw_apparent_matrix)
            w_refl = self.profile.temp_celsius_to_radiation(t_refl)
            w_atm = self.profile.temp_celsius_to_radiation(t_atm)

            # Radiação emitida unicamente pelo objeto fotovoltaico:
            # W_obj = [W_tot - (1 - eps) * tau * W_refl - (1 - tau) * W_atm] / (eps * tau)
            numerator = w_tot - ((1.0 - eps) * tau * w_refl) - ((1.0 - tau) * w_atm)
            denominator = eps * tau

            w_obj = numerator / denominator

            # Inverte o fluxo radiativo para temperatura física em graus Celsius (°C)
            calibrated_celsius = self.profile.radiation_to_temp_celsius(w_obj)

            # Aplica arredondamento de precisão (duas casas decimais)
            calibrated_celsius = np.round(calibrated_celsius, 2).astype(np.float32)

            # 5. Encapsulamento na estrutura científica com metadados completos
            metadata = RadiometricMetadata(
                emissivity=eps,
                reflected_temp_celsius=t_refl,
                ambient_temp_celsius=round(float(ambient_temp_celsius), 2),
                atmospheric_transmittance=tau,
                distance_meters=round(float(distance_meters), 1),
                relative_humidity=round(float(relative_humidity), 2),
                sensor_profile=self.profile.name,
            )

            result_matrix = ScientificThermalMatrix(calibrated_celsius, metadata)
            return Success(result_matrix)

        except Exception as ex:
            logger.error(f"Erro durante a calibração radiométrica da matriz: {ex}", exc_info=True)
            return Failure(f"Falha na calibração radiométrica: {str(ex)}")

    def calibrate_raw_16bit_tiff(
        self,
        raw_16bit: np.ndarray,
        distance_meters: float = 25.0,
        ambient_temp_celsius: float = 28.0,
        relative_humidity: float = 0.50,
        material: MaterialType = MaterialType.PV_GLASS_CLEAN,
    ) -> Result[ScientificThermalMatrix, str]:
        """
        Calibra uma matriz bruta uint16 originada de TIFF radiométrico (centi-Kelvin ou deci-Kelvin).
        """
        if raw_16bit.dtype != np.uint16:
            return Failure(f"A matriz esperada deve ser uint16. Recebido: {raw_16bit.dtype}")

        raw_float = raw_16bit.astype(np.float32)
        mean_val = float(np.mean(raw_float))

        if mean_val > 10_000:
            # Centi-Kelvin: 30000 -> 300.0 K -> 26.85 °C
            apparent_celsius = (raw_float / 100.0) - 273.15
        elif mean_val > 1_000:
            # Deci-Kelvin: 3000 -> 300.0 K -> 26.85 °C
            apparent_celsius = (raw_float / 10.0) - 273.15
        else:
            apparent_celsius = 20.0 + (raw_float / (np.max(raw_float) or 1.0)) * 60.0

        return self.calibrate_matrix(
            raw_apparent_matrix=apparent_celsius,
            distance_meters=distance_meters,
            ambient_temp_celsius=ambient_temp_celsius,
            relative_humidity=relative_humidity,
            material=material,
        )
