Bloodfang is an original vampire-bat pet model for the Vampiric skill family.
Its charcoal body, crimson wing membranes, shaped ears, fur crest, ruby eyes,
curved ivory fangs and claws were authored procedurally in Blender. No existing
pet geometry, skin, rig, weights or animation poses were imported.

The editable source is bloodfang-original.blend. The portable animated model is
bloodfang-original.glb. Both contain 3,810 triangles and a 12-bone rig, with six
original actions: Idle, Move, Attack, Death, Angry and Happy. The mesh has 2,187
source vertices; flat normals and material boundaries produce 7,952 export
vertices. Both counts fit the native format's 16-bit mesh-index range.

Previews:

- bloodfang-hero.png: three-quarter studio view.
- bloodfang-rear.png: rear view.
- bloodfang-animation-contact-sheet.png: representative poses from all six clips.

The native directory contains Bloodfang_male_001.jcs, an MSZIP binary DirectX X
model, and Bloodfang_male_001.gwo, an original 256x256 palette texture encoded as
32-bit RLE TGA. The exporter transforms the original Blender Z-up coordinates to
native Y-up, writes the authored skeleton and skin weights, and maps actions to
the client's nomal_* identifiers. It adds nomal_attack_01 as an alias of Attack.
The suffix identifies this first asset; separate sex/rebirth variants have not
been authored yet.

Validation completed:

- Blender mesh validation needed no repairs; skin weights normalize correctly.
- GLB contains all six actions and one skin.
- Front, rear and motion renders were visually inspected. Hover and death-pose
  root orientation were corrected before final export.
- The exported JCS was decompressed and its topology read back.
- Microsoft's installed D3DX9_31 parser accepted all 305 data objects, 84
  references and seven named animation sets in the final JCS.
- D3DX recognized the GWO as a 256x256 TGA image.

These are file-format and authored-render checks. Bloodfang is not installed or
registered as a live pet. In-game lighting, animation playback speed, scale and
animation transitions still need a client check when species 46 is integrated.
The export uses a chosen 4800-tick timebase; actual game timing was not measured.
Existing client assets, pets, account state and server containers were unchanged.

Rebuild from C:\Reborn using the source tools in tools/bloodfang_model:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' --background --python tools/bloodfang_model/build_bloodfang.py -- --output artifacts/bloodfang-original-pet-20260914
python tools/bloodfang_model/native_export.py artifacts/bloodfang-original-pet-20260914/bloodfang-original.mesh.json --schema artifacts/bloodfang-original-pet-20260914/native-x-templates.bin --output artifacts/bloodfang-original-pet-20260914/native
python tools/bloodfang_model/native_validate.py artifacts/bloodfang-original-pet-20260914/native/Bloodfang_male_001.jcs --texture artifacts/bloodfang-original-pet-20260914/native/Bloodfang_male_001.gwo --report artifacts/bloodfang-original-pet-20260914/native/native-parser-final.json
```

The schema-only prefix contains standard DirectX template declarations and zero
mesh, rig or animation data. The native validator uses documented Microsoft SDK
interfaces: https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3dxfilecreate
and https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3dxgetimageinfofromfileinmemory .
Inspection provenance and the subsequent species-integration scope are separate
artifacts beside this README. The new-species scope identifies the existing
45-species guards that must be extended before a new pet is activated.
