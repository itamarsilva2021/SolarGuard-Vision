"""
Gerador de Relatórios Técnicos de Auditoria de Datasets em formato PDF com ReportLab.
Apresenta integridade relacional, tabelas de distribuição de classes e recomendações de treino.
"""

from pathlib import Path
from typing import Optional
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from src.application.dataset.dataset_audit import DatasetAuditResult
from src.infrastructure.reporting.numbered_canvas import NumberedCanvas
from src.core.logger import get_logger

logger = get_logger("DatasetPdfReportGenerator")


class DatasetPdfReportGenerator:
    """
    Constrói e compila relatórios em PDF de auditoria e validação de datasets para YOLOv11.
    """

    def __init__(self) -> None:
        self.styles = self._setup_styles()

    def _setup_styles(self) -> dict:
        """Configura a tipografia e paleta visual executiva SolarGuard Vision."""
        base_styles = getSampleStyleSheet()
        custom = {}

        custom["Title"] = ParagraphStyle(
            "ReportTitle",
            parent=base_styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            alignment=TA_LEFT,
        )

        custom["Subtitle"] = ParagraphStyle(
            "ReportSubtitle",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748B"),
            alignment=TA_LEFT,
        )

        custom["SectionHeader"] = ParagraphStyle(
            "SectionHeader",
            parent=base_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=14,
            spaceAfter=6,
        )

        custom["Body"] = ParagraphStyle(
            "BodyTextCustom",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155"),
        )

        custom["TableHeader"] = ParagraphStyle(
            "TableHeaderCustom",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.white,
            alignment=TA_CENTER,
        )

        custom["TableCell"] = ParagraphStyle(
            "TableCellCustom",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1E293B"),
        )

        custom["TableCellCenter"] = ParagraphStyle(
            "TableCellCenterCustom",
            parent=custom["TableCell"],
            alignment=TA_CENTER,
        )

        custom["Recommendation"] = ParagraphStyle(
            "RecText",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#1E293B"),
        )

        return custom

    def generate_report(
        self,
        audit_result: DatasetAuditResult,
        output_pdf_path: str | Path,
    ) -> Path:
        """
        Renderiza e salva o documento PDF de auditoria técnica do dataset.
        
        :param audit_result: Resultado da auditoria gerado pelo DatasetAuditor.
        :param output_pdf_path: Caminho de saída para o arquivo .pdf.
        :return: Path do arquivo gerado.
        """
        out_path = Path(output_pdf_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=letter,
            leftMargin=40,
            rightMargin=40,
            topMargin=50,
            bottomMargin=50,
        )

        story = []

        # 1. Cabeçalho Institucional
        story.append(Paragraph("SOLARGUARD VISION - AUDITORIA DE DATASET", self.styles["Title"]))
        story.append(Paragraph(
            f"Relatório Técnico de Integridade e Balanceamento para Treinamento YOLOv11 &bull; {audit_result.audit_timestamp.strftime('%d/%m/%Y %H:%M:%S')}",
            self.styles["Subtitle"],
        ))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceAfter=12))

        # 2. Resumo Executivo e Status
        status_color = "#16A34A" if audit_result.is_approved_for_training else "#DC2626"
        status_text = "APROVADO PARA TREINAMENTO" if audit_result.is_approved_for_training else "REPROVADO / REQUER AJUSTES"

        summary_table_data = [
            [
                Paragraph("<b>Diretório do Dataset:</b>", self.styles["TableCell"]),
                Paragraph(str(audit_result.dataset_path), self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>Status de Homologação:</b>", self.styles["TableCell"]),
                Paragraph(f"<font color='{status_color}'><b>{status_text}</b></font>", self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>Grau de Balanceamento:</b>", self.styles["TableCell"]),
                Paragraph(audit_result.balance.severity.display_name, self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>Diagnóstico Executivo:</b>", self.styles["TableCell"]),
                Paragraph(audit_result.executive_summary, self.styles["TableCell"]),
            ],
        ]

        summary_table = Table(summary_table_data, colWidths=[140, 390])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 14))

        # 3. Métricas de Integridade Relacional
        story.append(Paragraph("1. Integridade Relacional e Sintática", self.styles["SectionHeader"]))
        val = audit_result.validation
        stats = audit_result.statistics

        integrity_data = [
            [
                Paragraph("Métrica de Validação", self.styles["TableHeader"]),
                Paragraph("Valor Observado", self.styles["TableHeader"]),
                Paragraph("Avaliação Técnica", self.styles["TableHeader"]),
            ],
            [
                Paragraph("Total de Imagens", self.styles["TableCell"]),
                Paragraph(str(val.total_images), self.styles["TableCellCenter"]),
                Paragraph("Amostras de imagens térmicas detectadas", self.styles["TableCell"]),
            ],
            [
                Paragraph("Total de Bounding Boxes", self.styles["TableCell"]),
                Paragraph(str(stats.total_annotations), self.styles["TableCellCenter"]),
                Paragraph("Anotações válidas para inferência", self.styles["TableCell"]),
            ],
            [
                Paragraph("Imagens sem Rótulo (Órfãs/Fundo)", self.styles["TableCell"]),
                Paragraph(str(len(val.images_without_label_file)), self.styles["TableCellCenter"]),
                Paragraph("Tratadas como negativos (background)" if len(val.images_without_label_file) > 0 else "Nenhuma imagem sem anotação", self.styles["TableCell"]),
            ],
            [
                Paragraph("Labels Órfãos (sem Imagem)", self.styles["TableCell"]),
                Paragraph(f"<font color='{'red' if val.orphan_labels else 'black'}'><b>{len(val.orphan_labels)}</b></font>", self.styles["TableCellCenter"]),
                Paragraph("Inconsistência crítica!" if val.orphan_labels else "Nenhum label sem imagem correspondente", self.styles["TableCell"]),
            ],
            [
                Paragraph("Anotações com Classes Inválidas", self.styles["TableCell"]),
                Paragraph(f"<font color='{'red' if val.invalid_class_errors else 'black'}'><b>{len(val.invalid_class_errors)}</b></font>", self.styles["TableCellCenter"]),
                Paragraph("ID de classe fora do schema oficial!" if val.invalid_class_errors else "Todas as classes em conformidade", self.styles["TableCell"]),
            ],
        ]

        integrity_table = Table(integrity_data, colWidths=[180, 90, 260])
        integrity_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(integrity_table)
        story.append(Spacer(1, 14))

        # 4. Distribuição de Classes Fotovoltaicas
        story.append(Paragraph("2. Distribuição Quantitativa por Classe Térmica", self.styles["SectionHeader"]))

        class_table_data = [
            [
                Paragraph("ID", self.styles["TableHeader"]),
                Paragraph("Classe Térmica", self.styles["TableHeader"]),
                Paragraph("Contagem", self.styles["TableHeader"]),
                Paragraph("Proporção (%)", self.styles["TableHeader"]),
                Paragraph("Imagens", self.styles["TableHeader"]),
                Paragraph("Área Média Box", self.styles["TableHeader"]),
            ]
        ]

        for item in stats.class_distribution:
            class_table_data.append([
                Paragraph(str(item.class_id), self.styles["TableCellCenter"]),
                Paragraph(f"<b>{item.class_name}</b>", self.styles["TableCell"]),
                Paragraph(str(item.instance_count), self.styles["TableCellCenter"]),
                Paragraph(f"{item.percentage:.1f}%", self.styles["TableCellCenter"]),
                Paragraph(str(item.images_containing_count), self.styles["TableCellCenter"]),
                Paragraph(f"{item.avg_box_area * 100:.2f}%", self.styles["TableCellCenter"]),
            ])

        class_table = Table(class_table_data, colWidths=[35, 175, 75, 75, 75, 95])
        class_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0284C7")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(class_table)
        story.append(Spacer(1, 14))

        # 5. Métricas de Desbalanceamento e Recomendações de Treinamento
        story.append(KeepTogether([
            Paragraph("3. Diagnóstico de Desbalanceamento e Recomendações", self.styles["SectionHeader"]),
            Paragraph(
                f"<b>Imbalance Ratio (IR):</b> {audit_result.balance.imbalance_ratio}x &bull; "
                f"<b>Entropia Normalizada de Shannon:</b> {audit_result.balance.normalized_entropy * 100:.1f}%",
                self.styles["Body"],
            ),
            Spacer(1, 6),
        ]))

        rec_items = []
        for rec in audit_result.balance.recommendations:
            rec_items.append([
                Paragraph("&bull;", self.styles["TableCellCenter"]),
                Paragraph(rec, self.styles["Recommendation"]),
            ])

        if rec_items:
            rec_table = Table(rec_items, colWidths=[20, 510])
            rec_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(rec_table)

        story.append(Spacer(1, 14))

        # Compilação do PDF
        doc.build(story, canvasmaker=NumberedCanvas)
        logger.info(f"Relatório PDF de auditoria gerado com sucesso em: {out_path}")
        return out_path
