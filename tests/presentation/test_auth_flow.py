"""
Testes automatizados do fluxo de autenticação, tela de login, sessão e logout.
Valida o ciclo de vida do SessionManager, LoginDialog e integração com MainWindow.
"""

import os
import pytest
from pathlib import Path

# Configuração para execução gráfica headless (offscreen)
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from src.domain.entities.user import User
from src.domain.enums.user_role import UserRole
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories.sqlite_user_repository import SqliteUserRepository
from src.application.services.user_service import UserService
from src.application.services.session_service import SessionManager
from src.presentation.login_dialog import LoginDialog
from src.presentation.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Instância única de QApplication offscreen para os testes."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app


@pytest.fixture
def auth_setup(tmp_path):
    """Configura ambiente isolado de banco de dados e serviços de autenticação."""
    db_file = str(tmp_path / "auth_test.db")
    db = DatabaseManager(db_path=db_file)
    db.initialize_schema()

    user_repo = SqliteUserRepository(db)
    user_svc = UserService(user_repo)
    user_svc.ensure_default_admin(
        default_username="admin",
        default_password="adminpassword123",
        default_name="Administrador Principal",
    )

    # Cadastrar também um operador comum
    user_svc.create_user(
        username="operador_solar",
        password="op_password_456",
        full_name="Carlos Termografista",
        role=UserRole.INSPECTOR,
    )

    session_mgr = SessionManager(user_svc)
    return {
        "db": db,
        "user_repo": user_repo,
        "user_svc": user_svc,
        "session_mgr": session_mgr,
    }


# =============================================================================
# 1. TESTES DO SESSION MANAGER
# =============================================================================

def test_session_manager_initial_state(auth_setup):
    """Verifica que uma sessão recém-criada inicia desautenticada."""
    session_mgr: SessionManager = auth_setup["session_mgr"]

    assert session_mgr.is_authenticated() is False
    assert session_mgr.current_user is None
    assert session_mgr.session_start is None

    res_guard = session_mgr.require_authentication()
    assert res_guard.is_failure is True
    assert "Acesso bloqueado" in res_guard.error


def test_session_manager_successful_login_and_logout(auth_setup):
    """Valida login com sucesso, registro de sessão ativa e encerramento com logout."""
    session_mgr: SessionManager = auth_setup["session_mgr"]

    login_events = []
    logout_events = []
    session_mgr.register_on_login(lambda u: login_events.append(u.username))
    session_mgr.register_on_logout(lambda: logout_events.append(True))

    # Realizar login válido
    res = session_mgr.login("admin", "adminpassword123")
    assert res.is_success is True
    assert session_mgr.is_authenticated() is True
    assert session_mgr.current_user is not None
    assert session_mgr.current_user.username == "admin"
    assert session_mgr.is_admin() is True
    assert session_mgr.has_role(UserRole.ADMIN) is True
    assert session_mgr.session_start is not None
    assert len(login_events) == 1
    assert login_events[0] == "admin"

    # Verificar guarda de segurança
    assert session_mgr.require_authentication().is_success is True

    # Realizar logout
    session_mgr.logout()
    assert session_mgr.is_authenticated() is False
    assert session_mgr.current_user is None
    assert session_mgr.session_start is None
    assert len(logout_events) == 1


def test_session_manager_invalid_credentials_and_inactive_user(auth_setup):
    """Testa rejeição de credenciais inválidas e contas inativas."""
    session_mgr: SessionManager = auth_setup["session_mgr"]
    user_svc: UserService = auth_setup["user_svc"]
    user_repo: SqliteUserRepository = auth_setup["user_repo"]

    # Senha incorreta
    res_err_pwd = session_mgr.login("admin", "senha_errada_999")
    assert res_err_pwd.is_failure is True
    assert session_mgr.is_authenticated() is False

    # Usuário inexistente
    res_err_usr = session_mgr.login("usuario_inexistente", "qualquersenha")
    assert res_err_usr.is_failure is True
    assert session_mgr.is_authenticated() is False

    # Usuário inativo
    user_svc.create_user(
        username="bloqueado",
        password="password_segura123",
        full_name="Usuário Demitido",
        role=UserRole.VIEWER,
    )
    user = user_repo.get_by_username("bloqueado")
    user.is_active = False
    user_repo.save(user)

    res_inativo = session_mgr.login("bloqueado", "password_segura123")
    assert res_inativo.is_failure is True
    assert "desativada" in res_inativo.error
    assert session_mgr.is_authenticated() is False


# =============================================================================
# 2. TESTES DA TELA DE LOGIN (LOGIN DIALOG)
# =============================================================================

def test_login_dialog_validation_and_submission(qapp, auth_setup):
    """Testa o comportamento interativo da interface de login."""
    session_mgr: SessionManager = auth_setup["session_mgr"]
    dialog = LoginDialog(session_mgr)
    dialog.show()

    # 1. Submissão vazia deve exibir erro e não fechar
    dialog.username_input.setText("")
    dialog.password_input.setText("")
    dialog._attempt_login()
    assert not dialog.error_label.isHidden()
    assert "preencha o usuário e a senha" in dialog.error_label.text()
    assert session_mgr.is_authenticated() is False

    # 2. Submissão com senha errada deve exibir erro
    dialog.username_input.setText("admin")
    dialog.password_input.setText("senha_incorreta")
    dialog._attempt_login()
    assert not dialog.error_label.isHidden()
    assert "inválidos" in dialog.error_label.text()
    assert session_mgr.is_authenticated() is False

    # 3. Submissão com credenciais corretas deve autenticar com sucesso
    dialog.username_input.setText("operador_solar")
    dialog.password_input.setText("op_password_456")
    dialog._attempt_login()
    assert session_mgr.is_authenticated() is True
    assert session_mgr.current_user.username == "operador_solar"
    assert session_mgr.current_user.full_name == "Carlos Termografista"

    dialog.close()


def test_login_dialog_cancel(qapp, auth_setup):
    """Verifica que o cancelamento encerra o diálogo sem autenticar."""
    session_mgr: SessionManager = auth_setup["session_mgr"]
    session_mgr.logout()
    dialog = LoginDialog(session_mgr)
    dialog.show()

    dialog.cancel_btn.click()
    assert session_mgr.is_authenticated() is False
    dialog.close()


# =============================================================================
# 3. TESTES DE AUTENTICAÇÃO E LOGOUT NA MAIN WINDOW
# =============================================================================

def test_main_window_user_display_and_logout(qapp, auth_setup, monkeypatch):
    """Valida a exibição do usuário ativo e o fluxo de logout na MainWindow."""
    db = auth_setup["db"]
    session_mgr: SessionManager = auth_setup["session_mgr"]

    # Fazer login como operador
    session_mgr.login("operador_solar", "op_password_456")

    window = MainWindow(db=db, session_manager=session_mgr)

    # Verifica card de identificação na barra lateral
    assert "Carlos Termografista" in window.user_name_lbl.text()
    assert "Inspector" in window.user_role_lbl.text()
    assert window.logout_btn is not None

    # Simular confirmação afirmativa no diálogo de logout
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    # Mock do LoginDialog para não bloquear em headless
    from src.presentation.login_dialog import LoginDialog
    monkeypatch.setattr(LoginDialog, "exec", lambda self: QDialog.Rejected)

    # Acionar logout
    window.logout_btn.click()

    # Sessão deve estar encerrada
    assert session_mgr.is_authenticated() is False
    assert "Desconectado" in window.user_name_lbl.text()

    window.close()


def test_main_window_access_guard(qapp, auth_setup, monkeypatch):
    """Valida que páginas não são acessadas sem sessão ativa."""
    db = auth_setup["db"]
    session_mgr: SessionManager = auth_setup["session_mgr"]
    session_mgr.logout()

    from src.presentation.login_dialog import LoginDialog
    monkeypatch.setattr(LoginDialog, "exec", lambda self: QDialog.Rejected)

    window = MainWindow(db=db, session_manager=session_mgr)
    assert session_mgr.is_authenticated() is False

    # Tentativa de trocar de página sem autenticação
    window.switch_page(2)
    # Acesso deve ter sido interceptado e mantido desautenticado
    assert session_mgr.is_authenticated() is False

    window.close()
