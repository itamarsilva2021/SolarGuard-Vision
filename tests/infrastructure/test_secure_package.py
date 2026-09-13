"""
Suíte de Testes Automatizados para o Container Criptográfico Seguro:
ZIP + AES-256-GCM + Assinatura Ed25519 (RFC 8032).
Garante os pilares de:
- Confidencialidade (AES-256-GCM)
- Autenticidade (Assinatura assimétrica Ed25519)
- Integridade (GCM Tag, Digest SHA-256, Assinatura e CRC32 ZIP)
"""

import os
import io
import json
import struct
import zipfile
import pytest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519
from src.infrastructure.security.secure_package import SecurePackageManager
from src.infrastructure.storage.backup_service import BackupService
from src.infrastructure.database.connection import DatabaseManager


@pytest.fixture
def keypair():
    """Gera um par de chaves Ed25519 para os testes."""
    return SecurePackageManager.generate_keypair()


@pytest.fixture
def sample_sources(tmp_path: Path):
    """Cria arquivos e pastas de teste para empacotamento."""
    src_dir = tmp_path / "src_data"
    src_dir.mkdir(parents=True, exist_ok=True)

    file1 = src_dir / "relatorio_termografico.pdf"
    file1.write_bytes(b"%PDF-1.4 Dados Confidenciais de Laudo Termografico SolarGuard Vision 2026")

    file2 = src_dir / "anomalias_detectadas.json"
    file2.write_text(json.dumps({"anomalia": "Hotspot Severidade 3", "temp_c": 68.5}), encoding="utf-8")

    sub_dir = src_dir / "subpasta"
    sub_dir.mkdir(parents=True, exist_ok=True)
    file3 = sub_dir / "telemetria.csv"
    file3.write_text("timestamp,irradiancia,temp_amb\n2026-09-12T10:00:00,850,29.4\n", encoding="utf-8")

    return src_dir, [file1, file2, file3]


class TestKeyManagement:
    """Testes de geração e serialização de chaves Ed25519."""

    def test_keypair_generation_and_export_import(self):
        priv_key, pub_key = SecurePackageManager.generate_keypair()

        priv_b64 = SecurePackageManager.export_private_key_b64(priv_key)
        pub_b64 = SecurePackageManager.export_public_key_b64(pub_key)

        assert isinstance(priv_b64, str)
        assert isinstance(pub_b64, str)
        assert len(priv_b64) > 40
        assert len(pub_b64) > 40

        imported_priv = SecurePackageManager.import_private_key_b64(priv_b64)
        imported_pub = SecurePackageManager.import_public_key_b64(pub_b64)

        # Teste funcional da chave reconstruída: assinar e verificar
        msg = b"Mensagem de teste para validacao de chave"
        sig = imported_priv.sign(msg)
        imported_pub.verify(sig, msg)


class TestConfidentiality:
    """Validação do pilar de Confidencialidade (AES-256-GCM)."""

    def test_ciphertext_is_opaque_and_does_not_leak_plaintext(self, tmp_path: Path, sample_sources, keypair):
        priv_key, _ = keypair
        src_dir, files = sample_sources
        out_pkg = tmp_path / "package_confidential.sgz"
        passphrase = "SenhaMestreSuperSegura@2026!"

        pkg_mgr = SecurePackageManager()
        res = pkg_mgr.pack(
            output_path=out_pkg,
            passphrase=passphrase,
            signing_key=priv_key,
            sources=files,
            base_dir=src_dir,
        )
        assert res.is_success is True

        # Ler o arquivo binário direto do disco e verificar que texto claro não vaza
        raw_pkg_bytes = out_pkg.read_bytes()
        assert b"Dados Confidenciais de Laudo Termografico" not in raw_pkg_bytes
        assert b"Hotspot Severidade 3" not in raw_pkg_bytes
        assert b"telemetria.csv" not in raw_pkg_bytes

    def test_unpack_fails_with_wrong_passphrase(self, tmp_path: Path, sample_sources, keypair):
        priv_key, pub_key = keypair
        src_dir, files = sample_sources
        out_pkg = tmp_path / "package_wrong_pass.sgz"
        passphrase = "SenhaMestreSuperSegura@2026!"

        pkg_mgr = SecurePackageManager()
        pkg_mgr.pack(
            output_path=out_pkg,
            passphrase=passphrase,
            signing_key=priv_key,
            sources=files,
            base_dir=src_dir,
        )

        dest_dir = tmp_path / "extracted_fail"
        res_wrong = pkg_mgr.unpack(
            package_path=out_pkg,
            output_dir=dest_dir,
            passphrase="SenhaErradaIncorreta123!",
            expected_public_key=pub_key,
        )
        assert res_wrong.is_success is False
        assert "senha incorreta" in res_wrong.error.lower() or "decifração" in res_wrong.error.lower()
        # Garante que nenhum arquivo foi extraído
        assert not dest_dir.exists() or len(list(dest_dir.glob("*"))) == 0

    def test_reject_passphrase_less_than_12_characters(self, tmp_path: Path, keypair):
        priv_key, _ = keypair
        out_pkg = tmp_path / "short_pass.sgz"

        pkg_mgr = SecurePackageManager()
        res = pkg_mgr.pack(
            output_path=out_pkg,
            passphrase="curta123",
            signing_key=priv_key,
            virtual_files={"teste.txt": b"123"},
        )
        assert res.is_success is False
        assert "12 caracteres" in res.error


class TestAuthenticity:
    """Validação do pilar de Autenticidade (Assinatura Ed25519)."""

    def test_unpack_rejects_untrusted_public_key(self, tmp_path: Path, keypair):
        priv_key_legit, _ = keypair
        _, rogue_pub_key = SecurePackageManager.generate_keypair()

        out_pkg = tmp_path / "package_untrusted_signer.sgz"
        pkg_mgr = SecurePackageManager()
        pack_res = pkg_mgr.pack(
            output_path=out_pkg,
            passphrase="SenhaSuperSegura2026!",
            signing_key=priv_key_legit,
            virtual_files={"dados.txt": b"conteudo confidencial"},
        )
        assert pack_res.is_success is True

        dest_dir = tmp_path / "extracted_untrusted"
        unpack_res = pkg_mgr.unpack(
            package_path=out_pkg,
            output_dir=dest_dir,
            passphrase="SenhaSuperSegura2026!",
            expected_public_key=rogue_pub_key,
        )
        assert unpack_res.is_success is False
        assert "não corresponde à chave pública confiável" in unpack_res.error

    def test_tampered_signature_is_rejected(self, tmp_path: Path, keypair):
        priv_key, pub_key = keypair
        out_pkg = tmp_path / "package_tampered_sig.sgz"
        pkg_mgr = SecurePackageManager()
        pkg_mgr.pack(
            output_path=out_pkg,
            passphrase="SenhaSuperSegura2026!",
            signing_key=priv_key,
            virtual_files={"dados.txt": b"conteudo confidencial"},
        )

        # Adulterar a assinatura dentro do cabeçalho
        pkg_bytes = bytearray(out_pkg.read_bytes())
        magic_len = len(SecurePackageManager.MAGIC_BYTES)
        header_len = struct.unpack(">I", pkg_bytes[magic_len : magic_len + 4])[0]
        header_raw = pkg_bytes[magic_len + 4 : magic_len + 4 + header_len]
        header = json.loads(header_raw.decode("utf-8"))

        # Corromper 1 caractere da assinatura
        sig_corrompida = list(header["signature_b64"])
        sig_corrompida[5] = "A" if sig_corrompida[5] != "A" else "B"
        header["signature_b64"] = "".join(sig_corrompida)

        new_header_bytes = json.dumps(header, indent=2).encode("utf-8")
        tampered_pkg = (
            SecurePackageManager.MAGIC_BYTES
            + struct.pack(">I", len(new_header_bytes))
            + new_header_bytes
            + pkg_bytes[magic_len + 4 + header_len :]
        )
        out_pkg.write_bytes(tampered_pkg)

        dest_dir = tmp_path / "extracted_tampered_sig"
        res = pkg_mgr.unpack(
            package_path=out_pkg,
            output_dir=dest_dir,
            passphrase="SenhaSuperSegura2026!",
            expected_public_key=pub_key,
        )
        assert res.is_success is False
        assert "assinatura ed25519 inválida" in res.error.lower()


class TestIntegrity:
    """Validação do pilar de Integridade (GCM Tag + Digest SHA-256 + CRC32 ZIP)."""

    def test_tampered_ciphertext_byte_is_detected(self, tmp_path: Path, keypair):
        priv_key, pub_key = keypair
        out_pkg = tmp_path / "package_tampered_ct.sgz"
        pkg_mgr = SecurePackageManager()
        pkg_mgr.pack(
            output_path=out_pkg,
            passphrase="SenhaSuperSegura2026!",
            signing_key=priv_key,
            virtual_files={"dados.txt": b"conteudo confidencial original"},
        )

        # Corromper o último byte do arquivo (que faz parte da auth tag ou ciphertext do GCM)
        pkg_bytes = bytearray(out_pkg.read_bytes())
        pkg_bytes[-1] ^= 0xFF
        out_pkg.write_bytes(pkg_bytes)

        dest_dir = tmp_path / "extracted_tampered_ct"
        res = pkg_mgr.unpack(
            package_path=out_pkg,
            output_dir=dest_dir,
            passphrase="SenhaSuperSegura2026!",
            expected_public_key=pub_key,
        )
        assert res.is_success is False
        # Pode ser detectado tanto pelo hash de integridade do ciphertext quanto pela tag GCM
        assert (
            "integridade comprometida" in res.error.lower()
            or "tag gcm inválida" in res.error.lower()
            or "adulterado" in res.error.lower()
        )

    def test_successful_pack_and_unpack_roundtrip(self, tmp_path: Path, sample_sources, keypair):
        priv_key, pub_key = keypair
        src_dir, files = sample_sources
        out_pkg = tmp_path / "roundtrip.sgz"
        passphrase = "SenhaCompleta@SolarGuard2026!"

        pkg_mgr = SecurePackageManager()
        pack_res = pkg_mgr.pack(
            output_path=out_pkg,
            passphrase=passphrase,
            signing_key=priv_key,
            sources=files,
            base_dir=src_dir,
            metadata={"origem": "Voo DJI Matrice 300", "usina": "Usina Fotovoltaica Sertao I"},
        )
        assert pack_res.is_success is True

        dest_dir = tmp_path / "extracted_roundtrip"
        unpack_res = pkg_mgr.unpack(
            package_path=out_pkg,
            output_dir=dest_dir,
            passphrase=passphrase,
            expected_public_key=pub_key,
        )
        assert unpack_res.is_success is True
        extracted_files = unpack_res.value
        assert len(extracted_files) == 3

        # Validar conteúdo e integridade bit a bit
        pdf_extracted = dest_dir / "relatorio_termografico.pdf"
        assert pdf_extracted.exists()
        assert pdf_extracted.read_bytes() == (src_dir / "relatorio_termografico.pdf").read_bytes()

        json_extracted = dest_dir / "anomalias_detectadas.json"
        assert json_extracted.exists()
        assert json_extracted.read_bytes() == (src_dir / "anomalias_detectadas.json").read_bytes()

        csv_extracted = dest_dir / "subpasta" / "telemetria.csv"
        assert csv_extracted.exists()
        assert csv_extracted.read_bytes() == (src_dir / "subpasta" / "telemetria.csv").read_bytes()

    def test_inspect_package_without_passphrase(self, tmp_path: Path, keypair):
        priv_key, pub_key = keypair
        out_pkg = tmp_path / "inspect_test.sgz"
        pkg_mgr = SecurePackageManager()
        pkg_mgr.pack(
            output_path=out_pkg,
            passphrase="SenhaSuperSecreta@2026!",
            signing_key=priv_key,
            virtual_files={"documento.txt": b"texto qualquer"},
            metadata={"modulo": "Inspeção Termográfica Avançada", "iec": "IEC 62446-3"},
        )

        inspect_res = pkg_mgr.inspect_package(out_pkg, expected_public_key=pub_key)
        assert inspect_res.is_success is True
        meta = inspect_res.value
        assert meta["is_authentic"] is True
        assert meta["is_intact"] is True
        assert meta["cipher"] == "AES-256-GCM"
        assert meta["metadata"]["iec"] == "IEC 62446-3"


class TestSecurityProtections:
    """Testes de proteções de segurança contra ataques de arquivo."""

    def test_zip_slip_path_traversal_prevention(self, tmp_path: Path):
        dest_dir = tmp_path / "safe_target"
        dest_dir.mkdir()

        # Criar buffer zip com caminho malicioso
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w") as zf:
            zf.writestr("../../arquivo_invasor.txt", b"malicioso")

        with pytest.raises(PermissionError) as exc_info:
            SecurePackageManager.extract_zip_buffer(bio.getvalue(), dest_dir)
        assert "Path Traversal bloqueada" in str(exc_info.value)

    def test_zip_slip_string_prefix_sibling_directory_bypass_rejected(self, tmp_path: Path):
        """
        Teste de regressão: impede o bypass de Zip Slip onde o caminho de destino
        é um diretório irmão cujo nome começa com o mesmo prefixo textual do target_dir
        (ex.: target_dir='pacote' vs. dest_path='pacote_malicioso/arquivo.txt').
        A checagem antiga str.startswith() aceitaria erroneamente; a checagem estrutural
        is_relative_to() deve rejeitar com PermissionError.
        """
        target_dir = tmp_path / "pacote"
        target_dir.mkdir()

        # Entrada maliciosa que resolve para um irmão tmp_path / "pacote_malicioso" / "exploit.txt"
        malicious_entry = "../pacote_malicioso/exploit.txt"

        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w") as zf:
            zf.writestr(malicious_entry, b"conteudo_malicioso")

        # Garante que o arquivo malicioso NÃO seja gravado e que lance PermissionError
        with pytest.raises(PermissionError) as exc_info:
            SecurePackageManager.extract_zip_buffer(bio.getvalue(), target_dir)

        assert "Path Traversal bloqueada" in str(exc_info.value)

        # Confirma que o diretório irmão invasor não foi criado nem populado
        sibling_malicious_dir = tmp_path / "pacote_malicioso"
        assert not sibling_malicious_dir.exists()


class TestBackupServiceIntegration:
    """Integração dos pacotes seguros com o BackupService do SolarGuard Vision."""

    def test_create_and_restore_secure_backup(self, tmp_path: Path, keypair):
        priv_key, pub_key = keypair
        db_file = tmp_path / "test_secure.db"
        db = DatabaseManager(str(db_file))
        db.initialize_schema()

        # Inserir registro no banco para testar persistência
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, client_name, location_name, capacity_kwp, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("proj_sec_01", "Usina Solar Alpha", "Solar Energy SA", "Bahia, Brasil", 5000.0, "2026-09-12T10:00:00"),
            )

        backup_dir = tmp_path / "secure_backups"
        backup_svc = BackupService(backup_dir=backup_dir, db_path=db_file)
        passphrase = "SenhaBackupSolarGuard@2026!"

        # 1. Criar backup seguro
        res = backup_svc.create_secure_backup(
            passphrase=passphrase,
            signing_key=priv_key,
            custom_label="checkpoint_seguro",
        )
        assert res.is_success is True
        secure_pkg_path = res.value
        assert secure_pkg_path.exists()
        assert secure_pkg_path.suffix == ".sgz"

        # 2. Listar backups e verificar flag is_secure
        backups = backup_svc.list_backups()
        assert len(backups) == 1
        assert backups[0]["is_secure"] is True

        # 3. Simular perda/deleção do banco original
        db_file.unlink()
        assert not db_file.exists()

        # 4. Restaurar backup com sucesso
        restore_res = backup_svc.restore_secure_backup(
            package_path=secure_pkg_path,
            passphrase=passphrase,
            verify_key=pub_key,
        )
        assert restore_res.is_success is True
        assert db_file.exists()

        # 5. Conferir que dados foram restaurados intactos no SQLite
        db_restored = DatabaseManager(str(db_file))
        with db_restored.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, client_name FROM projects WHERE id = 'proj_sec_01'")
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "Usina Solar Alpha"
            assert row[1] == "Solar Energy SA"

    def test_restore_secure_backup_fails_with_invalid_credentials(self, tmp_path: Path, keypair):
        priv_key, pub_key = keypair
        db_file = tmp_path / "test_sec_fail.db"
        db = DatabaseManager(str(db_file))
        db.initialize_schema()
        db.close()

        backup_dir = tmp_path / "secure_backups_fail"
        backup_svc = BackupService(backup_dir=backup_dir, db_path=db_file)
        passphrase = "SenhaBackupSolarGuard@2026!"

        res = backup_svc.create_secure_backup(
            passphrase=passphrase,
            signing_key=priv_key,
        )
        assert res.is_success is True
        pkg_path = res.value

        # Tentar restaurar com senha errada
        restore_fail = backup_svc.restore_secure_backup(
            package_path=pkg_path,
            passphrase="SenhaIncorretaTentativa123!",
            verify_key=pub_key,
        )
        assert restore_fail.is_success is False
        assert "senha incorreta" in restore_fail.error.lower() or "decifração" in restore_fail.error.lower()
