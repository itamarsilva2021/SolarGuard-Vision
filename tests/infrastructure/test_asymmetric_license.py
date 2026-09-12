"""
Testes automatizados da Arquitetura de Licenciamento Assimétrico Ed25519 (RFC 8032).
Valida emissão no Servidor, verificação no Cliente, proibição de keygen local e bloqueio estrito.
"""

import os
import pytest
from pathlib import Path
from datetime import datetime, timedelta

# Configuração headless para Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from src.infrastructure.security.license_manager import LicenseManager, LicenseType, LicenseInfo, DEFAULT_PUBLIC_KEY_B64
from server_tools.license_issuer import LicenseIssuer
from src.presentation.license_dialog import LicenseActivationDialog


@pytest.fixture(scope="session")
def qapp():
    """Garante instância única do QApplication para testes de apresentação offscreen."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app


@pytest.fixture
def license_env(tmp_path):
    """Configura ambiente isolado com emissor do servidor e validador do cliente."""
    issuer = LicenseIssuer()
    lic_file = tmp_path / "test_license.key"
    client_mgr = LicenseManager(license_file=lic_file)
    return {
        "issuer": issuer,
        "client_mgr": client_mgr,
        "lic_file": lic_file,
    }


# =============================================================================
# 1. EMISSÃO NO SERVIDOR & VALIDAÇÃO NO CLIENTE
# =============================================================================

def test_asymmetric_issue_and_verify(license_env):
    """Valida emissão com chave privada (Servidor) e validação com chave pública (Cliente)."""
    issuer: LicenseIssuer = license_env["issuer"]
    client_mgr: LicenseManager = license_env["client_mgr"]

    hwid = client_mgr.get_current_machine_fingerprint()
    token = issuer.issue_license(
        client_name="Usina Fotovoltaica Sobradinho",
        license_type=LicenseType.ENTERPRISE,
        machine_fingerprint=hwid,
        days_valid=180,
        max_plants=50,
    )

    assert "." in token
    parts = token.split(".")
    assert len(parts) == 2

    # Salva e valida no cliente
    info = client_mgr.save_license(token)
    assert info.is_valid is True
    assert info.client_name == "Usina Fotovoltaica Sobradinho"
    assert info.license_type == LicenseType.ENTERPRISE
    assert info.machine_fingerprint == hwid
    assert info.days_remaining is not None
    assert 170 <= info.days_remaining <= 180
    assert "válida" in info.status_message.lower()


def test_prohibition_of_local_license_generation():
    """Garante que a classe do Cliente NÃO possui capacidade de gerar licenças locais."""
    # O cliente não deve ter o método de geração nem chave privada / sal simétrico
    assert not hasattr(LicenseManager, "generate_license_key")
    assert not hasattr(LicenseManager, "_SECRET_SALT")
    assert not hasattr(LicenseManager, "_private_key")


# =============================================================================
# 2. SEGURANÇA CRIPTOGRÁFICA ED25519 & PROTEÇÃO ANTI-ADULTERAÇÃO
# =============================================================================

def test_tampered_signature_rejected(license_env):
    """Garante que qualquer alteração na assinatura digital Ed25519 invalide a licença."""
    issuer: LicenseIssuer = license_env["issuer"]
    client_mgr: LicenseManager = license_env["client_mgr"]

    hwid = client_mgr.get_current_machine_fingerprint()
    token = issuer.issue_license("Cliente X", LicenseType.PROFESSIONAL, hwid)
    payload_b64, sig_b64 = token.split(".")

    # Forja os últimos caracteres da assinatura
    tampered_sig = sig_b64[:-6] + "AAAAAA"
    tampered_token = f"{payload_b64}.{tampered_sig}"

    info = client_mgr.validate_license_key(tampered_token)
    assert info.is_valid is False
    assert "inválida ou forjada" in info.status_message.lower()


def test_tampered_payload_rejected(license_env):
    """Garante que alterar dados no payload (ex: estender validade) invalide a assinatura."""
    issuer: LicenseIssuer = license_env["issuer"]
    client_mgr: LicenseManager = license_env["client_mgr"]

    hwid = client_mgr.get_current_machine_fingerprint()
    token = issuer.issue_license("Cliente Original", LicenseType.TRIAL, hwid, days_valid=10)
    payload_b64, sig_b64 = token.split(".")

    # Modificar um caractere no payload
    tampered_payload = "A" + payload_b64[1:]
    tampered_token = f"{tampered_payload}.{sig_b64}"

    info = client_mgr.validate_license_key(tampered_token)
    assert info.is_valid is False


def test_foreign_private_key_signature_rejected(license_env):
    """Garante que licenças assinadas por chave privada de terceiros (não oficial) sejam rejeitadas."""
    client_mgr: LicenseManager = license_env["client_mgr"]
    hwid = client_mgr.get_current_machine_fingerprint()

    # Cria outro emissor com outro par de chaves assimétricas
    rogue_priv_b64, _ = LicenseIssuer.generate_new_keypair()
    rogue_issuer = LicenseIssuer(private_key_b64=rogue_priv_b64)

    fake_token = rogue_issuer.issue_license("Cliente Hack", LicenseType.ENTERPRISE, hwid)

    info = client_mgr.validate_license_key(fake_token)
    assert info.is_valid is False
    assert "inválida ou forjada" in info.status_message.lower()


# =============================================================================
# 3. REGRAS DE BLOQUEIO DE USO: HWID, EXPIRAÇÃO E AUSÊNCIA
# =============================================================================

def test_hwid_mismatch_blocks_usage(license_env):
    """Licença emitida para outro hardware deve ser estritamente bloqueada."""
    issuer: LicenseIssuer = license_env["issuer"]
    client_mgr: LicenseManager = license_env["client_mgr"]

    foreign_hwid = "OUTRO_COMPUTADOR_999999"
    token = issuer.issue_license("Cliente", LicenseType.PROFESSIONAL, foreign_hwid)

    info = client_mgr.validate_license_key(token)
    assert info.is_valid is False
    assert "outro computador" in info.status_message.lower()


def test_expired_license_blocks_usage(license_env):
    """Licença expirada deve ser estritamente bloqueada."""
    issuer: LicenseIssuer = license_env["issuer"]
    client_mgr: LicenseManager = license_env["client_mgr"]

    hwid = client_mgr.get_current_machine_fingerprint()
    token = issuer.issue_license("Cliente", LicenseType.TRIAL, hwid, days_valid=-5)

    info = client_mgr.validate_license_key(token)
    assert info.is_valid is False
    assert "expirada" in info.status_message.lower()


def test_missing_license_file_blocks_usage(license_env):
    """Se nenhum arquivo de licença estiver instalado, o uso deve ser bloqueado."""
    client_mgr: LicenseManager = license_env["client_mgr"]
    # Garante que o arquivo não existe
    if client_mgr.license_file.exists():
        client_mgr.license_file.unlink()

    info = client_mgr.check_current_license()
    assert info.is_valid is False
    assert "bloqueado" in info.status_message.lower()


# =============================================================================
# 4. TESTE DO DIÁLOGO DE ATIVAÇÃO DE LICENÇA (HEADLESS)
# =============================================================================

def test_license_activation_dialog(qapp, license_env, monkeypatch):
    """Testa a interface de ativação de licença com token Ed25519."""
    # Impede que popups modais de mensagem bloqueiem os testes automatizados
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    issuer: LicenseIssuer = license_env["issuer"]
    client_mgr: LicenseManager = license_env["client_mgr"]

    dialog = LicenseActivationDialog(lic_mgr=client_mgr)
    dialog.show()

    # 1. Ativação vazia exibe erro
    dialog.key_input.setText("")
    dialog._attempt_activation()
    assert dialog.status_lbl.isVisible() is True
    assert "insira" in dialog.status_lbl.text().lower()

    # 2. Ativação com chave forjada exibe erro
    dialog.key_input.setText("chave.falsa.123")
    dialog._attempt_activation()
    assert dialog.status_lbl.isVisible() is True
    assert "inválido" in dialog.status_lbl.text().lower()

    # 3. Ativação com chave Ed25519 legítima desbloqueia o sistema
    hwid = client_mgr.get_current_machine_fingerprint()
    valid_token = issuer.issue_license("Empresa de Teste", LicenseType.PROFESSIONAL, hwid, days_valid=60)
    dialog.key_input.setText(valid_token)
    dialog._attempt_activation()

    # Verifica que o arquivo foi salvo e está válido
    current = client_mgr.check_current_license()
    assert current.is_valid is True
    assert current.client_name == "Empresa de Teste"

    dialog.close()


def test_license_and_update_public_keys_are_strictly_separated():
    """Garante que a chave pública de licenciamento é estritamente DIFERENTE da chave pública de atualização."""
    from src.infrastructure.updater.update_manager import DEFAULT_UPDATE_PUBLIC_KEY_B64

    assert DEFAULT_PUBLIC_KEY_B64 != DEFAULT_UPDATE_PUBLIC_KEY_B64
    assert len(DEFAULT_PUBLIC_KEY_B64) > 40
    assert len(DEFAULT_UPDATE_PUBLIC_KEY_B64) > 40
