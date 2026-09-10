"""
Gerenciador de Atualizações de Software e Verificação de Novas Versões para Desktop Windows.
Suporta versionamento semântico (SemVer), download seguro e verificação de checksum SHA256.
"""

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import urllib.request
import subprocess

from src.core.config import settings
from src.core.logger import get_logger
from src.core.result import Result, Success, Failure

logger = get_logger("UpdateManager")


@dataclass
class UpdateInfo:
    """Metadados de uma versão de atualização do SolarGuard Vision."""
    version: str
    release_date: str
    release_notes: str
    download_url: str
    sha256_checksum: str
    is_newer: bool
    mandatory: bool = False


class UpdateManager:
    """
    Controlador de checagem, download e verificação de integridade de novas versões.
    """

    # URL padrão de verificação de atualizações (ou mock para rede isolada)
    DEFAULT_MANIFEST_URL = "https://raw.githubusercontent.com/solarguard-vision/releases/main/update_manifest.json"

    def __init__(self, current_version: Optional[str] = None, downloads_dir: Optional[Path | str] = None) -> None:
        self.current_version = current_version or settings.app_version
        self.downloads_dir = Path(downloads_dir) if downloads_dir else settings.data_dir / "updates"
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

    def parse_semver(self, version_str: str) -> Tuple[int, int, int]:
        """Converte '1.2.3' em tupla de inteiros (1, 2, 3) para comparação confiável."""
        clean_v = version_str.strip().lstrip("v")
        parts = clean_v.split(".")
        try:
            return tuple(int(p) for p in parts[:3])
        except ValueError:
            return (0, 0, 0)

    def is_version_newer(self, remote_version: str) -> bool:
        """Compara a versão remota com a versão instalada atualmente."""
        current_tuple = self.parse_semver(self.current_version)
        remote_tuple = self.parse_semver(remote_version)
        return remote_tuple > current_tuple

    def check_for_updates_from_manifest(self, manifest_data: Dict[str, Any]) -> UpdateInfo:
        """
        Avalia um dicionário de manifesto de atualização e verifica se há nova versão disponível.
        """
        remote_version = manifest_data.get("version", "0.0.0")
        is_newer = self.is_version_newer(remote_version)

        return UpdateInfo(
            version=remote_version,
            release_date=manifest_data.get("release_date", datetime.now().strftime("%Y-%m-%d")),
            release_notes=manifest_data.get("release_notes", "Atualização geral de estabilidade e novos modelos IA."),
            download_url=manifest_data.get("download_url", ""),
            sha256_checksum=manifest_data.get("sha256", ""),
            is_newer=is_newer,
            mandatory=manifest_data.get("mandatory", False),
        )

    def verify_installer_integrity(self, file_path: Path | str, expected_sha256: str) -> bool:
        """Verifica se o instalador baixado corresponde ao hash criptográfico oficial."""
        path = Path(file_path)
        if not path.exists():
            return False

        file_bytes = path.read_bytes()
        computed_sha256 = hashlib.sha256(file_bytes).hexdigest().lower()
        is_valid = computed_sha256 == expected_sha256.strip().lower()

        if not is_valid:
            logger.error(f"Falha de integridade SHA256 para {path}: esperado {expected_sha256}, obtido {computed_sha256}")
        return is_valid
