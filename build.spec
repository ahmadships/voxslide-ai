# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

block_cipher = None

# Bundle the app icon so the running window can load it at runtime
# (PyInstaller EXE icon= only embeds it into the .exe file resources).
datas = [('icon.ico', '.')]
binaries = []
hiddenimports = [
    'customtkinter',
    'speech_recognition',
    'pyautogui',
    'PIL',
    'PIL._tkinter_finder',
    'sounddevice',
    '_sounddevice_data',
    'numpy',
    'numpy._core._multiarray_umath',
    'cffi',
    '_cffi_backend',
    'audioop',
    'audio_engine',
    'ui_components',
    'config',
    'license_manager',
    'session_manager',
    'version',
    'updater',
    'update_dialog',
    'requests',
]

for pkg in ('customtkinter', 'sounddevice', '_sounddevice_data'):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

binaries += collect_dynamic_libs('numpy')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
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
    name='VoxSlide AI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
