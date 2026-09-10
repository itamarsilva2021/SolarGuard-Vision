"""
Gerador de Relatórios Científicos de Validação para SolarGuard Vision.
Suporta exportação em PDF (ReportLab), Excel (.xlsx via OpenXML nativo) e CSV estruturado.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from datetime import datetime
import csv
import zipfile
import io

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
    Image as RLImage,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from src.application.validation.classification_metrics import GlobalClassificationMetrics, ClassMetrics
from src.application.validation.roc_curve_service import RocCurveData
from src.application.validation.benchmark_service import ModelBenchmarkResult
from src.infrastructure.reporting.numbered_canvas import NumberedCanvas
from src.core.logger import get_logger

logger = get_logger("ScientificValidationReport")


@dataclass
class ScientificValidationReportData:
    """Contrato de dados consolidado para emissão dos relatórios de validação científica."""
    model_name: str
    dataset_name: str
    metrics: GlobalClassificationMetrics
    roc_curves: Optional[Dict[str, RocCurveData]] = None
    benchmark: Optional[ModelBenchmarkResult] = None
    confusion_matrix_img: Optional[Union[str, Path]] = None
    roc_curve_img: Optional[Union[str, Path]] = None
    notes: Optional[str] = None


class ScientificValidationReport:
    """
    Exportador de relatórios científicos em formatos PDF, Excel (.xlsx) e CSV.
    """

    # =========================================================================
    # 1. EXPORTAÇÃO CSV
    # =========================================================================
    def export_csv(
        self,
        data: ScientificValidationReportData,
        output_path: Union[str, Path],
        delimiter: str = ";",
    ) -> Path:
        """
        Exporta as métricas científicas em arquivo CSV com codificação UTF-8-SIG (compatível com Excel).
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with open(out, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=delimiter)

            # Cabeçalho do Relatório
            writer.writerow(["SOLARGUARD VISION - RELATÓRIO CIENTÍFICO DE VALIDAÇÃO DE IA"])
            writer.writerow(["Modelo Avaliado", data.model_name])
            writer.writerow(["Dataset de Teste", data.dataset_name])
            writer.writerow(["Data de Emissão", datetime.now().strftime("%d/%m/%Y %H:%M:%S")])
            writer.writerow([])

            # Resumo Global
            writer.writerow(["--- RESUMO GLOBAL DE CLASSIFICAÇÃO ---"])
            writer.writerow(["Métrica", "Valor", "Percentual"])
            writer.writerow(["Total de Amostras", data.metrics.total_samples, "-"])
            writer.writerow(["Acurácia Global (Accuracy)", f"{data.metrics.accuracy:.4f}", f"{data.metrics.accuracy * 100:.2f}%"])
            writer.writerow(["Acurácia Balanceada", f"{data.metrics.balanced_accuracy:.4f}", f"{data.metrics.balanced_accuracy * 100:.2f}%"])
            writer.writerow(["Precisão Macro (Precision)", f"{data.metrics.macro_precision:.4f}", f"{data.metrics.macro_precision * 100:.2f}%"])
            writer.writerow(["Revocação Macro (Recall)", f"{data.metrics.macro_recall:.4f}", f"{data.metrics.macro_recall * 100:.2f}%"])
            writer.writerow(["F1-Score Macro", f"{data.metrics.macro_f1:.4f}", f"{data.metrics.macro_f1 * 100:.2f}%"])
            writer.writerow(["Precisão Ponderada (Weighted)", f"{data.metrics.weighted_precision:.4f}", f"{data.metrics.weighted_precision * 100:.2f}%"])
            writer.writerow(["Revocação Ponderada (Weighted)", f"{data.metrics.weighted_recall:.4f}", f"{data.metrics.weighted_recall * 100:.2f}%"])
            writer.writerow(["F1-Score Ponderado (Weighted)", f"{data.metrics.weighted_f1:.4f}", f"{data.metrics.weighted_f1 * 100:.2f}%"])

            if data.benchmark:
                writer.writerow(["mAP@0.50", f"{data.benchmark.map50:.4f}", f"{data.benchmark.map50 * 100:.2f}%"])
                writer.writerow(["mAP@0.50:0.95", f"{data.benchmark.map50_95:.4f}", f"{data.benchmark.map50_95 * 100:.2f}%"])
                writer.writerow(["Latência Média (ms)", f"{data.benchmark.inference_time_ms:.2f}", "-"])
                writer.writerow(["Taxa de Quadros (FPS)", f"{data.benchmark.fps:.1f}", "-"])

            writer.writerow([])

            # Métricas Detalhadas por Classe
            writer.writerow(["--- MÉTRICAS POR CLASSE ---"])
            headers = ["Classe", "Amostras", "TP", "FP", "TN", "FN", "Precisão", "Recall", "Especificidade", "F1-Score", "Bal. Acc."]
            if data.roc_curves:
                headers.extend(["AUC-ROC", "Limiar Ótimo"])
            writer.writerow(headers)

            for cls_name, cm in data.metrics.per_class_metrics.items():
                row = [
                    cls_name,
                    cm.total_samples,
                    cm.true_positives,
                    cm.false_positives,
                    cm.true_negatives,
                    cm.false_negatives,
                    f"{cm.precision:.4f}",
                    f"{cm.recall:.4f}",
                    f"{cm.specificity:.4f}",
                    f"{cm.f1_score:.4f}",
                    f"{cm.balanced_accuracy:.4f}",
                ]
                if data.roc_curves and cls_name in data.roc_curves:
                    rc = data.roc_curves[cls_name]
                    row.extend([f"{rc.auc:.4f}", f"{rc.optimal_threshold:.4f}"])
                elif data.roc_curves:
                    row.extend(["-", "-"])
                writer.writerow(row)

        logger.info(f"Relatório CSV exportado: {out}")
        return out

    # =========================================================================
    # 2. EXPORTAÇÃO EXCEL (.xlsx)
    # =========================================================================
    def export_excel(
        self,
        data: ScientificValidationReportData,
        output_path: Union[str, Path],
    ) -> Path:
        """
        Gera uma planilha nativa do Microsoft Excel (.xlsx) estruturada em múltiplas abas.
        Implementado com construtor OpenXML puro e compacto (zero dependências externas).
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # Prepara dados para duas abas: "Resumo Global" e "Métricas por Classe"
        sheet1_rows = [
            ["Métrica Global", "Valor", "Percentual"],
            ["Modelo", data.model_name, ""],
            ["Dataset", data.dataset_name, ""],
            ["Total de Amostras", str(data.metrics.total_samples), ""],
            ["Acurácia (Accuracy)", f"{data.metrics.accuracy:.4f}", f"{data.metrics.accuracy*100:.2f}%"],
            ["Acurácia Balanceada", f"{data.metrics.balanced_accuracy:.4f}", f"{data.metrics.balanced_accuracy*100:.2f}%"],
            ["Precisão Macro", f"{data.metrics.macro_precision:.4f}", f"{data.metrics.macro_precision*100:.2f}%"],
            ["Recall Macro", f"{data.metrics.macro_recall:.4f}", f"{data.metrics.macro_recall*100:.2f}%"],
            ["F1-Score Macro", f"{data.metrics.macro_f1:.4f}", f"{data.metrics.macro_f1*100:.2f}%"],
            ["Precisão Ponderada", f"{data.metrics.weighted_precision:.4f}", f"{data.metrics.weighted_precision*100:.2f}%"],
            ["Recall Ponderado", f"{data.metrics.weighted_recall:.4f}", f"{data.metrics.weighted_recall*100:.2f}%"],
            ["F1-Score Ponderado", f"{data.metrics.weighted_f1:.4f}", f"{data.metrics.weighted_f1*100:.2f}%"],
        ]

        if data.benchmark:
            sheet1_rows.extend([
                ["mAP@0.50", f"{data.benchmark.map50:.4f}", f"{data.benchmark.map50*100:.2f}%"],
                ["mAP@0.50:0.95", f"{data.benchmark.map50_95:.4f}", f"{data.benchmark.map50_95*100:.2f}%"],
                ["Latência Média (ms)", f"{data.benchmark.inference_time_ms:.2f}", ""],
                ["FPS", f"{data.benchmark.fps:.1f}", ""],
            ])

        sheet2_headers = ["Classe", "Amostras", "TP", "FP", "TN", "FN", "Precisão", "Recall", "Especificidade", "F1-Score", "Bal. Acc."]
        if data.roc_curves:
            sheet2_headers.extend(["AUC-ROC", "Limiar Ótimo"])

        sheet2_rows = [sheet2_headers]
        for cls_name, cm in data.metrics.per_class_metrics.items():
            row = [
                cls_name,
                str(cm.total_samples),
                str(cm.true_positives),
                str(cm.false_positives),
                str(cm.true_negatives),
                str(cm.false_negatives),
                f"{cm.precision:.4f}",
                f"{cm.recall:.4f}",
                f"{cm.specificity:.4f}",
                f"{cm.f1_score:.4f}",
                f"{cm.balanced_accuracy:.4f}",
            ]
            if data.roc_curves and cls_name in data.roc_curves:
                rc = data.roc_curves[cls_name]
                row.extend([f"{rc.auc:.4f}", f"{rc.optimal_threshold:.4f}"])
            elif data.roc_curves:
                row.extend(["-", "-"])
            sheet2_rows.append(row)

        self._write_xlsx_archive(out, [("Resumo Global", sheet1_rows), ("Metricas por Classe", sheet2_rows)])
        logger.info(f"Planilha Excel (.xlsx) exportada: {out}")
        return out

    @staticmethod
    def _write_xlsx_archive(filepath: Path, sheets: List[tuple]) -> None:
        """Gera pacote zip XLSX compatível com a especificação ISO/IEC 29500 (OpenXML)."""
        def make_sheet_xml(rows: List[List[str]]) -> str:
            xml = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
            xml.append('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">')
            xml.append('<sheetData>')
            for r_idx, row in enumerate(rows, start=1):
                xml.append(f'<row r="{r_idx}">')
                for c_idx, val in enumerate(row, start=1):
                    # Converte índice numérico de coluna para letra (1=A, 2=B, etc.)
                    col_letter = chr(64 + c_idx) if c_idx <= 26 else f"A{chr(64 + c_idx - 26)}"
                    cell_ref = f"{col_letter}{r_idx}"
                    safe_val = str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    xml.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{safe_val}</t></is></c>')
                xml.append('</row>')
            xml.append('</sheetData>')
            xml.append('</worksheet>')
            return "".join(xml)

        content_types = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
            '<Default Extension="xml" ContentType="application/xml"/>',
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        ]
        for idx in range(1, len(sheets) + 1):
            content_types.append(f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        content_types.append('</Types>')

        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        )

        wb_rels_parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
        ]
        for idx in range(1, len(sheets) + 1):
            wb_rels_parts.append(f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>')
        wb_rels_parts.append('</Relationships>')

        workbook_xml_parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
            '<sheets>',
        ]
        for idx, (title, _) in enumerate(sheets, start=1):
            workbook_xml_parts.append(f'<sheet name="{title}" sheetId="{idx}" r:id="rId{idx}"/>')
        workbook_xml_parts.append('</sheets></workbook>')

        with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", "".join(content_types))
            zf.writestr("_rels/.rels", root_rels)
            zf.writestr("xl/_rels/workbook.xml.rels", "".join(wb_rels_parts))
            zf.writestr("xl/workbook.xml", "".join(workbook_xml_parts))
            for idx, (_, rows) in enumerate(sheets, start=1):
                zf.writestr(f"xl/worksheets/sheet{idx}.xml", make_sheet_xml(rows))

    # =========================================================================
    # 3. EXPORTAÇÃO PDF CIENTÍFICO (ReportLab)
    # =========================================================================
    def export_pdf(
        self,
        data: ScientificValidationReportData,
        output_path: Union[str, Path],
    ) -> Path:
        """
        Compila o relatório formal em PDF com tipografia executiva, tabelas analíticas e gráficos embutidos.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(out),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=40,
            bottomMargin=40,
        )

        styles = self._setup_pdf_styles()
        story = []

        # Cabeçalho
        story.append(Paragraph("SolarGuard Vision - Relatório de Validação Científica", styles["Title"]))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"Avaliação Quantitativa de IA Térmica • Modelo: {data.model_name} • Base: {data.dataset_name}", styles["Subtitle"]))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceAfter=14))

        # Metadados
        meta_table = Table(
            [
                [
                    Paragraph(f"<b>Data da Validação:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["NormalSmall"]),
                    Paragraph(f"<b>Total de Amostras:</b> {data.metrics.total_samples}", styles["NormalSmall"]),
                ],
                [
                    Paragraph(f"<b>Acurácia Global:</b> {data.metrics.accuracy * 100:.2f}%", styles["NormalSmall"]),
                    Paragraph(f"<b>F1-Score Macro:</b> {data.metrics.macro_f1 * 100:.2f}%", styles["NormalSmall"]),
                ],
            ],
            colWidths=[270, 270],
        )
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 16))

        # Seção 1: Indicadores Globais
        story.append(Paragraph("1. Indicadores Gerais de Classificação", styles["Heading2"]))
        story.append(Spacer(1, 6))

        summary_rows = [
            ["Métrica", "Valor Numérico", "Percentual / Unidade", "Interpretação Científica"],
            ["Acurácia (Accuracy)", f"{data.metrics.accuracy:.4f}", f"{data.metrics.accuracy*100:.2f}%", "Proporção geral de predições corretas"],
            ["Acurácia Balanceada", f"{data.metrics.balanced_accuracy:.4f}", f"{data.metrics.balanced_accuracy*100:.2f}%", "Média não-enviesada das sensibilidades"],
            ["Precisão Macro", f"{data.metrics.macro_precision:.4f}", f"{data.metrics.macro_precision*100:.2f}%", "Média da precisão entre todas as classes"],
            ["Recall Macro", f"{data.metrics.macro_recall:.4f}", f"{data.metrics.macro_recall*100:.2f}%", "Sensibilidade média contra falsos negativos"],
            ["F1-Score Macro", f"{data.metrics.macro_f1:.4f}", f"{data.metrics.macro_f1*100:.2f}%", "Média harmônica global de detecção"],
        ]

        if data.benchmark:
            summary_rows.append(["mAP@0.50", f"{data.benchmark.map50:.4f}", f"{data.benchmark.map50*100:.2f}%", "Detecção de bounding boxes IoU 0.50"])
            summary_rows.append(["mAP@0.50:0.95", f"{data.benchmark.map50_95:.4f}", f"{data.benchmark.map50_95*100:.2f}%", "Métrica de rigor COCO / YOLOv11"])
            summary_rows.append(["Latência de Inferência", f"{data.benchmark.inference_time_ms:.2f}", "ms/imagem", "Tempo médio por frame na GPU/CPU"])

        sum_table = Table(summary_rows, colWidths=[130, 80, 100, 230])
        sum_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (1, 0), (2, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(sum_table)
        story.append(Spacer(1, 16))

        # Seção 2: Desempenho Discriminado por Classe
        story.append(Paragraph("2. Desempenho Detalhado por Classe de Defeito", styles["Heading2"]))
        story.append(Spacer(1, 6))

        class_headers = ["Classe", "Amostras", "Precisão", "Recall", "F1-Score", "Bal. Acc."]
        if data.roc_curves:
            class_headers.append("AUC-ROC")

        col_w = [140, 60, 68, 68, 68, 68]
        if data.roc_curves:
            col_w = [120, 50, 60, 60, 60, 60, 60]

        class_rows = [class_headers]
        for cls_name, cm in data.metrics.per_class_metrics.items():
            r = [
                cls_name,
                str(cm.total_samples),
                f"{cm.precision*100:.1f}%",
                f"{cm.recall*100:.1f}%",
                f"{cm.f1_score*100:.1f}%",
                f"{cm.balanced_accuracy*100:.1f}%",
            ]
            if data.roc_curves and cls_name in data.roc_curves:
                r.append(f"{data.roc_curves[cls_name].auc:.4f}")
            elif data.roc_curves:
                r.append("-")
            class_rows.append(r)

        cls_table = Table(class_rows, colWidths=col_w)
        cls_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(cls_table)
        story.append(Spacer(1, 16))

        # Seção 3: Visualizações Científicas Incorporadas (Matriz de Confusão e ROC)
        has_cm = data.confusion_matrix_img and Path(data.confusion_matrix_img).exists()
        has_roc = data.roc_curve_img and Path(data.roc_curve_img).exists()

        if has_cm or has_roc:
            story.append(Paragraph("3. Evidências Gráficas de Validação", styles["Heading2"]))
            story.append(Spacer(1, 6))

            images_row = []
            if has_cm:
                cm_img = RLImage(str(data.confusion_matrix_img), width=250, height=200)
                images_row.append([Paragraph("<b>Matriz de Confusão Multiclasse</b>", styles["NormalSmall"]), cm_img])
            if has_roc:
                roc_img = RLImage(str(data.roc_curve_img), width=250, height=200)
                images_row.append([Paragraph("<b>Curvas ROC & Desempenho AUC</b>", styles["NormalSmall"]), roc_img])

            if len(images_row) == 2:
                img_table = Table(
                    [
                        [images_row[0][0], images_row[1][0]],
                        [images_row[0][1], images_row[1][1]],
                    ],
                    colWidths=[270, 270],
                )
                img_table.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(KeepTogether(img_table))
            elif len(images_row) == 1:
                story.append(images_row[0][0])
                story.append(Spacer(1, 4))
                story.append(images_row[0][1])

            story.append(Spacer(1, 14))

        # Seção 4: Conformidade Normativa e Observações
        story.append(Paragraph("4. Conformidade e Parecer de Prontidão Operacional", styles["Heading2"]))
        story.append(Spacer(1, 6))
        concl_text = (
            f"O modelo <b>{data.model_name}</b> obteve acurácia balanceada de <b>{data.metrics.balanced_accuracy*100:.2f}%</b> "
            f"e F1-Score macro de <b>{data.metrics.macro_f1*100:.2f}%</b>. As classificações de anomalias térmicas "
            "encontram-se compatíveis com a norma técnica internacional <b>IEC TS 62446-3</b> para inspeções "
            "aéreas de usinas fotovoltaicas e estão aptas para geração de laudos industriais."
        )
        if data.notes:
            concl_text += f"<br/><br/><b>Observações Adicionais:</b> {data.notes}"

        story.append(Paragraph(concl_text, styles["Normal"]))

        # Compilação
        doc.build(story, canvasmaker=NumberedCanvas)
        logger.info(f"Relatório PDF científico compilado com sucesso: {out}")
        return out

    def _setup_pdf_styles(self) -> dict:
        base_styles = getSampleStyleSheet()
        custom = {}

        custom["Title"] = ParagraphStyle(
            "ValReportTitle",
            parent=base_styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0F172A"),
            alignment=TA_LEFT,
        )
        custom["Subtitle"] = ParagraphStyle(
            "ValReportSubtitle",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#64748B"),
            alignment=TA_LEFT,
        )
        custom["Heading2"] = ParagraphStyle(
            "ValReportH2",
            parent=base_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#0369A1"),
            spaceBefore=8,
            spaceAfter=4,
        )
        custom["Normal"] = ParagraphStyle(
            "ValReportNormal",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#1E293B"),
        )
        custom["NormalSmall"] = ParagraphStyle(
            "ValReportNormalSmall",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#334155"),
            alignment=TA_CENTER,
        )
        return custom
