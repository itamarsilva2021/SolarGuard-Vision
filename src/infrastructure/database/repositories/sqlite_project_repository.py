"""
Repositório concreto de Projetos / Usinas Solares utilizando SQLite3.
Implementa IProjectRepository.
"""

from typing import Optional
from src.domain.entities.project import Project
from src.domain.interfaces.repositories import IProjectRepository
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.models import row_to_project


class SqliteProjectRepository(IProjectRepository):
    """Implementação SQLite do repositório de usinas solares / projetos."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def save(self, project: Project) -> Project:
        """Insere ou atualiza um projeto (UPSERT)."""
        sql = """
            INSERT INTO projects (
                id, client_id, name, client_name, location_name, capacity_kwp,
                latitude, longitude, altitude_meters, module_manufacturer,
                module_model, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                client_id = excluded.client_id,
                name = excluded.name,
                client_name = excluded.client_name,
                location_name = excluded.location_name,
                capacity_kwp = excluded.capacity_kwp,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                altitude_meters = excluded.altitude_meters,
                module_manufacturer = excluded.module_manufacturer,
                module_model = excluded.module_model;
        """
        lat = project.coordinate.latitude if project.coordinate else None
        lon = project.coordinate.longitude if project.coordinate else None
        alt = project.coordinate.altitude_meters if project.coordinate else None

        with self._db.transaction() as conn:
            conn.execute(
                sql,
                (
                    project.id,
                    project.client_id,
                    project.name,
                    project.client_name,
                    project.location_name,
                    project.capacity_kwp,
                    lat,
                    lon,
                    alt,
                    project.module_manufacturer,
                    project.module_model,
                    project.created_at.isoformat(),
                ),
            )
        return project

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """Recupera um projeto pelo ID."""
        sql = "SELECT * FROM projects WHERE id = ?;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (project_id,))
            row = cursor.fetchone()
            return row_to_project(row) if row else None
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def list_all(self) -> list[Project]:
        """Lista todos os projetos cadastrados."""
        sql = "SELECT * FROM projects ORDER BY created_at DESC;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql)
            return [row_to_project(row) for row in cursor.fetchall()]
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def list_by_client(self, client_id: str) -> list[Project]:
        """Lista todos os projetos de um cliente específico."""
        sql = "SELECT * FROM projects WHERE client_id = ? ORDER BY created_at DESC;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (client_id,))
            return [row_to_project(row) for row in cursor.fetchall()]
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def delete(self, project_id: str) -> bool:
        """Remove um projeto pelo ID (cascateia para inspeções/imagens/anomalias via FK)."""
        sql = "DELETE FROM projects WHERE id = ?;"
        with self._db.transaction() as conn:
            cursor = conn.execute(sql, (project_id,))
            return cursor.rowcount > 0
