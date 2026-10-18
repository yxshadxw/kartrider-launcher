# PyInstaller one-file Windows executable. Build from this directory.
from pathlib import Path

root = Path(SPECPATH)
datas = [
    (str(root / "translations.jsonl"), "."),
    (str(root / "known.json"), "."),
    (str(root / "manual.json"), "."),
    (str(root / "decompiled-launcher" / "KartLibrary.Encrypt" / "RhoKey.cs"), "decompiled-launcher/KartLibrary.Encrypt"),
]

a = Analysis(
    [str(root / "apply_english_patch.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="KartRider-English-Patcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
