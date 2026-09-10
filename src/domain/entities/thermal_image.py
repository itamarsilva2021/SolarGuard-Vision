"""
Entidade de Domínio representando uma captura térmica aérea (R-JPEG DJI Matrice 4T).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from src.domain.entities.thermal_anomaly import ThermalAnomaly
from src.domain.entities.pv_module import PVModule
from src.domain.value_objects.geo_coordinate import GeoCoordinate
from src.domain.value_objects.thermal_matrix_meta import ThermalMatrixMeta
from src.domain.enums.severity_level import SeverityLevel


@dataclass
class ThermalImage:
    """
    Representa uma imagem térmica capturada durante a missão de voo.
    
    :param id: Identificador único universal.
    :param inspection_id: Identificador da inspeção à qual a imagem pertence.
    :param file_path: Caminho completo para o arquivo de imagem no disco.
    :param filename: Nome do arquivo (ex: 'DJI_20260910123045_0001_T.JPG').
    :param coordinate: Coordenadas GPS (WGS84) da posição do drone no momento do disparo.
    :param flight_altitude_meters: Altitude relativa de voo em relação ao ponto de decolagem.
    :param gimbal_pitch_degrees: Ângulo de inclinação do gimbal (ex: -90° para nadir).
    :param gimbal_yaw_degrees: Orientação azimutal da câmera.
    :param thermal_meta: Metadados radiométricos extraídos do sensor do DJI Matrice 4T.
    :param width: Largura em pixels (ex: 640).
    :param height: Altura em pixels (ex: 512).
    :param anomalies: Lista de anomalias detectadas nesta imagem.
    :param modules: Lista de módulos identificados na imagem.
    :param is_analyzed: Flag indicando se a inferência de IA e análise já foram executadas.
    :param captured_at: Data e hora do disparo da câmera (obtida via EXIF).
    """
    inspection_id: str
    file_path: str
    filename: str
    width: int = 640
    height: int = 512
    coordinate: Optional[GeoCoordinate] = None
    flight_altitude_meters: Optional[float] = None
    gimbal_pitch_degrees: Optional[float] = None
    gimbal_yaw_degrees: Optional[float] = None
    thermal_meta: Optional[ThermalMatrixMeta] = None
    anomalies: list[ThermalAnomaly] = field(default_factory=list)
    modules: list[PVModule] = field(default_factory=list)
    is_analyzed: bool = False
    captured_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def add_anomaly(self, anomaly: ThermalAnomaly) -> None:
        """Adiciona uma anomalia detectada nesta imagem."""
        self.anomalies.append(anomaly)

    def add_module(self, module: PVModule) -> None:
        """Adiciona um módulo fotovoltaico identificado nesta imagem."""
        self.modules.append(module)

    @property
    def has_faults(self) -> bool:
        """Indica se há alguma anomalia com defeito real (não saudável)."""
        return any(a.anomaly_type.is_fault for a in self.anomalies)

    @property
    def critical_count(self) -> int:
        """Retorna o número de anomalias classificadas como Críticas (Classe 3)."""
        return sum(1 for a in self.anomalies if a.severity == SeverityLevel.CRITICAL)

    @property
    def max_scene_temperature(self) -> Optional[float]:
        """Temperatura máxima observada na imagem (via metadados térmicos ou detecções)."""
        if self.thermal_meta is not None:
            return self.thermal_meta.max_temp_celsius
        if self.anomalies:
            return max(a.max_temp_celsius for a in self.anomalies)
        return None
