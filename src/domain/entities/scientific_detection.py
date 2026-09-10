"""
Entidades de domínio para persistência científica de inferências,
análise de Delta T e predições do modelo YOLOv11.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

from src.domain.value_objects.bounding_box import BoundingBox


@dataclass
class ThermalAnalysisRecord:
    """Entidade de domínio representando a sessão de análise radiométrica de uma imagem."""
    image_id: str
    emissivity: float = 0.95
    reflected_temp_celsius: float = 25.0
    ambient_temp_celsius: float = 28.0
    relative_humidity: float = 0.50
    distance_meters: float = 25.0
    min_temp_celsius: float = 20.0
    max_temp_celsius: float = 65.0
    avg_temp_celsius: float = 38.0
    global_delta_t: Optional[float] = None
    algorithm_version: str = "v1.0-scientific"
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class DeltaTResultRecord:
    """Entidade de domínio representando o cálculo normativo de Delta T (IEC TS 62446-3)."""
    image_id: str
    hotspot_temp_celsius: float
    reference_temp_celsius: float
    delta_t: float
    severity: str  # Ex: "critical", "major", "minor", "healthy"
    iec_class: str  # Ex: "Classe 3", "Classe 2", "Classe 1"
    analysis_id: Optional[str] = None
    reference_type: str = "healthy_module"
    created_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class YoloPredictionRecord:
    """Entidade de domínio representando uma predição bruta da inferência YOLOv11."""
    image_id: str
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    model_version: str = "YOLOv11"
    inference_time_ms: float = 12.5
    created_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class DetectionRecord:
    """Entidade de domínio consolidada correlacionando visão computacional e radiometria."""
    image_id: str
    class_name: str
    confidence: float
    bbox: BoundingBox
    delta_t: float
    max_temp_celsius: float
    avg_temp_celsius: float
    severity: str
    min_temp_celsius: Optional[float] = None
    analysis_id: Optional[str] = None
    delta_t_id: Optional[str] = None
    yolo_prediction_id: Optional[str] = None
    crop_path: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "image_id": self.image_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": {
                "xmin": self.bbox.xmin,
                "ymin": self.bbox.ymin,
                "xmax": self.bbox.xmax,
                "ymax": self.bbox.ymax,
            },
            "delta_t": round(self.delta_t, 2),
            "max_temp_celsius": round(self.max_temp_celsius, 2),
            "avg_temp_celsius": round(self.avg_temp_celsius, 2),
            "min_temp_celsius": round(self.min_temp_celsius, 2) if self.min_temp_celsius is not None else None,
            "severity": self.severity,
            "crop_path": self.crop_path,
            "created_at": self.created_at.isoformat(),
        }
