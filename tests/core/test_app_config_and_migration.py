"""
Testes unitários para AppConfig, platformdirs e migração retrocompatível de dados legados.
Valida o comportamento de diretórios por usuário do sistema operacional e preservação de dados.
"""

from pathlib import Path
import os
import platformdirs
import pytest

from src.core.config import AppConfig


def test_default_app_config_uses_platformdirs():
    """Valida que AppConfig() sem parâmetros utiliza platformdirs como diretório padrão do usuário."""
    expected_platform_dir = Path(platformdirs.user_data_dir("SolarGuardVision", "SolarGuardVision"))
    config = AppConfig()

    assert config.base_dir == expected_platform_dir
    assert config.data_dir == expected_platform_dir / "data"
    assert config.db_path == expected_platform_dir / "data" / "solarguard.sqlite3"
    assert config.models_dir == expected_platform_dir / "models"
    assert config.reports_dir == expected_platform_dir / "reports"
    assert config.cache_dir == expected_platform_dir / "cache"
    assert config.logs_dir == expected_platform_dir / "logs"


def test_app_config_custom_base_dir(tmp_path: Path):
    """Valida que especificar base_dir customizado deriva todos os subcaminhos corretamente."""
    custom_root = tmp_path / "custom_solarguard_root"
    config = AppConfig(base_dir=custom_root)

    assert config.base_dir == custom_root
    assert config.data_dir == custom_root / "data"
    assert config.db_path == custom_root / "data" / "solarguard.sqlite3"
    assert config.models_dir == custom_root / "models"
    assert config.reports_dir == custom_root / "reports"
    assert config.cache_dir == custom_root / "cache"
    assert config.logs_dir == custom_root / "logs"

    config.ensure_directories()
    assert config.data_dir.is_dir()
    assert config.models_dir.is_dir()
    assert config.reports_dir.is_dir()
    assert config.cache_dir.is_dir()
    assert config.logs_dir.is_dir()


def test_app_config_environment_variable_override(tmp_path: Path, monkeypatch):
    """Valida que a variável de ambiente SOLARGUARD_DATA_DIR tem precedência para base_dir."""
    override_path = tmp_path / "env_override_dir"
    monkeypatch.setenv("SOLARGUARD_DATA_DIR", str(override_path))

    config = AppConfig()
    assert config.base_dir == override_path
    assert config.data_dir == override_path / "data"


def test_migrate_legacy_data_full_flow(tmp_path: Path):
    """
    Testa a migração completa de uma pasta data/ legada de versão anterior para o novo
    diretório de usuário, incluindo banco, licença, settings, logs, modelos e backups.
    """
    legacy_root = tmp_path / "legacy_install"
    legacy_data = legacy_root / "data"
    legacy_logs = legacy_root / "logs"
    legacy_models = legacy_root / "models"

    legacy_data.mkdir(parents=True)
    legacy_logs.mkdir(parents=True)
    legacy_models.mkdir(parents=True)

    # Criação de arquivos legados de teste
    (legacy_data / "solarguard.sqlite3").write_text("LEGACY_SQLITE_CONTENT", encoding="utf-8")
    (legacy_data / "solarguard.sqlite3-wal").write_text("LEGACY_WAL_CONTENT", encoding="utf-8")
    (legacy_data / "license.key").write_text("SG-ENTERPRISE-LEGACY-KEY", encoding="utf-8")
    (legacy_data / "settings.json").write_text('{"theme": "dark"}', encoding="utf-8")
    (legacy_data / "admin_first_login.txt").write_text("Temporary admin password notice", encoding="utf-8")

    backups_dir = legacy_data / "backups"
    backups_dir.mkdir()
    (backups_dir / "backup_20260101.zip").write_text("BACKUP_BYTES", encoding="utf-8")

    (legacy_logs / "solarguard.log").write_text("Previous log line 1\n", encoding="utf-8")
    (legacy_models / "best.pt").write_bytes(b"YOLO11_MOCK_WEIGHTS")

    # Novo destino (simulando AppData)
    target_base = tmp_path / "new_appdata_target"
    config = AppConfig(base_dir=target_base)

    # Executa migração
    migrated = config.migrate_legacy_data(legacy_cwd=legacy_root)
    assert migrated is True

    # Verifica que todos os arquivos foram migrados
    assert config.db_path.exists()
    assert config.db_path.read_text(encoding="utf-8") == "LEGACY_SQLITE_CONTENT"
    assert (config.data_dir / "solarguard.sqlite3-wal").read_text(encoding="utf-8") == "LEGACY_WAL_CONTENT"
    assert (config.data_dir / "license.key").read_text(encoding="utf-8") == "SG-ENTERPRISE-LEGACY-KEY"
    assert (config.data_dir / "settings.json").read_text(encoding="utf-8") == '{"theme": "dark"}'
    assert (config.data_dir / "admin_first_login.txt").read_text(encoding="utf-8") == "Temporary admin password notice"
    assert (config.data_dir / "backups" / "backup_20260101.zip").read_text(encoding="utf-8") == "BACKUP_BYTES"
    assert (config.logs_dir / "solarguard.log").read_text(encoding="utf-8") == "Previous log line 1\n"
    assert (config.models_dir / "best.pt").read_bytes() == b"YOLO11_MOCK_WEIGHTS"

    # Marcador de migração deve existir na pasta legada
    marker = legacy_data / ".migrated_to_appdata"
    assert marker.exists()

    # Segunda chamada não re-migra (idempotência)
    second_run = config.migrate_legacy_data(legacy_cwd=legacy_root)
    assert second_run is False


def test_migrate_legacy_data_preserves_existing_target(tmp_path: Path):
    """Valida que a migração não sobrescreve banco SQLite ou arquivos já existentes no destino."""
    legacy_root = tmp_path / "legacy_install_2"
    legacy_data = legacy_root / "data"
    legacy_data.mkdir(parents=True)
    (legacy_data / "solarguard.sqlite3").write_text("OLD_DATABASE", encoding="utf-8")

    target_base = tmp_path / "target_appdata_2"
    config = AppConfig(base_dir=target_base)
    config.ensure_directories()
    # Cria previamente um banco no destino
    config.db_path.write_text("NEW_DATABASE", encoding="utf-8")

    config.migrate_legacy_data(legacy_cwd=legacy_root)

    # Conteúdo no destino deve ter sido preservado
    assert config.db_path.read_text(encoding="utf-8") == "NEW_DATABASE"


def test_migrate_legacy_data_noop_when_no_legacy_folder(tmp_path: Path):
    """Valida que sem pasta data/ legada, migrate_legacy_data retorna False sem erros."""
    empty_root = tmp_path / "empty_dir"
    empty_root.mkdir()
    config = AppConfig(base_dir=tmp_path / "appdata_noop")

    assert config.migrate_legacy_data(legacy_cwd=empty_root) is False
