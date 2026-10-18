# KartRider Korean resource patch

This package applies Korean text, Korean font resources, and reviewed Korean image variants to an existing compatible game Data folder. It does not include the game client, launcher, or RHO archives.

## Apply

1. Install Python 3.10 or newer.
2. Close the game.
3. Run in PowerShell:
   python .\patcherpply_korean_patch.py "C:\path	o\KartRider\Data" "C:\path	o\korean-patch-output"
4. Check the generated translation-manifest.json.
5. Back up your original Data folder, then copy generated files into it, preserving the folder structure.

The patcher emits changed RHO files plus aaa.pk. It does not modify Launcher.exe.

## Included work

- Korean values copied from existing Korean locale strings where formatting placeholders match.
- Korean font configuration and Source Han Sans Korean Medium/Bold OTF files (SIL Open Font License).
- 210 exact @kr image counterparts and 102 visually reviewed @zz Korean variants.
- 312 localized image replacements across the affected RHO archives.

Some Chinese-only images do not have Korean variants. Embedded text in those images remains untranslated; this package does not claim full image localization. Launcher behavior and runtime rendering were not changed or verified.

## Compatibility

Use only with a matching game data version. The patcher validates RHO headers and member roundtrips and updates aaa.pk metadata. Back up your original files and restore them if the client rejects patched data.
