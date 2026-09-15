# Client window-title branding

The installed client does not embed `Godswar Origin` in `Origin.exe`. At
startup it reads the `AppTitle` localization record from each locale's
`Text/Message.dat`. Stock `Origin.exe` formats that value with the configured
`AreaTitle11`, `AreaTitle12`, or `AreaTitle13` record by using `%s %s`.

`config.ini` selects the active locale through `Locals` and the area record
through `Region`. The last-selected realm remains server data in
`Localization/en_us/Settings/User/LastSelectServer.xml`; it is not a branding
source and this patch never modifies it.

The native client independently appends ` - ` and the selected server/realm
name after realm selection. That behavior must remain dynamic: a Tempest
client displays `Godswar Reborn - Tempest`, while a Dwargon client displays
`Godswar Reborn - Dwargon`. Before selection, the title is exactly
`Godswar Reborn`.

The `%s %s` string at `Origin.exe` file offset `0x554FCC` is shared by five
native callers. One of them composes equipment quality and equipment name, so
changing that literal globally makes a Q20 item display only `Boundless`.
Branding must leave this shared literal intact.

The patch changes `AppTitle` and redirects only the window-title caller's
32-bit operand at file offset `0xD8047`: it points to the existing standalone
`%s` literal at virtual address `0x951528` instead of the shared `%s %s` at
`0x954FCC`. The patcher guards all four remaining shared consumers, restores
`0x554FCC` when migrating the legacy shared-literal patch, and leaves every
`AreaTitle` record, the native ` - ` separator at `0x557904`, and server data
unchanged. The base title remains bounded to 127 UTF-16 code units because the
native destination buffer holds 128 code units including its terminator.

Use the fail-closed patcher from the repository root:

```powershell
./tools/PatchClientWindowTitle.ps1 -Mode Status `
  -ClientRoot 'C:\Godswar Origin'

./tools/PatchClientWindowTitle.ps1 -Mode Apply `
  -ClientRoot 'C:\Godswar Origin' -AllowMutation
```

Apply also repairs a recognized `LegacyPatched` executable in place. It
creates a hash-verified version-3 backup under
`artifacts/client-window-title-backups/<UTC timestamp>/` before replacing
the executable or either UTF-16LE localization asset. Its versioned manifest
links the preceding backup directory, preserving the rollback chain. It
reports the exact new directory. Restore chained backups in reverse order:

```powershell
./tools/PatchClientWindowTitle.ps1 -Mode Rollback `
  -ClientRoot 'C:\Godswar Origin' `
  -RollbackFrom '<reported backup directory>' -AllowMutation
```

`Message.dat` and the executable format are loaded during startup. The patcher
refuses to change the executable while any `Origin.exe` process is running; it
never stops or edits a running process. A patched client must be launched
again to show the new title.

Run the focused regression with:

```powershell
./tools/TestClientWindowTitlePatch.ps1
```
