"""
Repositório SQLite para as tabelas científicas de inferência:
'thermal_analysis', 'delta_t_results', 'yolo_predictions' e 'detections'.
Garante transações atômicas e consultas de alta performance.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import sqlite3

from src.domain.entities.scientific_detection import (
    ThermalAnalysisRecord as ThermalAnalysisDTO,
    DeltaTResultRecord as DeltaTResultDTO,
    YoloPredictionRecord as YoloPredictionDTO,
    DetectionRecord as DetectionRecordDTO,
)
from src.domain.value_objects.bounding_box import BoundingBox
from src.infrastructure.database.connection import DatabaseManager
from src.core.logger import get_logger

logger = get_logger("SqliteDetectionRepository")


class SqliteDetectionRepository:
    """
    Gerencia persistência relacional das inferências do detector YOLOv11 e análises Delta T.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or DatabaseManager()

    def save_thermal_analysis(self, record: ThermalAnalysisDTO) -> ThermalAnalysisDTO:
        """Persiste uma análise termográfica de imagem."""
        sql = """
        INSERT INTO thermal_analysis (
            id, image_id, emissivity, reflected_temp_celsius, ambient_temp_celsius,
            relative_humidity, distance_meters, min_temp_celsius, max_temp_celsius,
            avg_temp_celsius, global_delta_t, algorithm_version, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            min_temp_celsius = excluded.min_temp_celsius,
            max_temp_celsius = excluded.max_temp_celsius,
            avg_temp_celsius = excluded.avg_temp_celsius,
            global_delta_t = excluded.global_delta_t;
        """
        with self.db.transaction() as conn:
            conn.execute(
                sql,
                (
                    record.id,
                    record.image_id,
                    record.emissivity,
                    record.reflected_temp_celsius,
                    record.ambient_temp_celsius,
                    record.relative_humidity,
                    record.distance_meters,
                    record.min_temp_celsius,
                    record.max_temp_celsius,
                    record.avg_temp_celsius,
                    record.global_delta_t,
                    record.algorithm_version,
                    record.notes,
                    record.created_at.isoformat(),
                ),
            )
        return record

    def save_delta_t_results(self, records: List[DeltaTResultDTO]) -> List[DeltaTResultDTO]:
        """Persiste em lote os resultados de Delta T."""
        if not records:
            return []

        sql = """
        INSERT INTO delta_t_results (
            id, analysis_id, image_id, hotspot_temp_celsius, reference_temp_celsius,
            delta_t, severity, iec_class, reference_type, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.transaction() as conn:
            conn.executemany(
                sql,
                [
                    (
                        r.id,
                        r.analysis_id,
                        r.image_id,
                        r.hotspot_temp_celsius,
                        r.reference_temp_celsius,
                        r.delta_t,
                        r.severity,
                        r.iec_class,
                        r.reference_type,
                        r.created_at.isoformat(),
                    )
                    for r in records
                ],
            )
        return records

    def save_yolo_predictions(self, records: List[YoloPredictionDTO]) -> List[YoloPredictionDTO]:
        """Persiste em lote as predições do modelo YOLOv11."""
        if not records:
            return []

        sql = """
        INSERT INTO yolo_predictions (
            id, image_id, model_version, inference_time_ms, class_id,
            class_name, confidence, bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.transaction() as conn:
            conn.executemany(
                sql,
                [
                    (
                        r.id,
                        r.image_id,
                        r.model_version,
                        r.inference_time_ms,
                        r.class_id,
                        r.class_name,
                        r.confidence,
                        r.bbox.xmin,
                        r.bbox.ymin,
                        r.bbox.xmax,
                        r.bbox.ymax,
                        r.created_at.isoformat(),
                    )
                    for r in records
                ],
            )
        return records

    def save_detections(self, records: List[DetectionRecordDTO]) -> List[DetectionRecordDTO]:
        """Persiste em lote as detecções científicas consolidadas."""
        if not records:
            return []

        sql = """
        INSERT INTO detections (
            id, image_id, analysis_id, delta_t_id, yolo_prediction_id,
            class_name, confidence, bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax,
            delta_t, max_temp_celsius, avg_temp_celsius, min_temp_celsius,
            severity, crop_path, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.transaction() as conn:
            conn.executemany(
                sql,
                [
                    (
                        r.id,
                        r.image_id,
                        r.analysis_id,
                        r.delta_t_id,
                        r.yolo_prediction_id,
                        r.class_name,
                        r.confidence,
                        r.bbox.xmin,
                        r.bbox.ymin,
                        r.bbox.xmax,
                        r.bbox.ymax,
                        r.delta_t,
                        r.max_temp_celsius,
                        r.avg_temp_celsius,
                        r.min_temp_celsius,
                        r.severity,
                        r.crop_path,
                        r.notes,
                        r.created_at.isoformat(),
                    )
                    for r in records
                ],
            )
        return records

    def save_full_inference_transaction(
        self,
        analysis: ThermalAnalysisDTO,
        predictions: List[YoloPredictionDTO],
        delta_t_list: List[DeltaTResultDTO],
        detections: List[DetectionRecordDTO],
    ) -> None:
        """
        Executa a gravação de toda a sessão de inferência em uma única transação atômica.
        Se qualquer inserção falhar, todas as alterações são revertidas (rollback).
        """
        with self.db.transaction() as conn:
            # 1. Análise Térmica
            sql_analysis = """
            INSERT INTO thermal_analysis (
                id, image_id, emissivity, reflected_temp_celsius, ambient_temp_celsius,
                relative_humidity, distance_meters, min_temp_celsius, max_temp_celsius,
                avg_temp_celsius, global_delta_t, algorithm_version, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """
            conn.execute(
                sql_analysis,
                (
                    analysis.id,
                    analysis.image_id,
                    analysis.emissivity,
                    analysis.reflected_temp_celsius,
                    analysis.ambient_temp_celsius,
                    analysis.relative_humidity,
                    analysis.distance_meters,
                    analysis.min_temp_celsius,
                    analysis.max_temp_celsius,
                    analysis.avg_temp_celsius,
                    analysis.global_delta_t,
                    analysis.algorithm_version,
                    analysis.notes,
                    analysis.created_at.isoformat(),
                ),
            )

            # 2. Predições YOLO
            if predictions:
                sql_pred = """
                INSERT INTO yolo_predictions (
                    id, image_id, model_version, inference_time_ms, class_id,
                    class_name, confidence, bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """
                conn.executemany(
                    sql_pred,
                    [
                        (
                            p.id, p.image_id, p.model_version, p.inference_time_ms,
                            p.class_id, p.class_name, p.confidence,
                            p.bbox.xmin, p.bbox.ymin, p.bbox.xmax, p.bbox.ymax,
                            p.created_at.isoformat(),
                        )
                        for p in predictions
                    ],
                )

            # 3. Delta T
            if delta_t_list:
                sql_dt = """
                INSERT INTO delta_t_results (
                    id, analysis_id, image_id, hotspot_temp_celsius, reference_temp_celsius,
                    delta_t, severity, iec_class, reference_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """
                conn.executemany(
                    sql_dt,
                    [
                        (
                            d.id, d.analysis_id, d.image_id, d.hotspot_temp_celsius,
                            d.reference_temp_celsius, d.delta_t, d.severity,
                            d.iec_class, d.reference_type, d.created_at.isoformat(),
                        )
                        for d in delta_t_list
                    ],
                )

            # 4. Detecções Consolidadas
            if detections:
                sql_det = """
                INSERT INTO detections (
                    id, image_id, analysis_id, delta_t_id, yolo_prediction_id,
                    class_name, confidence, bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax,
                    delta_t, max_temp_celsius, avg_temp_celsius, min_temp_celsius,
                    severity, crop_path, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """
                conn.executemany(
                    sql_det,
                    [
                        (
                            det.id, det.image_id, det.analysis_id, det.delta_t_id, det.yolo_prediction_id,
                            det.class_name, det.confidence, det.bbox.xmin, det.bbox.ymin,
                            det.bbox.xmax, det.bbox.ymax, det.delta_t, det.max_temp_celsius,
                            det.avg_temp_celsius, det.min_temp_celsius, det.severity,
                            det.crop_path, det.notes, det.created_at.isoformat(),
                        )
                        for det in detections
                    ],
                )

            # 5. Atualiza a flag is_analyzed na imagem
            conn.execute("UPDATE thermal_images SET is_analyzed = 1 WHERE id = ?;", (analysis.image_id,))

        logger.info(
            f"Transação científica concluída para imagem {analysis.image_id}: "
            f"{len(detections)} detecções e {len(delta_t_list)} cálculos Delta-T salvos."
        )

    def get_detections_by_image_id(self, image_id: str) -> List[DetectionRecordDTO]:
        """Consulta todas as detecções de uma imagem específica."""
        sql = "SELECT * FROM detections WHERE image_id = ? ORDER BY max_temp_celsius DESC;"
        records: List[DetectionRecordDTO] = []
        with self.db.transaction() as conn:
            rows = conn.execute(sql, (image_id,)).fetchall()
            for r in rows:
                records.append(self._row_to_detection(r))
        return records

    def get_detections_by_inspection_id(self, inspection_id: str) -> List[DetectionRecordDTO]:
        """Consulta todas as detecções de todas as imagens de uma inspeção."""
        sql = """
        SELECT d.* FROM detections d
        JOIN thermal_images ti ON d.image_id = ti.id
        WHERE ti.inspection_id = ?
        ORDER BY d.created_at ASC;
        """
        records: List[DetectionRecordDTO] = []
        with self.db.transaction() as conn:
            rows = conn.execute(sql, (inspection_id,)).fetchall()
            for r in rows:
                records.append(self._row_to_detection(r))
        return records

    def get_thermal_analysis_by_image_id(self, image_id: str) -> Optional[ThermalAnalysisDTO]:
        """Recupera a análise térmica registrada para uma imagem."""
        sql = "SELECT * FROM thermal_analysis WHERE image_id = ? ORDER BY created_at DESC LIMIT 1;"
        with self.db.transaction() as conn:
            row = conn.execute(sql, (image_id,)).fetchone()
            if row:
                return ThermalAnalysisDTO(
                    id=row["id"],
                    image_id=row["image_id"],
                    emissivity=row["emissivity"],
                    reflected_temp_celsius=row["reflected_temp_celsius"],
                    ambient_temp_celsius=row["ambient_temp_celsius"],
                    relative_humidity=row["relative_humidity"],
                    distance_meters=row["distance_meters"],
                    min_temp_celsius=row["min_temp_celsius"],
                    max_temp_celsius=row["max_temp_celsius"],
                    avg_temp_celsius=row["avg_temp_celsius"],
                    global_delta_t=row["global_delta_t"],
                    algorithm_version=row["algorithm_version"],
                    notes=row["notes"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
        return None

    @staticmethod
    def _row_to_detection(row: sqlite3.Row) -> DetectionRecordDTO:
        """Converte linha SQLite em DetectionRecordDTO."""
        bbox = BoundingBox(
            xmin=row["bbox_xmin"],
            ymin=row["bbox_ymin"],
            xmax=row["bbox_xmax"],
            ymax=row["bbox_ymax"],
        )
        return DetectionRecordDTO(
            id=row["id"],
            image_id=row["image_id"],
            analysis_id=row["analysis_id"],
            delta_t_id=row["delta_t_id"],
            yolo_prediction_id=row["yolo_prediction_id"],
            class_name=row["class_name"],
            confidence=row["confidence"],
            bbox=bbox,
            delta_t=row["delta_t"],
            max_temp_celsius=row["max_temp_celsius"],
            avg_temp_celsius=row["avg_temp_celsius"],
            min_temp_celsius=row["min_temp_celsius"],
            severity=row["severity"],
            crop_path=row["crop_path"],
            notes=row["notes"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
