# Job recovery validation

**VERIFIED deterministic/process fixtures**, not native-provider certification. Evidence: `tests/test_phase2_jobs.py`, Phase 2 test logs, and `docs/artifacts/phase2/acceptance-v3/acceptance-results.json`.

| Scenario | Tested outcome |
|---|---|
| Parallel duplicate submission | Eight requests from four threads create one job and consume one receipt. |
| Process restart/replayed key | A separate Python process returns the existing identity; no new job. |
| Two real processes compete | One CLAIMED winner, one no-job result. |
| Another active owner | No takeover before expiry; wrong worker/fence commits rejected. |
| Crash before reservation | Actual killed subprocess; after clock-injected lease expiry, CANCELLED, never requeued. |
| Crash after reservation/during execution | Actual killed subprocess; after clock-injected expiry, INCONCLUSIVE, not presumed zero usage. |
| Crash after partial checkpoint | Partial JSON retained with INCONCLUSIVE terminal state. |
| Response received but not committed | Fixture response held in killed process memory; no fabricated durable result; INCONCLUSIVE. This is not a real provider response. |
| Receipt/job transaction interrupted | Actual subprocess killed inside uncommitted submission: no job, no events, receipt remains unused. SQLite trigger failure also rolls back all effects. |
| Cancellation before dispatch | Queued cancellation terminal; claimed cancellation prevents reserve; acknowledgment is CANCELLED. |
| Cancellation after reservation | CANCEL_REQUESTED then INCONCLUSIVE acknowledgment; unknown usage preserved. |
| Deadline and heartbeat | Queue expiry cancels; expired owners rejected; heartbeat extends only within deadline. |
| Approval/role revocation | Prevents reservation; revocation before terminal commit downgrades to INCONCLUSIVE. |
| Terminal retry / unsafe ACCEPT | Terminal jobs cannot restart; offline finish rejects ACCEPT. |
| Corrupt job payload | Digest mismatch fails closed. |

No provider retries, new generation authorizations or native inference were used. A lost worker is not automatically resumed even if the work might have been harmless. Fixed offline preflight is intentionally conservative. Legacy daemon threads are preserved for trusted-local compatibility; their job histories are not automatically migrated into this lifecycle. Their background lifetime now holds the cooperative backup lock. No exactly-once external effect, hard parser cancellation or complete legacy-job recovery claim is made.

Recovery commands are explicit foreground OS-admin operations; no hidden recovery loop runs on HTTP startup. Client disconnect after submission leaves the committed row available for inspection/retry with the same key; no worker is tied to that connection. Genuine network disconnect/provider uncertainty certification remains PENDING. See the design and Phase 3 handoff before enabling any real generation worker.

Additional revocation regressions cover reviewer password reset/same-role changes after receipt consumption and submitting-operator password reset/same-role changes after job creation. Both remain INCONCLUSIVE without reservation.
