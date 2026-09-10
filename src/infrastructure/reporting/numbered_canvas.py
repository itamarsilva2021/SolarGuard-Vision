"""
Canvas de Dois Passes para Numeração Dinâmica de Páginas ('Página X de Y'),
Cabeçalho Técnico e Rodapé Institucional com ReportLab.
"""

from reportlab.pdfgen import canvas
from reportlab.lib import colors


class NumberedCanvas(canvas.Canvas):
    """
    Canvas especializado que armazena as páginas durante a compilação
    e calcula o total de páginas no salvamento para gerar cabeçalhos e rodapés precisos.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        """Desenha cabeçalho superior e rodapé inferior em todas as páginas (exceto capa)."""
        # Se for página única ou capa dedicada (página 1 de muitas), pode suprimir cabeçalho
        page_num = self._pageNumber

        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        width, height = self._pagesize

        # Margens
        margin_x = 45

        # -------------------------------------------------------------
        # Cabeçalho (Páginas > 1)
        # -------------------------------------------------------------
        if page_num > 1:
            header_y = height - 32
            self.drawString(margin_x, header_y, "SOLARGUARD VISION  |  Relatório Técnico de Inspeção Fotovoltaica")
            self.drawRightString(width - margin_x, header_y, "Norma IEC TS 62446-3")

            # Linha sutil do cabeçalho
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(margin_x, header_y - 6, width - margin_x, header_y - 6)

        # -------------------------------------------------------------
        # Rodapé Institucional (Todas as páginas)
        # -------------------------------------------------------------
        footer_y = 28
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(margin_x, footer_y + 12, width - margin_x, footer_y + 12)

        self.drawString(
            margin_x,
            footer_y,
            "Documento confidencial gerado automaticamente por Inteligência Artificial e Termografia Aérea."
        )

        page_str = f"Página {page_num} de {page_count}"
        self.drawRightString(width - margin_x, footer_y, page_str)

        self.restoreState()
