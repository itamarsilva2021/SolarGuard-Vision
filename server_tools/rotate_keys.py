"""
Ferramenta interna de rotação de chaves Ed25519 do SolarGuard Vision.
Gera novos pares para Licenciamento e Atualização de Software.
Salva as chaves privadas exclusivamente em arquivos locais protegidos fora do Git.
"""

import base64
import json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


def generate_pair():
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


def main():
    root_dir = Path(__file__).resolve().parent.parent
    keys_dir = root_dir / "server_tools" / "keys" / ".local_only"
    keys_dir.mkdir(parents=True, exist_ok=True)

    # 1. Par de Licenciamento
    lic_priv, lic_pub = generate_pair()
    lic_file = keys_dir / "license_private.key"
    lic_file.write_text(lic_priv, encoding="utf-8")

    # 2. Par de Atualização
    upd_priv, upd_pub = generate_pair()
    upd_file = keys_dir / "update_private.key"
    upd_file.write_text(upd_priv, encoding="utf-8")

    # 3. Metadados de chaves públicas (não sensíveis)
    pub_keys_info = {
        "licensing_public_key": lic_pub,
        "update_public_key": upd_pub,
    }
    pub_file = root_dir / "server_tools" / "keys" / "public_keys.json"
    pub_file.parent.mkdir(parents=True, exist_ok=True)
    pub_file.write_text(json.dumps(pub_keys_info, indent=2), encoding="utf-8")

    # AVISO: NUNCA imprimir chaves privadas
    print("CHAVES GERADAS COM SUCESSO.")
    print(f"LICENSING_PUBLIC_KEY: {lic_pub}")
    print(f"UPDATE_PUBLIC_KEY: {upd_pub}")


if __name__ == "__main__":
    main()
