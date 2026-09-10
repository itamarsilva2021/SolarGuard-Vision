"""
Exportação centralizada das entidades da camada de domínio.
"""

from src.domain.entities.client import Client
from src.domain.entities.thermal_anomaly import ThermalAnomaly
from src.domain.entities.pv_module import PVModule
from src.domain.entities.thermal_image import ThermalImage
from src.domain.entities.inspection import Inspection
from src.domain.entities.project import Project
from src.domain.entities.report import Report, ReportType
from src.domain.entities.user import User
from src.domain.entities.solar_panel import SolarPanel, PanelFaultMapping

__all__ = [
    "Client",
    "ThermalAnomaly",
    "PVModule",
    "ThermalImage",
    "Inspection",
    "Project",
    "Report",
    "ReportType",
    "User",
    "SolarPanel",
    "PanelFaultMapping",
]

