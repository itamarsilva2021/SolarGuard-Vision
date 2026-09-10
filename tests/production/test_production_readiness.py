"""
Testes automatizados dos subsistemas de prontidão para produção (Etapa 10).
Valida Configurações, Backup/Restore, Gestão de Usuários, Licenciamento, Atualizações e Crash Reporting.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
import pytest

from src.domain.entities.user import User
from src.domain.enums.user_role import UserRole
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.repositories.sqlite_user_repository import SqliteUserRepository
from src.infrastructure.security.password_hasher import PasswordHasher
from src.infrastructure.security.license_manager import LicenseManager, LicenseType
from src.infrastructure.config.settings_manager import SettingsManager, AppSettings
from src.infrastructure.storage.backup_service import BackupService
from src.infrastructure.updater.update_manager import UpdateManager
from src.infrastructure.diagnostics.crash_reporter import CrashReporter
from src.application.services.user_service import UserService


# -----------------------------------------------------------------------------
# 1. TESTES DE CONFIGURAÇÕES
# -----------------------------------------------------------------------------
class TestSettingsManager:
    def test_load_and_save_settings(self, tmp_path: Path):
        cfg_file = tmp_path / "custom_settings.json"
        mgr = SettingsManager(config_file=cfg_file)

        # Carregar padrão
        settings = mgr.get_settings()
        assert settings.theme == "dark"
        assert settings.language == "pt_BR"

        # Modificar e salvar
        settings.theme = "light"
        settings.default_palette = "rainbow"
        settings.company_name = "SolarMax Energia Renovável"
        saved = mgr.save_settings(settings)
        assert saved is True
        assert cfg_file.exists()

        # Recarregar em nova instância
        mgr2 = SettingsManager(config_file=cfg_file)
        loaded = mgr2.load_settings()
        assert loaded.theme == "light"
        assert loaded.default_palette == "rainbow"
        assert loaded.company_name == "SolarMax Energia Renovável"

    def test_reset_to_defaults(self, tmp_path: Path):
        cfg_file = tmp_path / "settings_reset.json"
        mgr = SettingsManager(config_file=cfg_file)

        settings = mgr.get_settings()
        settings.theme = "light"
        mgr.save_settings(settings)

        resetted = mgr.reset_to_defaults()
        assert resetted.theme == "dark"


# -----------------------------------------------------------------------------
# 2. TESTES DE BACKUP E RESTORE
# -----------------------------------------------------------------------------
class TestBackupService:
    def test_create_and_restore_backup(self, tmp_path: Path):
        db_file = tmp_path / "test_backup.sqlite3"
        backup_dir = tmp_path / "backups"

        # Inicializar banco com dados
        db = DatabaseManager(str(db_file))
        db.initialize_schema()
        user_repo = SqliteUserRepository(db)
        pwd_hash, salt = PasswordHasher.hash_password("senha123")
        user = User(username="operador1", password_hash=pwd_hash, salt=salt, full_name="Operador Teste")
        user_repo.save(user)
        db.close()

        # Criar Backup
        backup_svc = BackupService(backup_dir=backup_dir, db_path=db_file)
        res_backup = backup_svc.create_backup(custom_label="teste_unitario")
        assert res_backup.is_success is True
        zip_path = res_backup.value
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"

        # Apagar ou corromper o banco propositalmente
        db_file.unlink()
        assert not db_file.exists()

        # Restaurar Backup
        res_restore = backup_svc.restore_backup(zip_path)
        assert res_restore.is_success is True
        assert db_file.exists()

        # Validar dados restaurados
        db_restored = DatabaseManager(str(db_file))
        user_repo_restored = SqliteUserRepository(db_restored)
        restored_user = user_repo_restored.get_by_username("operador1")
        assert restored_user is not None
        assert restored_user.full_name == "Operador Teste"
        db_restored.close()

    def test_rotate_backups(self, tmp_path: Path):
        db_file = tmp_path / "test_rot.sqlite3"
        db = DatabaseManager(str(db_file))
        db.initialize_schema()
        db.close()

        backup_svc = BackupService(backup_dir=tmp_path / "backups_rot", db_path=db_file)
        # Criar 5 backups
        for i in range(5):
            backup_svc.create_backup(custom_label=f"bkp_{i}")

        assert len(backup_svc.list_backups()) == 5
        removed = backup_svc.rotate_backups(keep_last=2)
        assert removed == 3
        assert len(backup_svc.list_backups()) == 2


# -----------------------------------------------------------------------------
# 3. TESTES DE USUÁRIOS E AUTENTICAÇÃO
# -----------------------------------------------------------------------------
class TestUserService:
    @pytest.fixture
    def user_service(self) -> UserService:
        db = DatabaseManager(":memory:")
        db.initialize_schema()
        repo = SqliteUserRepository(db)
        return UserService(repo)

    def test_create_and_authenticate_user(self, user_service: UserService):
        res = user_service.create_user(
            username="engenheiro_chefe",
            password="SenhaSegura@2026",
            full_name="Carlos Eduardo",
            role=UserRole.ADMIN,
            email="carlos@empresa.com",
        )
        assert res.is_success is True
        user = res.value
        assert user.username == "engenheiro_chefe"
        assert user.role == UserRole.ADMIN

        # Autenticação correta
        auth_res = user_service.authenticate("engenheiro_chefe", "SenhaSegura@2026")
        assert auth_res.is_success is True
        assert auth_res.value.id == user.id
        assert auth_res.value.last_login is not None

        # Autenticação com senha errada
        auth_fail = user_service.authenticate("engenheiro_chefe", "senha_errada")
        assert auth_fail.is_success is False

    def test_reject_duplicate_username(self, user_service: UserService):
        user_service.create_user("inspetor_solar", "senha123", "Inspetor 1")
        dup_res = user_service.create_user("inspetor_solar", "outrasenha", "Inspetor 2")
        assert dup_res.is_success is False
        assert "já está em uso" in dup_res.error


# -----------------------------------------------------------------------------
# 4. TESTES DE LICENCIAMENTO
# -----------------------------------------------------------------------------
class TestLicenseManager:
    def test_hardware_fingerprint_and_license_generation(self, tmp_path: Path):
        lic_file = tmp_path / "license.key"
        lic_mgr = LicenseManager(license_file=lic_file)

        hwid = lic_mgr.get_current_machine_fingerprint()
        assert len(hwid) > 10

        # Gerar chave legítima para a máquina local
        key = lic_mgr.generate_license_key(
            client_name="EletroSolar Corp",
            license_type=LicenseType.PROFESSIONAL,
            machine_fingerprint=hwid,
            days_valid=30,
            max_plants=20,
        )
        assert "." in key

        # Salvar e validar
        info = lic_mgr.save_license(key)
        assert info.is_valid is True
        assert info.client_name == "EletroSolar Corp"
        assert info.license_type == LicenseType.PROFESSIONAL
        assert info.days_remaining is not None
        assert info.days_remaining <= 30

    def test_tamper_detection_and_invalid_signature(self, tmp_path: Path):
        lic_mgr = LicenseManager(license_file=tmp_path / "license.key")
        hwid = lic_mgr.get_current_machine_fingerprint()
        legit_key = lic_mgr.generate_license_key("Cliente", LicenseType.TRIAL, hwid)

        # Adulterar assinatura
        tampered_key = legit_key[:-5] + "XXXXX"
        info = lic_mgr.validate_license_key(tampered_key)
        assert info.is_valid is False
        assert "inválida" in info.status_message.lower()

    def test_machine_mismatch(self, tmp_path: Path):
        lic_mgr = LicenseManager(license_file=tmp_path / "license.key")
        # Gerar chave para outro HWID
        key_other_machine = lic_mgr.generate_license_key("Cliente", LicenseType.PROFESSIONAL, "OUTRO_HWID_12345")
        info = lic_mgr.validate_license_key(key_other_machine)
        assert info.is_valid is False
        assert "outro computador" in info.status_message.lower()


# -----------------------------------------------------------------------------
# 5. TESTES DE ATUALIZAÇÕES
# -----------------------------------------------------------------------------
class TestUpdateManager:
    def test_semver_comparison(self):
        updater = UpdateManager(current_version="1.0.0")

        assert updater.is_version_newer("1.0.1") is True
        assert updater.is_version_newer("1.1.0") is True
        assert updater.is_version_newer("2.0.0") is True
        assert updater.is_version_newer("1.0.0") is False
        assert updater.is_version_newer("0.9.9") is False

    def test_check_from_manifest(self):
        updater = UpdateManager(current_version="1.0.0")
        manifest = {
            "version": "1.1.0",
            "release_date": "2026-10-01",
            "release_notes": "Novo detector YOLOv11 com maior acurácia.",
            "download_url": "https://downloads.solarguard.vision/Setup_v1.1.0.exe",
            "sha256": "abc123def456",
            "mandatory": False,
        }
        info = updater.check_for_updates_from_manifest(manifest)
        assert info.is_newer is True
        assert info.version == "1.1.0"
        assert info.download_url == "https://downloads.solarguard.vision/Setup_v1.1.0.exe"


# -----------------------------------------------------------------------------
# 6. TESTES DE TRATAMENTO GLOBAL DE ERROS (CRASH REPORTER)
# -----------------------------------------------------------------------------
class TestCrashReporter:
    def test_save_crash_dump(self, tmp_path: Path):
        reporter = CrashReporter(crash_dir=tmp_path / "crashes")

        dump_path = reporter._save_crash_dump(
            thread_name="WorkerThread-YOLO",
            exc_type="ValueError",
            exc_message="Erro simulado de teste para validação de produção",
            tb_lines=["Traceback simulated line 1\n", "ValueError: Erro simulado\n"],
        )

        assert dump_path.exists()
        content = json.loads(dump_path.read_text(encoding="utf-8"))
        assert content["thread"] == "WorkerThread-YOLO"
        assert content["exception_type"] == "ValueError"
        assert "Erro simulado" in content["exception_message"]
        assert "system_info" in content
        assert "os" in content["system_info"]
