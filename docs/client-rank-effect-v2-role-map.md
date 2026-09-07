# Client rank effects: v2 role map and armor authoring contract

## Status

This is the evidence base for the active role-aware design. The original v1
package and the first low-contrast metallic build were visually rejected;
their builders remain historical tooling and must not be installed. Live logs
separately proved that AR10--AR14 and aura IDs 10--14 activate correctly. The
quality/grade/elemental text palette remains a separate patch.

The active package is installed and validated at
`C:\Reborn\artifacts\rank-effect-v2-ar13-gold-ar14-celestial-blue-20260831-21`.
AR10/AR11 retain their grey/blue AR9 progression; AR12 keeps the approved
halo/wing plus AR4's orbit. AR13/AR14 use fixed route `(4,9,5)`: slot 0 AR4
orbit, slot 1 approved AR12 wing, slot 2 native AR5 animated flame
(`200v/150f`, 73 keys) at scale `1.00`/`1.06`. Flame UV stays native. Its
decoded-GWO footprint `x=0..11, y=0..32` is identical in the AR9 canonical and
private TGA; AR5 is a texture donor, not the installed canonical. WR10 is unchanged.
The live rollback is `C:\Reborn\backups\rank-effects-20260830T231433Z`.

Package `.18` is rejected: it used AR5 slot 0's small static `92v/46f` card,
not the requested animated flame. `.17` is also rejected because its private
flame target did not match its canonical. `.19` is superseded, not rejected,
and remains the correct geometry/animation baseline. `.20` is a superseded
palette baseline, not rejected. `.21` changes flame palettes only; geometry,
animation, and wing/orbit colors are unchanged. AR13 uses molten gold
`#5A2800/#E6A000/#FFF080`, gain `.86`, cap `238`; AR14 uses celestial blue
`#071F5B/#178ED6/#BDEFFF`, gain `1.03`, cap `245`. Exactly 12 install targets
differ from `.20`; the other 146, including every JCS, are byte-identical.

The superseded `.13`--`.15` capstones are rejected. They paired AR9 wing
geometry with an AR5-layout rank-wide atlas or tried ineffective private JCS
masks, rendering slabs or glyph cards instead of curved wings. Do not reinstall
them.

Earlier `.08` full-cage, `.03/.04/.05` AR8-sheet, Aether Laurel, and AR10 atlas
experiments remain rejected and must not be reinstalled. The three other class
WR10 effects remain outside the package; B20H must not be touched.

The separate text palette is also installed in the development client:
Superior is native orange, Boundless is imperial scarlet, and G25 is crown
gold. Its rollback is
`C:\Reborn\backups\client-gear-palette-20260830-111710740`.

## What v1 got wrong

JCS files are not interchangeable decorative layers: each mesh has a spatial,
animation, material, UV, and atlas role. V1 mixed families and broke those
relationships. V2 preserves each native role and changes only the role being
redesigned.

## Armor effect roles

The restored AR10--AR14 set uses three protected native families. AR9 supplies
the coherent AR10--AR12 halo/butterfly progression and the capstone butterfly;
AR4 supplies the orbit-only completion from AR12 onward; and native AR5 slot 2
supplies the capstones' animated flame. Native AR12 is not an active donor. Every
authored rank has exactly three complete loader slots; no fragment is appended
to another mesh.

| Authored rank | Slot 0 | Slot 1 | Slot 2 |
|---:|---|---|---|
| AR10 | exact AR9 core | exact AR9 butterfly | exact AR9 rune |
| AR11 | bounded AR9 core | bounded AR9 butterfly | exact AR9 rune |
| AR12 | expanded AR9 core | expanded AR9 butterfly | native AR4 orbit-only tail |
| AR13 | native AR4 orbit-only tail | exact approved AR12-transformed AR9 butterfly | native AR5 slot-2 animated flame, native UV, scale `1.00` |
| AR14 | native AR4 orbit-only tail | exact approved AR12-transformed AR9 butterfly | native AR5 slot-2 animated flame, native UV, scale `1.06` |

AR9's slots contain `116/100`, `976/848`, and `136/128` vertices/faces and keep
their native animation. Slot 1 uses U `0.392..0.496`, V `0.030..0.472`, and
forms the compact butterfly. AR9 geometry/canonical payloads remain protected.
Its JCS token remap is retained as compatibility metadata, not runtime texture
isolation.

Native AR5 slot 2 is a `200v/150f`, one-material animated flame with one track
and 73 matrix keys. Its native UV range is retained exactly. The conservative
bilinear footprint is `x=0..11, y=0..32` (396 pixels), sourced by decoding the
pinned 32-bit RLE native AR5 canonical GWO. The same tinted BGR footprint is
written at those coordinates in the 24-bit AR9 canonical and raw 32-bit private
TGA; all private alpha remains `255`. Wing/orbit sampling begins at column 20,
leaving columns 12..19 as separation. The AR5 GWO is never installed wholesale
as the AR13/AR14 rank canonical.

AR9 slot 2 is the four-loop subset of native AR4: AR4 vertices `48..183` and
faces `24..151` (reindexed by `-48`) match its positions/topology. Full AR4
adds 12 cage quads (`48v/24f`). AR12 deliberately removes that leading cage
band and retains the gender-matched AR4 tail, including its UVs, frame, and
native rotation; it never layers both copies.

AR10 copies the complete AR9 three-slot set exactly, preserving topology,
positions, UVs, materials, attachment data, and animation. AR11 retains that
family; AR12 retains its halo and butterfly and uses only the four native AR4
orbit ribbons in slot 2. AR13--AR14 reorder the capstone as AR4 orbit in slot 0,
the exact approved AR12 butterfly in slot 1, and native AR5 slot-2 flame in
output slot 2. None uses native AR12 geometry or an appended fragment.

Runtime review requires `native-uv-consistent-canonical-and-jcs-material`.
`Origin.exe` loads the rank-wide canonical while the flame JCS also uses its
declared private TGA. `.21` gives both surfaces the same tinted 396-pixel native
footprint; neither surface may be dismissed when validating visible output.

### Authored AR10--AR14 progression

AR10 keeps protected AR9 structure/animation and changes its canonical colour.
AR11 grows slot 0 by 5% in-plane with depth unchanged. Slot 1 keeps 32 inner
components fixed, shifts 12 shoulders by 25%, and moves 20 outer components by
the full bounded lift/spread: `+0.42` top, 18% span. Its `256/592` material
split is structurally retained, and the canonical supplies both groups. Slot 2
keeps AR9 geometry/animation.

AR12 uses a `1.10` planar halo scale with depth/animation unchanged. Its wing
keeps 512 anchor vertices fixed and moves 464 shoulder/outer vertices with
`+0.58` top lift, `0.24` lateral expansion, and `0.25` shoulder weighting. The
coherent AR9 butterfly stays `976v/848f`, materials `256/592`. Slot 2 is the
native-AR4 orbit-only `136v/128f` tail: four 34v/32f ribbons rotate through 13
keys over `0..1920`; the 12 cage components have no output. The authoritative
canonical supplies its deeper-blue core/rune/butterfly regions.

AR13 is the molten-gold post-AR12 bridge. It keeps the approved AR12-transformed
AR9 butterfly and AR4 orbit-only tail, adding native AR5 slot 2's animated flame
at scale `1.00`. AR14 is the celestial-blue conclusion with the same structures and
the flame at scale `1.06`. Both wings pin the
approved AR12 structural SHA-256
`2abdbcb19b1c6e44632f884f474788163518abe42b810a640b118640f223c4a8`.
Their canonical begins with the same native-AR9 `64x64`, 24-bit layout and
replaces only the native-UV flame footprint with its recoloured AR5 pixels.

| Rank | Identity | Palette | Deliberate silhouette role |
|---:|---|---|---|
| AR10 | Titansteel Inheritance | neutral steel and bright silver (`#626970/#AAB2B9/#F5F7F8`) | Exact AR9 compact-butterfly structure and animation with a neutral-grey canonical palette. |
| AR11 | Aetherwing Ascendant | canonical stormsteel wings (`#244A70/#5D9FD0/#A9D7EA`), darker halo (`#182F49/#386B91/#72ACC5`), and cyan rune (`#276D87/#63C4DE/#BFEFFF`) | AR9 animation with an unchanged inner anchor, 18% wider and `+0.42` lifted wings, 5% planar halo, and unchanged rune geometry. |
| AR12 | Aetherwing Zenith | canonical halo `#082755/#155B9F/#419BD2`, wings `#092E68/#1768B8/#43A1DE`, and darker orbit `#06275C/#125AA4/#378FCB` | Reviewed AR9 halo/butterfly plus only the four centered native-AR4 orbit ribbons; no outer cage. |
| AR13 | Crimson Phoenix | unchanged orbit `#120104/#4D0711/#8F1525`, wing `#200207/#700B1A/#BE2335`; flame `#5A2800/#E6A000/#FFF080`, gain `.86`, cap `238` | Exact AR4 orbit and AR12 wing with molten-gold native AR5 slot-2 flame at `1.00`; canonical/private match. |
| AR14 | Olympian Apotheosis | unchanged orbit `#24221B/#746B4C/#C9BB8F`, wing `#3A3422/#B7A66D/#F8EBC5`; flame `#071F5B/#178ED6/#BDEFFF`, gain `1.03`, cap `245` | Exact AR4 orbit and AR12 wing with celestial-blue native AR5 slot-2 flame at `1.06`; canonical/private match. |

The package contract explicitly requires AR10 to match the protected AR9
structural fingerprint while using a distinct canonical palette. AR11's contract
pins its reviewed AR9 mesh payloads, `32/12/20` component bands, 512 unchanged
anchor vertices, 464 moved shoulder/outer wing vertices, exact planar halo
transform, and complete active-pixel recolor coverage. It also pins the slot-1
material partition: 256 outer faces on material 0 and 592 inner/shoulder faces
on material 1. Its canonical halo/wing/rune channel ceilings are `200/220/230`.
AR12 additionally pins its exact AR9 mesh payloads, `1.10` planar halo scale,
unchanged depth and animation, `32/12/20` component bands, 512 fixed anchor
vertices, 464 moved shoulder/outer vertices, `+0.58` top lift, `0.24` lateral
expansion, `0.25` shoulder weighting, and slot-1 output `976v/848f` with
materials `256/592`. Slot 2 pins the gender-matched AR4 donor hashes, exact
AR9-subset relation, removal of `48v/24f`, four-component `136v/128f` output,
native UV/frame/13-key spin, deeper-blue canonical regions, and safe male vertex-
colour reindexing. AR13--AR14 additionally pin slot 1 to the exact approved
AR12 butterfly at `976v/848f`, materials `256/592`, and structural SHA-256
`2abdbcb19b1c6e44632f884f474788163518abe42b810a640b118640f223c4a8`;
slot 0 is the exact gender-matched AR4 orbit-only output. Slot 2 pins native
AR5 slot 2 at `200v/150f`, one material, one animation track, and 73 exact
matrix keys. UV and animation are unchanged; only the bounded centred scale is
permitted. AR13 uses `1.00`; AR14 uses `1.06`.

Each capstone canonical is a native-AR9-family `64x64`, 24-bit TGA payload
with the exact decoded native-AR5-GWO flame footprint copied at unchanged
coordinates `x=0..11, y=0..32`. The 396-pixel footprint is tinted with the
rank palette; every one of the other 3,700 canonical pixels remains identical
to the authored AR9 base. The private flame TGA is the raw 32-bit decoded AR5
atlas with only that footprint recoloured, alpha fixed at `255`, and all outside
pixels preserved. Private and canonical sampled BGR match at all 396 positions.
Contracts fail on UV remapping, footprint collision, or binding drift.

### The 64x64 armor atlas is a layout, not a canvas

The canonical `.gwo` is a TGA atlas whose regions have different jobs:

1. The large left oval/ring feeds slot 0's animated core halo.
2. The upper-middle crest/wing/lightning detail feeds the outer silhouette.
3. The lower-middle rune, flare, or triangle feeds slot 2's inner glyph.
4. The far-right vertical strip supplies narrow edge, beam, or trail detail
   reached by wrapped UVs.

Any edit must preserve this layout/transparency. A concept image or generic
texture is not a valid canonical atlas.

## Weapon effect roles

V2 starts from the client's native WR10 files and existing effect IDs, not
renamed WR7 geometry. Male and female native WR10 JCS files are byte-identical
for the audited families.

| Class | Native family / ID | Static outer-corona role | Animated travelling-spark role |
|---|---|---|---|
| Warrior | one-hand `0009` | slot 0: 78 vertices, 26 faces; U `0.517..0.835`, V `0.018..0.485`; all faces use material 1 | slot 1: 240 vertices, 80 faces; U `0.825..0.953`, V `0.049..0.186`; two animation tracks |
| Champion | two-hand `0009` | slot 0: 78 vertices, 26 faces; U `0.546..0.880`, V `0.079..0.461`; all faces use material 1 | slot 1: 240 vertices, 80 faces; U `0.897..0.995`, V `0.005..0.097`; two animation tracks |
| Priest | one-hand `0209` | **slot 1**: 52 vertices, 26 faces; U `0.510..0.769`, V `0.014..0.490`; static | **slot 0**: 240 vertices, 80 faces; U `0.897..0.995`, V `0.005..0.097`; two animation tracks |
| Mage | two-hand `0059` | slot 0: same 78/26 static family as Warrior | slot 1: same 240/80 animated family as Warrior |

The slot number is not the semantic contract: Priest reverses the order. Code
must identify and validate the native structure for each family.

In Warrior and Mage static slot 0, material 0 (`test07.tga`) is declared but
has zero assigned faces; material 1 is visible. Champion static slot 0 has the
same dead-material pattern (`male_weapontwohand_1401.tga` is material 0).
Priest's two slots each declare and use one material. V2 must neither author a
visible design into a dead texture nor accidentally revive a dead material.

For the first weapon prototype, the supported visual surfaces are limited to:

- the static outer corona around the weapon; and
- the animated travelling spark/stream along it.

Attachment frames, animation keys, slot order, topology, UVs, material-face
indices, and existing effect IDs remain native.

## Non-negotiable safety constraints

- Preserve native AR4, AR5, and AR9 donors and WR1 through WR9 exactly. The only
  AR9 byte change allowed is the reviewed shared-texture token remap above.
- AR10--AR11 retain protected AR9. AR12 keeps AR9 slots 0/1 and uses only
  native AR4's four orbit ribbons in slot 2. AR13 and AR14 use only the
  `(AR4:orbit-only, AR9:approved-butterfly, AR5-slot2:animated-flame)` route,
  fixed in that slot order. Flame UV/animation remain native; only centred
  scale `1.00`/`1.06` and its private texture name may change. The native AR5
  GWO may supply texture pixels but may not replace the AR9 rank canonical.
- Treat the rank-wide `gender_body_effect_NNNN.gwo` and the JCS-declared
  private slot-2 flame TGA as dual runtime-relevant inputs. Their native-UV
  flame footprints must remain pixel-consistent.
- Preserve topology, UVs, colours, frames, and animation except for the exact
  AR11/AR12 outer-wing partitions and pinned AR12 whole-slot completion.
- For AR11, change only the reviewed slot-0 planar scale, rigid slot-1
  component translations, and exact 256-face outer material assignment; its
  other 592 slot-1 faces remain on material 1 and slot 2 remains structurally
  unchanged. For AR12, change only the reviewed slot-0 planar scale, rigid
  slot-1 component translations, exact 256-face outer material assignment, and
  the pinned whole-slot AR4 completion described above. Slot 1 remains
  protected at 976 vertices/848 faces. AR13--AR14 copy that exact AR12 slot-1
  output into slot 1, put exact AR4 orbit-only in slot 0, and add native AR5
  slot-2 animated flame in output slot 2. Canonical/private flame pixels match
  at the unchanged native footprint.
- Never reinstall the rejected `.03`, `.04`, or `.05` AR8-ribbon hybrids. A
  future two-tendril design must be a newly authored coherent mesh, not isolated
  components extracted from AR8's disconnected mantle sheets.
- Start texture work from the stock rank/family atlas and edit its semantic
  regions intentionally.
- Keep private texture names scoped to one effect and validate the private
  flame target against the rank-wide canonical `.gwo` target.
- Concept PNGs are visual direction only. They are not client texture atlases.
- Do not change rank thresholds, server effect IDs, item rank calculations, or
  the separate quality/grade/elemental text palette in this work.
- Never install experiments into the B20H client or its observation runtime.

## Verification status and renderer review

The builder must start from a clean client state, pin protected AR4/AR5/AR9 and
WR1--WR9 assets, author five bounded armor shards plus one Warrior shard, and
fail before promotion on incomplete references, shared private assets,
role-contract drift, unsafe silhouettes, or changed protected files. For the
revised package, verification must prove:

1. AR10 is an exact per-root, per-gender clone of all three protected AR9 JCS
   structures and animations, with only metadata-token and canonical-colour
   changes;
2. AR10's canonical palette differs from AR9 while preserving luma detail,
   alpha, footer, and atlas layout;
3. AR11/AR12 halo-wing invariants pass, AR12 slot 2 and AR13/AR14 slot 0 prove
   the orbit-only native-AR4 relationship, and every capstone slot 1 matches
   the exact approved AR12 structural hash;
4. AR13/AR14 slot 2 proves native AR5's exact `200v/150f` structure, 73 keys,
   identity UV, and centred scale; canonical/private atlases pin the same 396
   native-footprint pixels and preserve everything outside them;
5. AR13/AR14 manifests pin runtime binding to
   `native-uv-consistent-canonical-and-jcs-material` and reject AR5 as the
   installed rank canonical, private/canonical drift, and AR8/native-AR12 geometry;
6. MSZIP parsing, topology, UV, material-face, animation, texture, role-contract,
   source-size, package-framework, preflight, install, and rollback checks all
   pass before any replacement is described as installed.

The remaining acceptance gate is visual review in the original renderer at
idle, walking, mounted, normal attack, skill casting, near/far camera distances,
and crowded backgrounds. Compare AR9 through AR14 and WR9 versus Warrior WR10.
The other three WR10 class families require the same native-role review before
being added; no generic Warrior assets should be copied onto those classes.

Static SVG/texture inspection can verify geometry and atlas intent, but only
the original client renderer can validate blending, billboarding, depth,
attachment, UV animation, and movement readability.

The safe butterfly-only `.02` predecessor was reproduced from the clean donor;
`.16` remains a known-good curved-wing plus AR4-orbit fallback without a flame.
`.17` is rejected because its private flame target did not match the canonical;
`.18` is rejected because it selected small static AR5 slot 0. Active `.21`
owns 24 effects/142 assets and passed eight framework checks, the 158-target
preflight, installation, and exact live verification. Verify `.21` with:

```powershell
python tools/TestArmorRank12Aether.py `
  --client-root "C:\Reborn\.tmp\rank-effect-metallic-source-20260830-02"
python tools/TestArmorRank13And14.py `
  --client-root "C:\Reborn\.tmp\rank-effect-metallic-source-20260830-02" `
  --package-root "C:\Reborn\artifacts\rank-effect-v2-ar13-gold-ar14-celestial-blue-20260831-21"
python tools/TestRankEffectV2Prototype.py `
  --package-root "C:\Reborn\artifacts\rank-effect-v2-ar13-gold-ar14-celestial-blue-20260831-21"
python tools/RankEffectPackages.py `
  --package-root "C:\Reborn\artifacts\rank-effect-v2-ar13-gold-ar14-celestial-blue-20260831-21" `
  --client-root "C:\Godswar Origin" `
  --verify-installed
```

The builder deliberately fails closed against an already-installed v2 client.
An installed client contains the reviewed AR9 compatibility remap and authored
private targets, so it is not a clean source even though AR4/AR5/AR9 donor
structures remain protected. For a future rebuild, use the disposable clean
client copy or restore the recorded pre-install rank backup; do not layer a new
baseline over installed private texture references.
