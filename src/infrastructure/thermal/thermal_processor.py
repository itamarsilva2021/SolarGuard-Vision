"""
Módulo de Processamento e Renderização Térmica (Heatmap e Normalização).
Implementa ThermalProcessor com suporte a normalização estocástica e paletas industriais.
"""

from pathlib import Path
from typing import Optional, Tuple, List, Union
import cv2
import numpy as np

from src.domain.enums.palette_type import PaletteType
from src.infrastructure.imaging.dji_thermal_parser import DjiThermalParser
from src.core.logger import get_logger

logger = get_logger("ThermalProcessor")


class ThermalProcessor:
    """
    Motor de processamento de matrizes radiométricas e geração de mapas de calor (Heatmaps).
    Oferece algoritmos de normalização de contraste térmico, aplicação de paletas radiométricas,
    barra de escala de temperatura (Colorbar) e sobreposição de isotermas.
    """

    def __init__(self, parser: Optional[DjiThermalParser] = None) -> None:
        self.parser = parser or DjiThermalParser()

    def load_matrix(self, source: Union[str, Path, np.ndarray]) -> np.ndarray:
        """
        Carrega ou valida uma matriz térmica 2D em float32 com valores em graus Celsius (°C).
        
        :param source: Caminho do arquivo (TIFF, R-JPEG, JPG) ou ndarray já em memória.
        :return: Array 2D float32 [H, W] com temperaturas em Celsius.
        """
        if hasattr(source, "data") and isinstance(source.data, np.ndarray):
            source = source.data

        if isinstance(source, np.ndarray):
            if source.ndim != 2:
                raise ValueError(f"A matriz térmica deve ser bidimensional (2D). Recebido: {source.ndim}D.")
            return source.astype(np.float32)

        file_path = Path(source)
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo térmico não encontrado: {file_path}")

        return self.parser.extract_temperature_matrix(file_path)

    def normalize(
        self,
        matrix: np.ndarray,
        method: str = "percentile",
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        pmin: float = 1.0,
        pmax: float = 99.0,
    ) -> np.ndarray:
        """
        Normaliza a matriz de temperatura float32 para uma imagem de 8 bits [0, 255] uint8.
        
        :param matrix: Matriz térmica 2D em °C.
        :param method: 'percentile' (elimina reflexos extremos do sol/céu) ou 'minmax'.
        :param vmin: Limite inferior forçado de temperatura (°C).
        :param vmax: Limite superior forçado de temperatura (°C).
        :param pmin: Percentil inferior para contraste estendido (padrão 1.0%).
        :param pmax: Percentil superior para contraste estendido (padrão 99.0%).
        :return: Imagem uint8 2D [0, 255].
        """
        if matrix.size == 0:
            return np.zeros((0, 0), dtype=np.uint8)

        if vmin is not None and vmax is not None:
            low_val, high_val = float(vmin), float(vmax)
        elif method == "percentile":
            low_val, high_val = np.percentile(matrix, (pmin, pmax))
        else:  # minmax
            low_val, high_val = float(np.min(matrix)), float(np.max(matrix))

        if high_val <= low_val:
            high_val = low_val + 1.0  # Previne divisão por zero em matriz homogênea

        clipped = np.clip(matrix, low_val, high_val)
        normalized = (clipped - low_val) / (high_val - low_val) * 255.0
        return np.round(normalized).astype(np.uint8)

    def _get_cv2_colormap(self, palette: PaletteType) -> Optional[int]:
        """Converte a enumeração de paleta para o identificador OpenCV."""
        colormaps = {
            PaletteType.IRONBOW: cv2.COLORMAP_INFERNO,
            PaletteType.RAINBOW: cv2.COLORMAP_JET,
            PaletteType.ARCTIC: cv2.COLORMAP_OCEAN,
            PaletteType.MEDICAL: cv2.COLORMAP_HOT,
        }
        return colormaps.get(palette, None)

    def generate_heatmap(
        self,
        matrix: np.ndarray,
        palette: PaletteType = PaletteType.IRONBOW,
        normalize: bool = True,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
    ) -> np.ndarray:
        """
        Gera uma imagem colorida (BGR, 3 canais) representando o mapa de calor térmico.
        
        :param matrix: Matriz térmica de temperaturas em °C.
        :param palette: Paleta radiométrica selecionada.
        :param normalize: Se True, estende o contraste antes de colorir.
        :param vmin: Temperatura mínima forçada para fixação de escala.
        :param vmax: Temperatura máxima forçada para fixação de escala.
        :return: Imagem BGR uint8 [H, W, 3].
        """
        if normalize:
            norm_8u = self.normalize(matrix, method="percentile", vmin=vmin, vmax=vmax)
        else:
            norm_8u = np.clip(matrix, 0, 255).astype(np.uint8)

        colormap_id = self._get_cv2_colormap(palette)

        if colormap_id is not None:
            return cv2.applyColorMap(norm_8u, colormap_id)
        elif palette == PaletteType.BLACK_HOT:
            inverted = 255 - norm_8u
            return cv2.cvtColor(inverted, cv2.COLOR_GRAY2BGR)
        else:  # WHITE_HOT
            return cv2.cvtColor(norm_8u, cv2.COLOR_GRAY2BGR)

    def overlay_colorbar(
        self,
        heatmap: np.ndarray,
        min_temp: float,
        max_temp: float,
        palette: PaletteType = PaletteType.IRONBOW,
        bar_width: int = 48,
    ) -> np.ndarray:
        """
        Anexa uma barra lateral calibrada de escala de temperatura (Colorbar) à direita do mapa de calor.
        
        :param heatmap: Imagem do mapa de calor gerada [H, W, 3].
        :param min_temp: Temperatura mínima indicada na escala (°C).
        :param max_temp: Temperatura máxima indicada na escala (°C).
        :param palette: Paleta de cores correspondente.
        :param bar_width: Largura em pixels da barra de cores lateral.
        :return: Nova imagem composta [H, W + bar_width + margem, 3].
        """
        h, w = heatmap.shape[:2]
        margin = 60  # Espaço para o texto das temperaturas em °C
        total_bar_w = bar_width + margin

        # Criar gradiente vertical de 255 (topo = quente) a 0 (fundo = frio)
        gradient = np.linspace(255, 0, h, dtype=np.uint8).reshape((h, 1))
        gradient_bar = np.repeat(gradient, bar_width, axis=1)

        colormap_id = self._get_cv2_colormap(palette)
        if colormap_id is not None:
            color_gradient = cv2.applyColorMap(gradient_bar, colormap_id)
        elif palette == PaletteType.BLACK_HOT:
            color_gradient = cv2.cvtColor(255 - gradient_bar, cv2.COLOR_GRAY2BGR)
        else:
            color_gradient = cv2.cvtColor(gradient_bar, cv2.COLOR_GRAY2BGR)

        # Monta painel lateral escuro com textos
        side_panel = np.full((h, total_bar_w, 3), 30, dtype=np.uint8)
        side_panel[:, 5 : 5 + bar_width] = color_gradient

        # Desenhar borda sutil na barra
        cv2.rectangle(side_panel, (5, 0), (5 + bar_width, h - 1), (180, 180, 180), 1)

        # Inserção das legendas de temperatura
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.38
        text_color = (240, 240, 240)
        thickness = 1

        # Temperatura Máxima (topo)
        cv2.putText(side_panel, f"{max_temp:.1f}C", (bar_width + 10, 18), font, font_scale, text_color, thickness, cv2.LINE_AA)

        # Temperatura Média (meio)
        mid_temp = (max_temp + min_temp) / 2.0
        cv2.putText(side_panel, f"{mid_temp:.1f}C", (bar_width + 10, h // 2 + 5), font, font_scale, text_color, thickness, cv2.LINE_AA)

        # Temperatura Mínima (base)
        cv2.putText(side_panel, f"{min_temp:.1f}C", (bar_width + 10, h - 8), font, font_scale, text_color, thickness, cv2.LINE_AA)

        return np.hstack([heatmap, side_panel])

    def mark_hotspots(
        self,
        heatmap: np.ndarray,
        points: list[tuple[int, int]],
        temps: list[float],
        color: tuple[int, int, int] = (0, 0, 255),
    ) -> np.ndarray:
        """
        Desenha retículos técnicos (miras) e anotações numéricas de temperatura (°C) sobre o mapa de calor.
        """
        annotated = heatmap.copy()
        for (x, y), temp in zip(points, temps):
            if 0 <= x < annotated.shape[1] and 0 <= y < annotated.shape[0]:
                # Círculo e mira
                cv2.circle(annotated, (x, y), 8, color, 2, cv2.LINE_AA)
                cv2.line(annotated, (x - 12, y), (x + 12, y), color, 1, cv2.LINE_AA)
                cv2.line(annotated, (x, y - 12), (x, y + 12), color, 1, cv2.LINE_AA)

                # Rótulo de texto com fundo para legibilidade
                label = f"{temp:.1f}C"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
                cv2.rectangle(annotated, (x + 12, y - th - 4), (x + 16 + tw, y + 2), (0, 0, 0), -1)
                cv2.putText(annotated, label, (x + 14, y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)

        return annotated

    def apply_isotherm(
        self,
        heatmap: np.ndarray,
        matrix: np.ndarray,
        min_celsius: float,
        max_celsius: float,
        highlight_color: tuple[int, int, int] = (0, 255, 255),
        alpha: float = 0.5,
    ) -> np.ndarray:
        """
        Destaca uma faixa específica de temperatura com uma cor de sobreposição semitransparente (isoterma).
        """
        mask = (matrix >= min_celsius) & (matrix <= max_celsius)
        output = heatmap.copy()
        color_layer = np.full_like(heatmap, highlight_color, dtype=np.uint8)

        blended = cv2.addWeighted(heatmap, 1.0 - alpha, color_layer, alpha, 0)
        output[mask] = blended[mask]
        return output

    def get_temperature_at(self, matrix: np.ndarray, x: int, y: int) -> float:
        """Lê com segurança a temperatura pontual no pixel (x, y)."""
        h, w = matrix.shape[:2]
        safe_x = max(0, min(w - 1, x))
        safe_y = max(0, min(h - 1, y))
        return float(matrix[safe_y, safe_x])
