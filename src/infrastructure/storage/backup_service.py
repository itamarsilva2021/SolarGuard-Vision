"""
Serviço de Backup Automatizado, Restauração Segura e Rotação de Snapshots do Banco SQLite.
Protege os dados de inspeções, clientes, usinas e termogramas contra perdas acidentais.
"""

import zipfile
import shutil
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Union

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.core.config import settings
from src.core.logger import get_logger
from src.core.result import Result, Success, Failure
from src.infrastructure.security.secure_package import SecurePackageManager

logger = get_logger("BackupService")


class BackupService:
    """
    Gerenciador de snapshots compactados e restauração de dados para o SolarGuard Vision.
    """

    def __init__(
        self,
        backup_dir: Optional[Path | str] = None,
        db_path: Optional[Path | str] = None,
    ) -> None:
        self.backup_dir = Path(backup_dir) if backup_dir else settings.data_dir / "backups"
        self.db_path = Path(db_path) if db_path else settings.db_path
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, custom_label: Optional[str] = None) -> Result[Path, str]:
        """
        Cria um arquivo .zip compactado contendo o banco de dados SQLite e metadados de integridade.
        """
        if not self.db_path.exists():
            return Failure(f"Banco de dados não encontrado em: {self.db_path}")

        try:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            label_suffix = f"_{custom_label}" if custom_label else ""
            zip_filename = f"backup_solarguard_{timestamp_str}{label_suffix}.zip"
            zip_path = self.backup_dir / zip_filename

            # Calcular SHA256 do banco original
            db_bytes = self.db_path.read_bytes()
            db_sha256 = hashlib.sha256(db_bytes).hexdigest()

            # Criar manifesto informativo
            manifest = {
                "app_name": settings.app_name,
                "app_version": settings.app_version,
                "created_at": datetime.now().isoformat(),
                "db_filename": self.db_path.name,
                "db_size_bytes": len(db_bytes),
                "db_sha256": db_sha256,
                "custom_label": custom_label,
            }

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Inclui o banco de dados
                zf.writestr(self.db_path.name, db_bytes)
                # Inclui o manifesto
                zf.writestr("manifest.json", json.dumps(manifest, indent=4, ensure_ascii=False))

                # Inclui arquivo de configurações se existir
                settings_file = settings.data_dir / "settings.json"
                if settings_file.exists():
                    zf.writestr("settings.json", settings_file.read_bytes())

            logger.info(f"Backup criado com sucesso: {zip_path} ({zip_path.stat().st_size} bytes)")
            return Success(zip_path)

        except Exception as e:
            logger.error(f"Erro ao criar backup: {e}", exc_info=True)
            return Failure(f"Falha ao gerar backup: {str(e)}")

    def restore_backup(self, backup_zip_path: Path | str) -> Result[bool, str]:
        """
        Restaura o banco de dados a partir de um arquivo de backup .zip verificado.
        """
        path = Path(backup_zip_path)
        if not path.exists():
            return Failure(f"Arquivo de backup não encontrado: {path}")

        try:
            with zipfile.ZipFile(path, "r") as zf:
                # 1. Validar integridade do zip
                if zf.testzip() is not None:
                    return Failure("Arquivo de backup corrompido (falha no CRC32 do ZIP).")

                # 2. Ler manifesto
                if "manifest.json" not in zf.namelist():
                    return Failure("Arquivo de backup inválido: manifest.json ausente.")

                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                db_filename = manifest.get("db_filename", self.db_path.name)
                expected_sha256 = manifest.get("db_sha256")

                # 3. Ler dados do banco do ZIP e conferir SHA256
                restored_db_bytes = zf.read(db_filename)
                computed_sha256 = hashlib.sha256(restored_db_bytes).hexdigest()

                if expected_sha256 and computed_sha256 != expected_sha256:
                    return Failure("Checksum SHA256 do banco de dados não confere. Restauração abortada.")

                # 4. Criar snapshot de segurança do banco atual antes de sobrescrever
                if self.db_path.exists():
                    safety_copy = self.db_path.with_suffix(".pre_restore.bak")
                    shutil.copy2(self.db_path, safety_copy)

                # 5. Sobrescrever o banco com os dados restaurados
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                self.db_path.write_bytes(restored_db_bytes)

                # 6. Restaurar configurações se presentes no backup
                if "settings.json" in zf.namelist():
                    settings_file = settings.data_dir / "settings.json"
                    settings_file.write_bytes(zf.read("settings.json"))

            logger.info(f"Banco de dados restaurado com sucesso a partir de: {path}")
            return Success(True)

        except Exception as e:
            logger.error(f"Erro ao restaurar backup {path}: {e}", exc_info=True)
            return Failure(f"Falha na restauração do backup: {str(e)}")

    def create_secure_backup(
        self,
        passphrase: str,
        signing_key: ed25519.Ed25519PrivateKey,
        custom_label: Optional[str] = None,
    ) -> Result[Path, str]:
        """
        Cria um backup criptográfico blindado (.sgz) conjugando ZIP, AES-256-GCM e assinatura Ed25519.
        Garante confidencialidade, integridade e autenticidade.
        """
        if not self.db_path.exists():
            return Failure(f"Banco de dados não encontrado em: {self.db_path}")

        try:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            label_suffix = f"_{custom_label}" if custom_label else ""
            package_filename = f"backup_solarguard_{timestamp_str}{label_suffix}.sgz"
            package_path = self.backup_dir / package_filename

            db_bytes = self.db_path.read_bytes()
            db_sha256 = hashlib.sha256(db_bytes).hexdigest()

            manifest = {
                "app_name": settings.app_name,
                "app_version": settings.app_version,
                "created_at": datetime.now().isoformat(),
                "db_filename": self.db_path.name,
                "db_size_bytes": len(db_bytes),
                "db_sha256": db_sha256,
                "custom_label": custom_label,
                "encryption": "AES-256-GCM",
                "signature": "Ed25519",
            }

            virtual_files: Dict[str, Union[bytes, str]] = {
                self.db_path.name: db_bytes,
                "manifest.json": json.dumps(manifest, indent=4, ensure_ascii=False),
            }

            settings_file = settings.data_dir / "settings.json"
            if settings_file.exists():
                virtual_files["settings.json"] = settings_file.read_bytes()

            pkg_mgr = SecurePackageManager()
            res = pkg_mgr.pack(
                output_path=package_path,
                passphrase=passphrase,
                signing_key=signing_key,
                virtual_files=virtual_files,
                metadata=manifest,
            )
            return res
        except Exception as e:
            logger.error(f"Erro ao criar backup seguro: {e}", exc_info=True)
            return Failure(f"Falha ao gerar backup seguro: {str(e)}")

    def restore_secure_backup(
        self,
        package_path: Union[Path, str],
        passphrase: str,
        verify_key: Optional[ed25519.Ed25519PublicKey] = None,
    ) -> Result[bool, str]:
        """
        Restaura o banco de dados a partir de um backup seguro (.sgz) verificado com Ed25519 e AES-256.
        """
        pkg_file = Path(package_path)
        if not pkg_file.exists():
            return Failure(f"Arquivo de backup seguro não encontrado: {pkg_file}")

        temp_restore_dir = self.backup_dir / f".temp_restore_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        try:
            temp_restore_dir.mkdir(parents=True, exist_ok=True)

            pkg_mgr = SecurePackageManager()
            unpack_res = pkg_mgr.unpack(
                package_path=pkg_file,
                output_dir=temp_restore_dir,
                passphrase=passphrase,
                expected_public_key=verify_key,
            )
            if not unpack_res.is_success:
                shutil.rmtree(temp_restore_dir, ignore_errors=True)
                return Failure(unpack_res.error)

            manifest_file = temp_restore_dir / "manifest.json"
            if not manifest_file.exists():
                shutil.rmtree(temp_restore_dir, ignore_errors=True)
                return Failure("Arquivo de backup inválido: manifest.json ausente no container.")

            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            db_filename = manifest.get("db_filename", self.db_path.name)
            restored_db_file = temp_restore_dir / db_filename
            if not restored_db_file.exists():
                shutil.rmtree(temp_restore_dir, ignore_errors=True)
                return Failure(f"Arquivo do banco {db_filename} não encontrado no backup desempacotado.")

            # Conferir SHA256 do banco
            expected_sha256 = manifest.get("db_sha256")
            computed_sha256 = hashlib.sha256(restored_db_file.read_bytes()).hexdigest()
            if expected_sha256 and computed_sha256 != expected_sha256:
                shutil.rmtree(temp_restore_dir, ignore_errors=True)
                return Failure("Checksum SHA256 do banco de dados não confere. Restauração abortada.")

            # Snapshot de segurança antes de sobrescrever
            if self.db_path.exists():
                safety_copy = self.db_path.with_suffix(".pre_restore.bak")
                shutil.copy2(self.db_path, safety_copy)

            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(restored_db_file, self.db_path)

            settings_file = temp_restore_dir / "settings.json"
            if settings_file.exists():
                dest_settings = settings.data_dir / "settings.json"
                shutil.copy2(settings_file, dest_settings)

            shutil.rmtree(temp_restore_dir, ignore_errors=True)
            logger.info(f"Backup seguro restaurado com sucesso a partir de: {pkg_file}")
            return Success(True)

        except Exception as e:
            shutil.rmtree(temp_restore_dir, ignore_errors=True)
            logger.error(f"Erro ao restaurar backup seguro {pkg_file}: {e}", exc_info=True)
            return Failure(f"Falha na restauração do backup seguro: {str(e)}")

    def list_backups(self) -> List[Dict[str, Any]]:
        """Lista todos os arquivos de backup existentes (.zip e .sgz) ordenados do mais recente ao mais antigo."""
        backups = []
        files = list(self.backup_dir.glob("backup_solarguard_*.zip")) + list(self.backup_dir.glob("backup_solarguard_*.sgz"))
        for file in files:
            stat = file.stat()
            backups.append({
                "filename": file.name,
                "path": str(file),
                "size_bytes": stat.st_size,
                "is_secure": file.suffix.lower() == ".sgz",
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups

    def rotate_backups(self, keep_last: int = 10) -> int:
        """Remove backups antigos que excederem o limite configurado."""
        backups = self.list_backups()
        if len(backups) <= keep_last:
            return 0

        to_remove = backups[keep_last:]
        removed_count = 0
        for item in to_remove:
            try:
                Path(item["path"]).unlink()
                removed_count += 1
            except Exception as e:
                logger.warning(f"Não foi possível remover backup antigo {item['filename']}: {e}")

        logger.info(f"Rotação de backups concluída. {removed_count} arquivos antigos removidos.")
        return removed_count
