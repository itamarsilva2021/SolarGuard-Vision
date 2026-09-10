"""
Sistema de Licenciamento Criptográfico e Proteção Anti-Pirataria para Desktop Windows.
Utiliza Hardware Fingerprinting (identificação única da máquina) e assinaturas digitais HMAC-SHA256.
"""

import json
import base64
import hmac
import hashlib
import platform
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger("LicenseManager")


class LicenseType(str, Enum):
    """Modalidades de licenciamento do software."""
    TRIAL = "trial"                 # Período de avaliação (ex: 30 dias, limite de 2 usinas)
    PROFESSIONAL = "professional"   # Licença completa profissional (1 máquina)
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
    Gerenciador, validador e emissor de chaves de ativação para o SolarGuard Vision.
    """

    # Chave mestra interna do software para verificação de autenticidade
    _SECRET_SALT = b"SOLARGUARD-VISION-OFFICIAL-DESKTOP-LICENSE-KEY-SALT-2026"

    def __init__(self, license_file: Optional[Path | str] = None) -> None:
        self.license_file = Path(license_file) if license_file else settings.data_dir / "license.key"

    def get_current_machine_fingerprint(self) -> str:
        """Retorna o código de identificação do hardware do computador atual."""
        return HardwareFingerprint.get_fingerprint()

    def generate_license_key(
        self,
        client_name: str,
        license_type: LicenseType,
        machine_fingerprint: str,
        days_valid: Optional[int] = 365,
        max_plants: int = 100,
    ) -> str:
        """
        Gera uma chave criptográfica de ativação assinada (para uso do setor de licenciamento/vendas).
        """
        issued_at = datetime.now()
        expires_at = (issued_at + timedelta(days=days_valid)) if days_valid else None

        payload = {
            "client": client_name,
            "type": license_type.value,
            "hwid": machine_fingerprint,
            "issued": issued_at.isoformat(),
            "expires": expires_at.isoformat() if expires_at else None,
            "max_plants": max_plants,
        }

        payload_json = json.dumps(payload, sort_keys=True)
        payload_b64 = base64.b64encode(payload_json.encode("utf-8")).decode("utf-8")

        signature = hmac.new(self._SECRET_SALT, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        license_key = f"{payload_b64}.{signature}"
        return license_key

    def validate_license_key(self, key_str: str) -> LicenseInfo:
        """
        Valida a integridade, autenticidade, hardware e expiração da chave de licença informada.
        """
        parts = key_str.strip().split(".")
        if len(parts) != 2:
            return LicenseInfo(
                client_name="Desconhecido",
                license_type=LicenseType.TRIAL,
                machine_fingerprint="",
                issued_at=datetime.now(),
                expires_at=None,
                max_plants=0,
                is_valid=False,
                status_message="Formato de chave de licença inválido.",
            )

        payload_b64, signature = parts

        # 1. Verificar assinatura criptográfica HMAC
        expected_sig = hmac.new(self._SECRET_SALT, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            logger.warning("Tentativa de uso de chave de licença com assinatura forjada.")
            return LicenseInfo(
                client_name="Não Autorizado",
                license_type=LicenseType.TRIAL,
                machine_fingerprint="",
                issued_at=datetime.now(),
                expires_at=None,
                max_plants=0,
                is_valid=False,
                status_message="Assinatura digital da licença inválida ou corrompida.",
            )

        # 2. Decodificar payload
        try:
            payload_json = base64.b64decode(payload_b64.encode("utf-8")).decode("utf-8")
            data = json.loads(payload_json)
        except Exception as e:
            return LicenseInfo(
                client_name="Corrompido",
                license_type=LicenseType.TRIAL,
                machine_fingerprint="",
                issued_at=datetime.now(),
                expires_at=None,
                max_plants=0,
                is_valid=False,
                status_message=f"Falha ao decodificar licença: {e}",
            )

        client_name = data.get("client", "Cliente")
        lic_type = LicenseType(data.get("type", LicenseType.TRIAL.value))
        hwid = data.get("hwid", "")
        issued_at = datetime.fromisoformat(data["issued"])
        expires_at = datetime.fromisoformat(data["expires"]) if data.get("expires") else None
        max_plants = data.get("max_plants", 10)

        # 3. Validar Hardware Fingerprint (ou wildcard "*" para enterprise flutuante)
        current_hwid = self.get_current_machine_fingerprint()
        if hwid != "*" and hwid != current_hwid:
            logger.warning(f"Licença gerada para HWID {hwid}, mas executada em {current_hwid}.")
            return LicenseInfo(
                client_name=client_name,
                license_type=lic_type,
                machine_fingerprint=hwid,
                issued_at=issued_at,
                expires_at=expires_at,
                max_plants=max_plants,
                is_valid=False,
                status_message="Esta licença pertence a outro computador ou servidor.",
            )

        # 4. Validar Expiração
        if expires_at and datetime.now() > expires_at:
            logger.warning(f"Licença de {client_name} expirada em {expires_at}.")
            return LicenseInfo(
                client_name=client_name,
                license_type=lic_type,
                machine_fingerprint=hwid,
                issued_at=issued_at,
                expires_at=expires_at,
                max_plants=max_plants,
                is_valid=False,
                status_message=f"Licença expirada em {expires_at.strftime('%d/%m/%Y')}.",
            )

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
        """Salva a chave informada no arquivo local e valida."""
        self.license_file.parent.mkdir(parents=True, exist_ok=True)
        self.license_file.write_text(key_str.strip(), encoding="utf-8")
        logger.info(f"Nova chave de licença salva em: {self.license_file}")
        return self.validate_license_key(key_str)

    def check_current_license(self) -> LicenseInfo:
        """Verifica a licença ativa salva no arquivo local ou retorna Trial padrão."""
        if not self.license_file.exists():
            return LicenseInfo(
                client_name="Usuário de Avaliação",
                license_type=LicenseType.TRIAL,
                machine_fingerprint=self.get_current_machine_fingerprint(),
                issued_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=14),
                max_plants=2,
                is_valid=True,
                status_message="Modo de Avaliação Gratuita (14 dias restantes).",
            )

        key_str = self.license_file.read_text(encoding="utf-8").strip()
        return self.validate_license_key(key_str)
