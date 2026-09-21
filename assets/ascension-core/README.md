# Ascension Core

Item 9025 replaces the player-facing Experience Prism name with Ascension Core.
It remains the same bound, stackable Holy Suit catalyst, created from
100,000,000 character EXP and consumed by the existing advanced upgrade rules.
It is also sold after Holy Box V in the Bound Gold Vendor's Holy Suit tab for
50,000 B-Gold per core, with the same bound item and stack cap of 99.

The icon is an ivory-and-gold casing around a luminous energy heart, with teal
shadow accents. It was generated with built-in ImageGen. Exact prompts,
selected original output path, and source hashes are in `generation.json`;
the selected master is `source/ascension-core.png`.

The dedicated `ExperienceCatalyst.gwo` uses cell 0,0 for this one 36px icon.
It preserves the previously approved Icon2 atlas and other item artwork.

Prepare with Python and Pillow 12.0.0:

```powershell
python tools/PrepareAscensionCoreIcon.py
python tools/PrepareAscensionCoreIcon.py --check
```

Install with standard Python:

```powershell
python tools/PatchClientAscensionCore.py --mode preview
python tools/PatchClientAscensionCore.py --mode apply
python tools/PatchClientAscensionCore.py --mode verify
```

The installer backs up exact originals and updates both locales' item name,
icon mapping, descriptions and Holy Suit instructions. It preserves unrelated
text and existing mechanics. Fully restart the client to load the changes.
