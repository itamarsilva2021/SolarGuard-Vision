"""
Sistema centralizado de logging para SolarGuard Vision.
Suporta logs no console e em arquivo rotativo na pasta logs/.
"""

import logging
import sys
from pathlib import Path
from src.core.config import settings


def get_logger(name: str) -> logging.Logger:
    """
    Retorna uma instância configurada de Logger para o componente especificado.
    
    :param name: Nome do módulo/classe que está gerando os logs.
    :return: Instância de logging.Logger formatada.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Formato limpo e informativo
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Handler de Console (Terminal)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Handler de Arquivo (se o diretório estiver pronto)
        try:
            settings.logs_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(
                settings.logs_dir / "solarguard.log",
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            # Não quebra caso não consiga criar o arquivo de log no momento inicial
            pass

    return logger
