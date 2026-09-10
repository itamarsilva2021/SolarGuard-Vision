"""
Exportação centralizada do núcleo do sistema.
"""

from src.core.result import Result, Success, Failure
from src.core.config import settings, AppConfig
from src.core.logger import get_logger

__all__ = [
    "Result",
    "Success",
    "Failure",
    "settings",
    "AppConfig",
    "get_logger",
]
