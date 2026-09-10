"""
Enumeração das paletas térmicas radiométricas comumente utilizadas pelo drone DJI Matrice 4T.
"""

from enum import Enum


class PaletteType(str, Enum):
    """
    Paletas de cores para renderização de matrizes térmicas brutas (R-JPEG).
    """
    WHITE_HOT = "white_hot"      # Tons de cinza (mais quente = branco)
    BLACK_HOT = "black_hot"      # Tons de cinza invertidos (mais quente = preto)
    IRONBOW = "ironbow"          # Padrão da termografia industrial (tons de roxo, laranja e amarelo)
    RAINBOW = "rainbow"          # Espectro completo visível (maior contraste de detalhes sutis)
    ARCTIC = "arctic"            # Tons frios com destaque para áreas quentes
    MEDICAL = "medical"          # Alto contraste térmico

    @property
    def display_name(self) -> str:
        names = {
            PaletteType.WHITE_HOT: "White Hot (Preto e Branco)",
            PaletteType.BLACK_HOT: "Black Hot (Invertido)",
            PaletteType.IRONBOW: "Ironbow (Ferro Aquecido)",
            PaletteType.RAINBOW: "Rainbow (Arco-íris)",
            PaletteType.ARCTIC: "Arctic (Ártico)",
            PaletteType.MEDICAL: "Medical (Alto Contraste)",
        }
        return names.get(self, self.value)
