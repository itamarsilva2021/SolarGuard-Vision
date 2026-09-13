"""
Utilitário CLI do Servidor para Emissão de Licenças Assimétricas Ed25519.
Uso exclusivo da equipe de licenciamento e suporte do SolarGuard Vision.
"""

import sys
import argparse
from pathlib import Path

# Adiciona a raiz do projeto ao path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.security.license_manager import LicenseType
from server_tools.license_issuer import LicenseIssuer


def main():
    parser = argparse.ArgumentParser(description="SolarGuard Vision - Emissor Oficial de Licenças Ed25519")
    parser.add_argument("--client", required=True, help="Nome ou Razão Social do Cliente")
    parser.add_argument("--hwid", required=True, help="Hardware Fingerprint (HWID) da máquina do cliente ou '*' para Enterprise")
    parser.add_argument("--type", choices=["trial", "professional", "enterprise"], default="professional", help="Modalidade de licença")
    parser.add_argument("--days", type=int, default=365, help="Dias de validade (ex: 30, 365, 730)")
    parser.add_argument("--plants", type=int, default=50, help="Limite máximo de usinas solares")
    parser.add_argument("--out", help="Caminho do arquivo .key para salvar o token gerado")

    args = parser.parse_args()

    issuer = LicenseIssuer()
    lic_type = LicenseType(args.type)
    token = issuer.issue_license(
        client_name=args.client,
        license_type=lic_type,
        machine_fingerprint=args.hwid,
        days_valid=args.days,
        max_plants=args.plants,
    )

    print("=" * 65)
    print("      SOLARGUARD VISION - CHAVE DE ATIVAÇÃO ED25519 GERADA")
    print("=" * 65)
    print(f"Cliente: {args.client}")
    print(f"HWID:    {args.hwid}")
    print(f"Tipo:    {lic_type.display_name}")
    print(f"Vigência: {args.days} dias")
    print("-" * 65)
    print("CHAVE CRIPTOGRÁFICA:")
    print(token)
    print("=" * 65)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(token, encoding="utf-8")
        print(f"[+] Arquivo salvo com sucesso em: {out_path.resolve()}")


if __name__ == "__main__":
    main()
