"""
Objeto de Valor para Bounding Box com suporte a IoU e conversão de coordenadas.
"""

from dataclasses import dataclass
from typing import Optional
from src.domain.exceptions import InvalidBoundingBoxError


@dataclass(frozen=True)
class BoundingBox:
    """
    Caixa delimitadora (Bounding Box) em coordenadas normalizadas [0.0, 1.0] ou em pixels absolutos.
    
    :param x_min: Coordenada X do canto superior esquerdo.
    :param y_min: Coordenada Y do canto superior esquerdo.
    :param x_max: Coordenada X do canto inferior direito.
    :param y_max: Coordenada Y do canto inferior direito.
    :param is_normalized: Indica se as coordenadas estão no intervalo [0.0, 1.0].
    """
    x_min: float = 0.0
    y_min: float = 0.0
    x_max: float = 1.0
    y_max: float = 1.0
    is_normalized: bool = True

    def __init__(
        self,
        x_min: Optional[float] = None,
        y_min: Optional[float] = None,
        x_max: Optional[float] = None,
        y_max: Optional[float] = None,
        is_normalized: bool = True,
        **kwargs,
    ) -> None:
        real_xmin = x_min if x_min is not None else kwargs.get("xmin", 0.0)
        real_ymin = y_min if y_min is not None else kwargs.get("ymin", 0.0)
        real_xmax = x_max if x_max is not None else kwargs.get("xmax", 1.0)
        real_ymax = y_max if y_max is not None else kwargs.get("ymax", 1.0)

        object.__setattr__(self, "x_min", float(real_xmin))
        object.__setattr__(self, "y_min", float(real_ymin))
        object.__setattr__(self, "x_max", float(real_xmax))
        object.__setattr__(self, "y_max", float(real_ymax))
        object.__setattr__(self, "is_normalized", bool(is_normalized))
        self._validate()

    def _validate(self) -> None:
        if self.x_max <= self.x_min:
            raise InvalidBoundingBoxError(
                f"x_max ({self.x_max}) deve ser estritamente maior que x_min ({self.x_min})."
            )
        if self.y_max <= self.y_min:
            raise InvalidBoundingBoxError(
                f"y_max ({self.y_max}) deve ser estritamente maior que y_min ({self.y_min})."
            )

        if self.is_normalized:
            for coord_name, val in [
                ("x_min", self.x_min),
                ("y_min", self.y_min),
                ("x_max", self.x_max),
                ("y_max", self.y_max),
            ]:
                if not (-0.01 <= val <= 1.01):  # Margem de tolerância numérica
                    raise InvalidBoundingBoxError(
                        f"Coordenada normalizada {coord_name}={val} fora do intervalo [0.0, 1.0]."
                    )

    @property
    def xmin(self) -> float:
        """Alias para x_min."""
        return self.x_min

    @property
    def ymin(self) -> float:
        """Alias para y_min."""
        return self.y_min

    @property
    def xmax(self) -> float:
        """Alias para x_max."""
        return self.x_max

    @property
    def ymax(self) -> float:
        """Alias para y_max."""
        return self.y_max

    @property
    def width(self) -> float:
        """Largura da caixa."""
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        """Altura da caixa."""
        return self.y_max - self.y_min

    @property
    def area(self) -> float:
        """Área da caixa delimitadora."""
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        """Ponto central (cx, cy) da caixa."""
        return (self.x_min + self.width / 2.0, self.y_min + self.height / 2.0)

    def to_pixels(self, img_width: int, img_height: int) -> "BoundingBox":
        """Converte de coordenadas normalizadas [0,1] para pixels inteiros."""
        if not self.is_normalized:
            return self
        return BoundingBox(
            x_min=round(self.x_min * img_width, 2),
            y_min=round(self.y_min * img_height, 2),
            x_max=round(self.x_max * img_width, 2),
            y_max=round(self.y_max * img_height, 2),
            is_normalized=False,
        )

    def to_normalized(self, img_width: int, img_height: int) -> "BoundingBox":
        """Converte de pixels absolutos para coordenadas normalizadas [0, 1]."""
        if self.is_normalized:
            return self
        if img_width <= 0 or img_height <= 0:
            raise InvalidBoundingBoxError("Dimensões da imagem devem ser maiores que zero.")
        return BoundingBox(
            x_min=max(0.0, min(1.0, self.x_min / img_width)),
            y_min=max(0.0, min(1.0, self.y_min / img_height)),
            x_max=max(0.0, min(1.0, self.x_max / img_width)),
            y_max=max(0.0, min(1.0, self.y_max / img_height)),
            is_normalized=True,
        )

    def iou(self, other: "BoundingBox") -> float:
        """
        Calcula a métrica de Interseção sobre União (IoU) com outra caixa.
        Ambas as caixas devem estar no mesmo sistema de coordenadas (normalizado ou pixel).
        """
        inter_x_min = max(self.x_min, other.x_min)
        inter_y_min = max(self.y_min, other.y_min)
        inter_x_max = min(self.x_max, other.x_max)
        inter_y_max = min(self.y_max, other.y_max)

        inter_width = max(0.0, inter_x_max - inter_x_min)
        inter_height = max(0.0, inter_y_max - inter_y_min)
        intersection_area = inter_width * inter_height

        if intersection_area <= 0.0:
            return 0.0

        union_area = self.area + other.area - intersection_area
        return round(intersection_area / union_area, 4) if union_area > 0 else 0.0

    def contains_point(self, x: float, y: float) -> bool:
        """Verifica se um ponto (x, y) está contido no interior da caixa."""
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max
