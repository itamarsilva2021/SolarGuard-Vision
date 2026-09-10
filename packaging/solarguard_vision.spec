# -*- mode: python ; coding: utf-8 -*-
"""
Especificação PyInstaller para Empacotamento Industrial do SolarGuard Vision para Windows.
Gera executável otimizado com suporte a PySide6, PyTorch, YOLOv11, OpenCV, ReportLab e Folium.
"""

from pathlib import Path
import sys

block_cipher = None

# Diretório raiz do projeto
root_dir = Path.cwd()

# Coleta de dados estáticos obrigatórios
datas = [
    (str(root_dir / "src" / "infrastructure" / "database" / "schema.sql"), "src/infrastructure/database"),
]

# Incluir pesos de modelo se existirem na pasta models/
models_dir = root_dir / "models"
if models_dir.exists():
    for model_file in models_dir.glob("*.pt"):
        datas.append((str(model_file), "models"))
    for manifest_file in models_dir.glob("*.json"):
        datas.append((str(manifest_file), "models"))

# Módulos com carregamento dinâmico que exigem inclusão explícita
hidden_imports = [
    "ultralytics",
    "ultralytics.models.yolo",
    "torch",
    "torchvision",
    "cv2",
    "numpy",
    "PIL",
    "PIL.Image",
    "reportlab",
    "reportlab.lib",
    "reportlab.platypus",
    "reportlab.pdfgen",
    "folium",
    "folium.plugins",
    "branca",
    "matplotlib",
    "matplotlib.backends.backend_agg",
    "sqlite3",
    "pydantic",
    "piexif",
]

a = Analysis(
    ["main.py"],
    pathex=[str(root_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "IPython", "notebook", "scipy.spatial.cKDTree"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SolarGuard_Vision",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Modo janela Desktop sem console cmd
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="resources/icon.ico" if (root_dir / "resources" / "icon.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SolarGuard_Vision",
)
