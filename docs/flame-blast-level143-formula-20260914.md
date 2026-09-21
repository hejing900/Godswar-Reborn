# Flame Blast V: level-143 comparison, September 14

Subsequent implementation and current scope are recorded in
[player skill damage alignment](player-skill-formula-alignment-20260914.md).
The sections below preserve the original analysis and its uncertainty.

The new capture supplies the missing unmerged Flame Blast comparison. One
candidate calculation reproduces the external level-139 and level-143
observations to within one damage point, including the much larger Petbird
buffed hits. This is a substantial advance over comparing the final damage
ratio. It is an analysis result; no server formula or character was changed.

## Exact new observations

| State | Magic attack | Magic damage bonus | Flame Blast damage |
| --- | ---: | ---: | ---: |
| Unmerged | 6,760 | 106.4% | 44,059 |
| Merged | 7,914 | 106.4% | 49,960 |

The outgoing Flame Blast Zodiac grid is rank 23; the overall Zodiac level
is 13. The equipped Holy sockets contribute raw critical percentage 1,010
(10.10% under the existing effect convention) and critical flat damage
1,740. These are identical to the earlier level-143 capture's sockets.
The numbers above are the captured active-buff stat state; Chocolate must
not be applied a second time to that displayed magic attack.

Unmerged 44,059 occurs on level-1 and level-2 creatures. Merged 49,960 occurs
on those creatures, the Wonderland Arrow Tower, Alpha Demon and other
Wonderland adds. Monster spawn packets do not expose numerical defense,
so this proves equal observed Flame damage across these targets, not that
every spell or every target universally bypasses defense.

## Candidate calculation

For the captured Flame Blast V outcomes:

```text
core = 1.5 * magicAttack + 90 + 95 * flameZodiacRank
damage = core * (1 + magicDamageBonus) * 1.5
              * (1 + criticalDamagePercentage) + criticalFlatDamage
```

External client content supplies the Flame V 50% tooltip coefficient,
base Power2 of 180, and a flat Zodiac increment of 95 per rank. The core
can therefore be written `MA + (MA + 180) * 0.5 + 95 * rank`. This ordering
is inferred from the captured results; the tooltip alone does not establish
the extra base-MA term or the scaling of 180.

The outer 1.5 and critical-percentage placement form a coherent critical
damage interpretation. Packet result zero uses the client's critical-style
presentation, which supports investigating that interpretation but does not
independently establish the external server's complete critical-hit policy.

| Capture context | Candidate before rounding | Observed |
| --- | ---: | ---: |
| Level 143, unmerged, MA 6,760 | 44,058.960840 | 44,059 |
| Level 143, merged, MA 7,914 | 49,959.413616 | 49,960 |
| Level 143, Petbird buff, MA 85,504 | 446,680.497576 | 446,680 |
| Level 139, merged, MA 7,488, Zodiac 25 | 37,228.446000 | 37,228 |
| Level 139, Petbird buff, MA 80,908, Zodiac 25 | 336,561.786000 | 336,562 |

The level-139 character has no Holy sockets, so both critical socket terms
are zero. Its earlier rank-24 casts at MA 7,262, 7,342 and 7,488 also match
the observed 36,049, 36,375 and 36,970 after nearest rounding.

The level-143 merged candidate rounds to 49,959, one below the recorded
49,960. Intermediate rounding or hidden precision remains unresolved;
the calculation is not claimed to be an exact recovered implementation.
Do not add a fitted constant merely to hide this difference.

Independent Decimal replay verifies 16 selected checkpoints, with a maximum
absolute difference of 0.586384 damage. A broader audit also finds 546 stable
hits across 385 casts, 11 session/stat/rank contexts and five sessions within
one damage point. Two additional casts change magic attack during their
windup; both fit when using the separately transmitted impact-time stat
state. They are retained as transition evidence rather than silently dropped.

## Implications for Reborn

The existing normal-hit calculation applies a 0.5 multiplier after defense,
adds `180 + 100 * ZodiacRank`, multiplies the typed bonus, and adds magical
append afterward. Its critical path adds the critical percentage to the
base 50% critical bonus. These choices differ materially from the candidate
above. Increasing AresMage's equipment bonuses cannot repair that mismatch.

Native pet reconstruction predicts an additional magical-append channel
on Merge, but adding that amount directly to this Flame candidate breaks
the otherwise consistent unmerged/merged comparison. Its participation in
other spells must be investigated separately. Likewise, this Flame result
must not be substituted into Fireball, basic attacks, PvP or all boss skills.

## Reproducible evidence

- Frozen capture: `artifacts/flame-blast-level143-20260914/external-level143.log`.
  SHA-256: `e3ac8a33da35da4e5c34211487af5e199c48a1f0e3e26cbaec79655c2926b8f4`.
- New frames: 99599 through 103916; character object 81.
- Equipment entry 99663; pet record 99674; Zodiac 99777;
  unmerged stats 99824; merged stats 101444.
- Open-world Flame damage frames 101184, 101372, 101555 and 101651.
- First clean Wonderland tower field: 102541, 102571, 102611, 102678, 102728.
- Semantic decoders and outputs: the capture folder's `combat`, `context`
  and `formula` subdirectories. Raw login payloads are not included in reports.

No additional instance entry is needed for this comparison.
