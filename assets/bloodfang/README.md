# Bloodfang client release assets

`native/` contains the frozen assets used by the Bloodfang v6 installer:

- `Bloodfang_male_001.jcs`: the Wonderland Platinum Dragon model, adapted for
  the pet loader by replacing texture references and adding missing animation
  aliases. Original geometry, skeleton and animation keys are preserved.
- `Bloodfang_male_001.gwo`: the unchanged native dragon texture.
- `bloodfang-portrait.png`: Bloodfang's approved original inventory portrait.

The native model was adapted from `Monster/monster_dragon_014.jcs` and its
`monster_dragon_013.gwo` texture using
`tools/bloodfang_model/adapt_wonderland_dragon.py`. Display scale and the fixed
native merge-effect paths are supplied by `tools/bloodfang_client/`, separately
from these assets. The v6 scale increase does not change any of their bytes.

`fixtures/v2/` and `fixtures/v3/` hold the previous authored dragon model and
texture pairs. They are test inputs for exact ownership checks and rollback
of upgrades from previously installed releases; the current installer does
not install them.

`manifest.json` records the size, role and SHA-256 of every packaged file.
The installer independently pins the release hashes and accepted predecessor
hashes in code. All seven assets are versioned here so installation and upgrade
checks do not depend on ignored capture or artifact directories.

From the repository root, preview the installed client without changing it:

```powershell
python tools/PatchClientBloodfang.py --client-root 'C:/Godswar Origin'
```

Add `--apply` to install with the client closed. The installer defaults to the
versioned `native/` directory and retains its guarded backup and rollback.

Run the focused checks with:

```powershell
python -m unittest discover -s tools -p 'TestClientBloodfang*.py'
```

The installed-client compatibility tests still read the native client at
`C:/Godswar Origin` for stock XML, Lua, merge effects and icon atlases. They copy
those inputs into disposable fixtures before every write. The upgrade and
portrait tests construct disposable inputs and use the versioned assets.
