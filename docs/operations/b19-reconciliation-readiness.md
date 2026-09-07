# Reconciliation readiness and scan progress

The report-only worker returns `Completed`, `Truncated`, or `TimedOut`.
Truncated and timed-out reports are not clean receipts. Readiness requires
valid schema/content and a healthy bounded batch, including truncated progress.
It does not require scanning all retained history before the server can run.

`FirstPassCompleted` still records a full logical sweep; `SweepAge` tracks its
age separately. Healthy truncated batches continue after one second. Timeouts,
authority mismatches, and completed sweeps use the configured polling interval.

The runner serializes its process-local keyset continuation across invocations.
Completed character, outbox-event, and outbox-position scopes remain complete
while other scopes advance. Event and position pages alternate under their
shared outbox budget. A complete logical sweep resets all cursors.

Findings accumulate across the sweep, so a clean final page cannot hide an
earlier mismatch. Run and command timeouts retain completed pages and their
findings; the interrupted page is retried. Other failures and caller
cancellation discard that invocation's progress. An unfinished page never
advances a cursor.

A process restart starts a new sweep. Row caps bound selected entities;
statement and run deadlines bound time, including the uncapped ledger history
of an individual selected character.

For configuration, investigation, and recovery procedures, see the
[reconciliation and restore runbook](b19-reconciliation-restore-runbook.md).
