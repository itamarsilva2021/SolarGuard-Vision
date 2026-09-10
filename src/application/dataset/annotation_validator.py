"""
Validador de anotações no formato YOLOv11 (<class_id> <x_center> <y_center> <width> <height>).
Verifica conformidade sintática, limites geométricos normalizados e classes válidas.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from src.infrastructure.ml.dataset_loader import PV_CLASSES


@dataclass(frozen=True)
class AnnotationError:
    """Representa um erro ou inconsistência em uma linha de anotação."""
    file_path: str
    line_number: int
    raw_line: str
    error_message: str
    is_critical: bool = True


@dataclass(frozen=True)
class ParsedAnnotation:
    """Anotação YOLO validada e estruturada."""
    class_id: int
    class_name: str
    x_center: float
    y_center: float
    width: float
    height: float


class AnnotationValidator:
    """
    Valida a integridade e limites de coordenadas de arquivos de anotação YOLO (.txt).
    """

    def __init__(self, allowed_classes: Optional[Dict[int, str]] = None) -> None:
        self.allowed_classes = allowed_classes or PV_CLASSES

    def validate_line(
        self, line: str, line_number: int, file_path: str
    ) -> Tuple[Optional[ParsedAnnotation], Optional[AnnotationError]]:
        """
        Valida uma única linha de anotação YOLO.
        
        :param line: Linha de texto bruta.
        :param line_number: Número da linha (1-indexed).
        :param file_path: Caminho do arquivo para registro de erro.
        :return: Tupla (ParsedAnnotation se válido, AnnotationError se inválido).
        """
        raw = line.strip()
        if not raw:
            return None, None  # Linha em branco é ignorada

        tokens = raw.split()
        if len(tokens) < 5 or (len(tokens) > 5 and len(tokens) % 2 == 0):
            return None, AnnotationError(
                file_path=file_path,
                line_number=line_number,
                raw_line=raw,
                error_message=f"Formato incorreto. Esperado 5 campos (bbox) ou número ímpar >= 7 campos (polígono), encontrado {len(tokens)}.",
            )

        # 1. Validação de Class ID
        try:
            class_id = int(tokens[0])
        except ValueError:
            return None, AnnotationError(
                file_path=file_path,
                line_number=line_number,
                raw_line=raw,
                error_message=f"ID de classe '{tokens[0]}' não é um número inteiro válido.",
            )

        if class_id not in self.allowed_classes:
            return None, AnnotationError(
                file_path=file_path,
                line_number=line_number,
                raw_line=raw,
                error_message=f"Classe inválida ID={class_id}. Classes permitidas: {sorted(list(self.allowed_classes.keys()))}.",
            )

        # 2. Validação de Coordenadas Numéricas e Cálculo da Bounding Box
        try:
            if len(tokens) == 5:
                # Formato padrão YOLO Bounding Box: class cx cy w h
                cx = float(tokens[1])
                cy = float(tokens[2])
                w = float(tokens[3])
                h = float(tokens[4])
            else:
                # Formato YOLO Segmentation: class x1 y1 x2 y2 ... xn yn
                xs = [float(tokens[i]) for i in range(1, len(tokens), 2)]
                ys = [float(tokens[i]) for i in range(2, len(tokens), 2)]
                xmin, xmax = min(xs), max(xs)
                ymin, ymax = min(ys), max(ys)
                cx = (xmin + xmax) / 2.0
                cy = (ymin + ymax) / 2.0
                w = max(0.001, xmax - xmin)
                h = max(0.001, ymax - ymin)
        except ValueError:
            return None, AnnotationError(
                file_path=file_path,
                line_number=line_number,
                raw_line=raw,
                error_message="Coordenadas contêm valores não-numéricos.",
            )

        # 3. Validação de Dimensões Positivas
        if w <= 0.0 or h <= 0.0:
            return None, AnnotationError(
                file_path=file_path,
                line_number=line_number,
                raw_line=raw,
                error_message=f"Bounding box degenerada: largura ({w}) e altura ({h}) devem ser maiores que 0.",
            )

        # 4. Validação de Espaço Normalizado [0.0, 1.0] com tolerância de borda
        tolerance = 0.05
        if not (-tolerance <= cx <= 1.0 + tolerance and -tolerance <= cy <= 1.0 + tolerance):
            return None, AnnotationError(
                file_path=file_path,
                line_number=line_number,
                raw_line=raw,
                error_message=f"Centro da caixa fora do espaço normalizado [0, 1]: ({cx}, {cy}).",
            )

        if w > 1.0 + tolerance or h > 1.0 + tolerance:
            return None, AnnotationError(
                file_path=file_path,
                line_number=line_number,
                raw_line=raw,
                error_message=f"Dimensões da caixa ultrapassam limites da imagem: w={w}, h={h}.",
            )

        # Ajuste de clamp nos limites exatos
        cx = max(0.0, min(1.0, cx))
        cy = max(0.0, min(1.0, cy))
        w = max(0.0, min(1.0, w))
        h = max(0.0, min(1.0, h))

        parsed = ParsedAnnotation(
            class_id=class_id,
            class_name=self.allowed_classes[class_id],
            x_center=round(cx, 6),
            y_center=round(cy, 6),
            width=round(w, 6),
            height=round(h, 6),
        )
        return parsed, None

    def validate_file(self, file_path: str | Path) -> Tuple[List[ParsedAnnotation], List[AnnotationError]]:
        """
        Valida todas as linhas de um arquivo de anotação .txt.
        
        :param file_path: Caminho para o arquivo .txt de anotação.
        :return: Tupla (anotações válidas, lista de erros encontrados).
        """
        path = Path(file_path)
        valid_annotations: List[ParsedAnnotation] = []
        errors: List[AnnotationError] = []

        if not path.exists():
            errors.append(
                AnnotationError(
                    file_path=str(path),
                    line_number=0,
                    raw_line="",
                    error_message="Arquivo de anotação não encontrado.",
                )
            )
            return valid_annotations, errors

        try:
            content = path.read_text(encoding="utf-8")
            lines = content.splitlines()
            for line_idx, line in enumerate(lines, 1):
                parsed, error = self.validate_line(line, line_idx, str(path))
                if error:
                    errors.append(error)
                elif parsed:
                    valid_annotations.append(parsed)
        except Exception as ex:
            errors.append(
                AnnotationError(
                    file_path=str(path),
                    line_number=0,
                    raw_line="",
                    error_message=f"Falha de leitura do arquivo: {ex}",
                )
            )

        return valid_annotations, errors
