"""
Entidades de Domínio para Módulos Solares Fotovoltaicos Físicos e Mapeamento de Falhas.
Clean Architecture: independente de frameworks, bibliotecas externas de banco ou UI.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

from src.domain.value_objects.bounding_box import BoundingBox


@dataclass
class SolarPanel:
    """
    Representa um módulo fotovoltaico físico segmentado no arranjo da usina solar.
    """
    image_id: str
    string_id: str
    row_index: int
    col_index: int
    panel_identifier: str
    bbox: BoundingBox
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "image_id": self.image_id,
            "string_id": self.string_id,
            "row_index": self.row_index,
            "col_index": self.col_index,
            "panel_identifier": self.panel_identifier,
            "bbox": {
                "xmin": self.bbox.xmin,
                "ymin": self.bbox.ymin,
                "xmax": self.bbox.xmax,
                "ymax": self.bbox.ymax,
            },
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class PanelFaultMapping:
    """
    Associação espacial e topológica entre uma anomalia/detecção térmica e o módulo físico.
    """
    image_id: str
    panel_id: str
    string_id: str
    row_index: int
    col_index: int
    panel_identifier: str
    overlap_iou: float
    relative_x: float  # Posição relativa [0.0, 1.0] na largura do painel
    relative_y: float  # Posição relativa [0.0, 1.0] na altura do painel
    detection_id: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "detection_id": self.detection_id,
            "panel_id": self.panel_id,
            "image_id": self.image_id,
            "string_id": self.string_id,
            "row_index": self.row_index,
            "col_index": self.col_index,
            "panel_identifier": self.panel_identifier,
            "overlap_iou": round(self.overlap_iou, 4),
            "relative_x": round(self.relative_x, 4),
            "relative_y": round(self.relative_y, 4),
            "created_at": self.created_at.isoformat(),
        }
