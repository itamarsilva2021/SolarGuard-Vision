"""
Repositório concreto de Imagens Térmicas utilizando SQLite3.
Implementa IThermalImageRepository.
"""

from typing import Optional
from src.domain.entities.thermal_image import ThermalImage
from src.domain.interfaces.repositories import IThermalImageRepository
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.models import row_to_thermal_image


class SqliteThermalImageRepository(IThermalImageRepository):
    """Implementação SQLite do repositório de capturas térmicas."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def save(self, image: ThermalImage) -> ThermalImage:
        """Insere ou atualiza os metadados de uma imagem térmica (UPSERT)."""
        sql = """
            INSERT INTO thermal_images (
                id, inspection_id, file_path, filename, width, height,
                latitude, longitude, altitude_meters, flight_altitude_meters,
                gimbal_pitch_degrees, gimbal_yaw_degrees, is_analyzed, captured_at,
                emissivity, reflected_temp_celsius, ambient_temp_celsius,
                relative_humidity, distance_meters, min_temp_celsius,
                max_temp_celsius, avg_temp_celsius
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                inspection_id = excluded.inspection_id,
                file_path = excluded.file_path,
                filename = excluded.filename,
                width = excluded.width,
                height = excluded.height,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                altitude_meters = excluded.altitude_meters,
                flight_altitude_meters = excluded.flight_altitude_meters,
                gimbal_pitch_degrees = excluded.gimbal_pitch_degrees,
                gimbal_yaw_degrees = excluded.gimbal_yaw_degrees,
                is_analyzed = excluded.is_analyzed,
                captured_at = excluded.captured_at,
                emissivity = excluded.emissivity,
                reflected_temp_celsius = excluded.reflected_temp_celsius,
                ambient_temp_celsius = excluded.ambient_temp_celsius,
                relative_humidity = excluded.relative_humidity,
                distance_meters = excluded.distance_meters,
                min_temp_celsius = excluded.min_temp_celsius,
                max_temp_celsius = excluded.max_temp_celsius,
                avg_temp_celsius = excluded.avg_temp_celsius;
        """
        lat = image.coordinate.latitude if image.coordinate else None
        lon = image.coordinate.longitude if image.coordinate else None
        alt = image.coordinate.altitude_meters if image.coordinate else None

        emissivity = image.thermal_meta.emissivity if image.thermal_meta else None
        refl_temp = image.thermal_meta.reflected_temp_celsius if image.thermal_meta else None
        amb_temp = image.thermal_meta.ambient_temp_celsius if image.thermal_meta else None
        rel_hum = image.thermal_meta.relative_humidity if image.thermal_meta else None
        dist_m = image.thermal_meta.distance_meters if image.thermal_meta else None
        min_temp = image.thermal_meta.min_temp_celsius if image.thermal_meta else None
        max_temp = image.thermal_meta.max_temp_celsius if image.thermal_meta else None
        avg_temp = image.thermal_meta.avg_temp_celsius if image.thermal_meta else None

        captured_at_str = image.captured_at.isoformat() if image.captured_at else None

        with self._db.transaction() as conn:
            conn.execute(
                sql,
                (
                    image.id,
                    image.inspection_id,
                    image.file_path,
                    image.filename,
                    image.width,
                    image.height,
                    lat,
                    lon,
                    alt,
                    image.flight_altitude_meters,
                    image.gimbal_pitch_degrees,
                    image.gimbal_yaw_degrees,
                    1 if image.is_analyzed else 0,
                    captured_at_str,
                    emissivity,
                    refl_temp,
                    amb_temp,
                    rel_hum,
                    dist_m,
                    min_temp,
                    max_temp,
                    avg_temp,
                ),
            )
        return image

    def get_by_id(self, image_id: str) -> Optional[ThermalImage]:
        """Recupera uma imagem térmica pelo ID."""
        sql = "SELECT * FROM thermal_images WHERE id = ?;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (image_id,))
            row = cursor.fetchone()
            return row_to_thermal_image(row) if row else None
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def list_by_inspection(self, inspection_id: str) -> list[ThermalImage]:
        """Lista todas as imagens térmicas de uma inspeção."""
        sql = "SELECT * FROM thermal_images WHERE inspection_id = ? ORDER BY captured_at ASC, filename ASC;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (inspection_id,))
            return [row_to_thermal_image(row) for row in cursor.fetchall()]
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def get_by_inspection_id(self, inspection_id: str) -> list[ThermalImage]:
        """Alias de conveniência para list_by_inspection."""
        return self.list_by_inspection(inspection_id)

    def delete(self, image_id: str) -> bool:
        """Remove uma imagem térmica pelo ID."""
        sql = "DELETE FROM thermal_images WHERE id = ?;"
        with self._db.transaction() as conn:
            cursor = conn.execute(sql, (image_id,))
            return cursor.rowcount > 0
