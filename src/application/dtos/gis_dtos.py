"""
DTOs para o módulo de Georreferenciamento, Mapas e GeoJSON no SolarGuard Vision.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.domain.enums.anomaly_type import AnomalyType
from src.domain.enums.severity_level import SeverityLevel
from src.domain.value_objects.geo_coordinate import GeoCoordinate


@dataclass
class GeoReferencedAnomaly:
    """
    Representa uma falha térmica localizada com precisão geográfica na usina fotovoltaica.
    """
    anomaly_id: str
    image_id: str
    anomaly_type: AnomalyType
    severity: SeverityLevel
    coordinate: GeoCoordinate
    max_temp_celsius: float
    confidence: float
    delta_t_celsius: Optional[float] = None
    min_temp_celsius: Optional[float] = None
    avg_temp_celsius: Optional[float] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    inspection_id: Optional[str] = None
    inspection_title: Optional[str] = None
    captured_at: Optional[datetime] = None
    crop_path: Optional[str] = None
    notes: Optional[str] = None

    @property
    def anomaly_type_name(self) -> str:
        names = {
            AnomalyType.HOTSPOT: "Hotspot",
            AnomalyType.DISCONNECTED_MODULE: "Módulo Desconectado",
            AnomalyType.PID: "Degradação PID",
            AnomalyType.SOILING: "Sujidade / Poeira",
            AnomalyType.SHADING: "Sombreamento Parcial",
            AnomalyType.HEALTHY_MODULE: "Módulo Saudável",
        }
        return names.get(self.anomaly_type, self.anomaly_type.value)

    @property
    def severity_display_name(self) -> str:
        return self.severity.display_name

    @property
    def severity_hex_color(self) -> str:
        """Cor hexadecimal para marcadores no mapa."""
        return self.severity.color_hex



@dataclass
class GeoInspectionResult:
    """
    Resultado consolidado do processamento cartográfico de uma usina ou inspeção.
    """
    total_anomalies: int
    anomalies: List[GeoReferencedAnomaly]
    map_html_path: Optional[Path] = None
    geojson_path: Optional[Path] = None
    center_coordinate: Optional[GeoCoordinate] = None
    critical_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def map_path(self) -> Optional[Path]:
        """Alias para map_html_path."""
        return self.map_html_path
