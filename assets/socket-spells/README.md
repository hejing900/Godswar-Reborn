# Socket Spell icons

Four original scroll sprites generated through built-in ImageGen. Exact shared
and per-tier prompts, selected generated paths, and master hashes are recorded
in `generation.json`; the selected original PNGs are in `source/`.

| Item | Design | Socket marks |
| --- | --- | ---: |
| Socket Spell I | Copper and emerald | 1 |
| Socket Spell II | Silver and sapphire | 2 |
| Socket Spell III | Gold and violet | 3 |
| Socket Spell IV | Gold, ivory, and crimson | 4 |

The original four items share one stock icon cell with unrelated items. The
new `SocketSpells.gwo` gives each spell its own 36px cell without changing the
shared stock atlas. `manifest.json` fixes the item IDs and coordinates.
`generated/preview.png` shows each icon enlarged beside actual inventory size.

Prepare with Python and Pillow 12.0.0:

```powershell
python tools/PrepareSocketSpellIcons.py
python tools/PrepareSocketSpellIcons.py --check
```

Install with standard Python:

```powershell
python tools/PatchClientSocketSpellIcons.py --mode preview
python tools/PatchClientSocketSpellIcons.py --mode apply
python tools/PatchClientSocketSpellIcons.py --mode verify
```

The installer backs up exact originals and updates both locale copies. It
preserves other item definitions, original atlas pixels, and existing artwork.
Fully restart the client to reload the new inventory textures.
