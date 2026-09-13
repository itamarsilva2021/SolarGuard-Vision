"""
Testes dedicados de segurança e gestão de usuários:
1. Geração de senha aleatória forte e não previsível no primeiro acesso (ensure_default_admin).
2. Marcação e persistência do campo must_change_password.
3. Fluxo de troca obrigatória de senha e reset para must_change_password=False.
4. Diálogo modal ForcePasswordChangeDialog e guarda no LoginDialog.
"""

import os
import pytest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QDialog
from src.domain.enums.user_role import UserRole
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories.sqlite_user_repository import SqliteUserRepository
from src.application.services.user_service import UserService
from src.application.services.session_service import SessionManager
from src.presentation.force_password_change_dialog import ForcePasswordChangeDialog
from src.presentation.login_dialog import LoginDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app


@pytest.fixture
def user_test_env(tmp_path: Path):
    db_file = tmp_path / "user_sec_test.sqlite3"
    db = DatabaseManager(str(db_file))
    db.initialize_schema()
    repo = SqliteUserRepository(db)
    svc = UserService(repo)
    session_mgr = SessionManager(svc)
    return {
        "db": db,
        "repo": repo,
        "svc": svc,
        "session_mgr": session_mgr,
        "tmp_path": tmp_path,
    }


def test_ensure_default_admin_generates_random_strong_password_and_flags_must_change(user_test_env):
    """
    (a) Valida que a senha do admin padrão não é fixa/previsível e possui alta entropia,
    marcando must_change_password=True.
    """
    svc: UserService = user_test_env["svc"]
    repo: SqliteUserRepository = user_test_env["repo"]

    # Criação do primeiro admin sem senha explícita
    admin1 = svc.ensure_default_admin()
    assert admin1.username == "admin"
    assert admin1.must_change_password is True
    assert admin1.role == UserRole.ADMIN

    # Valida persistência no banco
    admin_from_db = repo.get_by_username("admin")
    assert admin_from_db is not None
    assert admin_from_db.must_change_password is True

    # Verifica se o arquivo temporário foi gerado no diretório de dados configurado
    from src.core.config import settings
    first_login_file = settings.data_dir / "admin_first_login.txt"
    if not first_login_file.exists():
        first_login_file = Path("data/admin_first_login.txt")
    assert first_login_file.exists()
    content = first_login_file.read_text(encoding="utf-8")
    assert "Usuario Criado:   admin" in content
    assert "Senha Temporaria:" in content

    # Garante que a senha gerada tem pelo menos 16 caracteres
    lines = content.splitlines()
    pwd_line = [line for line in lines if "Senha Temporaria:" in line][0]
    generated_pwd = pwd_line.split("Senha Temporaria:")[1].strip()
    assert len(generated_pwd) >= 16

    # Garante que NÃO é a senha antiga fixa
    assert generated_pwd != "Admin@SolarGuard2026!"

    # Limpeza do arquivo de teste
    if first_login_file.exists():
        first_login_file.unlink()


def test_change_password_resets_must_change_password_flag(user_test_env):
    """
    (c) Valida que após UserService.change_password(), must_change_password vira False.
    """
    svc: UserService = user_test_env["svc"]
    repo: SqliteUserRepository = user_test_env["repo"]

    # Criar usuário com must_change_password=True
    create_res = svc.create_user(
        username="operador_novo",
        password="SenhaTemporaria@123",
        full_name="Operador Novo",
        role=UserRole.INSPECTOR,
        must_change_password=True,
    )
    assert create_res.is_success is True
    user = create_res.value
    assert user.must_change_password is True

    # Realizar a troca de senha
    change_res = svc.change_password(
        user_id=user.id,
        old_password="SenhaTemporaria@123",
        new_password="NovaSenhaSegura@2026",
    )
    assert change_res.is_success is True

    # Verificar entidade e banco
    reloaded = repo.get_by_id(user.id)
    assert reloaded is not None
    assert reloaded.must_change_password is False

    # Autenticar com a nova senha
    auth_res = svc.authenticate("operador_novo", "NovaSenhaSegura@2026")
    assert auth_res.is_success is True
    assert auth_res.value.must_change_password is False


def test_force_password_change_dialog_flow(qapp, user_test_env):
    """
    Testa o diálogo ForcePasswordChangeDialog diretamente:
    validação de campos, regras de tamanho e confirmação.
    """
    svc: UserService = user_test_env["svc"]
    create_res = svc.create_user(
        username="user_dialog_test",
        password="SenhaAtual@12345",
        full_name="Usuário Diálogo",
        must_change_password=True,
    )
    user = create_res.value

    dialog = ForcePasswordChangeDialog(
        user=user,
        user_service=svc,
        preset_current_password="SenhaAtual@12345",
    )
    dialog.show()

    # 1. Senha curta (< 12)
    dialog.new_password_input.setText("curta123")
    dialog.confirm_password_input.setText("curta123")
    dialog._attempt_change_password()
    assert not dialog.error_label.isHidden()
    assert "12 caracteres" in dialog.error_label.text()
    assert user.must_change_password is True

    # 2. Confirmação divergente
    dialog.new_password_input.setText("NovaSenhaForte@2026")
    dialog.confirm_password_input.setText("OutraSenhaDiferente@2026")
    dialog._attempt_change_password()
    assert not dialog.error_label.isHidden()
    assert "não coincidem" in dialog.error_label.text()

    # 3. Senha igual à atual
    dialog.new_password_input.setText("SenhaAtual@12345")
    dialog.confirm_password_input.setText("SenhaAtual@12345")
    dialog._attempt_change_password()
    assert not dialog.error_label.isHidden()
    assert "não pode ser idêntica" in dialog.error_label.text()

    # 4. Troca válida com sucesso
    dialog.new_password_input.setText("NovaSenhaForte@2026")
    dialog.confirm_password_input.setText("NovaSenhaForte@2026")
    dialog._attempt_change_password()
    assert user.must_change_password is False

    dialog.close()


def test_login_dialog_intercepts_must_change_password(qapp, user_test_env, monkeypatch):
    """
    (b) Valida que o fluxo de login intercepta o usuário quando must_change_password é True,
    forçando o diálogo de alteração antes de aceitar.
    """
    svc: UserService = user_test_env["svc"]
    session_mgr: SessionManager = user_test_env["session_mgr"]

    create_res = svc.create_user(
        username="usuario_expirado",
        password="SenhaInicial@123",
        full_name="Operador Expirado",
        must_change_password=True,
    )
    assert create_res.is_success is True

    # Caso 1: Usuário cancela o diálogo de troca -> Login é rejeitado e sessão deslogada
    monkeypatch.setattr(ForcePasswordChangeDialog, "exec", lambda self: QDialog.Rejected)

    login_dlg = LoginDialog(session_mgr)
    login_dlg.username_input.setText("usuario_expirado")
    login_dlg.password_input.setText("SenhaInicial@123")
    login_dlg._attempt_login()

    assert session_mgr.is_authenticated() is False
    assert not login_dlg.error_label.isHidden()
    assert "obrigatória" in login_dlg.error_label.text()
    login_dlg.close()

    # Caso 2: Usuário aceita e troca a senha no diálogo -> Login é aceito
    def mock_accept_and_change(self):
        # Simula sucesso da troca no ForcePasswordChangeDialog
        res = svc.change_password(self.user.id, "SenhaInicial@123", "NovaSenhaPerfeita@2026")
        assert res.is_success is True
        self.user.must_change_password = False
        return QDialog.Accepted

    monkeypatch.setattr(ForcePasswordChangeDialog, "exec", mock_accept_and_change)

    login_dlg2 = LoginDialog(session_mgr)
    login_dlg2.username_input.setText("usuario_expirado")
    login_dlg2.password_input.setText("SenhaInicial@123")
    login_dlg2._attempt_login()

    assert session_mgr.is_authenticated() is True
    assert session_mgr.current_user.username == "usuario_expirado"
    assert session_mgr.current_user.must_change_password is False
    login_dlg2.close()


def test_brute_force_lockout_after_five_failed_attempts(user_test_env):
    """
    Valida o bloqueio exato após 5 falhas consecutivas de senha com bloqueio inicial de 5 minutos,
    mantendo mensagem genérica antes do bloqueio.
    """
    svc: UserService = user_test_env["svc"]
    repo: SqliteUserRepository = user_test_env["repo"]

    create_res = svc.create_user(
        username="vitima_brute_force",
        password="SenhaCorreta@2026",
        full_name="Usuário Teste Bloqueio",
    )
    assert create_res.is_success is True

    # 4 tentativas incorretas consecutivas
    for i in range(1, 5):
        res = svc.authenticate("vitima_brute_force", "SenhaIncorreta@123")
        assert res.is_success is False
        assert "Usuário ou senha inválidos" in res.error
        u = repo.get_by_username("vitima_brute_force")
        assert u.failed_login_attempts == i
        assert u.locked_until is None

    # 5ª tentativa incorreta: aciona o bloqueio temporário
    res5 = svc.authenticate("vitima_brute_force", "SenhaIncorreta@123")
    assert res5.is_success is False
    assert "Conta bloqueada por tentativas excessivas" in res5.error
    assert "5 minuto(s)" in res5.error

    u5 = repo.get_by_username("vitima_brute_force")
    assert u5.failed_login_attempts == 5
    assert u5.locked_until is not None


def test_lockout_prevents_password_check_while_active(user_test_env, monkeypatch):
    """
    Valida que com a conta bloqueada, a senha sequer é verificada (SEM cálculo criptográfico)
    e o contador de falhas NÃO é incrementado.
    """
    from datetime import datetime, timezone, timedelta
    from src.infrastructure.security.password_hasher import PasswordHasher

    svc: UserService = user_test_env["svc"]
    repo: SqliteUserRepository = user_test_env["repo"]

    create_res = svc.create_user(
        username="usuario_bloqueado",
        password="SenhaCorreta@2026",
        full_name="Usuário Bloqueado",
    )
    user = create_res.value
    user.failed_login_attempts = 5
    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=4, seconds=45)
    repo.save(user)

    # Garante que verify_password NÃO será invocado
    def explode_if_called(*args, **kwargs):
        raise AssertionError("PasswordHasher.verify_password não deveria ter sido chamado durante bloqueio!")

    monkeypatch.setattr(PasswordHasher, "verify_password", explode_if_called)

    # Tenta autenticar mesmo com a senha correta
    res = svc.authenticate("usuario_bloqueado", "SenhaCorreta@2026")
    assert res.is_success is False
    assert "Conta bloqueada por tentativas excessivas" in res.error
    assert "5 minuto(s)" in res.error  # Arredondado para 5 min

    # O contador não pode ter sido incrementado
    u_reloaded = repo.get_by_username("usuario_bloqueado")
    assert u_reloaded.failed_login_attempts == 5


def test_successful_login_resets_failed_attempts_and_lockout(user_test_env):
    """
    Valida que ao realizar login com sucesso, o contador de falhas e o locked_until são zerados.
    """
    svc: UserService = user_test_env["svc"]
    repo: SqliteUserRepository = user_test_env["repo"]

    create_res = svc.create_user(
        username="operador_resiliente",
        password="SenhaForteValida@2026",
        full_name="Operador Resiliente",
    )
    assert create_res.is_success is True

    # Comete 3 falhas
    for _ in range(3):
        svc.authenticate("operador_resiliente", "SenhaErrada")

    u_before = repo.get_by_username("operador_resiliente")
    assert u_before.failed_login_attempts == 3

    # Agora acerta a senha
    auth_ok = svc.authenticate("operador_resiliente", "SenhaForteValida@2026")
    assert auth_ok.is_success is True

    u_after = repo.get_by_username("operador_resiliente")
    assert u_after.failed_login_attempts == 0
    assert u_after.locked_until is None


def test_progressive_lockout_escalation(user_test_env):
    """
    Valida a progressão temporal de bloqueio em falhas repetidas:
    5 falhas -> 5 min; 10 falhas -> 15 min; 15 falhas -> 30 min (teto).
    """
    from datetime import datetime, timezone, timedelta

    svc: UserService = user_test_env["svc"]
    repo: SqliteUserRepository = user_test_env["repo"]

    svc.create_user(
        username="alvo_progressao",
        password="SenhaOriginal@2026",
        full_name="Alvo Progressão",
    )

    # 1º Ciclo: 5 falhas consecutivas -> Bloqueio de 5 min
    for _ in range(4):
        svc.authenticate("alvo_progressao", "Errada")
    res5 = svc.authenticate("alvo_progressao", "Errada")
    assert "5 minuto(s)" in res5.error

    # Simula expiração do 1º bloqueio
    u = repo.get_by_username("alvo_progressao")
    u.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    repo.save(u)

    # 2º Ciclo: mais 4 falhas (total 9) -> mensagem genérica
    for _ in range(4):
        res = svc.authenticate("alvo_progressao", "Errada")
        assert "Usuário ou senha inválidos" in res.error

    # 10ª falha: aciona 2º bloqueio -> 15 minutos!
    res10 = svc.authenticate("alvo_progressao", "Errada")
    assert "15 minuto(s)" in res10.error

    # Simula expiração do 2º bloqueio
    u = repo.get_by_username("alvo_progressao")
    u.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    repo.save(u)

    # 3º Ciclo: mais 4 falhas (total 14) -> mensagem genérica
    for _ in range(4):
        svc.authenticate("alvo_progressao", "Errada")

    # 15ª falha: aciona 3º bloqueio -> 30 minutos (teto)!
    res15 = svc.authenticate("alvo_progressao", "Errada")
    assert "30 minuto(s)" in res15.error

    # Simula expiração do 3º bloqueio e mais 5 falhas (total 20) -> continua mantendo 30 min como teto
    u = repo.get_by_username("alvo_progressao")
    u.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    repo.save(u)
    for _ in range(4):
        svc.authenticate("alvo_progressao", "Errada")
    res20 = svc.authenticate("alvo_progressao", "Errada")
    assert "30 minuto(s)" in res20.error


def test_login_dialog_displays_lockout_message_clearly(qapp, user_test_env):
    """
    Valida que o LoginDialog exibe de forma clara ao usuário a mensagem de bloqueio
    com tempo restante, sem revelar detalhes nas falhas normais pré-bloqueio.
    """
    svc: UserService = user_test_env["svc"]
    session_mgr: SessionManager = user_test_env["session_mgr"]

    svc.create_user(
        username="operador_gui_lockout",
        password="SenhaCorreta@2026",
        full_name="Operador GUI Lockout",
    )

    login_dlg = LoginDialog(session_mgr)
    login_dlg.username_input.setText("operador_gui_lockout")

    # Tentativa 1 com senha incorreta
    login_dlg.password_input.setText("SenhaErrada1")
    login_dlg._attempt_login()
    assert not login_dlg.error_label.isHidden()
    assert "Usuário ou senha inválidos" in login_dlg.error_label.text()

    # Tentativas 2, 3 e 4
    for _ in range(3):
        login_dlg.password_input.setText("SenhaErrada")
        login_dlg._attempt_login()

    # Tentativa 5: aciona bloqueio e diálogo exibe aviso com minutos
    login_dlg.password_input.setText("SenhaErrada5")
    login_dlg._attempt_login()
    assert not login_dlg.error_label.isHidden()
    assert "Conta bloqueada por tentativas excessivas" in login_dlg.error_label.text()
    assert "5 minuto(s)" in login_dlg.error_label.text()

    login_dlg.close()


def test_lockout_and_must_change_password_interaction(qapp, user_test_env, monkeypatch):
    """
    Valida a interação completa entre bloqueio por força bruta e o fluxo must_change_password:
    1. Usuário com must_change_password=True erra 5 vezes seguidas -> bloqueado normalmente.
    2. Enquanto locked_until está no futuro, a tela de troca de senha NUNCA aparece (nem com senha errada nem com a correta).
    3. Fora da janela de bloqueio, ao acertar a senha correta, o diálogo de troca obrigatória aparece normalmente.
    4. Após a troca, login é concluído normalmente como se o bloqueio nunca tivesse acontecido.
    """
    from datetime import datetime, timezone, timedelta

    svc: UserService = user_test_env["svc"]
    repo: SqliteUserRepository = user_test_env["repo"]
    session_mgr: SessionManager = user_test_env["session_mgr"]

    # 1. Cria usuário com must_change_password=True
    create_res = svc.create_user(
        username="operador_expirado_lockout",
        password="SenhaInicialForte@123",
        full_name="Operador Expirado Lockout",
        must_change_password=True,
    )
    assert create_res.is_success is True

    # Rastreia qualquer abertura do ForcePasswordChangeDialog
    dialog_open_events = []

    def spy_force_dialog_exec(self):
        dialog_open_events.append(self)
        # Executa a troca de senha como ocorreria no diálogo
        res = svc.change_password(self.user.id, "SenhaInicialForte@123", "NovaSenhaDefinitiva@2026")
        assert res.is_success is True
        self.user.must_change_password = False
        return QDialog.Accepted

    monkeypatch.setattr(ForcePasswordChangeDialog, "exec", spy_force_dialog_exec)

    login_dlg = LoginDialog(session_mgr)
    login_dlg.username_input.setText("operador_expirado_lockout")

    # 4 erros consecutivos de senha
    for i in range(1, 5):
        login_dlg.password_input.setText(f"SenhaErrada_{i}")
        login_dlg._attempt_login()
        assert session_mgr.is_authenticated() is False
        assert "Usuário ou senha inválidos" in login_dlg.error_label.text()
        assert len(dialog_open_events) == 0, "ForcePasswordChangeDialog não pode abrir durante falha de senha!"

    # 5ª falha: aciona o bloqueio temporário por 5 minutos
    login_dlg.password_input.setText("SenhaErrada_5")
    login_dlg._attempt_login()
    assert session_mgr.is_authenticated() is False
    assert "Conta bloqueada por tentativas excessivas" in login_dlg.error_label.text()
    assert "5 minuto(s)" in login_dlg.error_label.text()
    assert len(dialog_open_events) == 0, "ForcePasswordChangeDialog não pode abrir ao ser bloqueado!"

    # 2. Confirma que enquanto locked_until está no futuro, o diálogo de troca NUNCA aparece
    # Testando com senha incorreta
    login_dlg.password_input.setText("OutraSenhaErrada")
    login_dlg._attempt_login()
    assert session_mgr.is_authenticated() is False
    assert "Conta bloqueada por tentativas excessivas" in login_dlg.error_label.text()
    assert len(dialog_open_events) == 0

    # Testando com a senha CORRETA durante o bloqueio ativo
    login_dlg.password_input.setText("SenhaInicialForte@123")
    login_dlg._attempt_login()
    assert session_mgr.is_authenticated() is False
    assert "Conta bloqueada por tentativas excessivas" in login_dlg.error_label.text()
    assert len(dialog_open_events) == 0, "ForcePasswordChangeDialog JAMAIS pode abrir enquanto locked_until estiver ativo no futuro!"

    # 3. Fora da janela de bloqueio: simula tempo expirado
    u = repo.get_by_username("operador_expirado_lockout")
    u.locked_until = datetime.now(timezone.utc) - timedelta(seconds=2)
    repo.save(u)

    # 4. Usuário agora digita a senha correta pós-desbloqueio
    login_dlg.password_input.setText("SenhaInicialForte@123")
    login_dlg._attempt_login()

    # O diálogo de troca de senha obrigatória DEVE ter sido acionado exatamente agora
    assert len(dialog_open_events) == 1, "ForcePasswordChangeDialog deve abrir normalmente quando a senha correta é informada pós-bloqueio!"
    assert session_mgr.is_authenticated() is True
    assert session_mgr.current_user.username == "operador_expirado_lockout"
    assert session_mgr.current_user.must_change_password is False

    # Valida persistência final no banco
    u_final = repo.get_by_username("operador_expirado_lockout")
    assert u_final.failed_login_attempts == 0
    assert u_final.locked_until is None
    assert u_final.lockout_count == 0
    assert u_final.must_change_password is False

    login_dlg.close()


