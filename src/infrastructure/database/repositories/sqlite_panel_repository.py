"""
Repositório SQLite para persistência e consulta de módulos solares físicos (solar_panels)
e mapeamentos de defeitos topológicos (panel_mappings).
"""

from typing import List, Optional
from datetime import datetime

from src.infrastructure.database.connection import DatabaseManager
from src.domain.entities.solar_panel import SolarPanel, PanelFaultMapping
from src.domain.value_objects.bounding_box import BoundingBox
from src.core.logger import get_logger

logger = get_logger("SqlitePanelRepository")


class SqlitePanelRepository:
    """
    Gerencia a persistência relacional de módulos fotovoltaicos físicos e seus mapeamentos de falhas.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db = db_manager

    # =========================================================================
    # 1. SOLAR PANELS
    # =========================================================================
    def save_panels(self, panels: List[SolarPanel]) -> None:
        """Salva uma lista de painéis fotovoltaicos em operação transacional atômica."""
        if not panels:
            return

        with self.db.transaction() as conn:
            cursor = conn.cursor()
            for p in panels:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO solar_panels (
                        id, image_id, string_id, row_index, col_index,
                        panel_identifier, bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p.id,
                        p.image_id,
                        p.string_id,
                        p.row_index,
                        p.col_index,
                        p.panel_identifier,
                        p.bbox.xmin,
                        p.bbox.ymin,
                        p.bbox.xmax,
                        p.bbox.ymax,
                        p.created_at.isoformat() if isinstance(p.created_at, datetime) else str(p.created_at),
                    ),
                )
        logger.info(f"{len(panels)} painéis solares salvos com sucesso.")

    def get_panels_by_image_id(self, image_id: str) -> List[SolarPanel]:
        """Recupera todos os painéis solares segmentados para uma imagem específica."""
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, image_id, string_id, row_index, col_index,
                       panel_identifier, bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax, created_at
                FROM solar_panels
                WHERE image_id = ?
                ORDER BY row_index ASC, col_index ASC
                """,
                (image_id,),
            )
            rows = cursor.fetchall()

        panels: List[SolarPanel] = []
        for r in rows:
            p = SolarPanel(
                id=r[0],
                image_id=r[1],
                string_id=r[2],
                row_index=r[3],
                col_index=r[4],
                panel_identifier=r[5],
                bbox=BoundingBox(xmin=r[6], ymin=r[7], xmax=r[8], ymax=r[9]),
                created_at=datetime.fromisoformat(r[10]) if r[10] else datetime.now(),
            )
            panels.append(p)
        return panels

    def get_panel_by_id(self, panel_id: str) -> Optional[SolarPanel]:
        """Recupera um painel pelo seu UUID único."""
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, image_id, string_id, row_index, col_index,
                       panel_identifier, bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax, created_at
                FROM solar_panels
                WHERE id = ?
                """,
                (panel_id,),
            )
            r = cursor.fetchone()

        if not r:
            return None

        return SolarPanel(
            id=r[0],
            image_id=r[1],
            string_id=r[2],
            row_index=r[3],
            col_index=r[4],
            panel_identifier=r[5],
            bbox=BoundingBox(xmin=r[6], ymin=r[7], xmax=r[8], ymax=r[9]),
            created_at=datetime.fromisoformat(r[10]) if r[10] else datetime.now(),
        )

    # =========================================================================
    # 2. PANEL MAPPINGS (ASSOCIAÇÕES DE FALHAS)
    # =========================================================================
    def save_mappings(self, mappings: List[PanelFaultMapping]) -> None:
        """Salva a lista de correlações entre detecções e painéis solares."""
        if not mappings:
            return

        with self.db.transaction() as conn:
            cursor = conn.cursor()
            for m in mappings:
                valid_det_id = None
                if m.detection_id:
                    cursor.execute("SELECT 1 FROM detections WHERE id = ?", (m.detection_id,))
                    if cursor.fetchone():
                        valid_det_id = m.detection_id

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO panel_mappings (
                        id, detection_id, panel_id, image_id, string_id,
                        row_index, col_index, panel_identifier, overlap_iou,
                        relative_x, relative_y, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        m.id,
                        valid_det_id,
                        m.panel_id,
                        m.image_id,
                        m.string_id,
                        m.row_index,
                        m.col_index,
                        m.panel_identifier,
                        m.overlap_iou,
                        m.relative_x,
                        m.relative_y,
                        m.created_at.isoformat() if isinstance(m.created_at, datetime) else str(m.created_at),
                    ),
                )
        logger.info(f"{len(mappings)} mapeamentos de falha x painel salvos.")

    def get_mappings_by_image_id(self, image_id: str) -> List[PanelFaultMapping]:
        """Recupera todas as associações de falhas para a imagem."""
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, detection_id, panel_id, image_id, string_id,
                       row_index, col_index, panel_identifier, overlap_iou,
                       relative_x, relative_y, created_at
                FROM panel_mappings
                WHERE image_id = ?
                ORDER BY row_index ASC, col_index ASC
                """,
                (image_id,),
            )
            rows = cursor.fetchall()

        mappings: List[PanelFaultMapping] = []
        for r in rows:
            m = PanelFaultMapping(
                id=r[0],
                detection_id=r[1],
                panel_id=r[2],
                image_id=r[3],
                string_id=r[4],
                row_index=r[5],
                col_index=r[6],
                panel_identifier=r[7],
                overlap_iou=r[8],
                relative_x=r[9],
                relative_y=r[10],
                created_at=datetime.fromisoformat(r[11]) if r[11] else datetime.now(),
            )
            mappings.append(m)
        return mappings

    def get_mapping_by_detection_id(self, detection_id: str) -> Optional[PanelFaultMapping]:
        """Recupera o mapeamento correspondente a uma detecção específica."""
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, detection_id, panel_id, image_id, string_id,
                       row_index, col_index, panel_identifier, overlap_iou,
                       relative_x, relative_y, created_at
                FROM panel_mappings
                WHERE detection_id = ?
                """,
                (detection_id,),
            )
            r = cursor.fetchone()

        if not r:
            return None

        return PanelFaultMapping(
            id=r[0],
            detection_id=r[1],
            panel_id=r[2],
            image_id=r[3],
            string_id=r[4],
            row_index=r[5],
            col_index=r[6],
            panel_identifier=r[7],
            overlap_iou=r[8],
            relative_x=r[9],
            relative_y=r[10],
            created_at=datetime.fromisoformat(r[11]) if r[11] else datetime.now(),
        )
