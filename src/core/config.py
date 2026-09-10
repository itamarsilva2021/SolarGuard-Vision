"""
Configurações centrais da aplicação SolarGuard Vision.
Gerenciamento de caminhos de arquivos, banco de dados SQLite e diretórios de execução.
"""

from pathlib import Path
from dataclasses import dataclass, field
import os


@dataclass
class AppConfig:
    """Configurações globais de caminhos e parâmetros do sistema SolarGuard Vision."""

    app_name: str = "SolarGuard Vision"
    app_version: str = "1.0.0"

    # Diretório Base da Aplicação
    base_dir: Path = field(default_factory=lambda: Path(os.getcwd()))

    # Diretórios de Dados Persistentes
    data_dir: Path = field(default_factory=lambda: Path(os.getcwd()) / "data")
    db_path: Path = field(default_factory=lambda: Path(os.getcwd()) / "data" / "solarguard.sqlite3")
    models_dir: Path = field(default_factory=lambda: Path(os.getcwd()) / "models")
    reports_dir: Path = field(default_factory=lambda: Path(os.getcwd()) / "reports")
    cache_dir: Path = field(default_factory=lambda: Path(os.getcwd()) / "cache")
    logs_dir: Path = field(default_factory=lambda: Path(os.getcwd()) / "logs")

    # Parâmetros Térmicos Padrão do DJI Matrice 4T
    default_emissivity: float = 0.95       # Vidro de módulo fotovoltaico
    default_distance_meters: float = 25.0  # Voo padrão
    default_confidence_threshold: float = 0.40

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


# Instância singleton padrão de configuração
settings = AppConfig()
