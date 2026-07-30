# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all

icon_path = os.path.join('assets', 'icon.ico')
if sys.platform != 'win32':
    icon_path = os.path.join('assets', 'icon.png')

# The GitHub Actions toolcache Python ships libpython3.x.so with full debug
# info (~30 MB, of which ~23 MB is .debug_*/.symtab). Stripping brings it to
# ~7 MB, in line with python3xx.dll on Windows. Linux-only: strip is a no-op
# concern on Windows and unnecessary on macOS, whose libs are already lean.
strip_binaries = sys.platform == 'linux'


datas = [('assets', 'assets')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['sync_everdrive.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='sync_everdrive',
    debug=False,
    bootloader_ignore_signals=False,
    strip=strip_binaries,
    # Deliberately off. UPX has never actually been applied to a release (it
    # is installed neither on the GitHub runners nor on dev machines), it is
    # a common trigger for antivirus false positives on Windows, and with
    # Linux binaries stripped there is no size problem left to solve.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    icon=[icon_path],
)

if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='sync_everdrive.app',
        icon=icon_path,
        bundle_identifier='com.receptionfadesx.everdrive-sync',
    )
