"""
Gerenciador de Conexões e Ciclo de Vida do Banco de Dados SQLite.
Oferece suporte a modo WAL, verificação de integridade referencial e transações atômicas.
"""

import sqlite3
from pathlib import Path
from typing import Generator, Optional
from contextlib import contextmanager
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("DatabaseManager")


class DatabaseManager:
    """
    Gerencia conexões com o SQLite para SolarGuard Vision.
    Permite operar tanto com banco em disco persistente quanto com banco em memória (:memory:).
    """

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        if db_path is None:
            self.db_path = settings.db_path
        elif str(db_path) == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(db_path)

        self._in_memory_connection: Optional[sqlite3.Connection] = None
        if self.is_in_memory:
            # Em memória mantém conexão persistente compartilhada para a instância
            self._in_memory_connection = self._create_connection()

    @property
    def is_in_memory(self) -> bool:
        return str(self.db_path) == ":memory:"

    def _create_connection(self) -> sqlite3.Connection:
        """Cria e configura uma nova conexão SQLite com pragmas de segurança e performance."""
        if not self.is_in_memory and isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row

        # Ativar Foreign Keys e otimizações
        conn.execute("PRAGMA foreign_keys = ON;")
        if not self.is_in_memory:
            conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")

        return conn

    def get_connection(self) -> sqlite3.Connection:
        """Retorna uma conexão ativa."""
        if self.is_in_memory and self._in_memory_connection is not None:
            return self._in_memory_connection
        return self._create_connection()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Gerenciador de contexto para transações seguras.
        Executa commit automático em caso de sucesso ou rollback em caso de exceção.
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as ex:
            conn.rollback()
            logger.error(f"Erro em transação de banco de dados. Rollback executado: {ex}")
            raise
        finally:
            if not self.is_in_memory:
                conn.close()

    def initialize_schema(self) -> None:
        """Executa o script DDL schema.sql para criar tabelas e índices se não existirem e aplica migrações."""
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"Arquivo de schema SQL não encontrado em: {schema_path}")

        schema_sql = schema_path.read_text(encoding="utf-8")
        with self.transaction() as conn:
            conn.executescript(schema_sql)
            
            # Migração retrocompatível para tabelas existentes
            try:
                cursor = conn.execute("PRAGMA table_info(users);")
                columns = [row[1] for row in cursor.fetchall()]
                if "must_change_password" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0;")
                    logger.info("Migração de schema aplicada: coluna 'must_change_password' adicionada à tabela 'users'.")
                if "failed_login_attempts" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0;")
                    logger.info("Migração de schema aplicada: coluna 'failed_login_attempts' adicionada à tabela 'users'.")
                if "locked_until" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN locked_until TEXT;")
                    logger.info("Migração de schema aplicada: coluna 'locked_until' adicionada à tabela 'users'.")
                if "lockout_count" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN lockout_count INTEGER NOT NULL DEFAULT 0;")
                    logger.info("Migração de schema aplicada: coluna 'lockout_count' adicionada à tabela 'users'.")
            except Exception as ex:
                logger.warning(f"Erro ao verificar migrações da tabela users: {ex}")

        logger.info(f"Schema do banco de dados inicializado com sucesso em: {self.db_path}")

    def close(self) -> None:
        """Fecha a conexão em memória caso exista."""
        if self._in_memory_connection:
            self._in_memory_connection.close()
            self._in_memory_connection = None
