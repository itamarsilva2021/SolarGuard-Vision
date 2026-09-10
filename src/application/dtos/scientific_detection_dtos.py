"""
DTOs para persistência científica de inferências de IA, termografia e análise de Delta T.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Any

from src.domain.entities.scientific_detection import (
    ThermalAnalysisRecord,
    DeltaTResultRecord,
    YoloPredictionRecord,
    DetectionRecord,
)

# Aliases de compatibilidade para a camada de DTOs
ThermalAnalysisDTO = ThermalAnalysisRecord
DeltaTResultDTO = DeltaTResultRecord
YoloPredictionDTO = YoloPredictionRecord
DetectionRecordDTO = DetectionRecord


@dataclass
class DetectionPersistenceRequest:
    """Requisição para persistência científica de uma imagem inspecionada."""
    image_id: str
    # Predições de anomalias (usualmente do Detector / DefectClassifier)
    anomalies: List[Any]  # List[ThermalAnomaly]
    # Parâmetros radiométricos opcionais da cena
    emissivity: float = 0.95
    reflected_temp_celsius: float = 25.0
    ambient_temp_celsius: float = 28.0
    relative_humidity: float = 0.50
    distance_meters: float = 25.0
    reference_temp_celsius: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class DetectionPersistenceResult:
    """Resultado da transação de persistência científica."""
    image_id: str
    analysis_id: str
    saved_detections_count: int
    saved_predictions_count: int
    saved_delta_t_count: int
    critical_anomalies_count: int
    created_at: datetime
    detections: List[DetectionRecordDTO] = field(default_factory=list)
