"""
DTOs para geração e configuração de relatórios técnicos em PDF no SolarGuard Vision.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.domain.enums.anomaly_type import AnomalyType
from src.domain.enums.severity_level import SeverityLevel
from src.domain.value_objects.geo_coordinate import GeoCoordinate


@dataclass
class AnomalyReportItem:
    """Dados de uma falha individual formatados para exibição no relatório PDF."""
    anomaly_id: str
    anomaly_type: AnomalyType
    severity: SeverityLevel
    max_temp_celsius: float
    confidence: float
    delta_t_celsius: Optional[float] = None
    ref_temp_celsius: Optional[float] = None
    coordinate: Optional[GeoCoordinate] = None
    crop_image_path: Optional[str] = None
    context_image_path: Optional[str] = None
    notes: Optional[str] = None
    corrective_action: Optional[str] = None

    @property
    def anomaly_type_name(self) -> str:
        names = {
            AnomalyType.HOTSPOT: "Hotspot (Ponto Quente)",
            AnomalyType.DISCONNECTED_MODULE: "Módulo Desconectado",
            AnomalyType.PID: "Degradação PID",
            AnomalyType.SOILING: "Sujidade / Poeira",
            AnomalyType.SHADING: "Sombreamento Parcial",
            AnomalyType.HEALTHY_MODULE: "Módulo Saudável",
        }
        return names.get(self.anomaly_type, self.anomaly_type.value)

    @property
    def severity_name(self) -> str:
        return self.severity.display_name

    @property
    def severity_hex(self) -> str:
        return self.severity.color_hex

    @property
    def default_recommendation(self) -> str:
        """Gera recomendação normativa padrão com base na falha e severidade IEC."""
        if self.severity == SeverityLevel.CRITICAL:
            return (
                "Risco crítico de incêndio ou dano estrutural permanente. Isolar eletricamente "
                "a string afetada e substituir o módulo fotovoltaico com urgência."
            )
        elif self.severity == SeverityLevel.MEDIUM:
            if self.anomaly_type == AnomalyType.DISCONNECTED_MODULE:
                return "Inspecionar diodos de bypass, conectores MC4 e fusíveis da string box."
            elif self.anomaly_type == AnomalyType.PID:
                return "Verificar aterramento das molduras e avaliar instalação de dispositivo anti-PID no inversor."
            else:
                return "Agendar manutenção corretiva em até 30 dias para evitar degradação acelerada."
        elif self.severity == SeverityLevel.LOW:
            if self.anomaly_type == AnomalyType.SOILING:
                return "Realizar lavagem técnica dos módulos seguindo cronograma de O&M."
            elif self.anomaly_type == AnomalyType.SHADING:
                return "Poda de vegetação circundante ou manejo de obstáculos físicos."
            else:
                return "Manter em monitoramento preventivo no próximo ciclo termográfico semestral."
        else:
            return "Parâmetros normais de operação. Nenhuma intervenção necessária."


@dataclass
class InspectionReportData:
    """Dados completos consolidados para geração do relatório técnico em PDF."""
    # Cliente e Usina
    client_name: str
    project_name: str
    location: str
    capacity_kwp: float

    # Inspeção
    inspection_id: str
    inspection_title: str
    inspection_date: datetime
    inspector_name: str
    drone_model: str = "DJI Matrice 4T (Sensor Radiométrico VOx 640x512)"
    ambient_temp_celsius: Optional[float] = 30.0
    irradiance_w_m2: Optional[float] = 850.0
    wind_speed_m_s: Optional[float] = 2.5

    # KPIs
    total_images: int = 0
    total_anomalies: int = 0
    critical_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    max_temp_celsius: float = 0.0
    max_delta_t_celsius: float = 0.0
    compliance_rate_pct: float = 100.0

    # Itens detalhados
    anomalies: List[AnomalyReportItem] = field(default_factory=list)

    # Recursos Visuais (Caminhos para arquivos de imagem)
    chart_distribution_path: Optional[str] = None
    chart_severity_path: Optional[str] = None
    chart_history_path: Optional[str] = None
    map_overview_image_path: Optional[str] = None

    # Conclusão Técnica
    technical_conclusion: Optional[str] = None
    company_name: str = "SolarGuard Vision - Engenharia Diagnóstica Solar"
