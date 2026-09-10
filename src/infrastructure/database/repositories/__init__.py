"""
Exportação centralizada das implementações SQLite dos Repositórios.
"""

from src.infrastructure.database.repositories.sqlite_client_repository import SqliteClientRepository
from src.infrastructure.database.repositories.sqlite_project_repository import SqliteProjectRepository
from src.infrastructure.database.repositories.sqlite_inspection_repository import SqliteInspectionRepository
from src.infrastructure.database.repositories.sqlite_thermal_image_repository import SqliteThermalImageRepository
from src.infrastructure.database.repositories.sqlite_thermal_anomaly_repository import SqliteThermalAnomalyRepository
from src.infrastructure.database.repositories.sqlite_report_repository import SqliteReportRepository
from src.infrastructure.database.repositories.sqlite_user_repository import SqliteUserRepository
from src.infrastructure.database.repositories.sqlite_detection_repository import SqliteDetectionRepository
from src.infrastructure.database.repositories.sqlite_panel_repository import SqlitePanelRepository

__all__ = [
    "SqliteClientRepository",
    "SqliteProjectRepository",
    "SqliteInspectionRepository",
    "SqliteThermalImageRepository",
    "SqliteThermalAnomalyRepository",
    "SqliteReportRepository",
    "SqliteUserRepository",
    "SqliteDetectionRepository",
    "SqlitePanelRepository",
]

