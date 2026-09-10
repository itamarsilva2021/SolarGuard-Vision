"""
Mecanismo de Tratamento Global de Exceções Não Tratadas, Crash Reporting e Diagnóstico para Windows.
Garante que falhas catastróficas gerem relatórios periciais de diagnóstico em disco sem corromper dados.
"""

import sys
import os
import traceback
import platform
import threading
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("CrashReporter")


class CrashReporter:
    """
    Capturador e registrador global de exceções e falhas fatais do sistema.
    """

    def __init__(self, crash_dir: Optional[Path | str] = None) -> None:
        self.crash_dir = Path(crash_dir) if crash_dir else settings.logs_dir / "crashes"
        self.crash_dir.mkdir(parents=True, exist_ok=True)
        self._installed = False

    def install(self) -> None:
        """Instala os ganchos globais de exceção no Python e nas threads secundárias."""
        if self._installed:
            return

        sys.excepthook = self.handle_sys_exception
        if hasattr(threading, "excepthook"):
            threading.excepthook = self.handle_thread_exception

        self._installed = True
        logger.info("Tratamento global de exceções instalado com sucesso.")

    def handle_sys_exception(self, exc_type, exc_value, exc_traceback) -> None:
        """Callback acionado em exceções não tratadas da thread principal."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        self._save_crash_dump(
            thread_name="MainThread",
            exc_type=exc_type.__name__,
            exc_message=str(exc_value),
            tb_lines=traceback.format_exception(exc_type, exc_value, exc_traceback),
        )

    def handle_thread_exception(self, args) -> None:
        """Callback acionado em exceções não tratadas de threads de background (YOLO, worker threads)."""
        thread_name = args.thread.name if args.thread else "UnknownThread"
        self._save_crash_dump(
            thread_name=thread_name,
            exc_type=args.exc_type.__name__,
            exc_message=str(args.exc_value),
            tb_lines=traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback),
        )

    def _save_crash_dump(
        self,
        thread_name: str,
        exc_type: str,
        exc_message: str,
        tb_lines: list[str],
    ) -> Path:
        """Grava arquivo JSON detalhado de diagnóstico em disco e emite log crítico."""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_file = self.crash_dir / f"crash_{timestamp_str}.json"

        crash_data = {
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "timestamp": datetime.now().isoformat(),
            "thread": thread_name,
            "exception_type": exc_type,
            "exception_message": exc_message,
            "system_info": {
                "os": platform.system(),
                "os_release": platform.release(),
                "os_version": platform.version(),
                "architecture": platform.architecture()[0],
                "processor": platform.processor(),
                "python_version": platform.python_version(),
            },
            "traceback": "".join(tb_lines),
        }

        try:
            dump_file.write_text(json.dumps(crash_data, indent=4, ensure_ascii=False), encoding="utf-8")
            logger.critical(
                f"FALHA CRÍTICA NÃO TRATADA [{exc_type}]: {exc_message}. Relatório gerado em: {dump_file}"
            )
        except Exception as io_err:
            logger.critical(f"Erro ao gravar crash dump: {io_err}. Falha original: {exc_message}")

        return dump_file
