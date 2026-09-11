"""
Gerenciador de Configurações Operacionais, Preferências de Usuário e Parâmetros Industriais.
Permite customizar limiares normativos IEC, preferências de interface e diretórios de trabalho.
"""

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Dict, Any

from src.core.config import settings as global_settings
from src.core.logger import get_logger

logger = get_logger("SettingsManager")


@dataclass
class AppSettings:
    """Configurações e preferências do operador do SolarGuard Vision."""

    # Preferências Visuais e Idioma
    theme: str = "dark"                   # "dark" ou "light"
    language: str = "pt_BR"               # Português do Brasil
    default_palette: str = "ironbow"      # ironbow, rainbow, white_hot, black_hot, arctic

    # Parâmetros de Inferência e Inteligência Artificial
    confidence_threshold: float = 0.40    # Limiar mínimo de confiança YOLOv11 (0.0 a 1.0)
    device_preference: str = "auto"       # "auto", "cuda", "cpu"
    auto_detect_hotspots: bool = True     # Análise radiométrica automática pós-importação

    # Limiares Normativos IEC TS 62446-3 (°C)
    iec_delta_t_low: float = 3.0          # Classe 1: >= 3°C
    iec_delta_t_medium: float = 10.0      # Classe 2: >= 10°C
    iec_delta_t_critical: float = 30.0    # Classe 3: >= 30°C

    # Dados Corporativos para Emissão de Relatórios Técnicos
    company_name: str = "SolarGuard Vision - Engenharia Diagnóstica"
    company_document: str = "00.000.000/0001-00"
    company_email: str = "contato@solarguard.vision"
    default_inspector_name: str = "Engenheiro Termografista Nível 2"
    crea_art_number: str = "CREA / ART Registrada"

    # Backup Automático
    auto_backup_enabled: bool = True
    backup_retention_days: int = 30
    backup_frequency_hours: int = 24


class SettingsManager:
    """
    Controlador de leitura, escrita e validação do arquivo de configurações locais `settings.json`.
    """

    def __init__(self, config_file: Optional[Path | str] = None) -> None:
        self.config_file = Path(config_file) if config_file else global_settings.data_dir / "settings.json"
        self._current_settings: Optional[AppSettings] = None

    def get_settings(self) -> AppSettings:
        """Retorna as configurações ativas em memória ou carrega do disco."""
        if self._current_settings is None:
            self._current_settings = self.load_settings()
        return self._current_settings

    def load_settings(self) -> AppSettings:
        """Carrega as configurações salvas em arquivo JSON ou inicializa os valores padrão."""
        if not self.config_file.exists():
            logger.info("Arquivo de configurações não encontrado. Criando com valores padrão.")
            defaults = AppSettings()
            self.save_settings(defaults)
            return defaults

        try:
            content = self.config_file.read_text(encoding="utf-8")
            data = json.loads(content)
            # Filtra apenas chaves válidas de AppSettings
            valid_keys = {f.name for f in AppSettings.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in data.items() if k in valid_keys}
            loaded = AppSettings(**filtered_data)
            self._current_settings = loaded
            logger.info(f"Configurações carregadas com sucesso de: {self.config_file}")
            return loaded
        except Exception as e:
            logger.error(f"Erro ao ler configurações de {self.config_file}: {e}. Restaurando padrões.", exc_info=True)
            return AppSettings()

    def save_settings(self, new_settings: AppSettings) -> bool:
        """Persiste as configurações informadas no arquivo JSON local."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(asdict(new_settings), indent=4, ensure_ascii=False)
            self.config_file.write_text(payload, encoding="utf-8")
            self._current_settings = new_settings
            logger.info(f"Configurações salvas com sucesso em: {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar configurações em {self.config_file}: {e}", exc_info=True)
            return False

    def update(self, **kwargs) -> AppSettings:
        """Atualiza campos específicos das configurações e persiste no disco."""
        cfg = self.get_settings()
        for k, v in kwargs.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        self.save_settings(cfg)
        return cfg

    def reset_to_defaults(self) -> AppSettings:
        """Restaura todas as configurações para os padrões de fábrica."""
        defaults = AppSettings()
        self.save_settings(defaults)
        return defaults
