# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# --- Hidden imports robustes ---
hiddenimports = []
hiddenimports += collect_submodules("ui")
hiddenimports += collect_submodules("engine")

# Forcer ces modules (même si l'analyse les rate)
hiddenimports += ["PySimpleGUI", "psutil"]

# --- Datas / Binaries ---
datas = []
binaries = []

# Ressources (JSON / WAV / etc.)
datas += [
    Tree("config", prefix="config"),
    Tree("assets", prefix="assets"),
]

# Scripts appelés par subprocess -> doivent exister dans dist
datas += [
    ("runner.py", "."),
    ("scheduler.py", "."),
]

# (Option filet de sécurité) Copier aussi les packages en data
# -> utile si certains imports utilisent des chemins, ou si tu veux lire des fichiers dans ui/engine
datas += [
    Tree("ui", prefix="ui"),
    Tree("engine", prefix="engine"),
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="StoryFX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="StoryFX",
)
