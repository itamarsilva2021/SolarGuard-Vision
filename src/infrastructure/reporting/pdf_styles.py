"""
Estilos e Sistema de Design Tipográfico para Relatórios PDF com ReportLab.
Define paletas de cores institucionais, hierarquia de parágrafos e formatações de tabelas.
"""

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY


class PdfTheme:
    """Paleta de cores e constantes visuais corporativas do SolarGuard Vision."""
    PRIMARY = colors.HexColor("#0F172A")       # Azul Escuro Profundo (Slate 900)
    SECONDARY = colors.HexColor("#1E293B")     # Slate 800
    ACCENT_GOLD = colors.HexColor("#D97706")   # Âmbar Solar
    ACCENT_BLUE = colors.HexColor("#0284C7")   # Azul Céu
    
    TEXT_MAIN = colors.HexColor("#1E293B")     # Texto principal
    TEXT_MUTED = colors.HexColor("#64748B")    # Texto secundário
    TEXT_LIGHT = colors.HexColor("#FFFFFF")    # Texto branco
    
    BG_LIGHT = colors.HexColor("#F8FAFC")      # Fundo suave
    BG_ALT = colors.HexColor("#F1F5F9")        # Fundo alternado de tabela
    BORDER = colors.HexColor("#E2E8F0")        # Bordas elegantes
    
    # Cores de Severidade IEC TS 62446-3
    CRITICAL = colors.HexColor("#DC2626")      # Vermelho
    MEDIUM = colors.HexColor("#EA580C")        # Laranja
    LOW = colors.HexColor("#CA8A04")           # Amarelo/Ouro
    INFO = colors.HexColor("#16A34A")          # Verde


def create_report_styles() -> dict[str, ParagraphStyle]:
    """Cria e retorna o catálogo completo de estilos tipográficos customizados."""
    base_styles = getSampleStyleSheet()

    styles = {
        "DocTitle": ParagraphStyle(
            name="DocTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=PdfTheme.PRIMARY,
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        "DocSubtitle": ParagraphStyle(
            name="DocSubtitle",
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=PdfTheme.ACCENT_GOLD,
            alignment=TA_LEFT,
            spaceAfter=14,
        ),
        "SectionHeader": ParagraphStyle(
            name="SectionHeader",
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=PdfTheme.PRIMARY,
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "SubsectionHeader": ParagraphStyle(
            name="SubsectionHeader",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=PdfTheme.SECONDARY,
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "Body": ParagraphStyle(
            name="Body",
            fontName="Helvetica",
            fontSize=9,
            leading=12.5,
            textColor=PdfTheme.TEXT_MAIN,
            spaceAfter=4,
        ),
        "BodyJustify": ParagraphStyle(
            name="BodyJustify",
            fontName="Helvetica",
            fontSize=9,
            leading=12.5,
            textColor=PdfTheme.TEXT_MAIN,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "BodyBold": ParagraphStyle(
            name="BodyBold",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12.5,
            textColor=PdfTheme.TEXT_MAIN,
        ),
        "Muted": ParagraphStyle(
            name="Muted",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=PdfTheme.TEXT_MUTED,
        ),
        "TableHeader": ParagraphStyle(
            name="TableHeader",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=PdfTheme.TEXT_LIGHT,
            alignment=TA_CENTER,
        ),
        "TableCell": ParagraphStyle(
            name="TableCell",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=PdfTheme.TEXT_MAIN,
            alignment=TA_LEFT,
        ),
        "TableCellCenter": ParagraphStyle(
            name="TableCellCenter",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=PdfTheme.TEXT_MAIN,
            alignment=TA_CENTER,
        ),
        "BadgeText": ParagraphStyle(
            name="BadgeText",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=PdfTheme.TEXT_LIGHT,
            alignment=TA_CENTER,
        ),
        "CalloutText": ParagraphStyle(
            name="CalloutText",
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=PdfTheme.SECONDARY,
        ),
    }

    return styles
