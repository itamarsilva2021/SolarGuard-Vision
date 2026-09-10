"""
Repositório concreto de Clientes utilizando SQLite3.
Implementa IClientRepository seguindo os princípios SOLID.
"""

from typing import Optional
from src.domain.entities.client import Client
from src.domain.interfaces.repositories import IClientRepository
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.models import row_to_client


class SqliteClientRepository(IClientRepository):
    """Implementação SQLite do repositório de clientes."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def save(self, client: Client) -> Client:
        """Insere ou atualiza um cliente (UPSERT)."""
        sql = """
            INSERT INTO clients (id, name, document, email, phone, address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                document = excluded.document,
                email = excluded.email,
                phone = excluded.phone,
                address = excluded.address;
        """
        with self._db.transaction() as conn:
            conn.execute(
                sql,
                (
                    client.id,
                    client.name,
                    client.document,
                    client.email,
                    client.phone,
                    client.address,
                    client.created_at.isoformat(),
                ),
            )
        return client

    def get_by_id(self, client_id: str) -> Optional[Client]:
        """Recupera um cliente pelo ID."""
        sql = "SELECT * FROM clients WHERE id = ?;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (client_id,))
            row = cursor.fetchone()
            return row_to_client(row) if row else None
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def list_all(self) -> list[Client]:
        """Lista todos os clientes ordenados por data de criação decrescente."""
        sql = "SELECT * FROM clients ORDER BY created_at DESC;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql)
            return [row_to_client(row) for row in cursor.fetchall()]
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def delete(self, client_id: str) -> bool:
        """Remove um cliente pelo ID."""
        sql = "DELETE FROM clients WHERE id = ?;"
        with self._db.transaction() as conn:
            cursor = conn.execute(sql, (client_id,))
            return cursor.rowcount > 0
