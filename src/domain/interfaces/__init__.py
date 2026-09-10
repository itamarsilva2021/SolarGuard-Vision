"""
Exportação centralizada das interfaces e contratos de domínio.
"""

from src.domain.interfaces.repositories import (
    IClientRepository,
    IProjectRepository,
    IInspectionRepository,
    IThermalImageRepository,
    IThermalAnomalyRepository,
    IReportRepository,
)
from src.domain.interfaces.thermal_parser import IThermalParser
from src.domain.interfaces.anomaly_detector import IAnomalyDetector
from src.domain.interfaces.report_exporter import IPDFReportExporter, IExcelExporter

__all__ = [
    "IClientRepository",
    "IProjectRepository",
    "IInspectionRepository",
    "IThermalImageRepository",
    "IThermalAnomalyRepository",
    "IReportRepository",
    "IThermalParser",
    "IAnomalyDetector",
    "IPDFReportExporter",
    "IExcelExporter",
]
