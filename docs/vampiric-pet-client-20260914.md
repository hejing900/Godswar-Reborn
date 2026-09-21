Vampiric adds six pet-skill tiers that restore 6%, 8%, 11%, 14%, 17% and 20% of damage actually inflicted. Family428 is new; family427 already belongs to Spiky Armor. The server owns the percentage calculation, successful-hit eligibility and per-target settlement. This client change supplies skill/book names, descriptions and existing icons.

| Tier | Runtime skill | Book | Accuracy required | Healing |
|---|---:|---:|---:|---:|
| I | 6400 | 16400 | 0 | 6% |
| II | 6401 | 16401 | 64 | 8% |
| III | 6402 | 16402 | 192 | 11% |
| IV | 6403 | 16403 | 235 | 14% |
| V | 6404 | 16404 | 270 | 17% |
| VI | 6405 | 16405 | 305 | 20% |

Each tier has one rank0 step. The XML Trait vector expresses Accuracy in hundredths, matching existing Extraction II (`6400` for64). Skill rows reuse Lifedrain's native icon at684,792 and known Genre34/Effect34. Books reuse Icon2.gwo at216,972, `consume item`, Use1, Overlap99 and zero price. TierI uses native ItemType4; upgrades use ItemType3 and the preceding tier.

Native compatibility evidence is in `artifacts/vampiric-pet-20260914/client/native-loader.json`. The installed loader reads ID, Type and Priority as integers (6A748C,6A75E7,6A7615) and stores IDs in a tree through6AE4F0; that loader does not index a fixed array ending at6323 or reject family428. This is a bounded static loader audit, not an in-game acceptance result.

`fact_Value` is parsed by native integer conversion at6A7C74–6A7C84. The new rows explicitly set it to0 so the client does not introduce a flat healing value. Fractional `Values` retain the server contract, but tooltips use explicit percentages and never interpolate `%Values%` or `%Restrict%`. No executable, effect or atlas is patched. Native HP updates continue to come from authoritative packets.

Run from the repository:

```powershell
python tools/TestClientVampiricPet.py
python tools/PatchClientVampiricPet.py --mode preview
python tools/PatchClientVampiricPet.py --mode apply
python tools/PatchClientVampiricPet.py --mode verify
```

The default roots are `C:\Godswar Origin` and `C:\Reborn`; both may be overridden explicitly. Preview reads all13 targets before any installation. For both installed en_us/zh_cn locales it changes Pet_Skill.xml, ItemBaseAttribute.xml, Message_Pet.dat, EquipName.dat and EquipDescription.dat. The repository mirror changes only its three existing English item files: ItemBaseAttribute.xml, EquipName.dat and EquipDescription.dat. Pet definitions/text remain reproducible from the small maintained patch tool; no full legacy pet catalog is copied into the repository.

New text is English in both locales. Existing GB2312 pet XML bytes, UTF16/UTF8 text encodings, BOMs and unrelated rows remain intact. The external capture client is not a target. Apply checks for running GodsWar executables twice, backs up exact bytes for both roots under `C:\Godswar Origin\backups\vampiric-pet\<timestamp>\`, verifies all preflight inputs again, and replaces files atomically. A failure rolls back recognized written bytes across both roots; unrelated concurrent changes are preserved and reported. Unknown IDs, duplicate or modified new entries, family collisions, changed native prerequisites and missing icon atlases fail closed.

The12 hermetic tests pass, covering exact tier/trait/flag contracts, static tooltip percentages, encoding preservation, collision rejection, both repository and locale updates, process guards, full backups, stale inputs, rollback after a late repository failure and concurrent-edit preservation. Preview against both actual roots succeeds. Installed application and byte-for-byte readback passed for all 13 files on 14 September 2026. In-game visual acceptance still requires launching the client; no executable was changed.
