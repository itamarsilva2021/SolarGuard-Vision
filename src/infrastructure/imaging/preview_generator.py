"""
Gerador de Pré-Visualizações (Thumbnails e Renderização de Paletas Térmicas).
Utiliza OpenCV para redimensionamento e aplicação de paletas radiométricas.
"""

from pathlib import Path
from typing import Optional
import hashlib
import cv2
import numpy as np
from PIL import Image

from src.domain.enums.palette_type import PaletteType
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("PreviewGenerator")


class PreviewGenerator:
    """
    Gera miniaturas e pré-visualizações otimizadas de imagens térmicas e ópticas
    com suporte a paletas de cores termográficas (Ironbow, White-Hot, Rainbow).
    """

    def __init__(self, cache_dir: Optional[Path | str] = None) -> None:
        if cache_dir is None:
            self.cache_dir = settings.cache_dir / "previews"
        else:
            self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_colormap_for_palette(self, palette: PaletteType) -> Optional[int]:
        """Mapeia o enum de paleta para a constante de Colormap do OpenCV."""
        mapping = {
            PaletteType.IRONBOW: cv2.COLORMAP_INFERNO,
            PaletteType.RAINBOW: cv2.COLORMAP_JET,
            PaletteType.ARCTIC: cv2.COLORMAP_OCEAN,
            PaletteType.MEDICAL: cv2.COLORMAP_HOT,
        }
        return mapping.get(palette, None)

    def generate_preview(
        self,
        file_path: str | Path,
        max_dimension: int = 480,
        palette: PaletteType = PaletteType.IRONBOW,
    ) -> Path:
        """
        Gera uma imagem de pré-visualização no disco e retorna o caminho para exibição na UI.
        
        :param file_path: Caminho da imagem de origem (JPG, PNG, TIFF).
        :param max_dimension: Largura ou altura máxima da miniatura em pixels.
        :param palette: Paleta térmica a ser aplicada em imagens monocromáticas/16-bit.
        :return: Path do arquivo JPEG de miniatura em cache.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado para gerar prévia: {file_path}")

        # Gerar hash único para cache baseado no caminho e parâmetros
        cache_key = hashlib.md5(
            f"{file_path.resolve()}_{file_path.stat().st_mtime}_{max_dimension}_{palette.value}".encode()
        ).hexdigest()
        preview_path = self.cache_dir / f"prev_{cache_key}.jpg"

        # Se já existir em cache, retorna diretamente
        if preview_path.exists():
            return preview_path

        ext = file_path.suffix.lower()

        # Leitura da imagem
        if ext in [".tif", ".tiff"]:
            raw = cv2.imread(str(file_path), cv2.IMREAD_UNCHANGED)
            if raw is None:
                raise ValueError(f"Não foi possível abrir o TIFF: {file_path}")

            if raw.dtype == np.uint16:
                # Normalização linear de 16-bit para 8-bit com estiramento de contraste
                p_min, p_max = np.percentile(raw, (1, 99))
                if p_max <= p_min:
                    p_min, p_max = np.min(raw), np.max(raw)
                p_max = p_max if p_max > p_min else p_min + 1.0

                scaled = np.clip((raw - p_min) / (p_max - p_min) * 255.0, 0, 255).astype(np.uint8)
                colormap_id = self._get_colormap_for_palette(palette)
                if colormap_id is not None:
                    img_rgb = cv2.applyColorMap(scaled, colormap_id)
                elif palette == PaletteType.BLACK_HOT:
                    img_rgb = cv2.cvtColor(255 - scaled, cv2.COLOR_GRAY2BGR)
                else:  # WHITE_HOT
                    img_rgb = cv2.cvtColor(scaled, cv2.COLOR_GRAY2BGR)
            elif len(raw.shape) == 2:
                # 8-bit monocanal
                colormap_id = self._get_colormap_for_palette(palette)
                img_rgb = cv2.applyColorMap(raw, colormap_id) if colormap_id else cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)
            else:
                img_rgb = raw
        else:
            # JPG / PNG
            img_rgb = cv2.imread(str(file_path), cv2.IMREAD_COLOR)
            if img_rgb is None:
                raise ValueError(f"Falha ao ler arquivo de imagem: {file_path}")

        # Redimensionamento proporcional para visualização leve na interface
        h, w = img_rgb.shape[:2]
        if max(h, w) > max_dimension:
            scale = max_dimension / float(max(h, w))
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            img_rgb = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Salvar em JPEG de alta qualidade para renderização na interface
        cv2.imwrite(str(preview_path), img_rgb, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        return preview_path
