"""
Gerador de Relatórios Técnicos Profissionais em PDF utilizando ReportLab para o SolarGuard Vision.
Consolida dados do Cliente, Inspeção, Fotos Térmicas, Catálogo de Falhas (IEC TS 62446-3),
Mapa Georreferenciado, Gráficos Analíticos e Conclusão Técnica com Assinatura.
"""

from pathlib import Path
from typing import Optional, List, Union
from datetime import datetime
import os

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    KeepTogether,
    HRFlowable,
    PageBreak,
)
from reportlab.lib import colors

from src.application.dtos.report_dtos import InspectionReportData, AnomalyReportItem
from src.domain.enums.severity_level import SeverityLevel
from src.infrastructure.reporting.pdf_styles import PdfTheme, create_report_styles

from src.infrastructure.reporting.numbered_canvas import NumberedCanvas
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("PdfReportGenerator")


class PdfReportGenerator:
    """
    Gerador industrial de relatórios periciais e técnicos em PDF com ReportLab.
    """

    # Dimensões da página A4: 595.27 x 841.89 pontos
    PAGE_WIDTH, PAGE_HEIGHT = A4
    MARGIN = 36.0  # 0.5 polegadas (12.7 mm) para aproveitamento técnico ideal

    def __init__(self, output_dir: Optional[Union[Path, str]] = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else settings.reports_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = create_report_styles()

    def generate_report(
        self,
        data: InspectionReportData,
        output_filename: Optional[str] = None,
    ) -> Path:
        """
        Compila e gera o documento PDF completo para a inspeção termográfica.
        
        :param data: DTO consolidado com dados de cliente, usina, falhas, fotos e conclusão.
        :param output_filename: Nome personalizado para o arquivo PDF (opcional).
        :return: Path do arquivo PDF gerado.
        """
        if not output_filename:
            safe_title = "".join(c if c.isalnum() else "_" for c in data.project_name)[:20]
            output_filename = f"Relatorio_Termografico_{safe_title}_{data.inspection_id[:8]}.pdf"

        out_path = self.output_dir / output_filename

        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=A4,
            leftMargin=self.MARGIN,
            rightMargin=self.MARGIN,
            topMargin=self.MARGIN,
            bottomMargin=self.MARGIN + 6,
        )

        content_width = self.PAGE_WIDTH - (2 * self.MARGIN)
        story = []

        # -------------------------------------------------------------
        # 1. Cabeçalho Principal e Dados do Cliente / Inspeção
        # -------------------------------------------------------------
        story.extend(self._build_header_and_client_section(data, content_width))
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 2. Resumo Executivo e Indicadores Normativos (KPIs)
        # -------------------------------------------------------------
        story.extend(self._build_kpis_and_charts_section(data, content_width))
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 3. Georreferenciamento e Mapa Espacial
        # -------------------------------------------------------------
        story.extend(self._build_map_and_spatial_section(data, content_width))
        story.append(Spacer(1, 12))

        # -------------------------------------------------------------
        # 4. Catálogo Detalhado das Falhas com Fotos Térmicas
        # -------------------------------------------------------------
        story.extend(self._build_anomalies_catalog_section(data, content_width))
        story.append(Spacer(1, 12))

        # -------------------------------------------------------------
        # 5. Conclusão Técnica e Assinatura do Responsável
        # -------------------------------------------------------------
        story.extend(self._build_conclusion_and_signature_section(data, content_width))

        # Compilação do PDF usando o NumberedCanvas para numeração dinâmica de páginas
        doc.build(story, canvasmaker=NumberedCanvas)

        logger.info(f"Relatório técnico em PDF gerado com sucesso: {out_path}")
        return out_path

    def _build_header_and_client_section(self, data: InspectionReportData, width: float) -> List:
        """Constrói o cabeçalho institucional e as tabelas com dados do cliente e da inspeção."""
        flowables = []

        # Topo institucional com badge solar
        header_table = Table(
            [
                [
                    Paragraph("<b>SOLARGUARD VISION</b>", self.styles["DocTitle"]),
                    Paragraph(
                        f"<b>RELATÓRIO TÉCNICO DE INSPEÇÃO</b><br/>"
                        f"<font size=8 color='#64748B'>IEC TS 62446-3  |  Emissão: {datetime.now().strftime('%d/%m/%Y')}</font>",
                        self.styles["TableCellCenter"]
                    ),
                ]
            ],
            colWidths=[width * 0.55, width * 0.45],
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        flowables.append(header_table)
        flowables.append(HRFlowable(width="100%", thickness=1.5, color=PdfTheme.ACCENT_GOLD, spaceAfter=8, spaceBefore=4))

        # Tabela com Dados do Cliente, Usina Fotovoltaica e Inspeção
        date_str = data.inspection_date.strftime("%d/%m/%Y %H:%M")
        info_data = [
            [
                Paragraph("<b>Cliente:</b>", self.styles["BodyBold"]),
                Paragraph(data.client_name, self.styles["TableCell"]),
                Paragraph("<b>Inspeção:</b>", self.styles["BodyBold"]),
                Paragraph(data.inspection_title, self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>Usina / Projeto:</b>", self.styles["BodyBold"]),
                Paragraph(f"{data.project_name} ({data.capacity_kwp:.1f} kWp)", self.styles["TableCell"]),
                Paragraph("<b>Data do Voo:</b>", self.styles["BodyBold"]),
                Paragraph(date_str, self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>Localização:</b>", self.styles["BodyBold"]),
                Paragraph(data.location, self.styles["TableCell"]),
                Paragraph("<b>Responsável:</b>", self.styles["BodyBold"]),
                Paragraph(data.inspector_name, self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>Aeronave / Sensor:</b>", self.styles["BodyBold"]),
                Paragraph(data.drone_model, self.styles["TableCell"]),
                Paragraph("<b>Condições:</b>", self.styles["BodyBold"]),
                Paragraph(
                    f"Amb: {data.ambient_temp_celsius or 30:.1f}°C | Irr: {data.irradiance_w_m2 or 800:.0f} W/m² | Vento: {data.wind_speed_m_s or 2.0:.1f} m/s",
                    self.styles["TableCell"]
                ),
            ],
        ]

        info_table = Table(info_data, colWidths=[width * 0.18, width * 0.32, width * 0.18, width * 0.32])
        info_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PdfTheme.BG_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, PdfTheme.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, PdfTheme.BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        flowables.append(info_table)
        return flowables

    def _build_kpis_and_charts_section(self, data: InspectionReportData, width: float) -> List:
        """Constrói os cards de KPIs analíticos e os gráficos do Matplotlib."""
        flowables = [Paragraph("1. Resumo Executivo e Indicadores Normativos", self.styles["SectionHeader"])]

        # Cards de KPI em tabela
        kpi_cells = [
            [
                Paragraph(f"<b>{data.total_images}</b><br/><font size=7 color='#64748B'>Termogramas</font>", self.styles["TableCellCenter"]),
                Paragraph(f"<b>{data.total_anomalies}</b><br/><font size=7 color='#64748B'>Falhas Totais</font>", self.styles["TableCellCenter"]),
                Paragraph(f"<b><font color='#DC2626'>{data.critical_count}</font></b><br/><font size=7 color='#64748B'>Críticas (Classe 3)</font>", self.styles["TableCellCenter"]),
                Paragraph(f"<b><font color='#EA580C'>{data.medium_count}</font></b><br/><font size=7 color='#64748B'>Médias (Classe 2)</font>", self.styles["TableCellCenter"]),
                Paragraph(f"<b><font color='#CA8A04'>{data.low_count}</font></b><br/><font size=7 color='#64748B'>Baixas (Classe 1)</font>", self.styles["TableCellCenter"]),
                Paragraph(f"<b>{data.max_delta_t_celsius:.1f}°C</b><br/><font size=7 color='#64748B'>Gradiente ΔT Máx</font>", self.styles["TableCellCenter"]),
                Paragraph(f"<b><font color='#16A34A'>{data.compliance_rate_pct:.1f}%</font></b><br/><font size=7 color='#64748B'>Conformidade</font>", self.styles["TableCellCenter"]),
            ]
        ]
        kpi_table = Table(kpi_cells, colWidths=[width / 7.0] * 7)
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PdfTheme.BG_ALT),
            ("BOX", (0, 0), (-1, -1), 0.5, PdfTheme.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, PdfTheme.BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        flowables.append(kpi_table)

        # Inclusão de Gráficos Analíticos Matplotlib (se informados e existentes)
        charts_to_display = []
        if data.chart_distribution_path and os.path.exists(data.chart_distribution_path):
            charts_to_display.append(Image(data.chart_distribution_path, width=width * 0.48, height=140))
        if data.chart_severity_path and os.path.exists(data.chart_severity_path):
            charts_to_display.append(Image(data.chart_severity_path, width=width * 0.48, height=140))

        if charts_to_display:
            flowables.append(Spacer(1, 6))
            if len(charts_to_display) == 2:
                charts_table = Table([[charts_to_display[0], charts_to_display[1]]], colWidths=[width * 0.5, width * 0.5])
            else:
                charts_table = Table([[charts_to_display[0]]], colWidths=[width])
            charts_table.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]))
            flowables.append(charts_table)

        return flowables

    def _build_map_and_spatial_section(self, data: InspectionReportData, width: float) -> List:
        """Constrói a seção de georreferenciamento e distribuição espacial das anomalias."""
        flowables = [Paragraph("2. Mapeamento e Georreferenciamento de Falhas", self.styles["SectionHeader"])]

        desc_text = (
            "As coordenadas geodésicas (WGS84) foram obtidas por telemetria e projeção fotogramétrica aérea "
            "do drone DJI Matrice 4T, permitindo a localização imediata em campo das strings e módulos com avarias."
        )
        flowables.append(Paragraph(desc_text, self.styles["Body"]))

        # Se houver imagem do mapa geral/satélite disponível
        if data.map_overview_image_path and os.path.exists(data.map_overview_image_path):
            flowables.append(Spacer(1, 4))
            map_img = Image(data.map_overview_image_path, width=width, height=160)
            flowables.append(map_img)

        # Tabela sintética de localização espacial das falhas
        if data.anomalies:
            table_header = [
                Paragraph("<b>Item</b>", self.styles["TableHeader"]),
                Paragraph("<b>Falha Detectada</b>", self.styles["TableHeader"]),
                Paragraph("<b>Severidade IEC</b>", self.styles["TableHeader"]),
                Paragraph("<b>T. Máx</b>", self.styles["TableHeader"]),
                Paragraph("<b>Gradiente (ΔT)</b>", self.styles["TableHeader"]),
                Paragraph("<b>Latitude</b>", self.styles["TableHeader"]),
                Paragraph("<b>Longitude</b>", self.styles["TableHeader"]),
            ]
            rows = [table_header]

            for idx, anom in enumerate(data.anomalies[:8], start=1):  # Lista sumária até 8 registros no quadro
                lat_str = f"{anom.coordinate.latitude:.6f}°" if anom.coordinate else "N/A"
                lon_str = f"{anom.coordinate.longitude:.6f}°" if anom.coordinate else "N/A"
                delta_str = f"+{anom.delta_t_celsius:.1f}°C" if anom.delta_t_celsius is not None else "N/A"

                rows.append([
                    Paragraph(f"#{idx:02d}", self.styles["TableCellCenter"]),
                    Paragraph(anom.anomaly_type_name, self.styles["TableCell"]),
                    Paragraph(f"<b><font color='{anom.severity_hex}'>{anom.severity_name}</font></b>", self.styles["TableCellCenter"]),
                    Paragraph(f"{anom.max_temp_celsius:.1f}°C", self.styles["TableCellCenter"]),
                    Paragraph(delta_str, self.styles["TableCellCenter"]),
                    Paragraph(lat_str, self.styles["TableCellCenter"]),
                    Paragraph(lon_str, self.styles["TableCellCenter"]),
                ])

            spatial_table = Table(
                rows,
                colWidths=[width * 0.08, width * 0.26, width * 0.22, width * 0.11, width * 0.11, width * 0.11, width * 0.11]
            )
            spatial_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), PdfTheme.PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, PdfTheme.BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, PdfTheme.BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PdfTheme.BG_LIGHT]),
            ]))
            flowables.append(Spacer(1, 4))
            flowables.append(spatial_table)

        return flowables

    def _build_anomalies_catalog_section(self, data: InspectionReportData, width: float) -> List:
        """Constrói o catálogo individual com fotos térmicas, diagnósticos e recomendações técnicas."""
        flowables = [
            PageBreak(),  # Quebra para iniciar o catálogo de evidências fotográficas em nova página
            Paragraph("3. Catálogo Técnico de Falhas e Termogramas", self.styles["SectionHeader"])
        ]

        if not data.anomalies:
            flowables.append(
                Paragraph("<i>Nenhuma anomalia térmica detectada nesta inspeção. Sistema em plena conformidade.</i>", self.styles["Body"])
            )
            return flowables

        for idx, anom in enumerate(data.anomalies, start=1):
            anom_flowables = []

            # Cabeçalho do Card da Falha
            title_text = f"<b>Falha #{idx:02d} — {anom.anomaly_type_name}</b>"
            badge_html = f"<b><font color='{anom.severity_hex}'>[{anom.severity_name.upper()}]</font></b>"

            card_top = Table(
                [[Paragraph(title_text, self.styles["SubsectionHeader"]), Paragraph(badge_html, self.styles["TableCellCenter"])]],
                colWidths=[width * 0.70, width * 0.30]
            )
            card_top.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), PdfTheme.BG_ALT),
                ("BOX", (0, 0), (-1, -1), 0.5, PdfTheme.BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            anom_flowables.append(card_top)

            # Tabela de parâmetros e medições
            delta_str = f"+{anom.delta_t_celsius:.1f}°C" if anom.delta_t_celsius is not None else "N/A"
            ref_str = f"{anom.ref_temp_celsius:.1f}°C" if anom.ref_temp_celsius is not None else "N/A"
            lat_str = f"{anom.coordinate.latitude:.6f}°" if anom.coordinate else "N/A"
            lon_str = f"{anom.coordinate.longitude:.6f}°" if anom.coordinate else "N/A"

            metrics_data = [
                [
                    Paragraph(f"<b>T. Máxima:</b> {anom.max_temp_celsius:.1f}°C", self.styles["TableCell"]),
                    Paragraph(f"<b>T. Referência:</b> {ref_str}", self.styles["TableCell"]),
                    Paragraph(f"<b>Gradiente (ΔT):</b> {delta_str}", self.styles["TableCell"]),
                    Paragraph(f"<b>Confiança IA:</b> {anom.confidence * 100:.1f}%", self.styles["TableCell"]),
                ],
                [
                    Paragraph(f"<b>Latitude:</b> {lat_str}", self.styles["TableCell"]),
                    Paragraph(f"<b>Longitude:</b> {lon_str}", self.styles["TableCell"]),
                    Paragraph("<b>Norma:</b> IEC TS 62446-3", self.styles["TableCell"]),
                    Paragraph("<b>Status:</b> Intervenção Recomendada", self.styles["TableCell"]),
                ]
            ]
            metrics_table = Table(metrics_data, colWidths=[width * 0.25] * 4)
            metrics_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), PdfTheme.BG_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, PdfTheme.BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, PdfTheme.BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            anom_flowables.append(metrics_table)

            # Bloco de Imagens Lado a Lado (Contexto Térmico e Crop Ampliado)
            images_cells = []
            img_width = (width / 2.0) - 6
            img_height = 135

            has_context = anom.context_image_path and os.path.exists(anom.context_image_path)
            has_crop = anom.crop_image_path and os.path.exists(anom.crop_image_path)

            if has_context and has_crop:
                img_context = Image(anom.context_image_path, width=img_width, height=img_height)
                img_crop = Image(anom.crop_image_path, width=img_width, height=img_height)
                images_cells = [[
                    Paragraph("<font size=7 color='#64748B'>Termograma Geral (DJI Matrice 4T)</font>", self.styles["TableCellCenter"]),
                    Paragraph("<font size=7 color='#64748B'>Recorte Ampliado da Falha (IA)</font>", self.styles["TableCellCenter"])
                ], [img_context, img_crop]]
            elif has_context:
                img_context = Image(anom.context_image_path, width=img_width * 1.5, height=img_height)
                images_cells = [[Paragraph("<font size=7 color='#64748B'>Termograma Geral</font>", self.styles["TableCellCenter"])], [img_context]]
            elif has_crop:
                img_crop = Image(anom.crop_image_path, width=img_width * 1.5, height=img_height)
                images_cells = [[Paragraph("<font size=7 color='#64748B'>Recorte da Anomalia Térmica</font>", self.styles["TableCellCenter"])], [img_crop]]

            if images_cells:
                img_table = Table(images_cells, colWidths=[width / len(images_cells[0])] * len(images_cells[0]))
                img_table.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]))
                anom_flowables.append(img_table)

            # Recomendação Técnica
            rec_text = anom.corrective_action or anom.default_recommendation
            obs_text = f"<br/><b>Observação em Campo:</b> {anom.notes}" if anom.notes else ""
            rec_html = f"<b>Ação Corretiva Recomendada:</b> {rec_text}{obs_text}"

            rec_table = Table([[Paragraph(rec_html, self.styles["CalloutText"])]], colWidths=[width])
            rec_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2") if anom.severity == SeverityLevel.CRITICAL else PdfTheme.BG_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, anom.severity.color_hex),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]))
            anom_flowables.append(rec_table)
            anom_flowables.append(Spacer(1, 10))

            # Mantém o card da falha indivisível entre páginas quando possível
            flowables.append(KeepTogether(anom_flowables))

        return flowables

    def _build_conclusion_and_signature_section(self, data: InspectionReportData, width: float) -> List:
        """Constrói a conclusão técnica normativa e o campo de assinatura do engenheiro."""
        flowables = [
            Paragraph("4. Conclusão Técnica e Parecer de Engenharia", self.styles["SectionHeader"])
        ]

        # Texto padrão pericial caso não informado texto específico
        if data.technical_conclusion:
            concl_text = data.technical_conclusion
        else:
            if data.critical_count > 0:
                concl_text = (
                    f"A inspeção termográfica automatizada identificou um total de <b>{data.total_anomalies} anomalias</b>, "
                    f"das quais <b><font color='#DC2626'>{data.critical_count} encontram-se em Nível Crítico (Classe 3 - IEC TS 62446-3)</font></b> "
                    f"com gradientes térmicos superiores a 30°C (máximo registrado: ΔT {data.max_delta_t_celsius:.1f}°C). "
                    "Recomenda-se intervenção emergencial com desenergização e substituição das unidades avariadas "
                    "para mitigar riscos iminentes de incêndio e perda permanente de rendimento da usina."
                )
            elif data.medium_count > 0:
                concl_text = (
                    f"Foram identificadas <b>{data.total_anomalies} anomalias térmicas</b> com classificação preponderante "
                    "em Nível Médio (Classe 2). Recomenda-se manutenção programada em até 30 dias para regularização de strings "
                    "e limpeza preventiva de sujidades acumuladas."
                )
            else:
                concl_text = (
                    "O parque fotovoltaico inspecionado encontra-se em excelente estado operacional, com "
                    f"<b>{data.compliance_rate_pct:.1f}% de conformidade normativa</b>. Nenhuma intervenção corretiva emergencial "
                    "é necessária no momento, mantendo-se o plano semestral de monitoramento preventivo."
                )

        concl_table = Table([[Paragraph(concl_text, self.styles["BodyJustify"])]], colWidths=[width])
        concl_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PdfTheme.BG_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, PdfTheme.BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        flowables.append(concl_table)
        flowables.append(Spacer(1, 24))

        # Bloco de Assinatura do Responsável Técnico
        sig_data = [
            [
                Paragraph("", self.styles["TableCell"]),
                Paragraph("____________________________________________________<br/>"
                          f"<b>{data.inspector_name}</b><br/>"
                          f"<font size=8 color='#64748B'>Engenheiro Responsável Técnico  |  Termografia Nível 2<br/>"
                          f"CREA / ART Registrada  |  {data.company_name}</font>", self.styles["TableCellCenter"]),
                Paragraph("", self.styles["TableCell"]),
            ]
        ]
        sig_table = Table(sig_data, colWidths=[width * 0.15, width * 0.70, width * 0.15])
        sig_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        flowables.append(KeepTogether([sig_table]))

        return flowables
