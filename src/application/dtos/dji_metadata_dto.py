"""
DTOs padronizados para telemetria, posicionamento RTK, parâmetros de câmera
e radiometria do drone DJI Matrice 4T.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class RtkStatus(str, Enum):
    """Status de fixação do sistema RTK da DJI."""
    NONE = "none"           # Flag 0: GPS autônomo comum (sem RTK)
    FLOAT = "float"         # Flag 16: Solução flutuante (submétrica)
    FIXED = "fixed"         # Flag 50: Solução fixa inteira (centimétrica)

    @property
    def is_precise(self) -> bool:
        """Indica se a medição possui precisão centimétrica (RTK Fixed)."""
        return self == RtkStatus.FIXED


class ThermalGainMode(str, Enum):
    """Modos de sensibilidade e ganho do sensor térmico do Matrice 4T."""
    HIGH_GAIN = "high_gain"   # -20°C a +150°C (alta resolução e contraste)
    LOW_GAIN = "low_gain"     # 0°C a +500°C (para temperaturas extremas)
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RtkTelemetryDTO:
    """Telemetria de precisão diferencial RTK."""
    status: RtkStatus = RtkStatus.NONE
    flag: int = 0
    std_latitude_meters: Optional[float] = None
    std_longitude_meters: Optional[float] = None
    std_altitude_meters: Optional[float] = None
    diff_age_seconds: Optional[float] = None

    @property
    def is_precise(self) -> bool:
        """Indica se a solução RTK possui precisão centimétrica (RTK Fixed)."""
        return self.status.is_precise

    @property
    def horizontal_accuracy_meters(self) -> Optional[float]:
        """Calcula a precisão horizontal (1 sigma 2D RMS) em metros."""
        if self.std_latitude_meters is not None and self.std_longitude_meters is not None:
            return round((self.std_latitude_meters ** 2 + self.std_longitude_meters ** 2) ** 0.5, 4)
        return None

    @property
    def vertical_accuracy_meters(self) -> Optional[float]:
        """Retorna a precisão vertical em metros."""
        return self.std_altitude_meters


@dataclass(frozen=True)
class FlightOrientationDTO:
    """Orientação angular 3D da aeronave e do gimbal em graus [-180, +180]."""
    # Gimbal (mira da câmera)
    gimbal_pitch: Optional[float] = None  # -90° = Nadir
    gimbal_roll: Optional[float] = None   # Estabilização horizontal
    gimbal_yaw: Optional[float] = None    # Azimute em relação ao Norte
    # Aeronave (corpo do drone)
    flight_pitch: Optional[float] = None
    flight_roll: Optional[float] = None
    flight_yaw: Optional[float] = None


@dataclass(frozen=True)
class RadiometricFlightParamsDTO:
    """Parâmetros radiométricos e ambientais configurados no DJI Pilot 2."""
    emissivity: float = 0.95
    reflected_temp_celsius: float = 25.0
    ambient_temp_celsius: float = 28.0
    relative_humidity: float = 0.50
    target_distance_meters: float = 25.0
    gain_mode: ThermalGainMode = ThermalGainMode.HIGH_GAIN


@dataclass(frozen=True)
class CameraSensorDTO:
    """Identificação e parâmetros ópticos da câmera DJI."""
    drone_model: Optional[str] = "Matrice 4T"
    drone_serial_number: Optional[str] = None
    camera_serial_number: Optional[str] = None
    camera_type: Optional[str] = "Thermal"
    is_thermal_lens: bool = True
    focal_length_mm: Optional[float] = None
    focal_length_35mm: Optional[float] = None
    calibrated_focal_length_px: Optional[float] = None
    optical_center_x: Optional[float] = None
    optical_center_y: Optional[float] = None
    dewarp_data: Optional[str] = None


@dataclass
class DjiParsedMetadataDTO:
    """DTO padronizado e consolidado de metadados extraídos de imagens DJI."""
    file_name: str
    file_path: str
    width: int
    height: int
    captured_at: Optional[datetime]
    # Posicionamento Geodésico
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    relative_altitude_meters: Optional[float] = None
    absolute_altitude_meters: Optional[float] = None
    # Módulos especializados
    rtk: RtkTelemetryDTO = field(default_factory=RtkTelemetryDTO)
    orientation: FlightOrientationDTO = field(default_factory=FlightOrientationDTO)
    radiometry: RadiometricFlightParamsDTO = field(default_factory=RadiometricFlightParamsDTO)
    camera: CameraSensorDTO = field(default_factory=CameraSensorDTO)
    # Validações e Flags
    is_valid: bool = True
    validation_warnings: List[str] = field(default_factory=list)
    raw_xmp_found: bool = False
