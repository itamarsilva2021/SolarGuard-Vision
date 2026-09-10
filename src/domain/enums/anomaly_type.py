"""
Enumeração dos tipos de anomalias e condições térmicas em sistemas fotovoltaicos.
Compatível com as classes de detecção do modelo YOLOv11 do SolarGuard Vision.
"""

from enum import Enum


class AnomalyType(str, Enum):
    """
    Tipos de defeitos, anomalias e estados térmicos inspecionados em módulos fotovoltaicos.
    
    Classes de interesse:
    - HOTSPOT: Ponto quente em célula isolada (defeito de solda, trinca oculta, diodo bypass).
    - DISCONNECTED_MODULE: Módulo com circuito aberto/desconectado (temperatura uniforme mais alta).
    - PID: Degradação Induzida por Potencial (gradiente térmico em módulos próximos ao polo aterrado).
    - SOILING: Acúmulo de poeira, fezes de pássaros ou sujeira superficial gerando aquecimento localizado.
    - SHADING: Sombreamento parcial por vegetação, relevo ou estruturas adjacentes.
    - HEALTHY_MODULE: Módulo operando dentro dos parâmetros nominais e distribuição térmica uniforme.
    """
    HOTSPOT = "hotspot"
    DISCONNECTED_MODULE = "disconnected_module"
    PID = "pid"
    SOILING = "soiling"
    SHADING = "shading"
    HEALTHY_MODULE = "healthy_module"

    @property
    def display_name(self) -> str:
        """Nome formatado para exibição na interface e relatórios em Português do Brasil."""
        translations = {
            AnomalyType.HOTSPOT: "Hotspot (Ponto Quente)",
            AnomalyType.DISCONNECTED_MODULE: "Módulo Desconectado",
            AnomalyType.PID: "Degradação PID",
            AnomalyType.SOILING: "Sujidade / Poeira",
            AnomalyType.SHADING: "Sombreamento Parcial",
            AnomalyType.HEALTHY_MODULE: "Módulo Saudável (Sem Falha)",
        }
        return translations.get(self, self.value)

    @property
    def description(self) -> str:
        """Descrição técnica detalhada do tipo de falha."""
        descriptions = {
            AnomalyType.HOTSPOT: (
                "Aquecimento concentrado em uma ou mais células fotovoltaicas, "
                "geralmente causado por microfissuras, sombreamento de célula ou falha de fabricação."
            ),
            AnomalyType.DISCONNECTED_MODULE: (
                "Módulo em circuito aberto sem extração de potência, "
                "ficando homogeneamente mais quente que a string adjacente operando sob carga."
            ),
            AnomalyType.PID: (
                "Degradação Induzida por Potencial decorrente de correntes de fuga "
                "entre a célula e a moldura aterrada, manifestando padrão térmico característico."
            ),
            AnomalyType.SOILING: (
                "Deposição de partículas opacas (sujeira, poeira, excrementos) que bloqueiam a radiação "
                "e induzem efeito de carga reversa na célula."
            ),
            AnomalyType.SHADING: (
                "Obstrução da irradiação solar incidente decorrente de vegetação, obstáculos fixos ou postes."
            ),
            AnomalyType.HEALTHY_MODULE: (
                "Módulo sem irregularidades térmicas, operando com distribuição homogênea de calor."
            ),
        }
        return descriptions.get(self, "")

    @property
    def is_fault(self) -> bool:
        """Indica se a classe representa uma anomalia que requer intervenção técnica."""
        return self != AnomalyType.HEALTHY_MODULE
