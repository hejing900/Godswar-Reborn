# Holy Stones and Spirits

This package replaces the inventory artwork for three Holy Stones, ten Fire
Spirits, ten Water Spirits, and four Zephyr Spirits. IDs, names, prices, grades,
stack limits, compatibility, and combat behavior remain unchanged.

`manifest.json` owns the existing item-to-cell mapping. `generation.json`
records the built-in ImageGen prompts and exact source hashes. The independent
packer requires Pillow 12.0.0 and retains each source's square framing and
alpha, using premultiplied-alpha Lanczos to produce 36px sprites.

The three stones use broad faceted mineral bodies with a central flame, frost,
or wind vein: ember red, sapphire blue, and pale jade respectively. Spirits use
flowing elemental forms around large effect symbols. Fire is crimson/gold,
Water sapphire/cyan with green recovery cores, and Zephyr jade/ivory with gold
accents. All 27 masters were generated individually with the built-in tool.
Stone prompts are in `generation.json`; its spirit entries refer to the full
shared brief and individual prompts in `prompts/spirits.json`.

`generated/preview.png` shows the complete set at 144px and actual 36px sizes;
`generated/icons-native.png` is the native strip. The final generated masters
remain under `source/`, and the generated release records their hashes.

## Prepare and install

```powershell
python tools/PrepareHolyStoneSpiritIcons.py
python tools/PrepareHolyStoneSpiritIcons.py --check
python tools/TestHolyStoneSpiritIcons.py -v
python tools/PatchClientHolyStoneSpiritIcons.py --mode preview
python tools/PatchClientHolyStoneSpiritIcons.py --mode apply
python tools/PatchClientHolyStoneSpiritIcons.py --mode verify
```

The installer itself uses the standard Python library and does not require
Pillow. The preparer and tests require `Pillow==12.0.0`.

Only four live files are replaced: `Icon2.gwo` and `Icon5.gwo` under the
`en_us` and `zh_cn` client texture directories. The installer validates both
locales' existing item and socket metadata but does not modify it. It accepts
only the exact pinned baseline or the exact generated release, backs up all
transaction inputs beneath the selected client's `backups/holy-suit-tiers/`,
verifies readback, and restores earlier writes if publication fails. Repeating
the installation makes no changes. Restart the client to refresh texture caches.

## Isolation and compatibility

`base/` contains the exact pre-redesign client atlases, with hashes pinned in
the manifest and the tooling. Every decoded pixel outside the 27 owned cells
is preserved. This includes stock upgrade materials and elemental-stone art
in Icon2, plus all seventeen prior Aether/concept cells in Icon5.

The pinned Icon2 baseline has an old TGA footer extension pointer left behind
by an earlier local patch. The packer repairs only that pointer, from 2073610
to the actual extension position 2099511, before applying the new artwork.
Generated RLE containers preserve native header, extension, footer fields,
pixel orientation, and alpha; the extension pointer then follows the new
stream length. Both the native parser and Pillow independently validate output.

The native mounted Zephyr display reads the central 20px square of the Holy
Stone cell at `620,8`. `generated/zephyr-socket-20.png` exposes that exact crop
for review. Original Fire/Water mounted-socket glyphs are separate `main.gwo`
artwork and are outside this inventory icon release.

Default `PrepareHolySpiritIcons.ps1` and `InstallHolySpiritIcons.py` commands
delegate to this current release. The PowerShell preparer uses `python`, or
the executable specified by `GODSWAR_ASSET_PYTHON`. Explicit custom asset roots
retain the earlier 22-image tool behavior. The current installer deliberately
rejects legacy `--force` and `--backup-root`; unknown atlas content requires
review rather than replacement.

The four existing sustain items are included visually: Water Renewal/Vitality
9068/9069 and Fire Flow/Tranquility 9088/9089. The older proposed Aether names
and art are not their live item definitions. Their authoritative effectiveness
activation remains unchanged by this package.
