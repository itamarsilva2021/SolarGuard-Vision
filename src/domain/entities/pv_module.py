"""
Entidade de Domínio representando um módulo fotovoltaico inspecionado.
"""

from dataclasses import dataclass, field
from typing import Optional
import uuid

from src.domain.entities.thermal_anomaly import ThermalAnomaly
from src.domain.value_objects.bounding_box import BoundingBox
from src.domain.value_objects.geo_coordinate import GeoCoordinate


@dataclass
class PVModule:
    """
    Representa um módulo/placa fotovoltaica individual identificado na planta solar.
    
    :param id: Identificador único universal.
    :param bbox: Posição do módulo delimitada na imagem térmica.
    :param string_id: Identificador da string (ex: 'STR-04').
    :param table_id: Identificador da mesa/rastreador (ex: 'MESA-12').
    :param coordinate: Coordenada geográfica estimada do módulo.
    :param anomalies: Lista de anomalias detectadas no corpo do módulo.
    """
    bbox: BoundingBox
    string_id: Optional[str] = None
    table_id: Optional[str] = None
    coordinate: Optional[GeoCoordinate] = None
    anomalies: list[ThermalAnomaly] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def add_anomaly(self, anomaly: ThermalAnomaly) -> None:
        """Associa uma anomalia detectada a este módulo."""
        self.anomalies.append(anomaly)

    @property
    def is_healthy(self) -> bool:
        """Retorna True se o módulo não possui anomalias que representem falhas."""
        return len(self.anomalies) == 0 or all(
            not a.anomaly_type.is_fault for a in self.anomalies
        )

    @property
    def worst_severity(self):
        """Retorna o nível de severidade mais crítico presente no módulo."""
        if not self.anomalies:
            return None
        return max(self.anomalies, key=lambda a: a.severity.priority_rank).severity
