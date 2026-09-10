"""
Repositório concreto de Inspeções utilizando SQLite3.
Implementa IInspectionRepository.
"""

from typing import Optional
from src.domain.entities.inspection import Inspection
from src.domain.interfaces.repositories import IInspectionRepository
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.models import row_to_inspection


class SqliteInspectionRepository(IInspectionRepository):
    """Implementação SQLite do repositório de missões de inspeção."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def save(self, inspection: Inspection) -> Inspection:
        """Insere ou atualiza uma inspeção (UPSERT)."""
        sql = """
            INSERT INTO inspections (
                id, project_id, title, inspector_name, drone_model, status,
                irradiance_w_m2, ambient_temp_celsius, wind_speed_m_s, notes, date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                project_id = excluded.project_id,
                title = excluded.title,
                inspector_name = excluded.inspector_name,
                drone_model = excluded.drone_model,
                status = excluded.status,
                irradiance_w_m2 = excluded.irradiance_w_m2,
                ambient_temp_celsius = excluded.ambient_temp_celsius,
                wind_speed_m_s = excluded.wind_speed_m_s,
                notes = excluded.notes,
                date = excluded.date;
        """
        with self._db.transaction() as conn:
            conn.execute(
                sql,
                (
                    inspection.id,
                    inspection.project_id,
                    inspection.title,
                    inspection.inspector_name,
                    inspection.drone_model,
                    inspection.status.value,
                    inspection.irradiance_w_m2,
                    inspection.ambient_temp_celsius,
                    inspection.wind_speed_m_s,
                    inspection.notes,
                    inspection.date.isoformat(),
                ),
            )
        return inspection

    def get_by_id(self, inspection_id: str) -> Optional[Inspection]:
        """Recupera uma inspeção pelo ID."""
        sql = "SELECT * FROM inspections WHERE id = ?;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (inspection_id,))
            row = cursor.fetchone()
            return row_to_inspection(row) if row else None
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def list_all(self) -> list[Inspection]:
        """Lista todas as inspeções registradas no sistema."""
        sql = "SELECT * FROM inspections ORDER BY date DESC;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql)
            return [row_to_inspection(row) for row in cursor.fetchall()]
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def list_by_project(self, project_id: str) -> list[Inspection]:
        """Lista todas as inspeções de uma determinada usina/projeto."""
        sql = "SELECT * FROM inspections WHERE project_id = ? ORDER BY date DESC;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (project_id,))
            return [row_to_inspection(row) for row in cursor.fetchall()]
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def delete(self, inspection_id: str) -> bool:
        """Remove uma inspeção pelo ID."""
        sql = "DELETE FROM inspections WHERE id = ?;"
        with self._db.transaction() as conn:
            cursor = conn.execute(sql, (inspection_id,))
            return cursor.rowcount > 0
