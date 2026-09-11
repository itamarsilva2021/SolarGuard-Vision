"""
Ponto de Entrada Principal (Entrypoint) do SolarGuard Vision para Desktop Windows.
Inicializa tratamento global de exceções, checagem de licença, banco de dados e interface PySide6.
"""

import sys
import argparse
from pathlib import Path

# 1. Instalar tratamento global de exceções de primeira ordem antes de qualquer outra rotina
from src.infrastructure.diagnostics.crash_reporter import CrashReporter
crash_reporter = CrashReporter()
crash_reporter.install()

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.config.settings_manager import SettingsManager
from src.infrastructure.security.license_manager import LicenseManager
from src.infrastructure.database.connection import DatabaseManager

logger = get_logger("Main")


def parse_args():
    parser = argparse.ArgumentParser(description="SolarGuard Vision - Inspeção Termográfica Fotovoltaica Inteligente")
    parser.add_argument("--check-system", action="store_true", help="Executa diagnóstico de integridade do sistema e encerra")
    parser.add_argument("--version", action="store_true", help="Exibe a versão do software")
    parser.add_argument("--hwid", action="store_true", help="Exibe o Hardware Fingerprint desta máquina para licenciamento")
    return parser.parse_args()


def run_system_check() -> int:
    """Executa checagem de componentes e saúde da instalação."""
    print("=" * 65)
    print(f"       SOLARGUARD VISION v{settings.app_version} - DIAGNÓSTICO DE SISTEMA")
    print("=" * 65)

    settings_mgr = SettingsManager()
    cfg = settings_mgr.get_settings()
    print(f"[+] Versão da Aplicação: {settings.app_version}")
    print(f"[+] Idioma configurado: {cfg.language}")
    print(f"[+] Tema ativo: {cfg.theme}")

    # Verificar banco de dados
    settings.ensure_directories()
    db = DatabaseManager()
    db.initialize_schema()
    print(f"[+] Banco de dados SQLite operacional em: {settings.db_path}")

    # Verificar licença
    lic_mgr = LicenseManager()
    lic_info = lic_mgr.check_current_license()
    print(f"[+] HWID desta máquina: {lic_info.machine_fingerprint}")
    print(f"[+] Licença: {lic_info.license_type.display_name} ({lic_info.status_message})")

    print("[+] Todos os subsistemas operacionais e validados com sucesso.")
    print("=" * 65)
    return 0


def main():
    args = parse_args()

    if args.version:
        print(f"{settings.app_name} v{settings.app_version}")
        sys.exit(0)

    if args.hwid:
        lic_mgr = LicenseManager()
        print(f"HWID: {lic_mgr.get_current_machine_fingerprint()}")
        sys.exit(0)

    if args.check_system:
        sys.exit(run_system_check())

    logger.info(f"Iniciando {settings.app_name} v{settings.app_version}...")
    settings.ensure_directories()

    # Inicializar banco de dados SQLite
    db = DatabaseManager()
    db.initialize_schema()

    # Validação de Licença
    lic_mgr = LicenseManager()
    lic_info = lic_mgr.check_current_license()
    logger.info(f"Status da Licença: {lic_info.license_type.display_name} - {lic_info.status_message}")

    # Inicialização da interface gráfica PySide6
    try:
        from PySide6.QtWidgets import QApplication
        from src.presentation.main_window import MainWindow

        app = QApplication(sys.argv)
        app.setApplicationName(settings.app_name)
        app.setApplicationVersion(settings.app_version)

        logger.info("Módulo gráfico PySide6 inicializado com sucesso.")

        window = MainWindow(db)
        window.show()
        sys.exit(app.exec())

    except ImportError:
        logger.warning("PySide6 não disponível para modo gráfico desktop. Executando em modo headless.")
        run_system_check()
        sys.exit(0)


if __name__ == "__main__":
    main()
