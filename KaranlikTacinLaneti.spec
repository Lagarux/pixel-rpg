# -*- mode: python ; coding: utf-8 -*-
# KaranlikTacinLaneti.spec — PyInstaller build config
import os, sys

block_cipher = None

# assets klasörü varsa dahil et
assets_exist = os.path.isdir('assets')

a = Analysis(
    ['pixel_rpg.py'],
    pathex=['.'],
    binaries=[],
    datas=[('assets', 'assets')] if assets_exist else [],
    hiddenimports=['pygame', 'numpy', 'json', 'os', 'sys', 'math', 'random'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
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
    name='KaranlikTacinLaneti',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join('assets','icon.ico')] if os.path.isfile(os.path.join('assets','icon.ico')) else [],
)
