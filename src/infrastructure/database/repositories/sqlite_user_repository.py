"""
Repositório concreto de Usuários utilizando SQLite3.
Implementa IUserRepository.
"""

from typing import Optional, List
from src.domain.entities.user import User
from src.domain.interfaces.repositories import IUserRepository
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.models import row_to_user


class SqliteUserRepository(IUserRepository):
    """Implementação SQLite do repositório de usuários."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def save(self, user: User) -> User:
        """Insere ou atualiza um usuário no banco (UPSERT)."""
        sql = """
            INSERT INTO users (
                id, username, password_hash, salt, full_name, email, role,
                is_active, last_login, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username = excluded.username,
                password_hash = excluded.password_hash,
                salt = excluded.salt,
                full_name = excluded.full_name,
                email = excluded.email,
                role = excluded.role,
                is_active = excluded.is_active,
                last_login = excluded.last_login;
        """
        last_login_str = user.last_login.isoformat() if user.last_login else None

        with self._db.transaction() as conn:
            conn.execute(
                sql,
                (
                    user.id,
                    user.username,
                    user.password_hash,
                    user.salt,
                    user.full_name,
                    user.email,
                    user.role.value,
                    1 if user.is_active else 0,
                    last_login_str,
                    user.created_at.isoformat(),
                ),
            )
        return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        """Recupera um usuário pelo ID."""
        sql = "SELECT * FROM users WHERE id = ?;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (user_id,))
            row = cursor.fetchone()
            return row_to_user(row) if row else None
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def get_by_username(self, username: str) -> Optional[User]:
        """Recupera um usuário pelo nome de login."""
        sql = "SELECT * FROM users WHERE username = ?;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql, (username,))
            row = cursor.fetchone()
            return row_to_user(row) if row else None
        finally:
            if not self._db.is_in_memory:
                conn.close()

    def list_all(self) -> List[User]:
        """Lista todos os usuários cadastrados."""
        sql = "SELECT * FROM users ORDER BY created_at ASC;"
        conn = self._db.get_connection()
        try:
            cursor = conn.execute(sql)
            return [row_to_user(r) for r in cursor.fetchall()]
        finally:
            if not self._db.is_in_memory:
                conn.close()


    def delete(self, user_id: str) -> bool:
        """Remove um usuário do banco."""
        sql = "DELETE FROM users WHERE id = ?;"
        with self._db.transaction() as conn:
            cursor = conn.execute(sql, (user_id,))
            return cursor.rowcount > 0
