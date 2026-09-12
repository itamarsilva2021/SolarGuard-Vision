"""
Suíte de Testes Automatizados para o Sistema de Atualizações Assinadas.
Garante o fluxo criptográfico completo:
Manifesto assinado (Ed25519) -> Validação da assinatura -> Download seguro -> Validação SHA-256 -> Instalação auditada.
Protege ativamente contra ataques de downgrade/rollback, injeção de binários maliciosos e TOCTOU.
"""

import hashlib
import json
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.infrastructure.updater.update_manager import (
    UpdateManager,
    UpdateManifestSigner,
    UpdateInfo,
)


@pytest.fixture
def update_keypair():
    """Gera par de chaves Ed25519 oficial para assinatura de atualizações."""
    priv = ed25519.Ed25519PrivateKey.generate()
    return priv, priv.public_key()


@pytest.fixture
def dummy_installer(tmp_path: Path):
    """Cria um executável simulado legítimo e calcula seu SHA-256."""
    installer_file = tmp_path / "SolarGuard_Setup_v1.1.0.exe"
    content = "MZ\x90\x00 Executavel Instalador Legitimo SolarGuard Vision v1.1.0 (Assinado Oficial)".encode("utf-8")
    installer_file.write_bytes(content)
    sha256 = hashlib.sha256(content).hexdigest()
    return installer_file, sha256


class TestSignedManifestValidation:
    """Testes de validação da assinatura Ed25519 no manifesto de atualização."""

    def test_signed_manifest_valid(self, update_keypair, dummy_installer):
        priv_key, pub_key = update_keypair
        _, sha256 = dummy_installer

        manifest = {
            "version": "1.1.0",
            "release_date": "2026-09-12",
            "release_notes": "Nova versão segura com modelos térmicos avançados.",
            "download_url": "https://releases.solarguard.ai/SolarGuard_Setup_v1.1.0.exe",
            "sha256": sha256,
            "mandatory": False,
        }

        signed_manifest = UpdateManifestSigner.sign_manifest(manifest, priv_key)
        assert "signature_b64" in signed_manifest
        assert "signer_public_key_b64" in signed_manifest

        updater = UpdateManager(current_version="1.0.0", trusted_public_key=pub_key)
        res = updater.verify_manifest_signature(signed_manifest)
        assert res.is_success is True

        check_res = updater.check_signed_manifest(signed_manifest)
        assert check_res.is_success is True
        info = check_res.value
        assert info.version == "1.1.0"
        assert info.is_newer is True
        assert info.sha256_checksum == sha256.lower()

    def test_reject_unsigned_manifest(self, update_keypair):
        _, pub_key = update_keypair
        raw_manifest = {
            "version": "1.1.0",
            "download_url": "https://example.com/setup.exe",
            "sha256": "a" * 64,
        }

        updater = UpdateManager(current_version="1.0.0", trusted_public_key=pub_key)
        res = updater.check_signed_manifest(raw_manifest)
        assert res.is_success is False
        assert "não assinado" in res.error.lower() or "ausente" in res.error.lower()

    def test_reject_manifest_signed_by_untrusted_key(self, update_keypair):
        priv_legit, pub_legit = update_keypair
        rogue_priv = ed25519.Ed25519PrivateKey.generate()

        manifest = {
            "version": "1.1.0",
            "download_url": "https://attacker.com/malicious_setup.exe",
            "sha256": "b" * 64,
        }
        # Assinado por chave não autorizada (rogue key)
        rogue_signed = UpdateManifestSigner.sign_manifest(manifest, rogue_priv)

        updater = UpdateManager(current_version="1.0.0", trusted_public_key=pub_legit)
        res = updater.check_signed_manifest(rogue_signed)
        assert res.is_success is False
        assert "não autorizada" in res.error.lower() or "autenticidade violada" in res.error.lower()

    def test_reject_tampered_manifest_payload(self, update_keypair, dummy_installer):
        priv_key, pub_key = update_keypair
        _, sha256 = dummy_installer

        manifest = {
            "version": "1.1.0",
            "download_url": "https://releases.solarguard.ai/legit.exe",
            "sha256": sha256,
        }
        signed_manifest = UpdateManifestSigner.sign_manifest(manifest, priv_key)

        # Atacante altera a URL no trânsito para injetar link de malware
        signed_manifest["download_url"] = "https://malicious-site.com/exploit.exe"

        updater = UpdateManager(current_version="1.0.0", trusted_public_key=pub_key)
        res = updater.check_signed_manifest(signed_manifest)
        assert res.is_success is False
        assert "adulterado" in res.error.lower() or "inválida" in res.error.lower()


class TestDowngradeRollbackProtection:
    """Prevenção contra ataques de Downgrade / Rollback para versões vulneráveis."""

    def test_reject_downgrade_attempt(self, update_keypair):
        priv_key, pub_key = update_keypair
        manifest = {
            "version": "0.9.0",  # Versão inferior à atual 1.0.0
            "download_url": "https://releases.solarguard.ai/old.exe",
            "sha256": "c" * 64,
        }
        signed_manifest = UpdateManifestSigner.sign_manifest(manifest, priv_key)

        updater = UpdateManager(current_version="1.0.0", trusted_public_key=pub_key)
        res = updater.check_signed_manifest(signed_manifest)
        assert res.is_success is True
        info = res.value
        # Deve sinalizar que não é versão mais nova
        assert info.is_newer is False


class TestSecureDownloadAndShaIntegrity:
    """Download seguro e validação estrita de integridade SHA-256."""

    def test_download_legitimate_update_succeeds(self, tmp_path: Path, update_keypair, dummy_installer):
        _, pub_key = update_keypair
        installer_file, sha256 = dummy_installer

        downloads_dir = tmp_path / "downloads"
        updater = UpdateManager(
            current_version="1.0.0",
            downloads_dir=downloads_dir,
            trusted_public_key=pub_key,
        )

        update_info = UpdateInfo(
            version="1.1.0",
            release_date="2026-09-12",
            release_notes="Melhorias",
            download_url=f"file://{installer_file.resolve().as_posix()}",
            sha256_checksum=sha256,
            is_newer=True,
        )

        res = updater.download_update(update_info, allow_local_source=True)
        assert res.is_success is True
        downloaded_file = res.value
        assert downloaded_file.exists()
        assert updater.verify_installer_integrity(downloaded_file, sha256) is True

    def test_download_malicious_tampered_binary_is_discarded(self, tmp_path: Path, update_keypair):
        _, pub_key = update_keypair

        # Criar binário adulterado com hash diferente do esperado no manifesto
        tampered_file = tmp_path / "fake_installer.exe"
        tampered_file.write_bytes(b"MALWARE_INJETADO_BINARIO_CORROMPIDO")

        downloads_dir = tmp_path / "downloads_malicious"
        updater = UpdateManager(
            current_version="1.0.0",
            downloads_dir=downloads_dir,
            trusted_public_key=pub_key,
        )

        # Manifesto assinado dizia que o hash era outro
        expected_legit_sha = hashlib.sha256(b"BINARIO_LEGITIMO").hexdigest()

        update_info = UpdateInfo(
            version="1.1.0",
            release_date="2026-09-12",
            release_notes="Versão fraudulenta",
            download_url=f"file://{tampered_file.resolve().as_posix()}",
            sha256_checksum=expected_legit_sha,
            is_newer=True,
        )

        res = updater.download_update(update_info, allow_local_source=True)
        assert res.is_success is False
        assert "falha crítica de segurança" in res.error.lower() or "diverge" in res.error.lower()

        # Garantir que o binário malicioso NÃO foi gravado no diretório de downloads
        dest_expected = downloads_dir / "solarguard_update_v1.1.0.exe"
        assert not dest_expected.exists()
        # Arquivo temporário também deve ter sido removido
        assert not (dest_expected.with_suffix(".exe.downloading")).exists()

    def test_download_rejects_insecure_http_url(self, tmp_path: Path):
        updater = UpdateManager(current_version="1.0.0", downloads_dir=tmp_path)
        update_info = UpdateInfo(
            version="1.1.0",
            release_date="2026-09-12",
            release_notes="Inseguro",
            download_url="http://downloads.solarguard.internal/update.exe",
            sha256_checksum="a" * 64,
            is_newer=True,
        )
        res = updater.download_update(update_info)
        assert res.is_success is False
        assert "inseguro" in res.error.lower() or "http://" in res.error.lower()

    def test_download_rejects_file_url_by_default_in_production(self, tmp_path: Path, dummy_installer):
        installer_file, sha256 = dummy_installer
        updater = UpdateManager(current_version="1.0.0", downloads_dir=tmp_path)
        update_info = UpdateInfo(
            version="1.1.0",
            release_date="2026-09-12",
            release_notes="Teste de produção",
            download_url=f"file://{installer_file.resolve().as_posix()}",
            sha256_checksum=sha256,
            is_newer=True,
        )
        # Por padrão allow_local_source=False
        res = updater.download_update(update_info)
        assert res.is_success is False
        assert "origem local rejeitada" in res.error.lower() or "file://" in res.error.lower()

    def test_download_rejects_schemeless_local_path_by_default_in_production(self, tmp_path: Path, dummy_installer):
        installer_file, sha256 = dummy_installer
        updater = UpdateManager(current_version="1.0.0", downloads_dir=tmp_path)
        update_info = UpdateInfo(
            version="1.1.0",
            release_date="2026-09-12",
            release_notes="Teste relativo",
            download_url=installer_file.resolve().as_posix(),
            sha256_checksum=sha256,
            is_newer=True,
        )
        # Por padrão allow_local_source=False
        res = updater.download_update(update_info)
        assert res.is_success is False
        assert "origem local rejeitada" in res.error.lower()


class TestSecureInstallation:
    """Testes de instalação segura e proteção pré-execução anti-TOCTOU."""

    def test_installation_dry_run_with_valid_hash(self, tmp_path: Path, dummy_installer):
        installer_file, sha256 = dummy_installer
        updater = UpdateManager(current_version="1.0.0")

        res = updater.install_update(
            installer_path=installer_file,
            expected_sha256=sha256,
            dry_run=True,
        )
        assert res.is_success is True

    def test_installation_blocks_if_binary_modified_before_exec_toctou(self, tmp_path: Path, dummy_installer):
        installer_file, original_sha = dummy_installer
        updater = UpdateManager(current_version="1.0.0")

        # Modifica o arquivo em disco logo antes da instalação (ataque TOCTOU)
        installer_file.write_bytes(b"SUBSTITUIDO_EM_DISCO_APOS_DOWNLOAD")

        res = updater.install_update(
            installer_path=installer_file,
            expected_sha256=original_sha,
            dry_run=True,
        )
        assert res.is_success is False
        assert "anti-toctou" in res.error.lower() or "modificado" in res.error.lower()


class TestCompleteUpdatePipelineE2E:
    """Teste ponta a ponta do ciclo completo de atualização assinada."""

    def test_full_pipeline_success(self, tmp_path: Path, update_keypair, dummy_installer):
        priv_key, pub_key = update_keypair
        installer_file, sha256 = dummy_installer

        # 1. Servidor/CI gera manifesto assinado digitalmente
        manifest_payload = {
            "version": "1.1.0",
            "release_date": "2026-09-12",
            "release_notes": "SolarGuard Vision v1.1.0 com proteção ativa.",
            "download_url": f"file://{installer_file.resolve().as_posix()}",
            "sha256": sha256,
            "mandatory": True,
        }
        signed_manifest = UpdateManifestSigner.sign_manifest(manifest_payload, priv_key)

        # 2. Cliente recebe manifesto e valida assinatura Ed25519
        downloads_dir = tmp_path / "e2e_downloads"
        updater = UpdateManager(
            current_version="1.0.0",
            downloads_dir=downloads_dir,
            trusted_public_key=pub_key,
        )

        check_res = updater.check_signed_manifest(signed_manifest)
        assert check_res.is_success is True
        update_info = check_res.value
        assert update_info.is_newer is True

        # 3. Cliente executa download seguro com validação SHA-256
        download_res = updater.download_update(update_info, allow_local_source=True)
        assert download_res.is_success is True
        verified_installer = download_res.value

        # 4. Instalação auditada e aprovada
        install_res = updater.install_update(
            installer_path=verified_installer,
            expected_sha256=update_info.sha256_checksum,
            dry_run=True,
        )
        assert install_res.is_success is True


def test_update_and_license_public_keys_segregation():
    """Valida que o par de atualização de software não compartilha chave com o licenciamento."""
    from src.infrastructure.updater.update_manager import DEFAULT_UPDATE_PUBLIC_KEY_B64
    from src.infrastructure.security.license_manager import DEFAULT_PUBLIC_KEY_B64

    assert DEFAULT_UPDATE_PUBLIC_KEY_B64 != DEFAULT_PUBLIC_KEY_B64
    assert len(DEFAULT_UPDATE_PUBLIC_KEY_B64) == 44
    assert len(DEFAULT_PUBLIC_KEY_B64) == 44
