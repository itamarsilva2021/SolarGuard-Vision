"""
Repositório concreto de Falhas / Anomalias Térmicas utilizando SQLite3.
Implementa IThermalAnomalyRepository.
"""

from typing import Optional
from src.domain.entities.thermal_anomaly import ThermalAnomaly
from src.domain.interfaces.repositories import IThermalAnomalyRepository
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.models import row_to_thermal_anomaly


class SqliteThermalAnomalyRepository(IThermalAnomalyRepository):
    """Implementação SQLite do repositório de falhas térmicas."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def save(self, anomaly: ThermalAnomaly, image_id: Optional[str] = None) -> ThermalAnomaly:
        """Insere ou atualiza uma anomalia associada a uma imagem (UPSERT)."""
        target_image_id = image_id or anomaly.image_id
        if not target_image_id:
            raise ValueError("image_id é obrigatório para persistir uma ThermalAnomaly.")

        anomaly.image_id = target_image_id

        sql = """
            INSERT INTO thermal_anomalies (
                id, image_id, anomaly_type, severity, confidence,
                bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax, bbox_is_normalized,
                max_temp_celsius, min_temp_celsius, avg_temp_celsius,
                delta_t_ref_temp, crop_path, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                image_id = excluded.image_id,
                anomaly_type = excluded.anomaly_type,
                severity = excluded.severity,
                confidence = excluded.confidence,
                bbox_xmin = excluded.bbox_xmin,
                bbox_ymin = excluded.bbox_ymin,
                bbox_xmax = excluded.bbox_xmax,
                bbox_ymax = excluded.bbox_ymax,
                bbox_is_normalized = excluded.bbox_is_normalized,
                max_temp_celsius = excluded.max_temp_celsius,
                min_temp_celsius = excluded.min_temp_celsius,
                avg_temp_celsius = excluded.avg_temp_celsius,
                delta_t_ref_temp = excluded.delta_t_ref_temp,
                crop_path = excluded.crop_path,
                notes = excluded.notes;
        """
        ref_temp = anomaly.delta_t.t_ref_celsius if anomaly.delta_t else None

        with self._db.transaction() as conn:
            conn.execute(
                sql,
                (
                    anomaly.id,
                    target_image_id,
                    anomaly.anomaly_type.value,
                    anomaly.severity.value,
                    anomaly.confidence,
                    anomaly.bbox.x_min,
                    anomaly.bbox.y_min,
                    anomaly.bbox.x_max,
                    anomaly.bbox.y_max,
                    1 if anomaly.bbox.is_normalized else 0,
                    anomaly.max_temp_celsius,
                    anomaly.min_temp_celsius,
                    anomaly.avg_temp_celsius,
                    ref_temp,
                    anomaly.crop_path,
                    anomaly.notes,
                    anomaly.created_at.isoformat(),
                ),
            )
        return anomaly

    def get_by_id(self, anomaly_id: str) -> Optional[ThermalAnomaly]:
        """Recupera uma anomalia pelo ID."""
        sql = "SELECT * FROM thermal_anomalies WHERE id = ?;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (anomaly_id,))
            row = cursor.fetchone()
            return row_to_thermal_anomaly(row) if row else None
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def list_by_image(self, image_id: str) -> list[ThermalAnomaly]:
        """Lista todas as anomalias detectadas em uma imagem térmica."""
        sql = "SELECT * FROM thermal_anomalies WHERE image_id = ? ORDER BY max_temp_celsius DESC;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (image_id,))
            return [row_to_thermal_anomaly(row) for row in cursor.fetchall()]
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def list_by_inspection(self, inspection_id: str) -> list[ThermalAnomaly]:
        """Lista todas as anomalias de todas as imagens de uma inspeção."""
        sql = """
            SELECT a.* FROM thermal_anomalies a
            JOIN thermal_images img ON a.image_id = img.id
            WHERE img.inspection_id = ?
            ORDER BY a.max_temp_celsius DESC;
        """
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (inspection_id,))
            return [row_to_thermal_anomaly(row) for row in cursor.fetchall()]
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def delete(self, anomaly_id: str) -> bool:
        """Remove uma anomalia pelo ID."""
        sql = "DELETE FROM thermal_anomalies WHERE id = ?;"
        with self._db.transaction() as conn:
            cursor = conn.execute(sql, (anomaly_id,))
            return cursor.rowcount > 0
