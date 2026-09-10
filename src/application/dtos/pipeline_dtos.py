"""
DTOs para o Serviço Orquestrador End-to-End de Inspeções (InspectionPipelineService).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class InspectionPipelineRequest:
    """Parâmetros e configurações para processamento autônomo de uma inspeção a partir de pasta DJI."""
    flight_folder: Path
    project_id: str
    inspection_title: Optional[str] = None
    inspector_name: str = "SolarGuard Automated Pipeline"
    drone_model: str = "DJI Matrice 4T"
    emissivity: float = 0.92
    ambient_temp_celsius: float = 25.0
    relative_humidity: float = 0.50
    reflected_temp_celsius: float = 20.0
    distance_meters: float = 25.0
    string_prefix: str = "STR-01"
    generate_dashboard_charts: bool = True
    generate_map: bool = True
    generate_report: bool = True
    notes: Optional[str] = None


@dataclass
class InspectionPipelineResult:
    """Resultado consolidado da execução do pipeline end-to-end."""
    inspection_id: str
    project_id: str
    total_images_processed: int
    total_anomalies_detected: int
    critical_anomalies_count: int
    map_file_path: Optional[Path] = None
    geojson_file_path: Optional[Path] = None
    report_file_path: Optional[Path] = None
    duration_seconds: float = 0.0
    status: str = "completed"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inspection_id": self.inspection_id,
            "project_id": self.project_id,
            "total_images_processed": self.total_images_processed,
            "total_anomalies_detected": self.total_anomalies_detected,
            "critical_anomalies_count": self.critical_anomalies_count,
            "map_file_path": str(self.map_file_path) if self.map_file_path else None,
            "geojson_file_path": str(self.geojson_file_path) if self.geojson_file_path else None,
            "report_file_path": str(self.report_file_path) if self.report_file_path else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "status": self.status,
            "details": self.details,
        }
