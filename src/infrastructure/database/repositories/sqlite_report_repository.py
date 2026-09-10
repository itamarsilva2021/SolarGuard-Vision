"""
Repositório concreto de Relatórios Técnicos utilizando SQLite3.
Implementa IReportRepository.
"""

from typing import Optional
from src.domain.entities.report import Report
from src.domain.interfaces.repositories import IReportRepository
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.models import row_to_report


class SqliteReportRepository(IReportRepository):
    """Implementação SQLite do repositório de relatórios."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def save(self, report: Report) -> Report:
        """Insere ou atualiza o registro de um relatório gerado (UPSERT)."""
        sql = """
            INSERT INTO reports (
                id, inspection_id, title, report_type, file_path,
                file_size_bytes, generated_by, generated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                inspection_id = excluded.inspection_id,
                title = excluded.title,
                report_type = excluded.report_type,
                file_path = excluded.file_path,
                file_size_bytes = excluded.file_size_bytes,
                generated_by = excluded.generated_by,
                generated_at = excluded.generated_at;
        """
        with self._db.transaction() as conn:
            conn.execute(
                sql,
                (
                    report.id,
                    report.inspection_id,
                    report.title,
                    report.report_type.value,
                    report.file_path,
                    report.file_size_bytes,
                    report.generated_by,
                    report.generated_at.isoformat(),
                ),
            )
        return report

    def get_by_id(self, report_id: str) -> Optional[Report]:
        """Recupera um relatório pelo ID."""
        sql = "SELECT * FROM reports WHERE id = ?;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (report_id,))
            row = cursor.fetchone()
            return row_to_report(row) if row else None
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def list_by_inspection(self, inspection_id: str) -> list[Report]:
        """Lista todos os relatórios emitidos para uma inspeção."""
        sql = "SELECT * FROM reports WHERE inspection_id = ? ORDER BY generated_at DESC;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (inspection_id,))
            return [row_to_report(row) for row in cursor.fetchall()]
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def list_all(self) -> list[Report]:
        """Lista todos os relatórios cadastrados."""
        sql = "SELECT * FROM reports ORDER BY generated_at DESC;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql)
            return [row_to_report(row) for row in cursor.fetchall()]
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def delete(self, report_id: str) -> bool:
        """Remove o registro de um relatório."""
        sql = "DELETE FROM reports WHERE id = ?;"
        with self._db.transaction() as conn:
            cursor = conn.execute(sql, (report_id,))
            return cursor.rowcount > 0
