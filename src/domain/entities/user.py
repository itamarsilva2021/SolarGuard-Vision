"""
Entidade de Domínio representando um Usuário do sistema com credenciais e papel de acesso.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from src.domain.enums.user_role import UserRole


@dataclass
class User:
    """
    Representa um usuário autenticado no sistema SolarGuard Vision.
    
    :param id: Identificador único universal.
    :param username: Nome de login único.
    :param password_hash: Hash criptográfico da senha (PBKDF2-HMAC-SHA256).
    :param salt: Sal criptográfico aleatório utilizado no hash.
    :param full_name: Nome completo do operador/engenheiro.
    :param email: E-mail para notificações.
    :param role: Papel de acesso no sistema (Admin, Inspector, Viewer).
    :param is_active: Indica se o usuário está ativo.
    :param last_login: Data e hora do último login realizado.
    :param created_at: Data de criação do cadastro.
    """
    username: str
    password_hash: str
    salt: str
    full_name: str
    role: UserRole = UserRole.INSPECTOR
    email: Optional[str] = None
    is_active: bool = True
    must_change_password: bool = False
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    lockout_count: int = 0
    last_login: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def can_inspect(self) -> bool:
        return self.role in [UserRole.ADMIN, UserRole.INSPECTOR]
