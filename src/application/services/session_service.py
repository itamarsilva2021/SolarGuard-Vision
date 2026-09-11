"""
Serviço de Controle e Gestão de Sessão do Usuário (SessionManager).
Gerencia o ciclo de vida do operador autenticado no SolarGuard Vision.
"""

from datetime import datetime
from typing import Optional, Callable, List

from src.core.result import Result, Success, Failure
from src.core.logger import get_logger
from src.domain.entities.user import User
from src.domain.enums.user_role import UserRole
from src.application.services.user_service import UserService

logger = get_logger("SessionManager")


class SessionManager:
    """
    Controlador central de sessão ativa de operador no sistema desktop.
    Fornece verificação de autenticação, retenção de identidade e guardas de segurança.
    """

    def __init__(self, user_service: UserService) -> None:
        self.user_service = user_service
        self._current_user: Optional[User] = None
        self._session_start: Optional[datetime] = None
        self._on_login_callbacks: List[Callable[[User], None]] = []
        self._on_logout_callbacks: List[Callable[[], None]] = []

    @property
    def current_user(self) -> Optional[User]:
        """Retorna o usuário atualmente autenticado ou None se deslogado."""
        return self._current_user

    @property
    def session_start(self) -> Optional[datetime]:
        """Retorna o timestamp de início da sessão atual."""
        return self._session_start

    def is_authenticated(self) -> bool:
        """Verifica se há uma sessão válida e ativa no momento."""
        return self._current_user is not None and self._current_user.is_active

    def login(self, username: str, password: str) -> Result[User, str]:
        """
        Executa a autenticação de credenciais e inicia a sessão ativa.
        """
        res = self.user_service.authenticate(username, password)
        if res.is_success:
            self._current_user = res.value
            self._session_start = datetime.now()
            logger.info(f"Sessão iniciada com sucesso para: {self._current_user.username} ({self._current_user.role.value})")
            
            # Notifica ouvintes registrados
            for callback in self._on_login_callbacks:
                try:
                    callback(self._current_user)
                except Exception as ex:
                    logger.error(f"Erro em callback de login: {ex}")

            return Success(self._current_user)
        
        return Failure(res.error)

    def logout(self) -> None:
        """
        Encerra a sessão atual, removendo o usuário ativo da memória.
        """
        if self._current_user:
            logger.info(f"Encerrando sessão do usuário: {self._current_user.username}")
        
        self._current_user = None
        self._session_start = None

        # Notifica ouvintes registrados
        for callback in self._on_logout_callbacks:
            try:
                callback()
            except Exception as ex:
                logger.error(f"Erro em callback de logout: {ex}")

    def require_authentication(self) -> Result[User, str]:
        """
        Guarda de proteção que bloqueia o acesso a rotinas se não houver usuário autenticado.
        """
        if not self.is_authenticated():
            return Failure("Acesso bloqueado: sessão não autenticada. Faça login para continuar.")
        return Success(self._current_user)

    def has_role(self, *roles: UserRole) -> bool:
        """Verifica se o usuário atual possui um dos papéis de acesso especificados."""
        if not self.is_authenticated() or not self._current_user:
            return False
        return self._current_user.role in roles

    def is_admin(self) -> bool:
        """Verifica se o usuário ativo é administrador do sistema."""
        return self.has_role(UserRole.ADMIN)

    def register_on_login(self, callback: Callable[[User], None]) -> None:
        """Registra callback acionado após login bem-sucedido."""
        self._on_login_callbacks.append(callback)

    def register_on_logout(self, callback: Callable[[], None]) -> None:
        """Registra callback acionado após encerramento da sessão."""
        self._on_logout_callbacks.append(callback)
