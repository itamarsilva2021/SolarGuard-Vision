"""
Sistema de Licenciamento Criptográfico e Proteção Anti-Pirataria para Desktop Windows.
Utiliza Hardware Fingerprinting (HWID) e validação de assinaturas assimétricas Ed25519 (RFC 8032).
ARQUITETURA DE SEGURANÇA:
- Cliente: Detém estritamente a CHAVE PÚBLICA Ed25519 para verificação criptográfica.
- Geração local: ESTRITAMENTE PROIBIDA no aplicativo cliente (chave privada reside apenas no servidor).
- Bloqueio estrito: Licença ausente, forjada, expirada ou com HWID divergente resulta em is_valid = False e bloqueio operacional.
"""

import json
import base64
import hashlib
import platform
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("LicenseManager")

# Chave pública oficial de verificação de licenciamento do SolarGuard Vision (Cliente)
DEFAULT_PUBLIC_KEY_B64 = "rNacn/V+4D6djCFjJXCin2zQx/oU6HfMK0jpj9hpsfU="


class LicenseType(str, Enum):
    """Modalidades de licenciamento do software."""
    TRIAL = "trial"                 # Avaliação autorizada pela equipe
    PROFESSIONAL = "professional"   # Licença completa profissional (estação de trabalho dedicada)
    ENTERPRISE = "enterprise"       # Licença corporativa para frotas de drones e múltiplos inspetores

    @property
    def display_name(self) -> str:
        names = {
            LicenseType.TRIAL: "Versão de Demonstração (Trial)",
            LicenseType.PROFESSIONAL: "Licença Profissional (Standard)",
            LicenseType.ENTERPRISE: "Licença Corporativa (Enterprise)",
        }
        return names.get(self, self.value)


@dataclass
class LicenseInfo:
    """Informações decodificadas e status de validação da licença atual."""
    client_name: str
    license_type: LicenseType
    machine_fingerprint: str
    issued_at: datetime
    expires_at: Optional[datetime]
    max_plants: int
    is_valid: bool
    status_message: str

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    @property
    def days_remaining(self) -> Optional[int]:
        if self.expires_at is None:
            return None
        diff = self.expires_at - datetime.now()
        return max(0, diff.days)


class HardwareFingerprint:
    """Gera um identificador criptográfico único e persistente da estação Windows."""

    @classmethod
    def get_fingerprint(cls) -> str:
        """
        Calcula o hash SHA256 dos identificadores de hardware da máquina local:
        Endereço MAC físico, nome da máquina, arquitetura do processador e sistema operacional.
        """
        raw_id = f"{uuid.getnode()}:{platform.node()}:{platform.processor()}:{platform.system()}"
        return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:24].upper()


class LicenseManager:
    """
    Gerenciador e validador de licenças no cliente desktop SolarGuard Vision.
    Executa exclusivamente validação assimétrica com Ed25519.
    Não possui métodos para gerar chaves de licença (proibição de keygen local).
    """

    def __init__(
        self,
        license_file: Optional[Path | str] = None,
        public_key_b64: Optional[str] = None,
    ) -> None:
        self.license_file = Path(license_file) if license_file else settings.data_dir / "license.key"
        pub_raw = public_key_b64 or DEFAULT_PUBLIC_KEY_B64
        pub_bytes = base64.b64decode(pub_raw.encode("utf-8"))
        self._public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)

    def get_current_machine_fingerprint(self) -> str:
        """Retorna o código de identificação do hardware do computador atual."""
        return HardwareFingerprint.get_fingerprint()

    def validate_license_key(self, key_str: str) -> LicenseInfo:
        """
        Valida a integridade, autenticidade, hardware e expiração da chave informada.
        Garante que qualquer inconsistência resulte em is_valid = False.
        """
        key_clean = key_str.strip()
        parts = key_clean.split(".")
        if len(parts) != 2:
            return LicenseInfo(
                client_name="Não Identificado",
                license_type=LicenseType.TRIAL,
                machine_fingerprint="",
                issued_at=datetime.now(),
                expires_at=None,
                max_plants=0,
                is_valid=False,
                status_message="Formato de chave de licença inválido (esperado <payload>.<assinatura>).",
            )

        payload_b64, signature_b64 = parts

        # 1. Decodificar assinatura e verificar com a Chave Pública Ed25519
        try:
            # Compatibilidade com urlsafe e standard base64 com padding flexível
            pad_sig = signature_b64 + "=" * (-len(signature_b64) % 4)
            signature_bytes = base64.urlsafe_b64decode(pad_sig.encode("utf-8"))

            self._public_key.verify(signature_bytes, payload_b64.encode("utf-8"))
        except (InvalidSignature, ValueError, Exception) as sig_err:
            logger.warning(f"Falha de validação criptográfica Ed25519: {sig_err}")
            return LicenseInfo(
                client_name="Não Autorizado",
                license_type=LicenseType.TRIAL,
                machine_fingerprint="",
                issued_at=datetime.now(),
                expires_at=None,
                max_plants=0,
                is_valid=False,
                status_message="Assinatura digital Ed25519 inválida ou forjada.",
            )

        # 2. Decodificar e desserializar o payload JSON
        try:
            pad_payload = payload_b64 + "=" * (-len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(pad_payload.encode("utf-8"))
            payload_json = payload_bytes.decode("utf-8")
            data = json.loads(payload_json)
        except Exception as e:
            logger.error(f"Erro ao decodificar dados da licença: {e}")
            return LicenseInfo(
                client_name="Corrompido",
                license_type=LicenseType.TRIAL,
                machine_fingerprint="",
                issued_at=datetime.now(),
                expires_at=None,
                max_plants=0,
                is_valid=False,
                status_message=f"Dados da licença corrompidos: {e}",
            )

        client_name = data.get("client", "Cliente")
        raw_type = data.get("type", LicenseType.TRIAL.value)
        try:
            lic_type = LicenseType(raw_type)
        except ValueError:
            lic_type = LicenseType.TRIAL

        hwid = data.get("hwid", "")
        try:
            issued_at = datetime.fromisoformat(data["issued"])
        except Exception:
            issued_at = datetime.now()

        expires_at = datetime.fromisoformat(data["expires"]) if data.get("expires") else None
        max_plants = data.get("max_plants", 10)

        # 3. Validar Hardware Fingerprint (HWID)
        current_hwid = self.get_current_machine_fingerprint()
        if hwid != "*" and hwid != current_hwid:
            logger.warning(f"HWID da licença ({hwid}) diverge desta estação de trabalho ({current_hwid}).")
            return LicenseInfo(
                client_name=client_name,
                license_type=lic_type,
                machine_fingerprint=hwid,
                issued_at=issued_at,
                expires_at=expires_at,
                max_plants=max_plants,
                is_valid=False,
                status_message=f"Esta licença foi emitida para outro computador (HWID: {hwid}).",
            )

        # 4. Validar Expiração Temporal
        if expires_at and datetime.now() > expires_at:
            logger.warning(f"Licença de '{client_name}' expirada em {expires_at.isoformat()}.")
            return LicenseInfo(
                client_name=client_name,
                license_type=lic_type,
                machine_fingerprint=hwid,
                issued_at=issued_at,
                expires_at=expires_at,
                max_plants=max_plants,
                is_valid=False,
                status_message=f"Licença expirada em {expires_at.strftime('%d/%m/%Y')}. Renove com o suporte.",
            )

        # Licença plenamente válida e assinada pela autoridade oficial
        logger.info(f"Licença Ed25519 validada com sucesso para '{client_name}' ({lic_type.display_name}).")
        return LicenseInfo(
            client_name=client_name,
            license_type=lic_type,
            machine_fingerprint=hwid,
            issued_at=issued_at,
            expires_at=expires_at,
            max_plants=max_plants,
            is_valid=True,
            status_message="Licença válida e ativa.",
        )

    def save_license(self, key_str: str) -> LicenseInfo:
        """
        Valida e salva a chave de ativação informada no arquivo local.
        Se a licença for válida, persiste no disco; caso contrário, retorna status de falha.
        """
        info = self.validate_license_key(key_str)
        if info.is_valid:
            self.license_file.parent.mkdir(parents=True, exist_ok=True)
            self.license_file.write_text(key_str.strip(), encoding="utf-8")
            logger.info(f"Nova chave de licença salva com sucesso em: {self.license_file}")
        return info

    def apply_license(self, key_str: str) -> LicenseInfo:
        """Alias para save_license."""
        return self.save_license(key_str)

    def check_current_license(self) -> LicenseInfo:
        """
        Verifica a licença ativa persistida no arquivo local.
        Se o arquivo não existir ou o conteúdo for inválido, retorna is_valid = False,
        garantindo bloqueio de uso sem chave autorizada pela autoridade emissora.
        """
        if not self.license_file.exists():
            return LicenseInfo(
                client_name="Não Ativado",
                license_type=LicenseType.TRIAL,
                machine_fingerprint=self.get_current_machine_fingerprint(),
                issued_at=datetime.now(),
                expires_at=None,
                max_plants=0,
                is_valid=False,
                status_message="Nenhuma licença instalada. O acesso ao sistema está bloqueado.",
            )

        key_str = self.license_file.read_text(encoding="utf-8").strip()
        return self.validate_license_key(key_str)
