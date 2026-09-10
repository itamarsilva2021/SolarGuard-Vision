"""
Módulo de Exceções de Domínio - SolarGuard Vision.
Hierarquia de exceções de domínio para validação de regras de negócio.
"""


class DomainError(Exception):
    """Exceção base para todas as violações de regras de negócio do domínio."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidCoordinateError(DomainError):
    """Lançada quando latitude, longitude ou altitude violam os limites geográficos válidos."""
    pass


class InvalidTemperatureError(DomainError):
    """Lançada quando um valor de temperatura é fisicamente impossível ou inválido."""
    pass


class InvalidBoundingBoxError(DomainError):
    """Lançada quando coordenadas de bounding box são geometricamente inconsistentes."""
    pass


class EntityNotFoundError(DomainError):
    """Lançada quando uma entidade de domínio requerida não é encontrada."""
    pass


class ThermalDataCorruptedError(DomainError):
    """Lançada quando os metadados radiométricos ou matriz térmica estão corrompidos."""
    pass
