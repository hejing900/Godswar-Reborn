# Bloodfang display size — 2026-09-15

Bloodfang's miniature Wonderland Platinum Dragon appearance is 50% larger.
The native scale is now 0.525 before rebirth and 0.5775 for the other three
rebirth stages, up from 0.35 and 0.385. Both genders use the same sizes.

The v6 installer accepts the exact v5 model configuration and changes only
the `Scale` attributes. The original model, texture, portrait, animation,
bounds and repaired merge-effect paths remain intact. No pet stats or skills
were changed. Other appearances and species are unaffected.

Validation: all 44 Bloodfang installer, portrait, upgrade and merge-path tests
passed. The v5 upgrade check verifies exact preservation of every byte except
the eight scale values in each locale, including encoding and newlines.

Installed with the client closed in `C:\Godswar Origin`. Only the English and
Chinese `Settings/Sys/Pet.xml` files changed. Readback matched the expected
scale-only replacement, all 16 merge-effect references resolved, and the
post-install plan was unchanged. The larger model is loaded on client startup;
visual confirmation in the game is pending.

The installer release model, texture and portrait, plus the v2/v3 upgrade-test
predecessors, are packaged under `assets/bloodfang/`. Default installer paths
and tests use those versioned files instead of ignored artifacts. This only
changes source packaging; the installed client asset hashes and v6 profile
are unchanged.

- Reports: `artifacts/bloodfang-scale-20260915/`
- Backup manifest:
  `C:\Godswar Origin\backups\bloodfang\20260915-050147-06e2e753b1594f8ba3667aef795feab9\manifest.json`
