Bloodfang is now a small vampiric dragon, following the user's chosen shape.
The earlier vampire-bat proposal is preserved separately. This version has an
elongated fanged snout, swept ivory horns, scaled neck and belly, four clawed
limbs, two separate crimson wings, and a long segmented tail with a crimson tip.
The model, rig and animation poses are original; no existing GodsWar pet mesh
was imported.

Open preview/viewer.html for an offline interactive preview. Drag to rotate,
scroll to zoom, and choose an animation. Play/pause, speed and the timeline let
you inspect poses. Arrow keys rotate; plus/minus zoom. The viewer contains all
its data locally, uses no external libraries or network requests, and respects
the reduced-motion preference. Keep the complete preview folder together.

The editable Blender source is bloodfang-original.blend; the portable animated
model is bloodfang-original.glb. The shared filenames belong to this dragon
package. It has 4,892 triangles, 2,814 source vertices and 17 bones. Hard normals
and material boundaries produce 10,090 export vertices. Six original clips are
included: Idle, Move, Attack, Death, Angry and Happy. The attack animates the jaw;
four tail segments move independently. Hero/rear views and the animation contact
sheet are included for quick review.

The native directory contains Bloodfang_male_001.jcs and
Bloodfang_male_001.gwo. The first is an MSZIP binary DirectX X model; the second
is an original 256x256 palette texture in 32-bit RLE TGA format. A presentation
root converts the authored Blender Z-up coordinates to native Y-up. Animation
names follow the client's nomal_* spellings, including nomal_attack_01 as an
alias of the original attack. Separate sex/rebirth appearances are not authored.

Validation:

- Blender mesh validation passed without repairs; weights normalize correctly.
- GLB contains one skin and all six animations.
- Hero, rear, opening-jaw attack, tail movement and death renders were inspected.
- Microsoft's D3DX9_31 parser accepts the model and recognizes its texture.
- Full D3DX9 hierarchy loading, indexed skin conversion and GPU texture creation
  pass with the corrected, row-bounded TGA encoding. A cloned controller passes
  18,000 animation updates and 150 clip switches with finite matrices.
- Independent native skinning checks compare all vertices in the bind pose and
  five representative poses per clip against the Blender world-pose matrices.
  All 363,240 vertex comparisons meet the 0.00002-unit tolerance.
- The offline preview's six poses render distinct images. Browser checks passed
  for rotation, zoom, camera reset, play/pause, timeline and WebGL error state.

This asset was installed as Bloodfang species46 on 2026-09-14. Its initial
texture compression was corrected after installation; this package contains
that correction. In-game scale, lighting, transitions and playback speed still
need a client playtest. The native export uses a chosen 4800-tick timebase.
Installation details are in docs/bloodfang-install-20260914.md; the texture
failure and correction are in docs/bloodfang-texture-crash-20260914.md.

Rebuild from C:\Reborn:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' --background --python tools/bloodfang_model/build_bloodfang.py -- --output artifacts/bloodfang-vampiric-dragon-20260914
python tools/bloodfang_model/native_export.py artifacts/bloodfang-vampiric-dragon-20260914/bloodfang-original.mesh.json --schema artifacts/bloodfang-vampiric-dragon-20260914/native-x-templates.bin --output artifacts/bloodfang-vampiric-dragon-20260914/native
python tools/bloodfang_model/native_validate.py artifacts/bloodfang-vampiric-dragon-20260914/native/Bloodfang_male_001.jcs --texture artifacts/bloodfang-vampiric-dragon-20260914/native/Bloodfang_male_001.gwo --report artifacts/bloodfang-vampiric-dragon-20260914/native/native-parser-final.json
python tools/bloodfang_model/validate_animation.py artifacts/bloodfang-vampiric-dragon-20260914/bloodfang-original.mesh.json artifacts/bloodfang-vampiric-dragon-20260914/native/Bloodfang_male_001.jcs --report artifacts/bloodfang-vampiric-dragon-20260914/native/animation-semantic-validation.json
python tools/bloodfang_model/build_viewer.py artifacts/bloodfang-vampiric-dragon-20260914/bloodfang-original.mesh.json --output artifacts/bloodfang-vampiric-dragon-20260914/preview
python tools/bloodfang_model/package_model.py artifacts/bloodfang-vampiric-dragon-20260914
```

The native schema prefix contains eight standard template declarations and zero
model, rig or animation objects. Native API/header provenance is recorded in the
earlier format investigation at artifacts/bloodfang-original-pet-20260914.
The separate new-species integration scope there records the 45-species guards
that must be extended before Bloodfang is activated as a new pet.
