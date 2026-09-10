"""
Serviço de Aplicação para Orquestração e Emissão de Relatórios Periciais e Técnicos em PDF.
Cruza dados de Clientes, Usinas, Voo DJI, Anomalias Térmicas, Gráficos Matplotlib e assina o documento.
"""

from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from src.core.result import Result, Success, Failure
from src.core.config import settings
from src.core.logger import get_logger
from src.domain.entities.report import Report, ReportType
from src.domain.entities.thermal_image import ThermalImage
from src.domain.entities.thermal_anomaly import ThermalAnomaly
from src.domain.enums.severity_level import SeverityLevel
from src.domain.interfaces.repositories import (
    IProjectRepository,
    IClientRepository,
    IInspectionRepository,
    IThermalImageRepository,
    IThermalAnomalyRepository,
    IReportRepository,
)
from src.application.dtos.report_dtos import InspectionReportData, AnomalyReportItem
from src.infrastructure.reporting.pdf_generator import PdfReportGenerator
from src.infrastructure.visualization.chart_generator import ChartGenerator
from src.infrastructure.gis.thermal_georeferencer import ThermalGeoReferencer

logger = get_logger("ReportService")


class ReportService:
    """
    Serviço central de emissão de relatórios periciais e técnicos (PDF / Excel).
    """

    def __init__(
        self,
        project_repository: IProjectRepository,
        client_repository: IClientRepository,
        inspection_repository: IInspectionRepository,
        thermal_image_repository: IThermalImageRepository,
        thermal_anomaly_repository: IThermalAnomalyRepository,
        report_repository: IReportRepository,
        pdf_generator: Optional[PdfReportGenerator] = None,
        chart_generator: Optional[ChartGenerator] = None,
        georeferencer: Optional[ThermalGeoReferencer] = None,
    ) -> None:
        self.project_repo = project_repository
        self.client_repo = client_repository
        self.inspection_repo = inspection_repository
        self.image_repo = thermal_image_repository
        self.anomaly_repo = thermal_anomaly_repository
        self.report_repo = report_repository
        self.pdf_generator = pdf_generator or PdfReportGenerator()
        self.chart_generator = chart_generator or ChartGenerator()
        self.georeferencer = georeferencer or ThermalGeoReferencer()

    def generate_inspection_pdf(
        self,
        inspection_id: str,
        inspector_name: Optional[str] = None,
        technical_conclusion: Optional[str] = None,
        include_charts: bool = True,
        output_filename: Optional[str] = None,
    ) -> Result[Report, str]:
        """
        Compila todos os dados da inspeção fotovoltaica e gera o relatório técnico formal em PDF.
        Persiste o registro do relatório gerado no banco de dados SQLite.
        
        :param inspection_id: Identificador único da inspeção.
        :param inspector_name: Nome do engenheiro/inspetor signatário (opcional).
        :param technical_conclusion: Parecer técnico descritivo personalizado (opcional).
        :param include_charts: Se True, gera e anexa gráficos analíticos do Matplotlib no PDF.
        :param output_filename: Nome personalizado para o arquivo PDF (opcional).
        :return: Result contendo a entidade Report persistida.
        """
        try:
            inspection = self.inspection_repo.get_by_id(inspection_id)
            if not inspection:
                return Failure(f"Inspeção não encontrada: {inspection_id}")

            project = self.project_repo.get_by_id(inspection.project_id) if inspection.project_id else None
            project_name = project.name if project else "Usina Fotovoltaica"
            location = project.location_name if project else "Localização não informada"
            capacity = project.capacity_kwp if project else 0.0

            # Buscar Cliente
            client_name = project.client_name if project else "Cliente Corporativo"
            if project and project.client_id:
                client = self.client_repo.get_by_id(project.client_id)
                if client:
                    client_name = client.name

            # Buscar Imagens e Anomalias
            images = self.image_repo.list_by_inspection(inspection_id)
            anomalies_items: List[AnomalyReportItem] = []

            max_t_global = 0.0
            max_dt_global = 0.0
            critical_count = 0
            medium_count = 0
            low_count = 0
            info_count = 0

            faults_by_type: Dict[str, int] = {}
            faults_by_severity: Dict[str, int] = {
                "Crítico (Classe 3 - IEC)": 0,
                "Médio (Classe 2 - IEC)": 0,
                "Baixo (Classe 1 - IEC)": 0,
                "Informativo / Normal": 0,
            }

            for img in images:
                anomalies = self.anomaly_repo.list_by_image(img.id)
                for anom in anomalies:
                    # Projetar coordenada geográfica se houver telemetria do drone
                    coord = None
                    if img.coordinate:
                        coord = self.georeferencer.project_anomaly_coordinate(
                            drone_coordinate=img.coordinate,
                            bbox=anom.bbox,
                            image_width_px=img.width,
                            image_height_px=img.height,
                            flight_altitude_m=img.flight_altitude_meters,
                            yaw_deg=img.gimbal_yaw_degrees or 0.0,
                        )

                    dt_val = anom.delta_t.value if anom.delta_t else None
                    ref_t = anom.delta_t.t_ref_celsius if anom.delta_t else None

                    if anom.max_temp_celsius > max_t_global:
                        max_t_global = anom.max_temp_celsius
                    if dt_val and dt_val > max_dt_global:
                        max_dt_global = dt_val

                    # Contadores
                    if anom.severity == SeverityLevel.CRITICAL:
                        critical_count += 1
                        faults_by_severity["Crítico (Classe 3 - IEC)"] += 1
                    elif anom.severity == SeverityLevel.MEDIUM:
                        medium_count += 1
                        faults_by_severity["Médio (Classe 2 - IEC)"] += 1
                    elif anom.severity == SeverityLevel.LOW:
                        low_count += 1
                        faults_by_severity["Baixo (Classe 1 - IEC)"] += 1
                    else:
                        info_count += 1
                        faults_by_severity["Informativo / Normal"] += 1

                    type_display = anom.anomaly_type.value
                    faults_by_type[type_display] = faults_by_type.get(type_display, 0) + 1

                    item = AnomalyReportItem(
                        anomaly_id=anom.id,
                        anomaly_type=anom.anomaly_type,
                        severity=anom.severity,
                        max_temp_celsius=anom.max_temp_celsius,
                        confidence=anom.confidence,
                        delta_t_celsius=dt_val,
                        ref_temp_celsius=ref_t,
                        coordinate=coord,
                        crop_image_path=anom.crop_path,
                        context_image_path=img.file_path,
                        notes=anom.notes,
                    )
                    anomalies_items.append(item)

            total_anomalies = len(anomalies_items)
            compliance_rate = 100.0 if total_anomalies == 0 else max(0.0, 100.0 - (critical_count * 15.0 + medium_count * 5.0))

            # Gerar gráficos Matplotlib para anexar no relatório
            chart_dist_path = None
            chart_sev_path = None
            if include_charts and total_anomalies > 0:
                try:
                    c_dist = self.chart_generator.generate_fault_distribution_pie(
                        faults_by_type=faults_by_type,
                        output_filename=f"report_dist_{inspection_id[:8]}.png",
                    )
                    chart_dist_path = str(c_dist)

                    c_sev = self.chart_generator.generate_severity_bar_chart(
                        faults_by_severity=faults_by_severity,
                        output_filename=f"report_sev_{inspection_id[:8]}.png",
                    )
                    chart_sev_path = str(c_sev)
                except Exception as ex_chart:
                    logger.warning(f"Não foi possível renderizar gráficos para o PDF: {ex_chart}")

            # Montar DTO consolidado
            report_data = InspectionReportData(
                client_name=client_name,
                project_name=project_name,
                location=location,
                capacity_kwp=capacity,
                inspection_id=inspection.id,
                inspection_title=inspection.title,
                inspection_date=inspection.date,
                inspector_name=inspector_name or inspection.inspector_name or "Engenheiro Termografista",
                total_images=len(images),
                total_anomalies=total_anomalies,
                critical_count=critical_count,
                medium_count=medium_count,
                low_count=low_count,
                info_count=info_count,
                max_temp_celsius=max_t_global,
                max_delta_t_celsius=max_dt_global,
                compliance_rate_pct=round(compliance_rate, 1),
                anomalies=anomalies_items,
                chart_distribution_path=chart_dist_path,
                chart_severity_path=chart_sev_path,
                technical_conclusion=technical_conclusion,
            )

            # Compilar o PDF físico
            pdf_path = self.pdf_generator.generate_report(report_data, output_filename=output_filename)
            file_size = pdf_path.stat().st_size

            # Persistir no repositório de relatórios
            report_entity = Report(
                inspection_id=inspection.id,
                title=f"Relatório Técnico - {inspection.title}",
                report_type=ReportType.PDF_TECHNICAL,
                file_path=str(pdf_path),
                file_size_bytes=file_size,
                generated_by=report_data.inspector_name,
            )
            saved_report = self.report_repo.save(report_entity)

            logger.info(f"Relatório persistido com sucesso no banco: {saved_report.id} ({file_size} bytes)")
            return Success(saved_report)

        except Exception as e:
            logger.error(f"Erro ao emitir relatório técnico para inspeção {inspection_id}: {e}", exc_info=True)
            return Failure(f"Falha na geração do relatório PDF: {str(e)}")
