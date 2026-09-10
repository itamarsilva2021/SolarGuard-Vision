"""
Enumeração do ciclo de vida e status de uma inspeção termográfica.
"""

from enum import Enum


class InspectionStatus(str, Enum):
    """
    Status de processamento de uma inspeção de usina fotovoltaica.
    """
    CREATED = "created"
    PARSING_THERMAL = "parsing_thermal"
    RUNNING_AI_DETECTION = "running_ai_detection"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def display_name(self) -> str:
        names = {
            InspectionStatus.CREATED: "Criada (Aguardando processamento)",
            InspectionStatus.PARSING_THERMAL: "Extraindo dados radiométricos DJI",
            InspectionStatus.RUNNING_AI_DETECTION: "Executando inferência YOLOv11",
            InspectionStatus.COMPLETED: "Concluída com sucesso",
            InspectionStatus.FAILED: "Falha durante o processamento",
        }
        return names.get(self, self.value)
