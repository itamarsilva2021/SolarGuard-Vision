"""
Script de Automação de Build de Produção e Empacotamento do Instalador Windows do SolarGuard Vision.
Executa PyInstaller e compila o instalador executável via Inno Setup (ISCC.exe).
"""

import sys
import subprocess
import shutil
from pathlib import Path

# Diretórios
ROOT_DIR = Path(__file__).resolve().parent.parent
PACKAGING_DIR = ROOT_DIR / "packaging"
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
SPEC_FILE = PACKAGING_DIR / "solarguard_vision.spec"
ISS_FILE = PACKAGING_DIR / "inno_setup_script.iss"


def run_command(cmd: list[str], description: str) -> bool:
    print(f"[*] Iniciando: {description}...")
    try:
        res = subprocess.run(cmd, cwd=str(ROOT_DIR), check=True)
        print(f"[+] Sucesso: {description}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[!] Erro ao executar {description}: {e}", file=sys.stderr)
        return False


def build_pyinstaller_bundle() -> bool:
    """Invoca o PyInstaller para empacotar o software."""
    pyinstaller_exe = sys.executable.replace("python.exe", "pyinstaller.exe")
    if not Path(pyinstaller_exe).exists():
        pyinstaller_exe = "pyinstaller"

    cmd = [
        pyinstaller_exe,
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        str(SPEC_FILE),
    ]
    return run_command(cmd, "Empacotamento com PyInstaller")


def compile_inno_setup_installer() -> bool:
    """Busca o compilador do Inno Setup (ISCC.exe) e compila o instalador Windows."""
    # Locais padrões do Inno Setup no Windows
    possible_paths = [
        Path.home() / r"AppData\Local\Programs\Inno Setup 6\ISCC.exe",
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"),
    ]

    iscc_path = shutil.which("ISCC")
    if not iscc_path:
        for p in possible_paths:
            if p.exists():
                iscc_path = str(p)
                break

    if not iscc_path:
        print("\n[!] Inno Setup (ISCC.exe) não localizado no PATH nem nos diretórios padrão.")
        print("[i] A pasta portável da aplicação está pronta e funcional em: dist/SolarGuard_Vision/")
        print("[i] Para gerar o executável de instalação 'Setup_SolarGuard_Vision_v1.0.0.exe', abra o arquivo")
        print(f"    '{ISS_FILE}' no aplicativo Inno Setup e clique em 'Compile'.\n")
        return False

    cmd = [iscc_path, str(ISS_FILE)]
    return run_command(cmd, "Compilação do Instalador Windows com Inno Setup")


def main():
    print("=" * 70)
    print("       SOLARGUARD VISION - BUILD DO INSTALADOR WINDOWS DE PRODUÇÃO")
    print("=" * 70)

    # 1. Empacotar executável
    print("\nEtapa 1/2: Gerando binários da aplicação...")
    pyinstaller_ok = build_pyinstaller_bundle()

    if not pyinstaller_ok:
        print("[!] Falha no empacotamento. Abortando processo de build.")
        sys.exit(1)

    # 2. Compilar instalador
    print("\nEtapa 2/2: Compilando instalador executável Windows...")
    installer_ok = compile_inno_setup_installer()

    print("\n" + "=" * 70)
    if installer_ok:
        print("[+] BUILD CONCLUÍDO COM SUCESSO!")
        print(f"[+] Instalador gerado em: dist/installer/Setup_SolarGuard_Vision_v1.0.0.exe")
    else:
        print("[+] Aplicação desktop compilada com sucesso em: dist/SolarGuard_Vision/SolarGuard_Vision.exe")
    print("=" * 70)


if __name__ == "__main__":
    main()
