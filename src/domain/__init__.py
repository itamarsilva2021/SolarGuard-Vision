"""
Camada de Domínio (Clean Architecture) - SolarGuard Vision.
Contém entidades puras, objetos de valor, enums, exceções e interfaces/contratos.
Independente de frameworks externos, bibliotecas gráficas ou bancos de dados específicos.
"""

from src.domain.exceptions import (
    DomainError,
    InvalidCoordinateError,
    InvalidTemperatureError,
    InvalidBoundingBoxError,
    EntityNotFoundError,
    ThermalDataCorruptedError,
)

__all__ = [
    "DomainError",
    "InvalidCoordinateError",
    "InvalidTemperatureError",
    "InvalidBoundingBoxError",
    "EntityNotFoundError",
    "ThermalDataCorruptedError",
]
