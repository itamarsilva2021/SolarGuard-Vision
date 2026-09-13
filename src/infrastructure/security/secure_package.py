"""
Módulo de Empacotamento Criptográfico Seguro: ZIP + AES-256-GCM + Assinatura Ed25519.
Garante os três pilares fundamentais da segurança em pacotes de exportação e snapshots:
1. Confidencialidade: Cifragem autenticada simétrica AES-256-GCM com chave derivada via Argon2id.
2. Autenticidade: Assinatura digital assimétrica Ed25519 (RFC 8032) pelo emissor.
3. Integridade: Dupla garantia (Authentication Tag de 128 bits do GCM + Assinatura Ed25519 + CRC32 ZIP).
"""

import base64
import hashlib
import io
import json
import os
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from src.core.logger import get_logger
from src.core.result import Failure, Result, Success

logger = get_logger("SecurePackageManager")


class SecurePackageError(Exception):
    """Exceção base para erros em pacotes criptográficos seguros."""
    pass


class SecurePackageManager:
    """
    Gerenciador de envelopes criptográficos seguros (SGZ).
    Estrutura do arquivo container (.sgz / .zip.enc):
      [4 Bytes: Magic SGZ1]
      [4 Bytes: Header Length (Big-Endian uint32)]
      [N Bytes: Canonical Header JSON UTF-8]
      [M Bytes: AES-256-GCM Ciphertext + 16 Bytes Auth Tag]
    """

    MAGIC_BYTES: bytes = b"SGZ1"
    FORMAT_VERSION: str = "1.0"
    DEFAULT_ITERATIONS: int = 3
    DEFAULT_MEMORY_KIB: int = 65536  # 64 MiB
    DEFAULT_LANES: int = 4
    KEY_LENGTH_BYTES: int = 32        # 256 bits para AES-256
    SALT_LENGTH_BYTES: int = 16       # 128 bits
    NONCE_LENGTH_BYTES: int = 12      # 96 bits para AES-GCM

    def __init__(
        self,
        iterations: int = DEFAULT_ITERATIONS,
        memory_cost_kib: int = DEFAULT_MEMORY_KIB,
        lanes: int = DEFAULT_LANES,
    ) -> None:
        self.iterations = iterations
        self.memory_cost_kib = memory_cost_kib
        self.lanes = lanes

    # -------------------------------------------------------------------------
    # Gerenciamento e Serialização de Chaves Ed25519
    # -------------------------------------------------------------------------

    @staticmethod
    def generate_keypair() -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
        """Gera um novo par de chaves assimétricas Ed25519 (RFC 8032)."""
        private_key = ed25519.Ed25519PrivateKey.generate()
        return private_key, private_key.public_key()

    @staticmethod
    def export_private_key_b64(private_key: ed25519.Ed25519PrivateKey) -> str:
        """Exporta chave privada Ed25519 como string Base64 crua (32 bytes)."""
        raw = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return base64.b64encode(raw).decode("ascii")

    @staticmethod
    def import_private_key_b64(b64_str: str) -> ed25519.Ed25519PrivateKey:
        """Reconstrói chave privada Ed25519 a partir de Base64 cru."""
        raw = base64.b64decode(b64_str.strip())
        return ed25519.Ed25519PrivateKey.from_bytes(raw) if hasattr(ed25519.Ed25519PrivateKey, "from_bytes") else ed25519.Ed25519PrivateKey.from_private_bytes(raw)

    @staticmethod
    def export_public_key_b64(public_key: ed25519.Ed25519PublicKey) -> str:
        """Exporta chave pública Ed25519 como string Base64 crua (32 bytes)."""
        raw = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(raw).decode("ascii")

    @staticmethod
    def import_public_key_b64(b64_str: str) -> ed25519.Ed25519PublicKey:
        """Reconstrói chave pública Ed25519 a partir de Base64 cru."""
        raw = base64.b64decode(b64_str.strip())
        return ed25519.Ed25519PublicKey.from_public_bytes(raw)

    # -------------------------------------------------------------------------
    # Operações ZIP em Memória com Proteção Path Traversal
    # -------------------------------------------------------------------------

    @staticmethod
    def create_zip_buffer(
        sources: Optional[Union[List[Path], Path]] = None,
        base_dir: Optional[Path] = None,
        virtual_files: Optional[Dict[str, Union[bytes, str]]] = None,
    ) -> bytes:
        """
        Compacta arquivos físicos e/ou arquivos em memória num buffer ZIP deflated.
        """
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Arquivos em memória
            if virtual_files:
                for arcname, data in virtual_files.items():
                    content = data.encode("utf-8") if isinstance(data, str) else data
                    zf.writestr(arcname, content)

            # 2. Arquivos do sistema de arquivos
            if sources:
                source_list = [sources] if isinstance(sources, Path) else sources
                for src in source_list:
                    src_path = Path(src)
                    if not src_path.exists():
                        raise FileNotFoundError(f"Arquivo de origem inexistente: {src_path}")

                    if src_path.is_file():
                        arcname = src_path.name if not base_dir else src_path.relative_to(base_dir).as_posix()
                        zf.write(src_path, arcname=arcname)
                    elif src_path.is_dir():
                        root_ref = base_dir if base_dir else src_path.parent
                        for child in src_path.rglob("*"):
                            if child.is_file():
                                arcname = child.relative_to(root_ref).as_posix()
                                zf.write(child, arcname=arcname)

        return bio.getvalue()

    @staticmethod
    def extract_zip_buffer(zip_bytes: bytes, output_dir: Path) -> List[Path]:
        """
        Extrai buffer ZIP para o diretório de destino com mitigação estrita contra Zip Slip.
        """
        extracted_files: List[Path] = []
        target_dir = Path(output_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            # Validar integridade básica do ZIP
            crc_err = zf.testzip()
            if crc_err is not None:
                raise ValueError(f"Corrupção de integridade detectada no ZIP (CRC32 inválido em: {crc_err})")

            for info in zf.infolist():
                # Proteção estrutural contra Zip Slip / Path Traversal
                dest_path = (target_dir / info.filename).resolve()
                if not dest_path.is_relative_to(target_dir):
                    raise PermissionError(
                        f"Tentativa maliciosa de Path Traversal bloqueada: {info.filename}"
                    )

                if info.is_dir():
                    dest_path.mkdir(parents=True, exist_ok=True)
                else:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as source, open(dest_path, "wb") as target:
                        target.write(source.read())
                    extracted_files.append(dest_path)

        return extracted_files

    # -------------------------------------------------------------------------
    # Cifragem, Assinatura e Empacotamento Seguro (Pack)
    # -------------------------------------------------------------------------

    def pack(
        self,
        output_path: Union[Path, str],
        passphrase: str,
        signing_key: ed25519.Ed25519PrivateKey,
        sources: Optional[Union[List[Path], Path]] = None,
        base_dir: Optional[Path] = None,
        virtual_files: Optional[Dict[str, Union[bytes, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Result[Path, str]:
        """
        Cria um container blindado (.sgz) contendo os arquivos compactados em ZIP,
        cifrados via AES-256-GCM e autenticados com assinatura assimétrica Ed25519.
        """
        out_file = Path(output_path)
        if len(passphrase) < 12:
            return Failure("A senha para cifragem AES-256 deve possuir no mínimo 12 caracteres.")

        try:
            # 1. Compactar em ZIP (Camada Estrutural)
            zip_bytes = self.create_zip_buffer(sources, base_dir=base_dir, virtual_files=virtual_files)
            zip_sha256 = hashlib.sha256(zip_bytes).hexdigest()

            # 2. Gerar material criptográfico e derivar chave AES-256 (Camada Confidencialidade)
            salt = os.urandom(self.SALT_LENGTH_BYTES)
            nonce = os.urandom(self.NONCE_LENGTH_BYTES)

            kdf = Argon2id(
                salt=salt,
                length=self.KEY_LENGTH_BYTES,
                iterations=self.iterations,
                lanes=self.lanes,
                memory_cost=self.memory_cost_kib,
            )
            aes_key = kdf.derive(passphrase.encode("utf-8"))

            aesgcm = AESGCM(aes_key)
            ciphertext = aesgcm.encrypt(nonce, zip_bytes, associated_data=None)
            ciphertext_sha256 = hashlib.sha256(ciphertext).hexdigest()

            # 3. Montar cabeçalho canônico para assinatura (Camada Autenticidade / Integridade)
            signer_pub_b64 = self.export_public_key_b64(signing_key.public_key())
            header_core: Dict[str, Any] = {
                "format": "SGZ",
                "version": self.FORMAT_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "cipher": "AES-256-GCM",
                "kdf": "Argon2id",
                "kdf_params": {
                    "iterations": self.iterations,
                    "memory_cost_kib": self.memory_cost_kib,
                    "lanes": self.lanes,
                    "salt_b64": base64.b64encode(salt).decode("ascii"),
                },
                "nonce_b64": base64.b64encode(nonce).decode("ascii"),
                "zip_sha256": zip_sha256,
                "ciphertext_sha256": ciphertext_sha256,
                "ciphertext_length": len(ciphertext),
                "signer_public_key_b64": signer_pub_b64,
                "metadata": metadata or {},
            }

            # Serialização canônica para evitar ambiguidades na assinatura
            canonical_bytes = json.dumps(header_core, sort_keys=True, separators=(",", ":")).encode("utf-8")

            # 4. Assinatura Ed25519 sobre os metadados canônicos (que incluem o hash do ciphertext)
            signature = signing_key.sign(canonical_bytes)
            signature_b64 = base64.b64encode(signature).decode("ascii")

            # 5. Cabeçalho completo final
            full_header = dict(header_core)
            full_header["signature_b64"] = signature_b64
            header_bytes = json.dumps(full_header, indent=2).encode("utf-8")

            # 6. Gravação no disco do container unificado
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "wb") as f:
                f.write(self.MAGIC_BYTES)
                f.write(struct.pack(">I", len(header_bytes)))
                f.write(header_bytes)
                f.write(ciphertext)

            logger.info(
                f"Container seguro criado com sucesso: {out_file} "
                f"({out_file.stat().st_size} bytes, ZIP SHA256: {zip_sha256[:8]}...)"
            )
            return Success(out_file)

        except Exception as e:
            logger.error(f"Erro ao gerar container seguro: {e}", exc_info=True)
            return Failure(f"Falha na geração do container seguro: {str(e)}")

    # -------------------------------------------------------------------------
    # Verificação, Decifração e Extração Segura (Unpack)
    # -------------------------------------------------------------------------

    def unpack(
        self,
        package_path: Union[Path, str],
        output_dir: Union[Path, str],
        passphrase: str,
        expected_public_key: Optional[ed25519.Ed25519PublicKey] = None,
    ) -> Result[List[Path], str]:
        """
        Verifica a assinatura Ed25519, decifra o payload AES-256-GCM e extrai o ZIP.
        Garante integralmente autenticidade, integridade e confidencialidade.
        """
        pkg_file = Path(package_path)
        out_dir = Path(output_dir)

        if not pkg_file.exists():
            return Failure(f"Arquivo de pacote seguro não encontrado: {pkg_file}")

        try:
            with open(pkg_file, "rb") as f:
                # 1. Validar Magic Bytes
                magic = f.read(len(self.MAGIC_BYTES))
                if magic != self.MAGIC_BYTES:
                    return Failure("Formato de arquivo inválido: identificador mágico SGZ ausente.")

                # 2. Ler tamanho e conteúdo do cabeçalho
                header_len_bytes = f.read(4)
                if len(header_len_bytes) < 4:
                    return Failure("Arquivo truncado: cabeçalho incompleto.")
                header_len = struct.unpack(">I", header_len_bytes)[0]

                header_raw = f.read(header_len)
                if len(header_raw) < header_len:
                    return Failure("Arquivo corrompido: tamanho do cabeçalho diverge dos dados lidos.")

                header = json.loads(header_raw.decode("utf-8"))

                # 3. Ler ciphertext
                ciphertext = f.read()

            # 4. Validar Autenticidade e Integridade do Envelope via Ed25519
            signature_b64 = header.get("signature_b64")
            if not signature_b64:
                return Failure("Assinatura Ed25519 ausente no cabeçalho do pacote.")

            signature = base64.b64decode(signature_b64)

            # Reconstruir cabeçalho canônico para conferência da assinatura
            header_core = {k: v for k, v in header.items() if k != "signature_b64"}
            canonical_bytes = json.dumps(header_core, sort_keys=True, separators=(",", ":")).encode("utf-8")

            # Definir chave de verificação
            signer_pub_b64 = header.get("signer_public_key_b64", "")
            if expected_public_key is not None:
                verify_key = expected_public_key
                expected_pub_b64 = self.export_public_key_b64(expected_public_key)
                if signer_pub_b64 != expected_pub_b64:
                    return Failure(
                        "Autenticidade violada: o assinante do pacote não corresponde à chave pública confiável."
                    )
            else:
                if not signer_pub_b64:
                    return Failure("Chave pública do assinante ausente no cabeçalho do pacote.")
                verify_key = self.import_public_key_b64(signer_pub_b64)

            try:
                verify_key.verify(signature, canonical_bytes)
            except InvalidSignature:
                return Failure("Assinatura Ed25519 inválida. O pacote foi corrompido ou adulterado por terceiros.")

            # 5. Validar integridade matemática do ciphertext
            expected_ct_sha256 = header.get("ciphertext_sha256")
            computed_ct_sha256 = hashlib.sha256(ciphertext).hexdigest()
            if expected_ct_sha256 and computed_ct_sha256 != expected_ct_sha256:
                return Failure("Integridade comprometida: SHA-256 do ciphertext diverge do cabeçalho assinado.")

            # 6. Decifração AES-256-GCM (Confidencialidade + Autenticação de Cifragem)
            kdf_params = header.get("kdf_params", {})
            salt = base64.b64decode(kdf_params["salt_b64"])
            nonce = base64.b64decode(header["nonce_b64"])
            iterations = kdf_params.get("iterations", self.iterations)
            memory_cost_kib = kdf_params.get("memory_cost_kib", self.memory_cost_kib)
            lanes = kdf_params.get("lanes", self.lanes)

            kdf = Argon2id(
                salt=salt,
                length=self.KEY_LENGTH_BYTES,
                iterations=iterations,
                lanes=lanes,
                memory_cost=memory_cost_kib,
            )
            aes_key = kdf.derive(passphrase.encode("utf-8"))

            aesgcm = AESGCM(aes_key)
            try:
                decrypted_zip_bytes = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
            except Exception:
                return Failure(
                    "Falha na decifração AES-256-GCM: senha incorreta ou conteúdo cifrado adulterado (tag GCM inválida)."
                )

            # 7. Validar SHA-256 do ZIP decifrado
            expected_zip_sha256 = header.get("zip_sha256")
            if expected_zip_sha256:
                computed_zip_sha256 = hashlib.sha256(decrypted_zip_bytes).hexdigest()
                if computed_zip_sha256 != expected_zip_sha256:
                    return Failure("Integridade do arquivo ZIP decifrado violada.")

            # 8. Extrair ZIP com proteção Zip Slip
            extracted_files = self.extract_zip_buffer(decrypted_zip_bytes, out_dir)
            logger.info(
                f"Container {pkg_file.name} decifrado e verificado com sucesso. "
                f"{len(extracted_files)} arquivos extraídos para: {out_dir}"
            )
            return Success(extracted_files)

        except Exception as e:
            logger.error(f"Erro ao desempacotar container seguro: {e}", exc_info=True)
            return Failure(f"Falha na extração do container seguro: {str(e)}")

    # -------------------------------------------------------------------------
    # Inspeção e Verificação sem Decifração
    # -------------------------------------------------------------------------

    def inspect_package(
        self,
        package_path: Union[Path, str],
        expected_public_key: Optional[ed25519.Ed25519PublicKey] = None,
    ) -> Result[Dict[str, Any], str]:
        """
        Valida a assinatura Ed25519 e integridade do envelope sem necessitar da senha AES-256.
        Retorna os metadados do pacote caso autêntico e íntegro.
        """
        pkg_file = Path(package_path)
        if not pkg_file.exists():
            return Failure(f"Arquivo não encontrado: {pkg_file}")

        try:
            with open(pkg_file, "rb") as f:
                magic = f.read(len(self.MAGIC_BYTES))
                if magic != self.MAGIC_BYTES:
                    return Failure("Arquivo inválido: Magic SGZ ausente.")

                header_len_bytes = f.read(4)
                if len(header_len_bytes) < 4:
                    return Failure("Arquivo truncado.")
                header_len = struct.unpack(">I", header_len_bytes)[0]
                header = json.loads(f.read(header_len).decode("utf-8"))
                ciphertext = f.read()

            signature_b64 = header.get("signature_b64", "")
            signature = base64.b64decode(signature_b64)
            header_core = {k: v for k, v in header.items() if k != "signature_b64"}
            canonical_bytes = json.dumps(header_core, sort_keys=True, separators=(",", ":")).encode("utf-8")

            signer_pub_b64 = header.get("signer_public_key_b64", "")
            if expected_public_key is not None:
                verify_key = expected_public_key
                expected_pub_b64 = self.export_public_key_b64(expected_public_key)
                if signer_pub_b64 != expected_pub_b64:
                    return Failure("Chave pública do assinante não coincide com a esperada.")
            else:
                verify_key = self.import_public_key_b64(signer_pub_b64)

            try:
                verify_key.verify(signature, canonical_bytes)
            except InvalidSignature:
                return Failure("Assinatura digital Ed25519 inválida!")

            # Verificar hash do ciphertext
            computed_ct_sha256 = hashlib.sha256(ciphertext).hexdigest()
            if computed_ct_sha256 != header.get("ciphertext_sha256"):
                return Failure("Hash do ciphertext não confere.")

            return Success({
                "is_authentic": True,
                "is_intact": True,
                "created_at": header.get("created_at"),
                "version": header.get("version"),
                "cipher": header.get("cipher"),
                "signer_public_key_b64": signer_pub_b64,
                "ciphertext_length": len(ciphertext),
                "metadata": header.get("metadata", {}),
            })

        except Exception as e:
            return Failure(f"Falha na inspeção do pacote: {str(e)}")
