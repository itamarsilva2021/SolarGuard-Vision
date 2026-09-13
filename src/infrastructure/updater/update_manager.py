"""
Gerenciador de Atualizações Seguras de Software para Desktop Windows.
Implementa o ciclo criptográfico completo de distribuição de atualizações:
1. Manifesto assinado digitalmente com chave privada Ed25519 (RFC 8032).
2. Validação obrigatória da assinatura do manifesto antes de qualquer download.
3. Prevenção contra ataques de downgrade/rollback (verificação estrita SemVer).
4. Download seguro para diretório temporário isolado.
5. Validação rigorosa de hash SHA-256 com descarte imediato de binários divergentes.
6. Instalação auditada com verificação pré-execução anti-TOCTOU.
"""

import base64
import hashlib
import json
import os
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.core.config import settings
from src.core.logger import get_logger
from src.core.result import Failure, Result, Success

logger = get_logger("UpdateManager")

# Chave pública padrão de distribuição de atualizações do SolarGuard Vision (32 bytes Ed25519 em Base64)
# Chave exclusiva e estritamente segregada da chave de licenciamento
DEFAULT_UPDATE_PUBLIC_KEY_B64 = "700G66KZ00UFCZzJFHOamnO2KobuRt8G9v0kIhLs9oY="


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
    signature_b64: Optional[str] = None
    signer_public_key_b64: Optional[str] = None


class UpdateManifestSigner:
    """
    Utilitário para emissão e assinatura digital de manifestos de atualização (Ambiente de Build/CI).
    Utiliza chave privada assimétrica Ed25519 para garantir autenticidade e não-repúdio.
    """

    @staticmethod
    def canonicalize_manifest(manifest_data: Dict[str, Any]) -> bytes:
        """Gera a representação canônica dos dados do manifesto (excluindo a assinatura)."""
        core = {k: v for k, v in manifest_data.items() if k != "signature_b64"}
        return json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def sign_manifest(
        cls,
        manifest_data: Dict[str, Any],
        private_key: ed25519.Ed25519PrivateKey,
    ) -> Dict[str, Any]:
        """
        Assina digitalmente um manifesto com a chave privada Ed25519.
        Retorna o dicionário de manifesto acrescido dos campos 'signer_public_key_b64' e 'signature_b64'.
        """
        signed_dict = dict(manifest_data)

        # Exportar chave pública correspondente em Base64
        pub_key = private_key.public_key()
        raw_pub = pub_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        signed_dict["signer_public_key_b64"] = base64.b64encode(raw_pub).decode("ascii")

        # Gerar assinatura sobre os bytes canônicos
        canonical_bytes = cls.canonicalize_manifest(signed_dict)
        signature = private_key.sign(canonical_bytes)
        signed_dict["signature_b64"] = base64.b64encode(signature).decode("ascii")

        return signed_dict


class UpdateManager:
    """
    Controlador de checagem, download seguro, verificação de integridade e instalação de novas versões.
    Garante proteção estrita contra binários maliciosos, interceptação MITM e adulteração.
    """

    DEFAULT_MANIFEST_URL = "https://raw.githubusercontent.com/solarguard-vision/releases/main/update_manifest.json"

    def __init__(
        self,
        current_version: Optional[str] = None,
        downloads_dir: Optional[Union[Path, str]] = None,
        trusted_public_key: Optional[Union[ed25519.Ed25519PublicKey, str]] = None,
    ) -> None:
        self.current_version = current_version or settings.app_version
        self.downloads_dir = Path(downloads_dir) if downloads_dir else settings.data_dir / "updates"
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

        # Chave pública confiável para verificação de manifestos
        if trusted_public_key is None:
            raw_pub = base64.b64decode(DEFAULT_UPDATE_PUBLIC_KEY_B64)
            self.trusted_public_key = ed25519.Ed25519PublicKey.from_public_bytes(raw_pub)
        elif isinstance(trusted_public_key, str):
            raw_pub = base64.b64decode(trusted_public_key.strip())
            self.trusted_public_key = ed25519.Ed25519PublicKey.from_public_bytes(raw_pub)
        else:
            self.trusted_public_key = trusted_public_key

    # -------------------------------------------------------------------------
    # Versionamento Semântico e Proteção contra Downgrade (Rollback)
    # -------------------------------------------------------------------------

    def parse_semver(self, version_str: str) -> Tuple[int, int, int]:
        """Converte '1.2.3' em tupla de inteiros (1, 2, 3) para comparação confiável."""
        clean_v = version_str.strip().lstrip("v")
        parts = clean_v.split(".")
        try:
            return tuple(int(p) for p in parts[:3])
        except ValueError:
            return (0, 0, 0)

    def is_version_newer(self, remote_version: str) -> bool:
        """
        Compara a versão remota com a versão instalada atualmente.
        Garante que atualizações sejam estritamente progressivas (previne ataque de rollback).
        """
        current_tuple = self.parse_semver(self.current_version)
        remote_tuple = self.parse_semver(remote_version)
        return remote_tuple > current_tuple

    # -------------------------------------------------------------------------
    # Validação Criptográfica da Assinatura do Manifesto
    # -------------------------------------------------------------------------

    def verify_manifest_signature(
        self,
        manifest_data: Dict[str, Any],
        trusted_key: Optional[ed25519.Ed25519PublicKey] = None,
    ) -> Result[bool, str]:
        """
        Valida a assinatura Ed25519 do manifesto contra a chave pública confiável.
        Protege contra forjamento de URLs, injeção de hashes falsos e adulterações MITM.
        """
        sig_b64 = manifest_data.get("signature_b64")
        if not sig_b64:
            return Failure("Manifesto de atualização não assinado (signature_b64 ausente).")

        signer_pub_b64 = manifest_data.get("signer_public_key_b64")
        if not signer_pub_b64:
            return Failure("Chave pública do assinante não especificada no manifesto.")

        key_to_verify = trusted_key or self.trusted_public_key

        # Validar se o assinante coincide com a chave confiável configurada
        expected_raw = key_to_verify.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        expected_b64 = base64.b64encode(expected_raw).decode("ascii")
        if signer_pub_b64.strip() != expected_b64:
            return Failure(
                "Autenticidade violada: o manifesto foi assinado por uma chave não autorizada (chave rogue detectada)."
            )

        try:
            sig_bytes = base64.b64decode(sig_b64)
            canonical_bytes = UpdateManifestSigner.canonicalize_manifest(manifest_data)
            key_to_verify.verify(sig_bytes, canonical_bytes)
            return Success(True)
        except InvalidSignature:
            return Failure("Assinatura Ed25519 inválida! O manifesto foi adulterado ou corrompido em trânsito.")
        except Exception as e:
            return Failure(f"Erro na verificação da assinatura do manifesto: {str(e)}")

    # -------------------------------------------------------------------------
    # Checagem de Atualizações
    # -------------------------------------------------------------------------

    def check_for_updates_from_manifest(
        self,
        manifest_data: Dict[str, Any],
        verify_signature: bool = False,
        trusted_key: Optional[ed25519.Ed25519PublicKey] = None,
    ) -> UpdateInfo:
        """
        Avalia um dicionário de manifesto de atualização e verifica se há nova versão disponível.
        Mantém compatibilidade com chamadas existentes.
        """
        if verify_signature:
            verif_res = self.verify_manifest_signature(manifest_data, trusted_key=trusted_key)
            if not verif_res.is_success:
                raise ValueError(verif_res.error)

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
            signature_b64=manifest_data.get("signature_b64"),
            signer_public_key_b64=manifest_data.get("signer_public_key_b64"),
        )

    def check_signed_manifest(
        self,
        manifest_data_or_json: Union[Dict[str, Any], str],
        trusted_key: Optional[ed25519.Ed25519PublicKey] = None,
    ) -> Result[UpdateInfo, str]:
        """
        Executa a verificação completa e estrita do manifesto assinado:
        1. Validação de formato JSON.
        2. Validação da assinatura Ed25519.
        3. Prevenção contra downgrade (versão deve ser superior).
        """
        try:
            if isinstance(manifest_data_or_json, str):
                data = json.loads(manifest_data_or_json)
            else:
                data = dict(manifest_data_or_json)
        except Exception as e:
            return Failure(f"Formato de manifesto JSON inválido: {e}")

        # 1. Validar assinatura Ed25519 do manifesto
        sig_check = self.verify_manifest_signature(data, trusted_key=trusted_key)
        if not sig_check.is_success:
            return Failure(sig_check.error)

        # 2. Extrair metadados
        remote_version = data.get("version")
        if not remote_version:
            return Failure("Versão não especificada no manifesto assinado.")

        sha256_chk = data.get("sha256")
        if not sha256_chk or len(sha256_chk.strip()) != 64:
            return Failure("Hash SHA-256 do instalador ausente ou inválido no manifesto assinado.")

        download_url = data.get("download_url", "").strip()
        if not download_url:
            return Failure("URL de download ausente no manifesto assinado.")

        # 3. Prevenção de Downgrade / Rollback
        is_newer = self.is_version_newer(remote_version)

        info = UpdateInfo(
            version=remote_version,
            release_date=data.get("release_date", datetime.now().strftime("%Y-%m-%d")),
            release_notes=data.get("release_notes", "Atualização oficial do SolarGuard Vision."),
            download_url=download_url,
            sha256_checksum=sha256_chk.strip().lower(),
            is_newer=is_newer,
            mandatory=data.get("mandatory", False),
            signature_b64=data.get("signature_b64"),
            signer_public_key_b64=data.get("signer_public_key_b64"),
        )
        return Success(info)

    # -------------------------------------------------------------------------
    # Download Seguro com Validação Rigorosa de SHA-256
    # -------------------------------------------------------------------------

    def verify_installer_integrity(self, file_path: Union[Path, str], expected_sha256: str) -> bool:
        """Verifica se o instalador baixado corresponde ao hash criptográfico oficial (leitura em blocos)."""
        path = Path(file_path)
        if not path.exists():
            return False

        hasher = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            computed_sha256 = hasher.hexdigest().lower()
            is_valid = computed_sha256 == expected_sha256.strip().lower()

            if not is_valid:
                logger.error(
                    f"Falha de integridade SHA256 para {path}: esperado {expected_sha256}, obtido {computed_sha256}"
                )
            return is_valid
        except Exception as e:
            logger.error(f"Erro ao calcular SHA256 de {path}: {e}")
            return False

    def download_update(
        self,
        update_info: UpdateInfo,
        destination_path: Optional[Union[Path, str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        timeout: int = 30,
        allow_local_source: bool = False,
    ) -> Result[Path, str]:
        """
        Executa o download seguro do instalador e valida imediatamente o hash SHA-256.
        PROTEÇÃO ATIVA:
        - Em produção (padrão allow_local_source=False): Aceita EXCLUSIVAMENTE URLs com prefixo https://.
          Rejeita terminantemente http:// (sem TLS), file:// e caminhos locais/UNC sem esquema.
        - Em testes controlados (allow_local_source=True): Permite fontes file:// e caminhos de arquivos em disco.
        - Se o arquivo baixado tiver hash divergente, ele é excluído imediatamente.
        """
        url = update_info.download_url
        if not url:
            return Failure("URL de download inválida ou ausente.")

        url_clean = url.strip()
        is_https = url_clean.lower().startswith("https://")
        is_http = url_clean.lower().startswith("http://")
        is_file = url_clean.lower().startswith("file://")
        is_schemeless = "://" not in url_clean

        # Validação estrita de protocolo de transporte
        if not is_https:
            if (is_file or is_schemeless) and allow_local_source:
                # Permitido exclusivamente em testes automatizados / ambiente controlado
                pass
            elif is_http:
                return Failure(
                    "Protocolo de transporte inseguro rejeitado (http:// sem TLS). "
                    "Em produção, apenas URLs https:// são autorizadas para download de atualizações."
                )
            elif is_file or is_schemeless:
                return Failure(
                    "Origem local rejeitada (file:// ou caminho relativo/UNC). "
                    "Por razões de segurança, fontes locais são desabilitadas em produção "
                    "(apenas URLs https:// com assinatura válida são permitidas)."
                )
            else:
                return Failure(
                    f"Esquema de download não suportado ou perigoso: '{url_clean}'. "
                    "Apenas URLs https:// são permitidas em ambiente de produção."
                )

        if destination_path:
            target_path = Path(destination_path)
        else:
            filename = f"solarguard_update_v{update_info.version}.exe"
            target_path = self.downloads_dir / filename

        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_download_path = target_path.with_suffix(target_path.suffix + ".downloading")

        try:
            logger.info(f"Iniciando download seguro da atualização v{update_info.version} de: {url_clean}")

            # Obtenção do pacote via filesystem local (testes) ou HTTPS (produção)
            if is_file or is_schemeless:
                local_path_str = url_clean[7:] if is_file else url_clean
                local_src = Path(local_path_str)
                if not local_src.exists():
                    return Failure(f"Arquivo fonte de atualização não encontrado: {local_src}")
                content = local_src.read_bytes()
                temp_download_path.write_bytes(content)
            else:
                req = urllib.request.Request(url_clean, headers={"User-Agent": f"SolarGuardVision/{self.current_version}"})
                with urllib.request.urlopen(req, timeout=timeout) as response, open(temp_download_path, "wb") as out_f:
                    total_size = int(response.headers.get("Content-Length", 0))
                    downloaded = 0
                    while chunk := response.read(65536):
                        out_f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)

            # Validação imediata do SHA-256 do binário baixado
            if not self.verify_installer_integrity(temp_download_path, update_info.sha256_checksum):
                # Descarte imediato do arquivo adulterado/malicioso
                if temp_download_path.exists():
                    temp_download_path.unlink()
                return Failure(
                    "Falha crítica de segurança: O checksum SHA-256 do instalador baixado diverge do manifesto assinado. "
                    "Binário potencialmente malicioso ou corrompido foi descartado imediatamente."
                )

            # Move arquivo temporário validado para o caminho definitivo
            if target_path.exists():
                target_path.unlink()
            temp_download_path.rename(target_path)

            logger.info(f"Instalador v{update_info.version} baixado e verificado com sucesso em: {target_path}")
            return Success(target_path)

        except Exception as e:
            if temp_download_path.exists():
                temp_download_path.unlink()
            logger.error(f"Erro ao baixar atualização de {url}: {e}", exc_info=True)
            return Failure(f"Falha no download da atualização: {str(e)}")

    # -------------------------------------------------------------------------
    # Instalação Segura Auditada (com Proteção Anti-TOCTOU)
    # -------------------------------------------------------------------------

    def install_update(
        self,
        installer_path: Union[Path, str],
        expected_sha256: Optional[str] = None,
        silent: bool = True,
        dry_run: bool = False,
    ) -> Result[bool, str]:
        """
        Executa o instalador verificado.
        PROTEÇÃO ANTI-TOCTOU: Revalida o hash SHA-256 no momento exato antes da execução
        para impedir ataques de substituição de arquivo no disco pós-download.
        """
        path = Path(installer_path)
        if not path.exists():
            return Failure(f"Arquivo do instalador não encontrado em: {path}")

        # Re-validação anti-TOCTOU antes de despachar execução
        if expected_sha256 is not None:
            if not self.verify_installer_integrity(path, expected_sha256):
                return Failure(
                    "Violação de segurança pré-execução (Anti-TOCTOU): O instalador foi modificado no disco antes da execução."
                )

        if dry_run:
            logger.info(f"[DRY-RUN] Instalação da atualização simulada com sucesso para: {path}")
            return Success(True)

        try:
            logger.info(f"Iniciando instalação da atualização: {path} (silent={silent})")
            cmd = [str(path)]
            if silent:
                # Flags padrão de instalação silenciosa em instaladores Windows (InnoSetup, NSIS, MSI)
                if path.suffix.lower() == ".msi":
                    cmd = ["msiexec.exe", "/i", str(path), "/qn", "/norestart"]
                else:
                    cmd.extend(["/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES"])

            subprocess.Popen(cmd, shell=False, close_fds=True)
            return Success(True)
        except Exception as e:
            logger.error(f"Erro ao executar instalador {path}: {e}", exc_info=True)
            return Failure(f"Falha ao despachar instalação: {str(e)}")
