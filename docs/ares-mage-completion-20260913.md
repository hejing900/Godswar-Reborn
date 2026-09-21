# AresMage Zodiac, mount and passive MP recovery

Account `aresmage`7256 / character `AresMage`7009 received the requested fixture
completion at 2026-09-13 10:51:09 UTC. Its level remains140 and profession Mage.

Zodiac is20 with all16 grids at31, the legal character140 limits. Level21
requires character142; grid32 requires Zodiac21. Offensive selections use
learned Mage families in the correct native flat/percentage rows; defensive
rows mirror the Mage families. Energy remains20. Exact grid selections are in
the private grant readback and reviewed SQL.

The equipped mount is permanent level120 Erebus Lion16208. Its installed native
status1390 → Ride117 mapping and model/texture were confirmed. The five level120
Faithcreed pieces are Coronet14508, Armor14608, Soul14708, Saddle14808 and
Tassels14908. They occupy slots15–19, with the mount in20. All six are bound,
Mystic quality10, grade12, with legal affixes357/377/417/437/397 at level12:
magic attack, magic damage percentage, magic penetration, added magic damage
and MP recovery. Mount items have Holy Suit code0, as required by their item
category. Existing main equipment remains MysticG12/PlatinumI.

Passive recovery was working: live logs showed634MP roughly every6seconds,
from314 Mage base recovery plus320 from rank60 Gaea's Energy. Pet Merge enlarged
the mana pool without increasing this fixed rate;10729MP took17 full recovery
intervals from empty without spending. Each new G12 affix397 contributes60MP
recovery. The six add360, making the persisted calculated recovery stat680 and
the normal runtime total994MP every6seconds, a56.8% increase. These equipped
bonuses apply mounted or unmounted. The global timer/formula was not changed.
The projection was verified after the live grant; no subsequent native login
or manual rendering test was performed.

Validation used a freshly restored, disposable database copy: the combined
transaction granted six items plus six named item-audit rows, then an exact
replay inserted zero items/audits. Preservation checks compared186 public tables,
including every prior item/audit and every non-Zodiac character field. Live
execution repeated those checks in one serializable transaction while Tempest
was stopped. Inventory revision remains0, matching this fixture's existing
legacy grant convention; no paid-command receipt, ledger or outbox was invented.

Tempest restarted healthy with zero restarts on the existing image
`sha256:57ac4db77e56ce4f90d10962b57a4b7b598c5cb01dd7c64b999406dca53ea953`.
Its ports and other containers were preserved. The validated stopped backup is
79008885bytes, SHA-256
`b882d766d166e00799dee3a6aed7a4b82ea20233f02e7fae2219b7e9ac5a1396`.

Private evidence lives in `artifacts/ares-mage-completion-20260913`: immutable
combined SQL, runner, before/after readback, backup, disposable preview/replay
receipt, live grant receipt, passive MP audit and restart receipt. The executed
SQL SHA-256 is `14c933045374b396d0586c2e971875243a052f3b4267e4735c45fbb119d6a9e9`.
