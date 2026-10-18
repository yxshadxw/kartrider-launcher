# KartRider Launcher and resource patches

This fork contains the upstream launcher source and separate English and Korean resource patch packages.

## English resource patch

Get the [latest English patch release](https://github.com/yxshadxw/kartrider-launcher/releases/tag/en-patch-2026.10.18.1). See [english-translation/README.md](english-translation/README.md) for instructions. It translates supported game text, fixes several machine-translated UI strings, and converts the shipped Korean bitmap glyphs to the game's native bitmap-font format. Images are unchanged.

## Korean resource patch

Get the [latest corrected patch release](https://github.com/yxshadxw/kartrider-launcher/releases/latest). See [korean-translation/README.md](korean-translation/README.md) for instructions. The package translates supported in-game strings, uses the game's native Korean bitmap font, and replaces 312 image assets with existing Korean variants. It works on a user's own compatible game installation and does not redistribute the game client or RHO archives.

The Korean patch does not modify `Launcher.exe`. Some Chinese-only images remain untranslated, and in-game runtime rendering has not been confirmed.

## Upstream

The launcher source remains from [MokeyBanana/kartrider-launcher](https://github.com/MokeyBanana/kartrider-launcher).
