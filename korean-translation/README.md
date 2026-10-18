# KartRider Korean resource patch

Apply Korean text and reviewed Korean image variants to a compatible game Data folder. This package contains no game client, launcher, or RHO archives.

## Apply

1. Install Python 3.10 or newer and Pillow: `python -m pip install -r patcher/requirements.txt`.
2. Close the game.
3. Run in PowerShell: `python patcher/apply_korean_patch.py "C:/path/to/KartRider/Data" "C:/path/to/korean-patch-output"`.
4. Review `translation-manifest.json` in the output folder.
5. Back up the original Data folder, then copy the generated files into it, preserving the folder structure.

The patcher writes changed RHO files and `aaa.pk`. It does not modify `Launcher.exe`. It uses the game's bundled Nanum Gothic bitmap glyphs and native bold/outline filters for all six locales; it does not rely on OTF or GDI font fallbacks.

## Included work

- 328 Korean string values copied from existing Korean locale entries when formatting placeholders match.
- Native bitmap font declarations for six locales, with the shipped Korean glyph set scaled for existing text styles.
- 210 exact `@kr` image counterparts and 102 visually reviewed `@zz` Korean variants.
- 312 localized image replacements across the affected RHO archives.

Some Chinese-only images have no Korean counterpart. Their embedded text remains untranslated. The package does not claim full image localization. Launcher behavior and in-game rendering still need confirmation on the target installation.

## Compatibility

Use only with a matching game data version. The patcher validates changed RHO members and updates `aaa.pk` metadata. Back up original files and restore them if the client rejects patched data.
