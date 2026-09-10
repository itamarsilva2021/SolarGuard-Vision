"""
Engine de Mapeamento, Segmentação e Indexação Topológica de Módulos Fotovoltaicos Físicos.
Relaciona Bounding Boxes de falhas térmicas ao Painel Físico, String, Linha e Coluna.
"""

from typing import List, Tuple, Optional, Dict, Any, Union
import math
import numpy as np
import cv2

from src.domain.entities.solar_panel import SolarPanel, PanelFaultMapping
from src.domain.value_objects.bounding_box import BoundingBox
from src.infrastructure.database.repositories.sqlite_panel_repository import SqlitePanelRepository
from src.core.logger import get_logger

logger = get_logger("PanelMapper")


class PanelMapper:
    """
    Segmenta módulos solares em imagens térmicas, indexa a topologia da usina (String, Linha, Coluna)
    e associa com precisão matemática cada defeito/hotspot ao seu painel físico.
    """

    def __init__(self, panel_repo: Optional[SqlitePanelRepository] = None) -> None:
        self.panel_repo = panel_repo

    # =========================================================================
    # 1. SEGMENTAÇÃO DOS MÓDULOS FOTOVOLTAICOS
    # =========================================================================
    def segment_grid(
        self,
        rows: int,
        cols: int,
        margin_x: float = 0.05,
        margin_y: float = 0.05,
        gap_x: float = 0.015,
        gap_y: float = 0.015,
    ) -> List[BoundingBox]:
        """
        Gera a segmentação geométrica paramétrica regular de módulos em coordenadas normalizadas [0, 1].
        Útil para arranjos regulares (ex: mesa de 2x6, 3x8, 4x10 módulos).
        """
        if rows <= 0 or cols <= 0:
            raise ValueError(f"Dimensões de grade inválidas: rows={rows}, cols={cols}")

        usable_w = 1.0 - (2.0 * margin_x) - ((cols - 1) * gap_x)
        usable_h = 1.0 - (2.0 * margin_y) - ((rows - 1) * gap_y)

        if usable_w <= 0 or usable_h <= 0:
            raise ValueError("Margens e espaçamentos (gaps) excedem os limites normalizados da imagem [0, 1].")

        mod_w = usable_w / cols
        mod_h = usable_h / rows

        bboxes: List[BoundingBox] = []
        for r in range(rows):
            ymin = margin_y + r * (mod_h + gap_y)
            ymax = ymin + mod_h
            for c in range(cols):
                xmin = margin_x + c * (mod_w + gap_x)
                xmax = xmin + mod_w
                bboxes.append(BoundingBox(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax))

        return bboxes

    def segment_from_radiometric_matrix(
        self,
        thermal_matrix: np.ndarray,
        min_area_ratio: float = 0.005,
        max_area_ratio: float = 0.5,
    ) -> List[BoundingBox]:
        """
        Segmenta módulos físicos a partir da matriz térmica/radiométrica utilizando
        limiarização adaptativa e detecção de contornos convexos regulares.
        """
        h, w = thermal_matrix.shape[:2]
        total_pixels = h * w

        # Normaliza matriz térmica para escala de cinza 8-bit [0, 255]
        t_min = float(np.min(thermal_matrix))
        t_max = float(np.max(thermal_matrix))
        if math.isclose(t_max, t_min):
            return []

        norm_8u = np.uint8(255 * (thermal_matrix - t_min) / (t_max - t_min))

        # Filtro bilateral para preservar bordas dos módulos atenuando ruído
        blurred = cv2.bilateralFilter(norm_8u, d=7, sigmaColor=50, sigmaSpace=50)

        # Otsu thresholding
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Operações morfológicas de fechamento retangular
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        bboxes: List[BoundingBox] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            ratio = area / total_pixels
            if min_area_ratio <= ratio <= max_area_ratio:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                # Converte para coordenadas normalizadas [0, 1]
                xmin = bx / w
                ymin = by / h
                xmax = (bx + bw) / w
                ymax = (by + bh) / h
                bboxes.append(BoundingBox(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax))

        return bboxes

    # =========================================================================
    # 2. INDEXAÇÃO AUTOMÁTICA DE TOPOLOGIA (STRING, LINHA, COLUNA)
    # =========================================================================
    def index_modules(
        self,
        panels_bboxes: List[BoundingBox],
        image_id: str,
        string_id: str = "STR-01",
        tolerance_y: float = 0.08,
    ) -> List[SolarPanel]:
        """
        Ordena topologicamente as caixas delimitadoras dos módulos na imagem:
        - Agrupa as linhas (rows) de cima para baixo (Y crescente).
        - Ordena as colunas (columns) da esquerda para a direita (X crescente).
        - Atribui row_index (1..R), col_index (1..C) e gera o panel_identifier.
        """
        if not panels_bboxes:
            return []

        # 1. Ordena primariamente por Y central
        sorted_by_y = sorted(panels_bboxes, key=lambda b: b.center[1])

        # 2. Agrupa em linhas horizontais por proximidade no eixo Y
        rows_groups: List[List[BoundingBox]] = []
        current_row: List[BoundingBox] = [sorted_by_y[0]]
        current_y = sorted_by_y[0].center[1]

        for bbox in sorted_by_y[1:]:
            cy = bbox.center[1]
            if abs(cy - current_y) <= tolerance_y:
                current_row.append(bbox)
                # Atualiza centroide Y médio da linha
                current_y = sum(b.center[1] for b in current_row) / len(current_row)
            else:
                rows_groups.append(current_row)
                current_row = [bbox]
                current_y = cy

        if current_row:
            rows_groups.append(current_row)

        # 3. Cria entidades SolarPanel indexadas (Linha 1..N, Coluna 1..M)
        indexed_panels: List[SolarPanel] = []
        for r_idx, row in enumerate(rows_groups, start=1):
            # Ordena os módulos da linha da esquerda para a direita (X crescente)
            row_sorted_by_x = sorted(row, key=lambda b: b.center[0])
            for c_idx, bbox in enumerate(row_sorted_by_x, start=1):
                identifier = f"{string_id}-R{r_idx:02d}-C{c_idx:02d}"
                panel = SolarPanel(
                    image_id=image_id,
                    string_id=string_id,
                    row_index=r_idx,
                    col_index=c_idx,
                    panel_identifier=identifier,
                    bbox=bbox,
                )
                indexed_panels.append(panel)

        logger.info(
            f"Indexação concluída: {len(indexed_panels)} painéis mapeados em "
            f"{len(rows_groups)} linhas para a String {string_id}."
        )
        return indexed_panels

    # =========================================================================
    # 3. ASSOCIAÇÃO DA FALHA (BOUNDING BOX) AO MÓDULO
    # =========================================================================
    @staticmethod
    def calculate_iou(box1: BoundingBox, box2: BoundingBox) -> float:
        """Calcula o Intersection over Union (IoU) entre duas caixas delimitadoras."""
        inter_xmin = max(box1.xmin, box2.xmin)
        inter_ymin = max(box1.ymin, box2.ymin)
        inter_xmax = min(box1.xmax, box2.xmax)
        inter_ymax = min(box1.ymax, box2.ymax)

        inter_w = max(0.0, inter_xmax - inter_xmin)
        inter_h = max(0.0, inter_ymax - inter_ymin)
        inter_area = inter_w * inter_h

        if inter_area <= 0:
            return 0.0

        area1 = (box1.xmax - box1.xmin) * (box1.ymax - box1.ymin)
        area2 = (box2.xmax - box2.xmin) * (box2.ymax - box2.ymin)
        union_area = area1 + area2 - inter_area

        return float(inter_area / union_area) if union_area > 0 else 0.0

    @staticmethod
    def is_center_inside(fault_bbox: BoundingBox, panel_bbox: BoundingBox) -> bool:
        """Verifica se o ponto central do defeito está geometricamente contido no módulo."""
        cx, cy = fault_bbox.center
        return (panel_bbox.xmin <= cx <= panel_bbox.xmax) and (panel_bbox.ymin <= cy <= panel_bbox.ymax)

    def associate_fault_to_panel(
        self,
        fault_bbox: BoundingBox,
        panels: List[SolarPanel],
        detection_id: Optional[str] = None,
    ) -> Optional[PanelFaultMapping]:
        """
        Associa uma anomalia/falha ao módulo fotovoltaico correspondente.
        Prioridade 1: Contenção do centroide do defeito dentro do módulo.
        Prioridade 2: Maior sobreposição espacial (IoU).
        """
        if not panels:
            return None

        # 1. Filtra módulos que contêm o centroide da falha
        containing_panels = [p for p in panels if self.is_center_inside(fault_bbox, p.bbox)]
        target_panel: Optional[SolarPanel] = None
        best_iou: float = 0.0

        if containing_panels:
            # Caso mais de um módulo capture o centroide (borda), seleciona o com maior IoU
            target_panel = max(containing_panels, key=lambda p: self.calculate_iou(fault_bbox, p.bbox))
            best_iou = self.calculate_iou(fault_bbox, target_panel.bbox)
        else:
            # Caso o centroide não esteja contido, busca o módulo com o maior IoU > 0
            best_panel = None
            for p in panels:
                iou = self.calculate_iou(fault_bbox, p.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_panel = p
            target_panel = best_panel

        if not target_panel:
            return None

        # 2. Calcula posição relativa [0.0, 1.0] da falha dentro do módulo físico
        cx_fault, cy_fault = fault_bbox.center
        panel_w = max(target_panel.bbox.width, 1e-5)
        panel_h = max(target_panel.bbox.height, 1e-5)

        rel_x = float(np.clip((cx_fault - target_panel.bbox.xmin) / panel_w, 0.0, 1.0))
        rel_y = float(np.clip((cy_fault - target_panel.bbox.ymin) / panel_h, 0.0, 1.0))

        return PanelFaultMapping(
            image_id=target_panel.image_id,
            panel_id=target_panel.id,
            string_id=target_panel.string_id,
            row_index=target_panel.row_index,
            col_index=target_panel.col_index,
            panel_identifier=target_panel.panel_identifier,
            overlap_iou=best_iou,
            relative_x=rel_x,
            relative_y=rel_y,
            detection_id=detection_id,
        )

    def associate_faults_batch(
        self,
        faults: List[Tuple[Optional[str], BoundingBox]],
        panels: List[SolarPanel],
    ) -> List[PanelFaultMapping]:
        """
        Associa uma lista de anomalias [(detection_id, fault_bbox)] aos módulos segmentados.
        """
        mappings: List[PanelFaultMapping] = []
        for det_id, f_box in faults:
            mapping = self.associate_fault_to_panel(f_box, panels, detection_id=det_id)
            if mapping:
                mappings.append(mapping)
        return mappings

    # =========================================================================
    # 4. ORQUESTRAÇÃO COMPLETA E PERSISTÊNCIA RELACIONAL
    # =========================================================================
    def map_and_persist(
        self,
        image_id: str,
        panels_bboxes: List[BoundingBox],
        faults: List[Tuple[Optional[str], BoundingBox]],
        string_id: str = "STR-01",
        tolerance_y: float = 0.08,
    ) -> Tuple[List[SolarPanel], List[PanelFaultMapping]]:
        """
        Executa o pipeline completo:
        1. Indexação topológica dos módulos.
        2. Associação das falhas detectadas.
        3. Gravação atômica no banco de dados SQLite (se repositório fornecido).
        """
        # 1. Indexação
        panels = self.index_modules(
            panels_bboxes=panels_bboxes,
            image_id=image_id,
            string_id=string_id,
            tolerance_y=tolerance_y,
        )

        # 2. Associação
        mappings = self.associate_faults_batch(faults=faults, panels=panels)

        # 3. Persistência
        if self.panel_repo:
            self.panel_repo.save_panels(panels)
            self.panel_repo.save_mappings(mappings)
            logger.info(f"Mapeamento topológico persistido para imagem {image_id}.")

        return panels, mappings
