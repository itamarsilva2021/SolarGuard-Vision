"""
Entidade de Domínio representando uma missão ou campanha de inspeção termográfica.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from src.domain.entities.thermal_image import ThermalImage
from src.domain.enums.anomaly_type import AnomalyType
from src.domain.enums.severity_level import SeverityLevel
from src.domain.enums.inspection_status import InspectionStatus


@dataclass
class Inspection:
    """
    Representa uma inspeção completa de uma usina fotovoltaica realizada por drone.
    
    :param id: Identificador único universal.
    :param project_id: Identificador do projeto/usina a que pertence.
    :param title: Título da inspeção (ex: 'Inspeção Termográfica Trimestral - Bloco B').
    :param inspector_name: Nome do piloto/inspetor técnico responsável.
    :param drone_model: Modelo do drone utilizado (padrão: 'DJI Matrice 4T').
    :param status: Status operacional do processamento.
    :param irradiance_w_m2: Irradiância solar média durante o voo em W/m² (Requisito IEC TS 62446-3: >= 600 W/m²).
    :param ambient_temp_celsius: Temperatura ambiente média no momento do voo (°C).
    :param wind_speed_m_s: Velocidade média do vento em m/s (Requisito IEC: <= 4 m/s para não mascarar gradientes).
    :param notes: Observações meteorológicas ou de campo.
    :param images: Lista de imagens térmicas associadas a esta inspeção.
    :param date: Data de realização do voo.
    """
    project_id: str
    title: str
    inspector_name: str
    drone_model: str = "DJI Matrice 4T"
    status: InspectionStatus = InspectionStatus.CREATED
    irradiance_w_m2: Optional[float] = None
    ambient_temp_celsius: Optional[float] = None
    wind_speed_m_s: Optional[float] = None
    notes: Optional[str] = None
    images: list[ThermalImage] = field(default_factory=list)
    date: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def add_image(self, image: ThermalImage) -> None:
        """Associa uma nova imagem térmica à inspeção."""
        self.images.append(image)

    @property
    def total_images(self) -> int:
        """Total de imagens capturadas na inspeção."""
        return len(self.images)

    @property
    def analyzed_images_count(self) -> int:
        """Total de imagens já processadas pela IA."""
        return sum(1 for img in self.images if img.is_analyzed)

    @property
    def all_anomalies(self):
        """Retorna todas as anomalias de todas as imagens desta inspeção."""
        anomalies = []
        for img in self.images:
            anomalies.extend(img.anomalies)
        return anomalies

    @property
    def total_anomalies(self) -> int:
        """Quantidade total de anomalias detectadas."""
        return len(self.all_anomalies)

    @property
    def total_faults(self) -> int:
        """Quantidade de anomalias que representam defeito real (excluindo módulos saudáveis)."""
        return sum(1 for a in self.all_anomalies if a.anomaly_type.is_fault)

    def count_by_type(self) -> dict[AnomalyType, int]:
        """Agrupamento de contagem por tipo de anomalia."""
        counts = {anomaly_type: 0 for anomaly_type in AnomalyType}
        for a in self.all_anomalies:
            counts[a.anomaly_type] = counts.get(a.anomaly_type, 0) + 1
        return counts

    def count_by_severity(self) -> dict[SeverityLevel, int]:
        """Agrupamento de contagem por nível de severidade (IEC TS 62446-3)."""
        counts = {severity: 0 for severity in SeverityLevel}
        for a in self.all_anomalies:
            if a.anomaly_type.is_fault:
                counts[a.severity] = counts.get(a.severity, 0) + 1
        return counts

    @property
    def max_temperature(self) -> Optional[float]:
        """Maior temperatura registrada em toda a inspeção."""
        temps = [a.max_temp_celsius for a in self.all_anomalies]
        return max(temps) if temps else None

    @property
    def meets_iec_conditions(self) -> bool:
        """
        Verifica se a inspeção atende aos requisitos ambientais ideais da IEC TS 62446-3:
        - Irradiância solar >= 600 W/m²
        - Velocidade do vento <= 4.0 m/s
        """
        if self.irradiance_w_m2 is not None and self.irradiance_w_m2 < 600.0:
            return False
        if self.wind_speed_m_s is not None and self.wind_speed_m_s > 4.0:
            return False
        return True
