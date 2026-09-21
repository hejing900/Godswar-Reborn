# Wonderland title palette

The approved eight-color palette in [the rarity table](title-rarity-order-20260912.md) is installed in both `en_us` and `zh_cn` under `C:\Godswar Origin`. Only the eight owned `DesigName.dat` rows changed. Their visible names are identical; both `DesigInfo.dat` files and every unrelated title are byte-identical to the verified backup. Server rarity sorting, selection, ownership and attributes are unaffected.

`tools/PatchClientWonderlandTitleColors.py` adds the native ARGB spans already used by the installed Medusa title rows. For example, Gatebreaker becomes `|cff4FD17BGatebreaker|cFFFFFFFF`: full opacity, the approved RGB color, the existing visible name, then the normal white reset. It adds no brackets or rarity suffix. This checks native catalog content and byte preservation; an in-game screenshot has not been taken after installation.

The color patch accepts either the complete exact plain eight-name set previously written by `PatchClientWonderlandTitles.ps1` or the complete exact approved color set. It rejects modified names, unknown colors, partial rows, duplicate IDs and mismatched owned descriptions. Each locale can independently be plain or already colored, allowing an exact completed locale to remain unchanged. Use the older title-name installer only when establishing the original title definitions; it does not own this color upgrade and its existing ownership guard rejects colored reserved rows rather than stripping them.

Run from the repository root:

```powershell
python tools/TestClientWonderlandTitleColors.py
python tools/PatchClientWonderlandTitleColors.py --mode preview
python tools/PatchClientWonderlandTitleColors.py --mode apply
python tools/PatchClientWonderlandTitleColors.py --mode verify
```

Apply checks that the client is closed before backup and immediately before publication. It backs up all four name/description files, records their SHA256 hashes, checks that the parsed preflight snapshots remain current, atomically replaces only the two changed name files and verifies all four final files. An interrupted write rolls back previously replaced files only while their bytes still match this patch; unknown concurrent changes are preserved with a `RollbackFailed` receipt and verified original backups. Reapplying the complete current palette changes nothing and creates no additional backup.

All 12 hermetic tests passed. Coverage includes independent expected color spans and visible text, actual server ID/name parity, both locales and newline styles, untouched unrelated and description rows, exact backups/idempotence, occupied and malformed IDs, encoding/size failures, client-open guards, stale parsed snapshots, second-file failure rollback and preservation of concurrent edits.

Installed September 12, 2026 at 00:02:48 UTC. Backup manifest:

`C:\Godswar Origin\backups\wonderland-title-colors\20260912-000248-b24d8cf94dd5474dbd2ff552485ea6ab\manifest.json`

| File | Installed SHA256 |
|---|---|
| en_us DesigName.dat | `32E654226C2E630683B965A55D366225DA192C12085AD8606AD2308F80191A05` |
| zh_cn DesigName.dat | `45F5F4800077061FD37611749E4C5BD1F9AE8E868D6F75A2EE942008A053D9EA` |
| en_us DesigInfo.dat (unchanged) | `49749ECFE8DD81A827DEEBC3C1C2FEB1EB05123D86CEF47725C8BEAB31FB3660` |
| zh_cn DesigInfo.dat (unchanged) | `5C07EFEE55433EFE8BD84230CF034626BED150BC5CEC794C56B1AE88FC2CAC14` |

Preview, apply, final verification and independent backup comparison are under `artifacts/wonderland-title-colors-20260912`. No client binary, packet, database or server deployment changes are part of this installation.
