"""
Serviço de Aplicação para Gestão de Usuários, Autenticação e Controle de Acesso (RBAC).
"""

from datetime import datetime
from typing import Optional, List

from src.core.result import Result, Success, Failure
from src.core.logger import get_logger
from src.domain.entities.user import User
from src.domain.enums.user_role import UserRole
from src.domain.interfaces.repositories import IUserRepository
from src.infrastructure.security.password_hasher import PasswordHasher

logger = get_logger("UserService")


class UserService:
    """
    Serviço central de controle de acesso, criação de contas e autenticação de operadores.
    """

    def __init__(self, user_repository: IUserRepository) -> None:
        self.user_repo = user_repository

    def create_user(
        self,
        username: str,
        password: str,
        full_name: str,
        role: UserRole = UserRole.INSPECTOR,
        email: Optional[str] = None,
    ) -> Result[User, str]:
        """
        Cadastra um novo usuário no sistema com hash criptográfico seguro PBKDF2.
        """
        clean_username = username.strip().lower()
        if len(clean_username) < 3:
            return Failure("O nome de usuário deve ter pelo menos 3 caracteres.")
        if len(password) < 6:
            return Failure("A senha deve possuir no mínimo 6 caracteres.")

        # Verificar se usuário já existe
        existing = self.user_repo.get_by_username(clean_username)
        if existing:
            return Failure(f"O nome de usuário '{clean_username}' já está em uso.")

        pwd_hash, salt = PasswordHasher.hash_password(password)

        new_user = User(
            username=clean_username,
            password_hash=pwd_hash,
            salt=salt,
            full_name=full_name.strip(),
            role=role,
            email=email.strip() if email else None,
            is_active=True,
        )

        saved = self.user_repo.save(new_user)
        logger.info(f"Usuário criado com sucesso: {saved.username} ({saved.role.value})")
        return Success(saved)

    def authenticate(self, username: str, password: str) -> Result[User, str]:
        """
        Autentica credenciais de login e atualiza data do último acesso.
        """
        clean_username = username.strip().lower()
        user = self.user_repo.get_by_username(clean_username)

        if not user:
            return Failure("Usuário ou senha inválidos.")

        if not user.is_active:
            return Failure("Esta conta de usuário está desativada. Contate o administrador.")

        if not PasswordHasher.verify_password(password, user.password_hash, user.salt):
            return Failure("Usuário ou senha inválidos.")

        # Atualizar data do último login
        user.last_login = datetime.now()
        self.user_repo.save(user)

        logger.info(f"Login bem-sucedido para o usuário: {user.username}")
        return Success(user)

    def change_password(self, user_id: str, old_password: str, new_password: str) -> Result[bool, str]:
        """Altera a senha de um usuário existente mediante confirmação da senha anterior."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return Failure("Usuário não encontrado.")

        if not PasswordHasher.verify_password(old_password, user.password_hash, user.salt):
            return Failure("Senha atual incorreta.")

        if len(new_password) < 6:
            return Failure("A nova senha deve ter pelo menos 6 caracteres.")

        new_hash, new_salt = PasswordHasher.hash_password(new_password)
        user.password_hash = new_hash
        user.salt = new_salt
        self.user_repo.save(user)

        logger.info(f"Senha alterada com sucesso para: {user.username}")
        return Success(True)

    def list_users(self) -> List[User]:
        """Lista todos os operadores e administradores cadastrados."""
        return self.user_repo.list_all()

    def delete_user(self, user_id: str) -> bool:
        """Remove o cadastro de um usuário."""
        return self.user_repo.delete(user_id)

    def ensure_default_admin(
        self,
        default_username: str = "admin",
        default_password: str = "admin123",
        default_name: str = "Administrador do Sistema",
    ) -> User:
        """
        Garante a existência de ao menos um administrador para acesso inicial ao sistema.
        Se nenhum usuário existir no banco de dados, cria o usuário padrão com hash PBKDF2 seguro.
        """
        existing = self.user_repo.get_by_username(default_username)
        if existing:
            return existing

        all_users = self.user_repo.list_all()
        if all_users:
            # Já existem outros usuários cadastrados, não sobrescreve nem cria
            return all_users[0]

        logger.info(f"Nenhum usuário encontrado no banco de dados. Criando administrador padrão '{default_username}'...")
        res = self.create_user(
            username=default_username,
            password=default_password,
            full_name=default_name,
            role=UserRole.ADMIN,
            email="admin@solarguard.vision",
        )
        if res.is_success:
            return res.value
        raise RuntimeError(f"Falha ao criar usuário padrão inicial: {res.error}")
