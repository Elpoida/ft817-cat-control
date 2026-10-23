# Build with: pyinstaller packaging/ft817-cleanroom.spec
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
STATIC = os.path.join(ROOT, "static")

a = Analysis(
    [os.path.join(ROOT, "server.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(STATIC, "static")],
    hiddenimports=collect_submodules("serial") + ["serial"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FT817CAT-cleanroom",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FT817CAT-cleanroom",
)
