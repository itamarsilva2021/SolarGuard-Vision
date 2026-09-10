"""
Enumeração e regras de classificação de severidade térmica conforme IEC TS 62446-3.
Classificação baseada no gradiente térmico (Delta T) entre a anomalia e a referência saudável.
"""

from enum import Enum


class SeverityLevel(str, Enum):
    """
    Níveis de severidade para classificação de defeitos em sistemas fotovoltaicos.
    Baseado nas diretrizes normativas da norma IEC TS 62446-3:
    - INFORMATIVE: Delta T < 3°C ou módulo sem falha detectável.
    - LOW (Classe 1): 3°C <= Delta T < 10°C (Manutenção preventiva programada).
    - MEDIUM (Classe 2): 10°C <= Delta T < 30°C (Manutenção corretiva necessária em médio prazo).
    - CRITICAL (Classe 3): Delta T >= 30°C (Risco de incêndio/dano irreversível, intervenção imediata).
    """
    INFORMATIVE = "informative"
    LOW = "low"
    MEDIUM = "medium"
    CRITICAL = "critical"

    @property
    def display_name(self) -> str:
        """Nome amigável em Português do Brasil."""
        translations = {
            SeverityLevel.INFORMATIVE: "Informativo / Normal",
            SeverityLevel.LOW: "Baixo (Classe 1 - IEC)",
            SeverityLevel.MEDIUM: "Médio (Classe 2 - IEC)",
            SeverityLevel.CRITICAL: "Crítico (Classe 3 - IEC)",
        }
        return translations.get(self, self.value)

    @property
    def color_hex(self) -> str:
        """Cor hexadecimal para plotagem em UI, mapas e relatórios."""
        colors = {
            SeverityLevel.INFORMATIVE: "#2ECC71",  # Verde
            SeverityLevel.LOW: "#F1C40F",          # Amarelo
            SeverityLevel.MEDIUM: "#E67E22",       # Laranja
            SeverityLevel.CRITICAL: "#E74C3C",     # Vermelho
        }
        return colors.get(self, "#95A5A6")

    @property
    def priority_rank(self) -> int:
        """Rank numérico para ordenação por prioridade (maior = mais grave)."""
        ranks = {
            SeverityLevel.INFORMATIVE: 0,
            SeverityLevel.LOW: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.CRITICAL: 3,
        }
        return ranks.get(self, 0)

    @classmethod
    def from_delta_t(cls, delta_t_celsius: float) -> "SeverityLevel":
        """
        Classifica automaticamente a severidade a partir do gradiente térmico (Delta T)
        conforme as recomendações da norma IEC TS 62446-3.
        
        :param delta_t_celsius: Diferença entre a temperatura máxima da anomalia
                                e a temperatura média de um módulo saudável adjacente.
        :return: Nível de severidade correspondente.
        """
        if delta_t_celsius >= 30.0:
            return cls.CRITICAL
        elif delta_t_celsius >= 10.0:
            return cls.MEDIUM
        elif delta_t_celsius >= 3.0:
            return cls.LOW
        else:
            return cls.INFORMATIVE
