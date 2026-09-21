# Wonderland final completion

Wonderland now completes after all four final-island bosses have been killed and
the chest guard is defeated. Scorpion King alone does not start the countdown.

The final island has five required actors: Minotaur, Titan's Xmas Deer, Iberian
Dragon King, Scorpion King, and the original Chest Guard. All eight Atlas remain
present and dangerous, including their death FireBlast, but are optional for
completion. Existing object IDs, positions, stats, loot and skill definitions are
preserved.

The guard remains passive and unavailable for damage or control until all four
boss deaths have been credited to the exact run. Unlocking uses the committed
progress snapshot under the established Wonderland-before-monster lock order;
an uncredited zero-HP boss cannot unlock it early. The death ledger also rejects
an early guard credit.

Defeating the unlocked guard records island eight, grants its title without
equipping it, unlocks the final treasure, and starts the existing five-minute
treasure countdown. The announcement still waits for the player or party to
leave. Surviving optional monsters remain available during that window.

Regression checks cover Scorpion-first kill ordering, early guard rejection,
completion with every Atlas alive, countdown and durable title handling, deferred
announcements, and an Atlas death blast resolving once after guard completion.
The survivor combat fixtures now exercise an optional Atlas rather than treating
the required guard as a post-completion survivor.

## Deployment and validation

The final Release checks cover 43 passing protocol groups across the Wonderland
suite and the focused reset/navigation/guard reruns. Nine PostgreSQL integration
groups were skipped because no test connection was configured; this correction
does not add a database migration. Bloodfang's separate installation/upgrade
suite passed 44 checks. Detailed local receipts are consolidated in
`artifacts/wonderland-final-reset-20260915/verification-summary.json`.

Deployed to `godswar-dev-tempest-openworld-01`, verified healthy with login 5999
and game 7000 listening. Image:
`sha256:25d4b3b404ba57928116c30e270fdadbd5dafd9ee9696be479e01d7c8708c710`.
Rollback image tag: `reborn-server:before-wonderland-final-reset-20260915`.

The normal Docker restore encountered NuGet TLS `PartialChain` on this machine.
The successful build used the same Dockerfile stages with an offline feed of the
six exact locally cached package versions. Their NuGet content hashes, archive
hashes and author/repository signatures were verified before use. TLS validation
was not disabled. The temporary Dockerfile, package manifest and signature/build
logs remain in the ignored deployment artifact directory; NuGet vulnerability
auditing was disabled only for that offline restore.
