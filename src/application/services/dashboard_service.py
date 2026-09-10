"""
Serviço de Aplicação para Cálculo de KPIs, Histórico e Orquestração do Dashboard.
Cruza dados de Usinas, Inspeções e Falhas Térmicas e aciona a geração de gráficos com Matplotlib.
"""

from typing import Optional, List, Dict
from datetime import datetime

from src.core.result import Result, Success, Failure
from src.core.logger import get_logger
from src.domain.interfaces.repositories import (
    IProjectRepository,
    IInspectionRepository,
    IThermalImageRepository,
    IThermalAnomalyRepository,
)
from src.domain.enums.anomaly_type import AnomalyType
from src.domain.enums.severity_level import SeverityLevel
from src.infrastructure.visualization.chart_generator import ChartGenerator
from src.application.dtos.dashboard_dtos import (
    DashboardData,
    DashboardKPIs,
    InspectionHistoryItem,
    FaultDistribution,
)

logger = get_logger("DashboardService")


class DashboardService:
    """
    Serviço central de inteligência analítica para o Dashboard gerencial e técnico.
    """

    def __init__(
        self,
        project_repository: IProjectRepository,
        inspection_repository: IInspectionRepository,
        thermal_image_repository: IThermalImageRepository,
        thermal_anomaly_repository: IThermalAnomalyRepository,
        chart_generator: Optional[ChartGenerator] = None,
    ) -> None:
        self.project_repo = project_repository
        self.inspection_repo = inspection_repository
        self.image_repo = thermal_image_repository
        self.anomaly_repo = thermal_anomaly_repository
        self.chart_gen = chart_generator or ChartGenerator()

    def get_dashboard_data(
        self,
        project_id: Optional[str] = None,
        generate_charts: bool = True,
    ) -> Result[DashboardData, str]:
        """
        Compila todos os dados, métricas e gráficos do Dashboard para o sistema completo
        ou filtrado por uma usina solar específica.
        
        :param project_id: ID opcional de um projeto/usina para filtragem.
        :param generate_charts: Se True, renderiza e salva os gráficos com Matplotlib.
        :return: Result contendo DashboardData.
        """
        try:
            # 1. Carregar Projetos
            if project_id:
                proj = self.project_repo.get_by_id(project_id)
                projects = [proj] if proj else []
            else:
                projects = self.project_repo.list_all()

            project_names = {p.id: p.name for p in projects}

            # 2. Carregar Inspeções
            if project_id:
                inspections = self.inspection_repo.list_by_project(project_id)
            else:
                inspections = self.inspection_repo.list_all()

            # Ordenação cronológica para histórico
            inspections.sort(key=lambda i: i.date)

            # 3. Carregar Falhas e Imagens
            all_anomalies = []
            history_items: List[InspectionHistoryItem] = []
            timeline_series: List[Dict[str, Any]] = []

            total_analyzed_images = 0
            iec_compliant_inspections = 0

            for insp in inspections:
                # Verificar conformidade IEC TS 62446-3 das condições meteorológicas
                if insp.meets_iec_conditions:
                    iec_compliant_inspections += 1

                # Imagens da inspeção
                images = self.image_repo.list_by_inspection(insp.id)
                total_analyzed_images += sum(1 for img in images if img.is_analyzed)

                # Anomalias da inspeção
                anomalies = self.anomaly_repo.list_by_inspection(insp.id)
                all_anomalies.extend(anomalies)

                faults_count = sum(1 for a in anomalies if a.anomaly_type.is_fault)
                critical_count = sum(1 for a in anomalies if a.severity == SeverityLevel.CRITICAL)

                max_t = max([a.max_temp_celsius for a in anomalies]) if anomalies else None

                history_items.append(
                    InspectionHistoryItem(
                        inspection_id=insp.id,
                        date=insp.date,
                        title=insp.title,
                        project_name=project_names.get(insp.project_id, "Usina"),
                        drone_model=insp.drone_model,
                        total_images=len(images),
                        faults_count=faults_count,
                        critical_count=critical_count,
                        max_temp_celsius=max_t,
                        status=insp.status.display_name,
                    )
                )

                timeline_series.append({
                    "date": insp.date,
                    "faults": faults_count,
                    "criticals": critical_count,
                    "inspections": 1,
                })

            # Inverter histórico para exibição (mais recentes primeiro)
            history_display = list(reversed(history_items))

            # 4. Cálculo dos KPIs
            total_faults = sum(1 for a in all_anomalies if a.anomaly_type.is_fault)
            critical_faults = sum(1 for a in all_anomalies if a.severity == SeverityLevel.CRITICAL)
            max_dt = max([a.delta_t.value for a in all_anomalies if a.delta_t]) if all_anomalies else 0.0
            highest_t = max([a.max_temp_celsius for a in all_anomalies]) if all_anomalies else 0.0

            compliance_rate = (
                (iec_compliant_inspections / len(inspections) * 100.0) if inspections else 100.0
            )

            kpis = DashboardKPIs(
                total_inspections=len(inspections),
                total_faults=total_faults,
                critical_faults=critical_faults,
                total_projects=len(projects),
                total_images_analyzed=total_analyzed_images,
                max_delta_t_celsius=round(max_dt, 1),
                highest_temp_celsius=round(highest_t, 1),
                iec_compliance_rate_pct=round(compliance_rate, 1),
            )

            # 5. Distribuição de Falhas
            by_type = {
                "Hotspot": 0,
                "Módulo Desconectado": 0,
                "Degradação PID": 0,
                "Sujidade / Poeira": 0,
                "Sombreamento Parcial": 0,
            }
            for a in all_anomalies:
                if a.anomaly_type == AnomalyType.HOTSPOT:
                    by_type["Hotspot"] += 1
                elif a.anomaly_type == AnomalyType.DISCONNECTED_MODULE:
                    by_type["Módulo Desconectado"] += 1
                elif a.anomaly_type == AnomalyType.PID:
                    by_type["Degradação PID"] += 1
                elif a.anomaly_type == AnomalyType.SOILING:
                    by_type["Sujidade / Poeira"] += 1
                elif a.anomaly_type == AnomalyType.SHADING:
                    by_type["Sombreamento Parcial"] += 1

            by_severity = {
                "Crítico (Classe 3 - IEC)": critical_faults,
                "Médio (Classe 2 - IEC)": sum(1 for a in all_anomalies if a.severity == SeverityLevel.MEDIUM),
                "Baixo (Classe 1 - IEC)": sum(1 for a in all_anomalies if a.severity == SeverityLevel.LOW),
                "Informativo / Normal": sum(1 for a in all_anomalies if a.severity == SeverityLevel.INFORMATIVE),
            }

            distribution = FaultDistribution(
                by_type=by_type,
                by_severity=by_severity,
                timeline_series=timeline_series,
            )

            dashboard_data = DashboardData(
                kpis=kpis,
                distribution=distribution,
                history=history_display,
            )

            # 6. Geração de Gráficos com Matplotlib
            if generate_charts:
                prefix = f"proj_{project_id}_" if project_id else "global_"
                p_pie = self.chart_gen.generate_fault_distribution_pie(
                    by_type, output_filename=f"{prefix}chart_distribution.png"
                )
                p_sev = self.chart_gen.generate_severity_bar_chart(
                    by_severity, output_filename=f"{prefix}chart_severity.png"
                )
                p_hist = self.chart_gen.generate_historical_trend_chart(
                    timeline_series, output_filename=f"{prefix}chart_timeline.png"
                )
                p_over = self.chart_gen.generate_consolidated_dashboard_figure(
                    dashboard_data, output_filename=f"{prefix}dashboard_overview.png"
                )

                dashboard_data.chart_distribution_path = str(p_pie)
                dashboard_data.chart_severity_path = str(p_sev)
                dashboard_data.chart_history_path = str(p_hist)
                dashboard_data.chart_overview_path = str(p_over)

            logger.info(f"Dashboard compilado com sucesso: {kpis.total_inspections} inspeções, {kpis.total_faults} falhas.")
            return Success(dashboard_data)

        except Exception as ex:
            msg = f"Erro ao gerar dados do Dashboard: {str(ex)}"
            logger.error(msg, exc_info=True)
            return Failure(msg)
