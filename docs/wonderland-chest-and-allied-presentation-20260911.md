# Wonderland chest and allied presentation

The island-five friendly monsters were correctly protected by the server but serialized with hostile native camp 2. Their opcode-10020 spawn now carries the existing faction camp of the allied spawn policy: 0 for Sparta or 1 for Athens. Opposing actors and ordinary monsters retain camp 2. The run's fixed party allegiance, progression objectives, health, attack rules and reward ownership are unchanged.

This is a native field correction. Origin.exe at 0x4EC191 copies wire byte 5 into monster actor+0x292, then compares that byte with the local player's camp at 0x4EC1C9. Equal camps take the friendly registration branch; camp 2 takes the ordinary-monster branch. Monster name rendering also compares those camp fields at 0x483D79–0x483D95. The source packet's low byte remains monster discriminator 0x12 and its high word remains map 207. Current-vitals appearance reconstruction preserves the camp byte.

Allied marshals and supporters remain immune to direct and periodic player damage. Their runtime still excludes player targets, while the separate existing allied-assistance path can attack hostile monsters. This change does not turn an allied actor into a new kill objective or alter the faction chosen for a mixed party.

## Chest appearance and limits of the evidence

All eight island treasures keep their distinct object/interaction IDs 5710–5717 and their existing Fane_008 through Fane_016 template keys. Island five keeps the opposing marshal's chest key according to the fixed party faction. No chest is renamed to the first island's chest, and reward routing is unchanged.

The installed Origin en_us and zh_cn NPC.INI files already give all nine possible chest templates identical appearance fields except their names: mesh monster_ark_003.jcs, texture monster_ark_003.gwo, Range 1, Shadow 1.5, the same avatar values and no Scale field. Both referenced files exist and are nonempty. The native constructor reads the mesh and texture from those same global template entries and applies a common direct-mesh transform. No chest-key or island-specific size branch was found in this bounded constructor/render audit.

The server's one NPC appearance constructor is used for all eight chests, with the same 108-byte frame, type 0x00CF0211, level/vitals constants, zero Y and empty detail packets. Their intentional differences are identity, template and position. Before this change, islands one through three additionally used captured facing 3.0718751 while later islands used zero. All eight now use the first three's orientation, whose literal float bytes at wire offset 40 are `9A994440`.

That field is **orientation, not scale**. The deferred NPC receiver writes it to actor+0x4D4 at 0x473BD3; rendering reads it at 0x48BB6B and constructs an axis-angle matrix at 0x48BB9C. Uniform orientation is a verified consistency change, not proof that the reported small rendered chest has been resized. The live log confirms actual clicks on treasure 5714/Fane_013 and 5715/Fane_014, but contains no outgoing 10020 payload or screenshot. A client playtest is still needed to establish whether matching orientation resolves the user's observed size difference. An appearance alias to Fane_008 would select the same mesh and lose the original native label, so it was not introduced.

## Evidence and validation

`artifacts/wonderland-visual-consistency-20260911/appearance-evidence.json` records client/table/mesh hashes, exact normalized fields and the three captured treasure spawns. The adjacent audit.py regenerates that bounded, sanitized evidence; native-*.txt files retain the relevant receiver, rendering and constructor instructions. The capture SHA-256 is cfdc5025ac07b42a198bb06716ed291ee97c36f7b6266cd979508e69329dde73. Origin.exe SHA-256 is 3d9715424f94f05c852ae691d446d52a9f51732d0a94112438f7cacc45581447. No client files were changed.

The focused protocol check is `Wonderland chest appearance identity and allied native camp presentation`. It covers both engines and both camps; exact native spawn/reprojection headers; five friendly and five opposing island-five actors; rejected direct/periodic attacks and absence of allied player attacks; eight distinct chest identities and reward-island mappings; and literal captured facing bytes. The existing `Wonderland live eight-island publication, committed clears, and isolated retirement` check also understands the corrected allied camp. Build/test outcomes are recorded separately by the coordinated release run.
