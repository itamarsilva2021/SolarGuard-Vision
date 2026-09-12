"""
Utilitário de Hashing Criptográfico e Verificação de Senhas.
Implementa Argon2id (RFC 9106) como padrão corporativo da indústria e mantém compatibilidade
retroativa com o algoritmo legado PBKDF2-HMAC-SHA256, viabilizando rehash automático.
"""

from typing import Tuple, Optional
import hashlib
import secrets
import hmac
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.exceptions import InvalidKey


class PasswordHasher:
    """Gerenciador de hash e verificação de senhas seguras com suporte a Argon2id e PBKDF2."""

    # Parâmetros de alta segurança recomendados pela OWASP para Argon2id
    ARGON2_TIME_COST = 3          # 3 iterações
    ARGON2_MEMORY_COST = 65536    # 64 MiB (em KiB)
    ARGON2_PARALLELISM = 4        # 4 lanes (grau de paralelismo)
    ARGON2_KEY_LEN = 32           # 32 bytes (256 bits)
    ARGON2_SALT_LEN = 16          # 16 bytes de sal criptográfico
    PREFIX_ARGON2ID = "$argon2id$"

    # Parâmetros legados para compatibilidade PBKDF2-HMAC-SHA256
    PBKDF2_ITERATIONS = 100_000
    PBKDF2_ALGORITHM = "sha256"

    @classmethod
    def hash_password(cls, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Gera o hash criptográfico seguro de uma senha utilizando Argon2id (RFC 9106).
        
        :param password: Senha em texto claro.
        :param salt: Sal hexadecimal opcional (se None, gera 16 bytes criptograficamente aleatórios).
        :return: Tupla (hash_str_com_prefixo, salt_hex).
        """
        if salt is None:
            salt_bytes = secrets.token_bytes(cls.ARGON2_SALT_LEN)
            salt_hex = salt_bytes.hex()
        else:
            salt_bytes = bytes.fromhex(salt)
            salt_hex = salt

        kdf = Argon2id(
            salt=salt_bytes,
            length=cls.ARGON2_KEY_LEN,
            iterations=cls.ARGON2_TIME_COST,
            lanes=cls.ARGON2_PARALLELISM,
            memory_cost=cls.ARGON2_MEMORY_COST,
        )
        derived = kdf.derive(password.encode("utf-8"))
        hash_str = f"{cls.PREFIX_ARGON2ID}{derived.hex()}"
        return hash_str, salt_hex

    @classmethod
    def verify_password(cls, password: str, expected_hash: str, salt: str) -> bool:
        """
        Verifica se a senha em texto claro corresponde ao hash esperado.
        Detecta automaticamente se o hash é Argon2id ou PBKDF2 legado.
        """
        if expected_hash.startswith(cls.PREFIX_ARGON2ID):
            # Validação via Argon2id (tempo e memória constantes)
            raw_hash_hex = expected_hash[len(cls.PREFIX_ARGON2ID):]
            try:
                raw_hash = bytes.fromhex(raw_hash_hex)
                salt_bytes = bytes.fromhex(salt)
                kdf = Argon2id(
                    salt=salt_bytes,
                    length=cls.ARGON2_KEY_LEN,
                    iterations=cls.ARGON2_TIME_COST,
                    lanes=cls.ARGON2_PARALLELISM,
                    memory_cost=cls.ARGON2_MEMORY_COST,
                )
                kdf.verify(password.encode("utf-8"), raw_hash)
                return True
            except (InvalidKey, ValueError):
                return False
        else:
            # Validação retrocompatível via PBKDF2-HMAC-SHA256
            try:
                computed_key = hashlib.pbkdf2_hmac(
                    cls.PBKDF2_ALGORITHM,
                    password.encode("utf-8"),
                    salt.encode("utf-8"),
                    cls.PBKDF2_ITERATIONS,
                )
                return hmac.compare_digest(computed_key.hex(), expected_hash)
            except Exception:
                return False

    @classmethod
    def needs_rehash(cls, stored_hash: str) -> bool:
        """
        Indica se o hash armazenado é de formato legado (ex: PBKDF2) e deve
        ser promovido/rehasheado para Argon2id no momento do login.
        """
        return not stored_hash.startswith(cls.PREFIX_ARGON2ID)

    @classmethod
    def hash_legacy_pbkdf2(cls, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Gera hash no padrão legado PBKDF2-HMAC-SHA256 para permitir testes de migração retrocompatível.
        """
        if salt is None:
            salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            cls.PBKDF2_ALGORITHM,
            password.encode("utf-8"),
            salt.encode("utf-8"),
            cls.PBKDF2_ITERATIONS,
        )
        return key.hex(), salt
