"""
===============================================================================
ATENÇÃO - COMPONENTE EXCLUSIVO DE SERVIDOR (SERVER-SIDE TOOLING)
===============================================================================
ESTE ARQUIVO CONTÉM A AUTORIDADE DE EMISSÃO DE LICENÇAS E A CHAVE PRIVADA
Ed25519 DE LICENCIAMENTO.
ESTE MÓDULO NUNCA DEVE SER INCLUÍDO NO PACOTE OU INSTALADOR DISTRIBUÍDO AO CLIENTE.
A ÁRVORE DO CLIENTE (src/) DEVE CONTER EXCLUSIVAMENTE A CHAVE PÚBLICA DE VERIFICAÇÃO.
===============================================================================
"""

import os
import json
import base64
from datetime import datetime, timedelta
from typing import Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from pathlib import Path

from src.core.logger import get_logger
from src.infrastructure.security.license_manager import LicenseType

logger = get_logger("LicenseIssuer")


def _resolve_private_key() -> str:
    """
    Resolve a chave privada Ed25519 para emissão de licenças.
    Prioridade:
    1. Variável de ambiente SOLARGUARD_LICENSE_PRIV_KEY (cofre de segredos / CI/CD)
    2. Arquivo local seguro fora da árvore do Git (server_tools/keys/.local_only/license_private.key)
    """
    env_key = os.environ.get("SOLARGUARD_LICENSE_PRIV_KEY")
    if env_key:
        return env_key.strip()

    local_path = Path(__file__).resolve().parent / "keys" / ".local_only" / "license_private.key"
    if local_path.is_file():
        return local_path.read_text(encoding="utf-8").strip()

    alt_path = Path(__file__).resolve().parent / "keys" / "license_private.key"
    if alt_path.is_file():
        return alt_path.read_text(encoding="utf-8").strip()

    raise RuntimeError(
        "Chave privada Ed25519 de licenciamento não encontrada. "
        "Defina a variável de ambiente SOLARGUARD_LICENSE_PRIV_KEY no cofre/pipeline ou "
        "armazene a chave em server_tools/keys/.local_only/license_private.key."
    )


class LicenseIssuer:
    """
    Autoridade de Emissão de Licenças do Servidor.
    Assina digitalmente os payloads de licença com Ed25519 para ativação no cliente desktop.
    """

    def __init__(self, private_key_b64: Optional[str] = None) -> None:
        key_raw_b64 = private_key_b64 or _resolve_private_key()
        key_bytes = base64.b64decode(key_raw_b64.encode("utf-8"))
        self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes)
        self._public_key = self._private_key.public_key()

    @property
    def public_key_b64(self) -> str:
        """Retorna a chave pública correspondente codificada em Base64."""
        pub_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(pub_bytes).decode("utf-8")

    @classmethod
    def generate_new_keypair(cls) -> Tuple[str, str]:
        """Gera um novo par de chaves assimétricas Ed25519 (privada, pública) em Base64."""
        priv = ed25519.Ed25519PrivateKey.generate()
        pub = priv.public_key()
        priv_bytes = priv.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_bytes = pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return (
            base64.b64encode(priv_bytes).decode("utf-8"),
            base64.b64encode(pub_bytes).decode("utf-8"),
        )

    def issue_license(
        self,
        client_name: str,
        license_type: LicenseType,
        machine_fingerprint: str,
        days_valid: Optional[int] = 365,
        max_plants: int = 100,
    ) -> str:
        """
        Gera e assina digitalmente com Ed25519 um token de licença para um cliente.

        :param client_name: Razão social ou nome do operador licenciado.
        :param license_type: Modalidade da licença (TRIAL, PROFESSIONAL, ENTERPRISE).
        :param machine_fingerprint: HWID da máquina cliente (ou '*' para enterprise flutuante).
        :param days_valid: Dias de validade a partir da data de emissão (None para vitalícia).
        :param max_plants: Limite de usinas solares monitoráveis.
        :return: String do token no formato: <payload_b64>.<signature_b64>
        """
        issued_at = datetime.now()
        expires_at = (issued_at + timedelta(days=days_valid)) if days_valid else None

        payload = {
            "client": client_name.strip(),
            "type": license_type.value if hasattr(license_type, "value") else str(license_type),
            "hwid": machine_fingerprint.strip().upper(),
            "issued": issued_at.isoformat(),
            "expires": expires_at.isoformat() if expires_at else None,
            "max_plants": max_plants,
        }

        # Serialização padronizada com chaves ordenadas
        payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        payload_bytes = payload_json.encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8")

        # Assinatura assimétrica com Ed25519 (64 bytes de assinatura)
        signature_bytes = self._private_key.sign(payload_b64.encode("utf-8"))
        signature_b64 = base64.urlsafe_b64encode(signature_bytes).decode("utf-8")

        token = f"{payload_b64}.{signature_b64}"
        logger.info(f"Licença Ed25519 emitida com sucesso para '{client_name}' (HWID: {machine_fingerprint}).")
        return token
