"""
Testes automatizados de migração criptográfica de senhas para Argon2id (RFC 9106),
compatibilidade retroativa com hashes legados PBKDF2, rehash automático e política de senha mínima.
"""

import pytest
from src.infrastructure.security.password_hasher import PasswordHasher
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories.sqlite_user_repository import SqliteUserRepository
from src.application.services.user_service import UserService
from src.domain.entities.user import User
from src.domain.enums.user_role import UserRole


@pytest.fixture
def user_service_env(tmp_path):
    """Cria banco isolado e serviço de usuários para teste de autenticação."""
    db_path = str(tmp_path / "test_argon2id_users.db")
    db = DatabaseManager(db_path=db_path)
    db.initialize_schema()
    repo = SqliteUserRepository(db)
    service = UserService(repo)
    return {"db": db, "repo": repo, "service": service}


# =============================================================================
# 1. TESTES DO HASHER ARGON2ID
# =============================================================================

def test_argon2id_hash_and_verification():
    """Garante que novas senhas são hasheadas com Argon2id e verificadas corretamente."""
    password = "SenhaSegura@2026!"
    pwd_hash, salt = PasswordHasher.hash_password(password)

    # Deve conter o prefixo oficial do Argon2id
    assert pwd_hash.startswith("$argon2id$")
    assert len(salt) == 32  # 16 bytes em hexadecimais = 32 caracteres
    assert PasswordHasher.needs_rehash(pwd_hash) is False

    # Verificação positiva
    assert PasswordHasher.verify_password(password, pwd_hash, salt) is True

    # Rejeição com senha incorreta
    assert PasswordHasher.verify_password("SenhaIncorreta@2026!", pwd_hash, salt) is False


def test_argon2id_unique_salts():
    """Garante que hashes consecutivos para a mesma senha gerem salts e saídas distintas."""
    password = "ChaveComplexa#999"
    hash1, salt1 = PasswordHasher.hash_password(password)
    hash2, salt2 = PasswordHasher.hash_password(password)

    assert salt1 != salt2
    assert hash1 != hash2
    assert PasswordHasher.verify_password(password, hash1, salt1) is True
    assert PasswordHasher.verify_password(password, hash2, salt2) is True


# =============================================================================
# 2. COMPATIBILIDADE RETROATIVA COM PBKDF2
# =============================================================================

def test_legacy_pbkdf2_compatibility():
    """Valida que hashes antigos no formato PBKDF2 continuam sendo reconhecidos e validados."""
    password = "AntigaSenhaLegada_2025"
    legacy_hash, salt = PasswordHasher.hash_legacy_pbkdf2(password)

    # Não deve possuir o prefixo do Argon2id
    assert not legacy_hash.startswith("$argon2id$")
    assert PasswordHasher.needs_rehash(legacy_hash) is True

    # Validação retrocompatível da senha correta
    assert PasswordHasher.verify_password(password, legacy_hash, salt) is True

    # Rejeição com senha incorreta
    assert PasswordHasher.verify_password("SenhaErrada", legacy_hash, salt) is False


# =============================================================================
# 3. FLUXO COMPLETO: REHASH AUTOMÁTICO TRANSPARENTE NO LOGIN
# =============================================================================

def test_automatic_rehash_from_pbkdf2_to_argon2id_on_login(user_service_env):
    """
    Testa que uma conta existente com hash PBKDF2 legado é automaticamente
    promovida para Argon2id no momento em que efetua login com sucesso.
    """
    repo: SqliteUserRepository = user_service_env["repo"]
    service: UserService = user_service_env["service"]

    # 1. Simular usuário legado cadastrado previamente com PBKDF2
    username = "engenheiro_antigo"
    plain_password = "MinhaSenhaDeAcesso@2025"
    legacy_hash, legacy_salt = PasswordHasher.hash_legacy_pbkdf2(plain_password)

    legacy_user = User(
        username=username,
        password_hash=legacy_hash,
        salt=legacy_salt,
        full_name="Dr. João Legado",
        role=UserRole.INSPECTOR,
    )
    repo.save(legacy_user)

    # Confirmar que está no banco com PBKDF2
    stored_before = repo.get_by_username(username)
    assert stored_before is not None
    assert stored_before.password_hash == legacy_hash
    assert PasswordHasher.needs_rehash(stored_before.password_hash) is True

    # 2. Executar login com a senha correta
    auth_res = service.authenticate(username, plain_password)
    assert auth_res.is_success is True
    authenticated_user = auth_res.value
    assert authenticated_user.username == username

    # 3. Verificar que o hash no banco de dados foi promovido automaticamente para Argon2id
    stored_after = repo.get_by_username(username)
    assert stored_after is not None
    assert stored_after.password_hash.startswith("$argon2id$")
    assert PasswordHasher.needs_rehash(stored_after.password_hash) is False
    assert stored_after.password_hash != legacy_hash

    # 4. Segundo login: autentica diretamente contra o novo hash Argon2id
    auth_res_2 = service.authenticate(username, plain_password)
    assert auth_res_2.is_success is True
    assert auth_res_2.value.password_hash.startswith("$argon2id$")


def test_failed_login_does_not_rehash(user_service_env):
    """Tentativa de login com senha incorreta em conta legada não altera o hash."""
    repo: SqliteUserRepository = user_service_env["repo"]
    service: UserService = user_service_env["service"]

    username = "usuario_alvo"
    plain_password = "SenhaGenuina@2025"
    legacy_hash, legacy_salt = PasswordHasher.hash_legacy_pbkdf2(plain_password)

    repo.save(User(
        username=username,
        password_hash=legacy_hash,
        salt=legacy_salt,
        full_name="Inspetor Alvo",
    ))

    # Tenta autenticar com senha errada
    fail_res = service.authenticate(username, "SenhaErradaTotalmente123")
    assert fail_res.is_failure is True

    # O hash no banco permanece o legado
    stored = repo.get_by_username(username)
    assert stored.password_hash == legacy_hash


# =============================================================================
# 4. POLÍTICA DE SENHA MÍNIMA (12 CARACTERES)
# =============================================================================

def test_minimum_password_length_policy_on_creation(user_service_env):
    """Rejeita senhas com menos de 12 caracteres na criação de usuário."""
    service: UserService = user_service_env["service"]

    # Tentativa com 11 caracteres -> Falha
    res_11 = service.create_user(
        username="novo_usuario_11",
        password="Senha11char",  # 11 chars
        full_name="Teste 11 Chars",
    )
    assert res_11.is_failure is True
    assert "12 caracteres" in res_11.error

    # Tentativa com 12 caracteres -> Sucesso
    res_12 = service.create_user(
        username="novo_usuario_12",
        password="Senha12chars",  # 12 chars
        full_name="Teste 12 Chars",
    )
    assert res_12.is_success is True
    assert res_12.value.password_hash.startswith("$argon2id$")


def test_minimum_password_length_policy_on_change(user_service_env):
    """Rejeita senhas com menos de 12 caracteres na alteração de senha."""
    service: UserService = user_service_env["service"]

    # Cria usuário com senha válida (>= 12 chars)
    create_res = service.create_user(
        username="troca_senha_user",
        password="SenhaInicialForte@123",
        full_name="Operador Troca Senha",
    )
    assert create_res.is_success is True
    user_id = create_res.value.id

    # Tenta alterar para senha curta de 8 caracteres -> Falha
    change_short = service.change_password(user_id, "SenhaInicialForte@123", "curta123")
    assert change_short.is_failure is True
    assert "12 caracteres" in change_short.error

    # Altera para nova senha forte (>= 12 caracteres) -> Sucesso
    change_ok = service.change_password(user_id, "SenhaInicialForte@123", "NovaSenhaSuperForte@2026")
    assert change_ok.is_success is True

    # Login com a nova senha funciona perfeitamente
    login_res = service.authenticate("troca_senha_user", "NovaSenhaSuperForte@2026")
    assert login_res.is_success is True
