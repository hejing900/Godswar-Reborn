# Holy Stone reagent artwork

Eight original inventory icons generated with built-in ImageGen. The exact
shared and per-item prompts, selected output paths, and source hashes are in
`generation.json`; selected masters are in `source/`. Original generated
files are retained outside the repository as well.

- Eclipse I: indigo stone with a silver crescent.
- Eclipse II: amethyst stone with a partial amber eclipse.
- Eclipse III: violet stone with a complete golden corona.
- Goddess' Stone: ivory mineral with a gold divine star.
- Evasion Signets: matching Copper, Silver, Gold, and Platinum shield rings.
  Platinum has a cyan shield gem and protects Holy Stone level 7 to 8.

`manifest.json` fixes the eight item IDs and 36px cells. The dedicated
`HolyStoneReagents.gwo` avoids overwriting old cells shared by unrelated items.
`generated/preview.png` shows enlarged icons beside native inventory size.

With Python and Pillow 12.0.0:

```powershell
python tools/PrepareHolyStoneReagentIcons.py
python tools/PrepareHolyStoneReagentIcons.py --check
```

The installer needs only standard Python:

```powershell
python tools/PatchClientHolyStoneReagentIcons.py --mode preview
python tools/PatchClientHolyStoneReagentIcons.py --mode apply
python tools/PatchClientHolyStoneReagentIcons.py --mode verify
```

Installation backs up exact originals, preserves unrelated metadata and help,
installs both locale copies, and verifies readback. Restart the game client to
reload its cached item names, textures, and Holy Stone instructions.
