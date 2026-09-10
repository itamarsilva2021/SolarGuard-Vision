"""
Exportação centralizada dos Enums da camada de domínio.
"""

from src.domain.enums.anomaly_type import AnomalyType
from src.domain.enums.severity_level import SeverityLevel
from src.domain.enums.palette_type import PaletteType
from src.domain.enums.inspection_status import InspectionStatus
from src.domain.enums.user_role import UserRole

__all__ = [
    "AnomalyType",
    "SeverityLevel",
    "PaletteType",
    "InspectionStatus",
    "UserRole",
]

