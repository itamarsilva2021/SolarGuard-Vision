"""
Objeto de Valor para representação de gradientes térmicos (Delta T) e conformidade normativa.
"""

from dataclasses import dataclass
from src.domain.enums.severity_level import SeverityLevel
from src.domain.exceptions import InvalidTemperatureError


@dataclass(frozen=True)
class DeltaT:
    """
    Representa a diferença térmica (Delta T) entre um ponto anômalo e uma referência saudável.
    
    :param t_max_celsius: Temperatura máxima medida na anomalia/hotspot.
    :param t_ref_celsius: Temperatura de referência do módulo saudável ou temperatura média da string.
    """
    t_max_celsius: float
    t_ref_celsius: float

    def __post_init__(self) -> None:
        absolute_zero_celsius = -273.15
        if self.t_max_celsius < absolute_zero_celsius:
            raise InvalidTemperatureError(
                f"Temperatura máxima ({self.t_max_celsius}°C) abaixo do zero absoluto."
            )
        if self.t_ref_celsius < absolute_zero_celsius:
            raise InvalidTemperatureError(
                f"Temperatura de referência ({self.t_ref_celsius}°C) abaixo do zero absoluto."
            )

    @property
    def value(self) -> float:
        """Diferencial de temperatura em graus Celsius (°C)."""
        return round(self.t_max_celsius - self.t_ref_celsius, 2)

    @property
    def delta_celsius(self) -> float:
        """Alias para o diferencial de temperatura em graus Celsius."""
        return self.value


    def classify_iec_62446_3(self) -> SeverityLevel:
        """
        Classifica a anomalia segundo a norma IEC TS 62446-3:
        - Delta T < 3°C: Informativo
        - 3°C <= Delta T < 10°C: Baixo (Classe 1)
        - 10°C <= Delta T < 30°C: Médio (Classe 2)
        - Delta T >= 30°C: Crítico (Classe 3)
        """
        return SeverityLevel.from_delta_t(self.value)
