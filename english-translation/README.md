# KartRider English resource patch

This package translates supported in-game text to English and rebuilds the game's native bitmap fonts from Korean glyph data already shipped in the client. The standalone patcher is included in the release ZIP; the game client, its launcher, archives, images, and font files are not redistributed. Image-baked text is unchanged.

## Requirements

- Windows x64 standalone build: no Python installation required
- Python 3.10 or newer
- Pillow: `python -m pip install -r patcher/requirements.txt`
- A KartRider installation with its `Data` folder

## Run the standalone executable

Download `KartRider-English-Patcher.exe` from the [English patch release](https://github.com/yxshadxw/kartrider-launcher/releases/tag/en-patch-2026.10.18.2), then run it from PowerShell with the game's `Data` folder and a new output folder:

```powershell
.\KartRider-English-Patcher.exe "C:\path\to\KartRider\Data" "C:\path\to\english-patch-output"
```

## Build the patch with Python

1. Close the game.
2. Run: `python patcher/apply_english_patch.py "C:/path/to/KartRider/Data" "C:/path/to/english-patch-output"`.
3. Back up the original `Data` folder.
4. Copy the generated files from `english-patch-output` into the game's `Data` folder, preserving the folder structure.
5. Start the game through the launcher.

The patcher reads and repacks legacy `.rho` resources from the local `Data` folder. It updates the locale font configuration and regenerates the client's native bitmap font data from the Korean glyph atlas already present in `gui_font.rho`. It writes a separate output folder and does not modify the launcher or the original data files. RHO5 archives and image-baked text are not changed. Review `english-patch-manifest.json` before installing. If the client rejects the patch, restore the backed-up files.

To rebuild the standalone executable on Windows, install `build-requirements.txt` and run `pyinstaller KartRider-English-Patcher.spec --clean --noconfirm` from this folder. The build includes the translation maps and runs without a separate Python installation.

## Translation notes

The patch includes reviewed overrides for VIP notices, placeholder formatting, emblem descriptions, KartRider terminology, and literal percentages that could be mistaken for format tokens. The translation map is based on available localized strings and machine translation; unreviewed text may still sound awkward.

