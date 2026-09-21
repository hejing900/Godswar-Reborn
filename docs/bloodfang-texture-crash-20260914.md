Bloodfang's first texture export contained RLE packets that crossed TGA
scanline boundaries. The initial native image-info check accepted the header,
but full `D3DXCreateTextureFromFileA` rejected its compressed pixels with
`0x88760B59` (`D3DXERR_INVALIDDATA`). Stock Dragon and Beelzeebub textures loaded
successfully on the same device. A row-bounded re-encoding of exactly the same
pixels succeeded, isolating the defect to compression rather than artwork,
mesh geometry or species identity.

The exporter now ends each RLE packet at the scanline boundary. The resulting
256x256,32-bit TGA remains4018bytes and decodes to exactly the original colors.
The corrected installed texture SHA256 is
`985ff33b98d644bea6bd1a9501f5c2e57340f3c0650b5eff01035d9eafbd15a8`;
the rejected predecessor was
`e5a68f411ef166eecf34987263ce141a5713bed805ca6f18ef4dffbbf65b038d`.
`PatchClientBloodfang.py` v2 admits only that reviewed texture predecessor or
the current bytes, backs it up, and replaces exactly one installed file.
The JCS hash remains20fb274b45e8c10b28778f7f57ff04c417b8cfea648735b860d4d8b6308baafc.
No server, database, skills, stats or executable changes were needed for this fix.

Validation against the installed corrected file passed real D3DX9 hierarchy
loading, indexed skin conversion, GPU texture creation and destruction. All
seven clips load; a cloned animation controller completed18,000 updates and
150 idle/run/attack switches simulating300seconds with finite matrices. The
new independent encoder regression verifies every packet's row boundary and
every decoded palette pixel. Fourteen client installer checks also pass.

```powershell
python tools/bloodfang_model/test_native_texture.py -v
python tools/bloodfang_model/runtime_validate.py 'C:\Godswar Origin\Pet\Bloodfang_male_001.jcs' --stress-seconds 300 --report artifacts/bloodfang-world-crash-20260914/installed-runtime-validation.json
```

The GPU probe runs the installed64-bit D3DX9_31 runtime on a hidden temporary
device. It exercises full model and texture loading but does not draw the model
or reproduce the32-bit game's entire state. The earlier interactive trace
expired and detached before the reported world crash, so it did not capture a
game fault address. The invalid texture is a reproduced defect; final stability
in the user's game session still requires confirmation after this replacement.

Evidence and the rejected texture are preserved under
`artifacts/bloodfang-world-crash-20260914` and
`artifacts/bloodfang-startup-crash-20260914/texture-encoding-probes`.
The published model package now includes the corrected texture and full native
runtime validation report. The original mesh, rig, GLB, Blender source and
rendered previews are unchanged.
