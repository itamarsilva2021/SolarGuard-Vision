"""
Utilitário de Hashing Criptográfico e Verificação de Senhas com PBKDF2-HMAC-SHA256 e Salt.
Protege contra ataques de dicionário e rainbow tables em conformidade com as recomendações OWASP.
"""

import hashlib
import secrets
import hmac
from typing import Tuple


class PasswordHasher:
    """Gerenciador de hash e verificação de senhas seguras."""

    ITERATIONS = 100_000
    ALGORITHM = "sha256"

    @classmethod
    def hash_password(cls, password: str, salt: str = None) -> Tuple[str, str]:
        """
        Gera o hash PBKDF2 de uma senha com salt criptográfico.
        
        :param password: Senha em texto claro.
        :param salt: Sal hexadecimal opcional (se None, gera salt randômico de 16 bytes).
        :return: Tupla (hash_hex, salt_hex).
        """
        if salt is None:
            salt = secrets.token_hex(16)

        key = hashlib.pbkdf2_hmac(
            cls.ALGORITHM,
            password.encode("utf-8"),
            salt.encode("utf-8"),
            cls.ITERATIONS,
        )
        return key.hex(), salt

    @classmethod
    def verify_password(cls, password: str, expected_hash: str, salt: str) -> bool:
        """
        Verifica se a senha em texto claro corresponde ao hash esperado em tempo constante.
        """
        computed_hash, _ = cls.hash_password(password, salt=salt)
        return hmac.compare_digest(computed_hash, expected_hash)
