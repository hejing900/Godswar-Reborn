# Bloodfang visual revision — 2026-09-14

Bloodfang's previous native presentation turned its authored forward axis the
wrong way, and its PetInfo entries still reused Blue Crystal Dragon's portrait.
The original primitive model was also too rough. This revision fixes the facing,
rebuilds the dragon and installs an original portrait without changing the pet's
species, statistics or learned skills.

## Installed result

- Native mapping: Blender `(X,Y,Z)` to client `(-X,Z,Y)`, a proper rotation.
  Authored front negative Y now faces native negative Z, matching stock Dragon.
- Original continuous body/neck, angular muzzle, inset ruby eyes, swept ivory
  horns, curved crimson wings, claws and tapering tail; smooth normals, an
  original 1024x1024 scale/membrane texture and crevice shading.
- Six authored motions with a forward flight lean, tucked limbs, wingtip lag
  and tail movement. 5,884 triangles, 5,810 native vertices, 17 bones.
- Original Bloodfang portrait in the exclusively owned Icon2 cell `396,864`,
  both genders and client locales. Other atlas pixels are unchanged.
- Solid facial pigments sample the centers of reserved baked texture tiles;
  detailed body/wing UVs are preserved. The eye sockets use open borders.

The installed patch is `reborn.bloodfang-species46.v3`. Exactly six client files
changed: `Pet/Bloodfang_male_001.jcs`, `Pet/Bloodfang_male_001.gwo`, and both
locale copies of `Pet.xml` and `Icon2.gwo`. No server/database change or client
executable modification was needed. AresMage's existing Bloodfang is retained.

Backup manifest:
`C:\Godswar Origin\backups\bloodfang\20260914-090633-4b336277dda94a568bf30ef2d41a495e\manifest.json`.

## Validation

Native D3DX9 parsing, full GPU texture creation, skin conversion and animation
controller cloning passed. 18,000 animation updates simulated 300 seconds and
150 idle/run/attack transitions with finite transforms. Independent checks
verified the native forward axis, 209,160 skinned vertex comparisons, all 17,652
triangle corners' positions/normals/UVs and all 1,048,576 source texture pixels.
The two portrait atlases passed actual DirectX texture creation and preserve
every pixel outside the new cell. The local WebGL preview passed all six clips,
rotation, zoom, reset, play/pause and texture loading; the final eyes were
visually checked in its rasterized render.

The 22 installer regression tests, 12 model/surface tests and 11 portrait tests
passed. Installation used guarded predecessor matching, backups, atomic writes
and readback; its second plan reported no remaining changes.

These tests use the native 64-bit D3DX9 library and a separate preview renderer;
an in-game visual playtest of this revision remains for the next client launch.

## Reproduction and artifacts

Authoring: `tools/bloodfang_model/build_refined.py` in Blender 5.1.2. Native
export and validation tools are alongside it; Python dependencies are recorded
in `tools/bloodfang_model/requirements.txt`. The source atlas is authored in
Blender; the original portrait uses the built-in image generation tool, with
the full prompt saved in the artifact's `portrait-prompt.txt`.

Client integration: `tools/PatchClientBloodfang.py`; release hashes and animated
bounds: `tools/bloodfang_client/release.py`. Owned v2 predecessors are accepted,
while unrelated changes or occupied icon cells fail before writing.

All assets, editable Blender/GLB files, original portrait, source snapshot,
offline viewer and native reports are in
`artifacts/bloodfang-refined-20260914`. The final model SHA256 is
`023d46de812a4f1c1f1cc396c664106331fec1608953adcaa635f55172006091`;
the native texture SHA256 is
`2522183ad17de949a816fe97e40289885c8de3dfcd5528883c30f9b2cf3184af`.
