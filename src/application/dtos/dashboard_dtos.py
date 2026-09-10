"""
DTOs para o Dashboard de Análise e Monitoramento Fotovoltaico do SolarGuard Vision.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


@dataclass
class DashboardKPIs:
    """Indicadores Chave de Desempenho (KPIs) da planta solar e inspeções."""
    total_inspections: int = 0
    total_faults: int = 0
    critical_faults: int = 0
    total_projects: int = 0
    total_images_analyzed: int = 0
    max_delta_t_celsius: float = 0.0
    highest_temp_celsius: float = 0.0
    iec_compliance_rate_pct: float = 100.0

    def to_dict(self) -> dict:
        return {
            "total_inspections": self.total_inspections,
            "total_faults": self.total_faults,
            "critical_faults": self.critical_faults,
            "total_projects": self.total_projects,
            "total_images_analyzed": self.total_images_analyzed,
            "max_delta_t_celsius": self.max_delta_t_celsius,
            "highest_temp_celsius": self.highest_temp_celsius,
            "iec_compliance_rate_pct": self.iec_compliance_rate_pct,
        }


@dataclass
class InspectionHistoryItem:
    """Registro histórico de uma campanha de inspeção individual."""
    inspection_id: str
    date: datetime
    title: str
    project_name: str
    drone_model: str
    total_images: int
    faults_count: int
    critical_count: int
    max_temp_celsius: Optional[float]
    status: str

    def to_dict(self) -> dict:
        return {
            "inspection_id": self.inspection_id,
            "date": self.date.strftime("%d/%m/%Y %H:%M"),
            "title": self.title,
            "project_name": self.project_name,
            "drone_model": self.drone_model,
            "total_images": self.total_images,
            "faults_count": self.faults_count,
            "critical_count": self.critical_count,
            "max_temp_celsius": self.max_temp_celsius,
            "status": self.status,
        }


@dataclass
class FaultDistribution:
    """Distribuição quantitativa de anomalias por categoria e severidade."""
    by_type: Dict[str, int] = field(default_factory=dict)
    by_severity: Dict[str, int] = field(default_factory=dict)
    timeline_series: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DashboardData:
    """Estrutura consolidada contendo todos os dados e gráficos do Dashboard."""
    kpis: DashboardKPIs
    distribution: FaultDistribution
    history: List[InspectionHistoryItem] = field(default_factory=list)
    chart_distribution_path: Optional[str] = None
    chart_severity_path: Optional[str] = None
    chart_history_path: Optional[str] = None
    chart_overview_path: Optional[str] = None
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "kpis": self.kpis.to_dict(),
            "distribution_by_type": self.distribution.by_type,
            "distribution_by_severity": self.distribution.by_severity,
            "history_count": len(self.history),
            "generated_at": self.generated_at.isoformat(),
        }
