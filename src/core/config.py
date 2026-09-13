"""
Configurações centrais da aplicação SolarGuard Vision.
Gerenciamento de caminhos de arquivos, banco de dados SQLite e diretórios de execução.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import os
import shutil
import logging
import platformdirs


def _get_default_base_dir() -> Path:
    """
    Retorna o diretório base de dados por usuário do sistema operacional.
    Prioriza variável de ambiente (SOLARGUARD_DATA_DIR ou SOLARGUARD_BASE_DIR),
    com fallback seguro para platformdirs (ex.: %APPDATA%/SolarGuardVision no Windows).
    """
    env_dir = os.environ.get("SOLARGUARD_DATA_DIR") or os.environ.get("SOLARGUARD_BASE_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(platformdirs.user_data_dir("SolarGuardVision", "SolarGuardVision"))


@dataclass
class AppConfig:
    """Configurações globais de caminhos e parâmetros do sistema SolarGuard Vision."""

    app_name: str = "SolarGuard Vision"
    app_version: str = "1.0.0"
    app_author: str = "SolarGuardVision"

    # Diretório Base da Aplicação por usuário do sistema operacional
    base_dir: Path = field(default_factory=_get_default_base_dir)

    # Diretórios de Dados Persistentes
    data_dir: Path = field(default=None)      # type: ignore
    db_path: Path = field(default=None)       # type: ignore
    models_dir: Path = field(default=None)    # type: ignore
    reports_dir: Path = field(default=None)   # type: ignore
    cache_dir: Path = field(default=None)     # type: ignore
    logs_dir: Path = field(default=None)      # type: ignore

    # Parâmetros Térmicos Padrão do DJI Matrice 4T
    default_emissivity: float = 0.95       # Vidro de módulo fotovoltaico
    default_distance_meters: float = 25.0  # Voo padrão
    default_confidence_threshold: float = 0.40

    def __post_init__(self) -> None:
        if self.base_dir is None:
            self.base_dir = _get_default_base_dir()
        if self.data_dir is None:
            self.data_dir = self.base_dir / "data"
        if self.db_path is None:
            self.db_path = self.data_dir / "solarguard.sqlite3"
        if self.models_dir is None:
            self.models_dir = self.base_dir / "models"
        if self.reports_dir is None:
            self.reports_dir = self.base_dir / "reports"
        if self.cache_dir is None:
            self.cache_dir = self.base_dir / "cache"
        if self.logs_dir is None:
            self.logs_dir = self.base_dir / "logs"

    def ensure_directories(self) -> None:
        """Garante que todos os diretórios necessários existam no sistema de arquivos."""
        for directory in [
            self.data_dir,
            self.models_dir,
            self.reports_dir,
            self.cache_dir,
            self.logs_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def migrate_legacy_data(self, legacy_cwd: Optional[Path | str] = None) -> bool:
        """
        Garante compatibilidade retroativa com instalações anteriores:
        Se existir uma pasta 'data/' no diretório de trabalho atual (cwd) ou caminho informado,
        detecta seus dados e realiza a migração transparente dos arquivos
        (banco SQLite, chave de licença, configurações, credenciais de primeiro login, backups)
        e também logs e modelos para os novos diretórios padrão do usuário (%APPDATA%),
        emitindo avisos explicativos no log.
        """
        logger = logging.getLogger("AppConfigMigration")
        cwd_path = Path(legacy_cwd) if legacy_cwd else Path.cwd()
        legacy_data = cwd_path / "data"

        # Se a pasta data/ não existe ou coincide exatamente com self.data_dir, nada a migrar
        if not legacy_data.is_dir():
            return False

        try:
            if legacy_data.resolve() == self.data_dir.resolve():
                return False
        except Exception:
            pass

        # Verifica marcador de migração prévia para evitar reprocessamento desnecessário
        migration_marker = legacy_data / ".migrated_to_appdata"
        if migration_marker.exists():
            return False

        self.ensure_directories()
        migrated_any = False

        logger.info(
            f"Detectada pasta de dados legada em '{legacy_data}'. "
            f"Iniciando migração automática para '{self.data_dir}'..."
        )

        # 1. Migração do banco de dados SQLite principal
        legacy_db = legacy_data / "solarguard.sqlite3"
        if legacy_db.is_file() and not self.db_path.exists():
            try:
                shutil.copy2(legacy_db, self.db_path)
                logger.info(f"[Migração] Banco de dados SQLite copiado com sucesso: '{legacy_db}' -> '{self.db_path}'.")
                migrated_any = True
                # Copiar arquivos de journal WAL/SHM se existirem
                for ext in ["-wal", "-shm"]:
                    extra_src = legacy_data / f"solarguard.sqlite3{ext}"
                    extra_dst = self.data_dir / f"solarguard.sqlite3{ext}"
                    if extra_src.is_file() and not extra_dst.exists():
                        shutil.copy2(extra_src, extra_dst)
            except Exception as ex:
                logger.error(f"[Migração] Erro ao copiar banco de dados SQLite: {ex}")

        # 2. Migração da chave de licença
        legacy_license = legacy_data / "license.key"
        target_license = self.data_dir / "license.key"
        if legacy_license.is_file() and not target_license.exists():
            try:
                shutil.copy2(legacy_license, target_license)
                logger.info(f"[Migração] Chave de licença copiada: '{legacy_license}' -> '{target_license}'.")
                migrated_any = True
            except Exception as ex:
                logger.error(f"[Migração] Erro ao copiar chave de licença: {ex}")

        # 3. Migração do arquivo de configurações (settings.json)
        legacy_settings = legacy_data / "settings.json"
        target_settings = self.data_dir / "settings.json"
        if legacy_settings.is_file() and not target_settings.exists():
            try:
                shutil.copy2(legacy_settings, target_settings)
                logger.info(f"[Migração] Configurações copiadas: '{legacy_settings}' -> '{target_settings}'.")
                migrated_any = True
            except Exception as ex:
                logger.error(f"[Migração] Erro ao copiar configurações: {ex}")

        # 4. Migração do arquivo de primeiro acesso (admin_first_login.txt)
        legacy_admin_notice = legacy_data / "admin_first_login.txt"
        target_admin_notice = self.data_dir / "admin_first_login.txt"
        if legacy_admin_notice.is_file() and not target_admin_notice.exists():
            try:
                shutil.copy2(legacy_admin_notice, target_admin_notice)
                logger.info(f"[Migração] Credenciais de primeiro acesso copiadas para '{target_admin_notice}'.")
                migrated_any = True
            except Exception as ex:
                logger.error(f"[Migração] Erro ao copiar credenciais de primeiro acesso: {ex}")

        # 5. Migração de backups existentes
        legacy_backups = legacy_data / "backups"
        target_backups = self.data_dir / "backups"
        if legacy_backups.is_dir():
            target_backups.mkdir(parents=True, exist_ok=True)
            for item in legacy_backups.iterdir():
                if item.is_file() and not (target_backups / item.name).exists():
                    try:
                        shutil.copy2(item, target_backups / item.name)
                        logger.info(f"[Migração] Backup copiado: '{item.name}'.")
                        migrated_any = True
                    except Exception as ex:
                        logger.warning(f"[Migração] Não foi possível copiar backup '{item.name}': {ex}")

        # 6. Migração de logs legados
        legacy_logs = cwd_path / "logs"
        try:
            if legacy_logs.is_dir() and legacy_logs.resolve() != self.logs_dir.resolve():
                for log_file in legacy_logs.glob("*.log*"):
                    target_log = self.logs_dir / log_file.name
                    if not target_log.exists():
                        try:
                            shutil.copy2(log_file, target_log)
                            migrated_any = True
                        except Exception as ex:
                            logger.warning(f"[Migração] Não foi possível copiar log '{log_file.name}': {ex}")
        except Exception:
            pass

        # 7. Migração de modelos legados (ex.: best.pt na pasta models/ do cwd)
        legacy_models = cwd_path / "models"
        try:
            if legacy_models.is_dir() and legacy_models.resolve() != self.models_dir.resolve():
                for model_file in legacy_models.glob("*.pt"):
                    target_model = self.models_dir / model_file.name
                    if not target_model.exists():
                        try:
                            shutil.copy2(model_file, target_model)
                            logger.info(f"[Migração] Modelo de pesos copiado: '{model_file.name}'.")
                            migrated_any = True
                        except Exception as ex:
                            logger.warning(f"[Migração] Não foi possível copiar modelo '{model_file.name}': {ex}")
        except Exception:
            pass

        # Marcação de conclusão da migração
        try:
            migration_marker.write_text(
                f"Migrated to {self.data_dir} successfully.\n",
                encoding="utf-8",
            )
        except Exception:
            pass

        if migrated_any:
            logger.info(f"[Migração] Migração de dados legados concluída com sucesso para '{self.base_dir}'.")

        return migrated_any


# Instância singleton padrão de configuração
settings = AppConfig()
