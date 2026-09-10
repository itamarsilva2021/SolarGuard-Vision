"""
Módulo de Engenharia Térmica e Radiometria - SolarGuard Vision.
Exporta o processador de imagens térmicas (ThermalProcessor) e o analisador quantitativo (ThermalAnalyzer).
"""

from src.infrastructure.thermal.thermal_processor import ThermalProcessor
from src.infrastructure.thermal.thermal_analyzer import ThermalAnalyzer
from src.domain.value_objects.thermal_metrics import ThermalMetrics

# Camada Científica de Radiometria (Etapa 11B)
from src.infrastructure.thermal.emissivity_model import EmissivityModel, MaterialType
from src.infrastructure.thermal.reflected_temperature import ReflectedTemperatureModel, SkyCondition
from src.infrastructure.thermal.atmospheric_compensation import AtmosphericCompensation
from src.infrastructure.thermal.calibration_profiles import (
    CalibrationProfile,
    CalibrationProfileFactory,
    SensorProfileType,
)
from src.infrastructure.thermal.thermal_matrix import ScientificThermalMatrix, RadiometricMetadata
from src.infrastructure.thermal.radiometry_engine import RadiometryEngine

__all__ = [
    "ThermalProcessor",
    "ThermalAnalyzer",
    "ThermalMetrics",
    "EmissivityModel",
    "MaterialType",
    "ReflectedTemperatureModel",
    "SkyCondition",
    "AtmosphericCompensation",
    "CalibrationProfile",
    "CalibrationProfileFactory",
    "SensorProfileType",
    "ScientificThermalMatrix",
    "RadiometricMetadata",
    "RadiometryEngine",
]
