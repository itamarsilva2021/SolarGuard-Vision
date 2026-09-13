"""
Serviço de Aplicação para Gestão de Usuários, Autenticação e Controle de Acesso (RBAC).
"""

from datetime import datetime, timezone, timedelta
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
        must_change_password: bool = False,
    ) -> Result[User, str]:
        """
        Cadastra um novo usuário no sistema com hash criptográfico seguro Argon2id.
        """
        clean_username = username.strip().lower()
        if len(clean_username) < 3:
            return Failure("O nome de usuário deve ter pelo menos 3 caracteres.")
        if len(password) < 12:
            return Failure("A senha deve possuir no mínimo 12 caracteres.")

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
            must_change_password=must_change_password,
        )

        saved = self.user_repo.save(new_user)
        logger.info(f"Usuário criado com sucesso com Argon2id: {saved.username} ({saved.role.value})")
        return Success(saved)

    def authenticate(self, username: str, password: str) -> Result[User, str]:
        """
        Autentica credenciais de login com proteção contra força bruta (bloqueio progressivo),
        auditoria de segurança, rehash automático para Argon2id e atualização do último acesso.
        """
        now = datetime.now(timezone.utc)
        clean_username = username.strip().lower()
        user = self.user_repo.get_by_username(clean_username)

        if not user:
            logger.warning(
                f"[Auditoria de Segurança] Tentativa de login com usuário inexistente: '{clean_username}' "
                f"em {now.strftime('%Y-%m-%d %H:%M:%S UTC')}."
            )
            return Failure("Usuário ou senha inválidos.")

        if not user.is_active:
            logger.warning(
                f"[Auditoria de Segurança] Tentativa de login em conta inativa: '{user.username}' "
                f"em {now.strftime('%Y-%m-%d %H:%M:%S UTC')}."
            )
            return Failure("Esta conta de usuário está desativada. Contate o administrador.")

        # 1. Verificação de Bloqueio Temporário Ativo (ANTES de verificar a senha)
        user_locked_until = user.locked_until
        if user_locked_until is not None:
            if user_locked_until.tzinfo is None:
                user_locked_until = user_locked_until.replace(tzinfo=timezone.utc)
            if user_locked_until > now:
                remaining_seconds = max(1, int((user_locked_until - now).total_seconds()))
                if remaining_seconds >= 60:
                    remaining_min = (remaining_seconds + 59) // 60
                    msg = f"Conta bloqueada por tentativas excessivas. Tente novamente em {remaining_min} minuto(s)."
                else:
                    msg = f"Conta bloqueada por tentativas excessivas. Tente novamente em {remaining_seconds} segundo(s)."

                logger.warning(
                    f"[Auditoria de Segurança] Tentativa de login rejeitada para conta bloqueada: '{user.username}' "
                    f"em {now.strftime('%Y-%m-%d %H:%M:%S UTC')}. Tempo restante de bloqueio: {remaining_seconds}s."
                )
                return Failure(msg)
            else:
                # O período de bloqueio expirou: reseta as tentativas falhas para o novo ciclo de 5 tentativas
                user.locked_until = None
                user.failed_login_attempts = 0
                self.user_repo.save(user)

        # 2. Verificação de Senha (com contagem de falhas consecutivas)
        if not PasswordHasher.verify_password(password, user.password_hash, user.salt):
            user.failed_login_attempts += 1

            # Bloqueio progressivo acionado quando atinge 5 falhas no ciclo ativo
            if user.failed_login_attempts >= 5:
                user.lockout_count += 1
                if user.lockout_count == 1:
                    lockout_minutes = 5
                elif user.lockout_count == 2:
                    lockout_minutes = 15
                else:
                    lockout_minutes = 30

                user.locked_until = now + timedelta(minutes=lockout_minutes)
                self.user_repo.save(user)

                logger.warning(
                    f"[Auditoria de Segurança] Conta '{user.username}' BLOQUEADA temporariamente por {lockout_minutes} "
                    f"minutos após {user.failed_login_attempts} falhas consecutivas (bloqueio #{user.lockout_count}) em {now.strftime('%Y-%m-%d %H:%M:%S UTC')}."
                )
                return Failure(
                    f"Conta bloqueada por tentativas excessivas. Tente novamente em {lockout_minutes} minuto(s)."
                )

            self.user_repo.save(user)
            logger.warning(
                f"[Auditoria de Segurança] Tentativa de login com senha incorreta para '{user.username}' "
                f"em {now.strftime('%Y-%m-%d %H:%M:%S UTC')}. Falhas consecutivas no ciclo: {user.failed_login_attempts}/5."
            )
            return Failure("Usuário ou senha inválidos.")

        # 3. Login Bem-Sucedido: resetar contador de falhas, desbloqueio e histórico de escalada
        if user.failed_login_attempts > 0 or user.locked_until is not None or user.lockout_count > 0:
            user.failed_login_attempts = 0
            user.locked_until = None
            user.lockout_count = 0

        # Rehash automático para Argon2id caso o hash seja legado (PBKDF2)
        if PasswordHasher.needs_rehash(user.password_hash):
            new_hash, new_salt = PasswordHasher.hash_password(password)
            user.password_hash = new_hash
            user.salt = new_salt
            logger.info(f"Hash de senha do usuário '{user.username}' migrado com sucesso de PBKDF2 para Argon2id.")

        # Atualizar data do último login
        user.last_login = datetime.now()
        self.user_repo.save(user)

        logger.info(
            f"[Auditoria de Segurança] Login bem-sucedido para o usuário: '{user.username}' "
            f"em {now.strftime('%Y-%m-%d %H:%M:%S UTC')}."
        )
        return Success(user)

    def change_password(self, user_id: str, old_password: str, new_password: str) -> Result[bool, str]:
        """Altera a senha de um usuário existente mediante confirmação da senha anterior e reseta must_change_password."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return Failure("Usuário não encontrado.")

        if not PasswordHasher.verify_password(old_password, user.password_hash, user.salt):
            return Failure("Senha atual incorreta.")

        if len(new_password) < 12:
            return Failure("A nova senha deve possuir no mínimo 12 caracteres.")

        new_hash, new_salt = PasswordHasher.hash_password(new_password)
        user.password_hash = new_hash
        user.salt = new_salt
        user.must_change_password = False
        self.user_repo.save(user)

        # Se houver arquivo local de credenciais temporárias do admin, remove-o por segurança
        try:
            from pathlib import Path
            from src.core.config import settings
            candidates = [
                settings.data_dir / "admin_first_login.txt",
                Path("data/admin_first_login.txt"),
            ]
            for first_login_file in candidates:
                if first_login_file.exists():
                    first_login_file.unlink()
                    logger.info(f"Arquivo de credenciais temporárias '{first_login_file}' removido com sucesso.")
        except Exception as ex:
            logger.warning(f"Não foi possível remover admin_first_login.txt: {ex}")

        logger.info(f"Senha alterada com sucesso (Argon2id) para: {user.username}")
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
        default_password: Optional[str] = None,
        default_name: str = "Administrador do Sistema",
    ) -> User:
        """
        Garante a existência de ao menos um administrador para acesso inicial ao sistema.
        Se nenhum usuário existir no banco de dados:
        - Gera uma senha aleatória forte de no mínimo 16 caracteres caso nenhuma seja fornecida;
        - Marca o usuário criado com must_change_password = True;
        - Registra a senha de forma destacada no console e em settings.data_dir / 'admin_first_login.txt'.
        """
        import secrets
        from pathlib import Path
        from src.core.config import settings

        existing = self.user_repo.get_by_username(default_username)
        if existing:
            return existing

        all_users = self.user_repo.list_all()
        if all_users:
            # Já existem outros usuários cadastrados, não sobrescreve nem cria
            return all_users[0]

        # Gera senha aleatória forte e não previsível se não foi passada explicitamente
        is_generated = False
        if default_password is None:
            # Pelo menos 16 caracteres com alta entropia
            default_password = secrets.token_urlsafe(16) + "!A1"
            is_generated = True

        logger.info(f"Nenhum usuário encontrado no banco de dados. Criando administrador padrão '{default_username}'...")
        res = self.create_user(
            username=default_username,
            password=default_password,
            full_name=default_name,
            role=UserRole.ADMIN,
            email="admin@solarguard.vision",
            must_change_password=True,
        )
        if not res.is_success:
            raise RuntimeError(f"Falha ao criar usuário padrão inicial: {res.error}")

        user = res.value

        # Registra destacadamente no console e em arquivo seguro local no diretório de dados
        first_login_path = settings.data_dir / "admin_first_login.txt"
        notice = (
            "\n" + "=" * 70 + "\n"
            "[*] SOLARGUARD VISION - PRIMEIRO ACESSO DO ADMINISTRADOR\n"
            "=" * 70 + "\n"
            f"Usuario Criado:   {user.username}\n"
            f"Senha Temporaria: {default_password}\n\n"
            "[!] ATENCAO: Por politicas de seguranca, esta senha foi gerada de forma\n"
            "aleatoria e DEVE ser alterada imediatamente no primeiro login.\n"
            "Este arquivo sera removido automaticamente assim que a senha for trocada.\n"
            "=" * 70 + "\n"
        )
        try:
            print(notice)
        except Exception:
            pass

        try:
            first_login_path.parent.mkdir(parents=True, exist_ok=True)
            first_login_path.write_text(notice, encoding="utf-8")
            logger.info(f"Credenciais temporárias do administrador salvas em '{first_login_path}'.")
        except Exception as ex:
            logger.warning(f"Não foi possível salvar '{first_login_path}': {ex}")

        return user
