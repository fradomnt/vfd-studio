# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: gera o VFD Studio empacotado. Mesmo arquivo para Windows e macOS.
#   Windows:  .venv\Scripts\pyinstaller vfd_studio.spec   ->  dist\VFD Studio\VFD Studio.exe
#   macOS:    .venv/bin/pyinstaller vfd_studio.spec       ->  dist/VFD Studio.app
# Pasta (onedir), não arquivo único: abre mais rápido, antivírus implica menos, e cenas.json/config.json
# ficam ao lado do executável (ver caminhos.py).
import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
NOME = "VFD Studio"
ICONE = "assets/icone/vfd_studio.icns" if sys.platform == "darwin" else "assets/icone/vfd_studio.ico"

ocultos = (collect_submodules("uvicorn") + collect_submodules("websockets")
           + collect_submodules("serial") + ["PIL.ImageFont", "PIL.ImageDraw", "PIL.ImageOps", "PIL.ImageFilter"])

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=[("static", "static"), ("assets/fonts", "assets/fonts"), ("assets/logo_vfd_256x128.png", "assets"),
           ("assets/icone/vfd_studio_512.png", "assets/icone")],
    hiddenimports=ocultos,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "anthropic", "psutil", "pytest"],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=NOME,
    icon=ICONE,
    console=True,            # janela preta com o log: no museu, é como se vê que está vivo
    disable_windowed_traceback=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name=NOME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{NOME}.app",
        icon=ICONE,
        bundle_identifier="studio.tekne.vfdstudio",
        info_plist={
            "CFBundleShortVersionString": "2.0",
            "CFBundleName": NOME,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
        },
    )
