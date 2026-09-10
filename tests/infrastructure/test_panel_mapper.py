"""
Testes unitários e de integração para a ETAPA 17: Mapeamento de Painéis Solares (PanelMapper).
Testa segmentação de módulos, indexação topológica (String/Linha/Coluna),
associação de defeitos por IoU/centroide e persistência relacional SQLite.
"""

import pytest
import numpy as np
import uuid
from datetime import datetime

from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories.sqlite_panel_repository import SqlitePanelRepository
from src.infrastructure.database.repositories.sqlite_thermal_image_repository import SqliteThermalImageRepository
from src.infrastructure.database.repositories.sqlite_inspection_repository import SqliteInspectionRepository
from src.infrastructure.database.repositories.sqlite_project_repository import SqliteProjectRepository
from src.infrastructure.database.repositories.sqlite_client_repository import SqliteClientRepository
from src.domain.entities.client import Client
from src.domain.entities.project import Project
from src.domain.entities.inspection import Inspection
from src.domain.entities.thermal_image import ThermalImage
from src.domain.entities.solar_panel import SolarPanel, PanelFaultMapping
from src.domain.value_objects.bounding_box import BoundingBox
from src.infrastructure.gis.panel_mapper import PanelMapper


@pytest.fixture
def in_memory_db():
    db = DatabaseManager(db_path=":memory:")
    db.initialize_schema()
    return db


@pytest.fixture
def setup_image_and_inspection(in_memory_db):
    img_repo = SqliteThermalImageRepository(in_memory_db)
    inspection_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())

    with in_memory_db.transaction() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, client_name, location_name, capacity_kwp, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?);",
            (project_id, "Planta Solar Topológica", "Cliente Solar", "Petrolina", 1200.0, datetime.now().isoformat()),
        )
        conn.execute(
            "INSERT INTO inspections (id, project_id, title, inspector_name, drone_model, status, date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?);",
            (inspection_id, project_id, "Inspeção Topológica #1", "Inspetor Solar", "DJI Matrice 4T", "completed", datetime.now().isoformat()),
        )

    img = ThermalImage(
        inspection_id=inspection_id,
        file_path="C:/photos/DJI_TOPOLOGY_001.JPG",
        filename="DJI_TOPOLOGY_001.JPG",
        width=640,
        height=512,
    )
    img_repo.save(img)

    return img, inspection_id


class TestPanelMapper:
    """Testes para o serviço e engine de mapeamento e segmentação de painéis."""

    def test_segment_grid_generates_correct_dimensions(self):
        mapper = PanelMapper()
        # Grade 2 linhas por 4 colunas (8 módulos)
        bboxes = mapper.segment_grid(rows=2, cols=4, margin_x=0.05, margin_y=0.05, gap_x=0.02, gap_y=0.02)

        assert len(bboxes) == 8
        for b in bboxes:
            assert 0.0 <= b.xmin < b.xmax <= 1.0
            assert 0.0 <= b.ymin < b.ymax <= 1.0
            assert b.width > 0
            assert b.height > 0

    def test_segment_grid_invalid_parameters_raises(self):
        mapper = PanelMapper()
        with pytest.raises(ValueError):
            mapper.segment_grid(rows=0, cols=4)
        with pytest.raises(ValueError):
            mapper.segment_grid(rows=2, cols=0)
        with pytest.raises(ValueError):
            mapper.segment_grid(rows=10, cols=10, margin_x=0.6, margin_y=0.6)

    def test_segment_from_radiometric_matrix(self):
        mapper = PanelMapper()
        # Matriz térmica sintética 512x640 com 2 painéis bem contrastados (temperatura alta)
        thermal_matrix = np.full((512, 640), 25.0, dtype=np.float32)  # Fundo 25°C
        # Módulo 1: (y: 100..200, x: 100..250) a 50°C
        thermal_matrix[100:200, 100:250] = 50.0
        # Módulo 2: (y: 100..200, x: 350..500) a 50°C
        thermal_matrix[100:200, 350:500] = 50.0

        bboxes = mapper.segment_from_radiometric_matrix(thermal_matrix, min_area_ratio=0.01)
        assert len(bboxes) >= 2

    def test_index_modules_spatial_sorting(self):
        mapper = PanelMapper()
        img_id = str(uuid.uuid4())

        # Cria 4 módulos em grade 2x2, propositalmente desordenados
        # Linha 1: Y ~ 0.2 (Col 1: X ~ 0.2, Col 2: X ~ 0.7)
        # Linha 2: Y ~ 0.6 (Col 1: X ~ 0.2, Col 2: X ~ 0.7)
        b_r2_c2 = BoundingBox(xmin=0.6, ymin=0.55, xmax=0.8, ymax=0.7)  # R2 C2
        b_r1_c1 = BoundingBox(xmin=0.1, ymin=0.15, xmax=0.3, ymax=0.3)  # R1 C1
        b_r2_c1 = BoundingBox(xmin=0.1, ymin=0.55, xmax=0.3, ymax=0.7)  # R2 C1
        b_r1_c2 = BoundingBox(xmin=0.6, ymin=0.15, xmax=0.8, ymax=0.3)  # R1 C2

        shuffled = [b_r2_c2, b_r1_c1, b_r2_c1, b_r1_c2]
        indexed = mapper.index_modules(shuffled, image_id=img_id, string_id="STR-05")

        assert len(indexed) == 4

        # Linha 1, Coluna 1
        assert indexed[0].row_index == 1 and indexed[0].col_index == 1
        assert indexed[0].panel_identifier == "STR-05-R01-C01"
        assert indexed[0].bbox.xmin == pytest.approx(0.1)

        # Linha 1, Coluna 2
        assert indexed[1].row_index == 1 and indexed[1].col_index == 2
        assert indexed[1].panel_identifier == "STR-05-R01-C02"
        assert indexed[1].bbox.xmin == pytest.approx(0.6)

        # Linha 2, Coluna 1
        assert indexed[2].row_index == 2 and indexed[2].col_index == 1
        assert indexed[2].panel_identifier == "STR-05-R02-C01"
        assert indexed[2].bbox.xmin == pytest.approx(0.1)

        # Linha 2, Coluna 2
        assert indexed[3].row_index == 2 and indexed[3].col_index == 2
        assert indexed[3].panel_identifier == "STR-05-R02-C02"
        assert indexed[3].bbox.xmin == pytest.approx(0.6)

    def test_associate_fault_to_panel(self):
        mapper = PanelMapper()
        img_id = str(uuid.uuid4())

        p1 = SolarPanel(
            image_id=img_id,
            string_id="STR-01",
            row_index=1,
            col_index=1,
            panel_identifier="STR-01-R01-C01",
            bbox=BoundingBox(xmin=0.1, ymin=0.1, xmax=0.4, ymax=0.4),
        )
        p2 = SolarPanel(
            image_id=img_id,
            string_id="STR-01",
            row_index=1,
            col_index=2,
            panel_identifier="STR-01-R01-C02",
            bbox=BoundingBox(xmin=0.6, ymin=0.1, xmax=0.9, ymax=0.4),
        )

        # Falha 1: Perfeitamente dentro de p1 (centroide x=0.25, y=0.25)
        fault_in_p1 = BoundingBox(xmin=0.2, ymin=0.2, xmax=0.3, ymax=0.3)
        mapping1 = mapper.associate_fault_to_panel(fault_in_p1, [p1, p2], detection_id="DET-001")

        assert mapping1 is not None
        assert mapping1.panel_identifier == "STR-01-R01-C01"
        assert mapping1.row_index == 1
        assert mapping1.col_index == 1
        assert mapping1.detection_id == "DET-001"
        assert mapping1.overlap_iou > 0
        assert mapping1.relative_x == pytest.approx(0.5, abs=0.05)
        assert mapping1.relative_y == pytest.approx(0.5, abs=0.05)

        # Falha 2: Fora de ambos os módulos
        fault_outside = BoundingBox(xmin=0.45, ymin=0.7, xmax=0.55, ymax=0.8)
        mapping_none = mapper.associate_fault_to_panel(fault_outside, [p1, p2])
        assert mapping_none is None

    def test_map_and_persist_full_pipeline(self, in_memory_db, setup_image_and_inspection):
        image, _ = setup_image_and_inspection
        panel_repo = SqlitePanelRepository(in_memory_db)
        mapper = PanelMapper(panel_repo=panel_repo)

        # 1. Gera grade 2x3 de módulos
        grid_bboxes = mapper.segment_grid(rows=2, cols=3, margin_x=0.05, margin_y=0.05)

        # 2. Gera falhas térmicas simuladas e insere detecção no banco
        f1_bbox = BoundingBox(xmin=0.45, ymin=0.2, xmax=0.5, ymax=0.25)
        with in_memory_db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO detections (
                    id, image_id, class_name, confidence, bbox_xmin, bbox_ymin,
                    bbox_xmax, bbox_ymax, delta_t, max_temp_celsius, avg_temp_celsius,
                    severity, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "DET-101", image.id, "hotspot", 0.95,
                    f1_bbox.xmin, f1_bbox.ymin, f1_bbox.xmax, f1_bbox.ymax,
                    25.0, 68.0, 52.0, "medium", datetime.now().isoformat()
                )
            )

        faults = [("DET-101", f1_bbox)]

        # 3. Executa indexação, associação e persistência
        panels, mappings = mapper.map_and_persist(
            image_id=image.id,
            panels_bboxes=grid_bboxes,
            faults=faults,
            string_id="STRING-B2",
        )

        assert len(panels) == 6
        assert len(mappings) == 1
        assert mappings[0].string_id == "STRING-B2"
        assert mappings[0].detection_id == "DET-101"

        # 4. Validação direta via consultas do Repositório SQLite
        saved_panels = panel_repo.get_panels_by_image_id(image.id)
        assert len(saved_panels) == 6

        saved_mappings = panel_repo.get_mappings_by_image_id(image.id)
        assert len(saved_mappings) == 1
        assert saved_mappings[0].panel_identifier == mappings[0].panel_identifier

        single_mapping = panel_repo.get_mapping_by_detection_id("DET-101")
        assert single_mapping is not None
        assert single_mapping.panel_id == mappings[0].panel_id
