"""
Módulo de Banco de Dados e Persistência SQLite - SolarGuard Vision.
"""

from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories import (
    SqliteClientRepository,
    SqliteProjectRepository,
    SqliteInspectionRepository,
    SqliteThermalImageRepository,
    SqliteThermalAnomalyRepository,
    SqliteReportRepository,
)

__all__ = [
    "DatabaseManager",
    "SqliteClientRepository",
    "SqliteProjectRepository",
    "SqliteInspectionRepository",
    "SqliteThermalImageRepository",
    "SqliteThermalAnomalyRepository",
    "SqliteReportRepository",
]
