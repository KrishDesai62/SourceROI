# Phase 2 engineering report — durable offline execution and complete recovery

Date: 2026-11-14. Existing standalone SourceROI. **No new real model calls, paid API/cloud use, production database changes, downloads or public deployment.** Tests and acceptance use temporary authored fixtures. Historical inference authorization remains consumed.

| Result | Classification |
|---|---|
| Required pre-change baseline | **VERIFIED:** 448 passed in 20.36 s before implementation. |
| Durable SQLite offline job orchestration | **VERIFIED internal acceptance:** transactional submission, idempotency, owner leases/fencing, checkpoints, cancellation and conservative recovery. |
| Authenticated approval/job binding | **VERIFIED internal acceptance:** receipt consumption and job creation in one private SQLite transaction; live role/version checks preserved. |
| Complete quiesced backup and independent restore | **VERIFIED internal acceptance:** sources/config/tasks/snapshots/history/artifacts recovered, identities matched; no live credentials/sessions/receipts/jobs restored. |
| Final regressions | **VERIFIED:** **500 passed in 25.22 s**, including 52 added parametrized test cases. |
| Historical preservation | **VERIFIED:** **938/938** captured historical artifact/root/doc files unchanged. |
| Real generation durability and production deployment | **PENDING:** no provider-dispatch worker enabled or certified; authenticated generation remains disabled. |
| Hostile-document processing, independent semantics/customer value | **PENDING**, not supplied by job or backup fixtures. |

**Phase 2 verdict:** scoped offline orchestration and stopped-writer recovery acceptance pass. This is not an unqualified completion claim for durable real-provider execution or production readiness. The worker performs a fixed offline release preflight; it does not execute actual RAG evaluations. A real authenticated evaluation worker and native-authorization integration remain gated for later acceptance. Single-tenant production, multi-tenant SaaS and enterprise readiness are not established.

## Audit and implementation plan

Before changes, the complete suite was run and its 448-pass log retained. Inspected: existing identity/receipt SQLite, `db.py` run/history storage, synchronous API routes, daemon-thread evaluation, in-memory semaphore/current progress, CLI, source snapshots and hashes, strict release validation, native execution controls and SQLite-only backup. The prioritized plan was recorded before implementation in `docs/artifacts/phase2/implementation-plan.md`.

Unsafe states identified: request committed while a daemon thread can die; no durable owner/fence or duplicate key; receipt use separate from job creation; uncertain work could appear merely running; no in-flight cancellation acknowledgment; backup of SQLite alone omits sources/config/tasks/evidence; cloned identity DB would carry credentials and stale authority. Phase 1 had already removed unsafe blanket startup interruption. This phase does not reintroduce it.

## Actual code changes

- `sourceroi/live/durable_jobs.py`: additive job schema v1 within the existing private identity store. No Redis/Celery/cloud framework. Persistent lifecycle, digest-bound payloads, queue limit, atomic submission/events/receipt consumption, scoped idempotency, leases/heartbeats/fences, conservative terminal recovery, cancellation and bounded result/checkpoint storage.
- `sourceroi/live/api.py`: authenticated offline job submit/read/cancel endpoints with actor isolation; original generation gates remain. HTTP request and legacy background job lifetime cooperate with workspace quiescence. No background durable worker starts automatically.
- `sourceroi/live/cli.py`: explicit foreground one-job worker, recovery/status, complete backup/restore and retention-preview commands. Current CLI invocations cooperate with backup locking; legacy feature commands retain their behavior.
- `sourceroi/live/workspace_lock.py`: POSIX cooperative shared-operation/exclusive-backup lock. Lock files reject symlinks/hardlinks. CLI service lifetime and worker lifetime prevent concurrent backup.
- `sourceroi/live/workspace_recovery.py`: versioned complete inventory, SHA-256, online SQLite captures, sanitized security/job provenance, source/task/config/frozen-snapshot checks, exclusive atomic backup publication and new-container verified restore. Retention is preview-only.
- `sourceroi/live/security.py`: additive persistent receipt-revocation and actor-credential-revision tables. These distinguish consumed receipts from subsequently revoked authority; resets/same-role changes invalidate queued work.
- New job/recovery regressions and `tools/validate_phase2_recovery.py` with preserved acceptance artifacts. No native accounting, model configuration, corpus, gold label, conventional evaluator or original empirical result was changed.

## Job lifecycle, guarantees and approval binding

See [DURABLE_JOBS_DESIGN.md](DURABLE_JOBS_DESIGN.md) and [AUTHENTICATED_EXECUTION_BINDING.md](AUTHENTICATED_EXECUTION_BINDING.md).

CREATED/QUEUED submission and receipt consumption commit together. Claims are atomic; a lease and incrementing fence authorize subsequent checkpoints/commit. Terminal jobs never restart. QUEUED expiry cancels. Expired claimed work is CANCELLED before reservation, INCONCLUSIVE afterward, with unknown usage. No automatic retry or takeover dispatch follows lease expiry. Cancelled in-flight work requires acknowledgment and remains INCONCLUSIVE after reservation.

Idempotency binds workspace, actor, operation, key and canonical request/input identity. Same key/input returns the existing job; changed payload conflicts, changed source identities reject. Existing-job lookup does not renew approval or execute anything. One receipt cannot fund a second key. Partial transaction failure/killed submission leaves no job and no consumed receipt. This proves transactional effects, **not exactly-once provider effects**.

Authority is server-derived: active operator/admin submission, registered plan, authenticated reviewer receipt, canonical source/config/task/policy hashes and exact approved maintenance decisions. Receipt/actor role and expiry are rechecked before reservation and before completion. Revocation/staleness fails closed. A separate generation authorization is mandatory for any future real generation; the only current operation explicitly has none because it cannot generate.

The fixed foreground worker performs `offline_release_preflight` and persists COMPLETED only for that offline operation. Its release assessment is always INCONCLUSIVE, token usage unavailable, generation attempts zero. No callback/provider/command import is client-selectable. Unsupported operations and all original authenticated generation endpoints remain denied, including admin acknowledgment/semantic-review injections. Independent semantic approval is neither invented nor inferred from maintenance review.

## Process-crash, lease, cancellation and recovery evidence

[JOB_RECOVERY_VALIDATION.md](JOB_RECOVERY_VALIDATION.md) records the matrix. Actual subprocess tests include two processes competing for one job, process-restarted idempotent submission, a killed uncommitted submission, and killed workers before reservation, after reservation, after partial checkpoint and after a fixture response held only in memory. Lease expiry is injected by the test clock in kill cases; actual process termination is real. The uncommitted database effects roll back; uncertain work is never redispatched. The response scenario is a deterministic fixture, not a real provider.

Heartbeat extension, stale/foreign fence rejection, deadlines, cancellation before/after reservation, revoked/expired approvals, post-reservation role changes, payload corruption and invalid ACCEPT attempts are covered. HTTP submission retries preserve the job after client closure; worker lifetime is independent because it is explicitly run later. Real provider/network cancellation and all legacy-job crash migration remain PENDING. Existing legacy daemon jobs remain trusted-local and are not retroactively promised durable execution.

## Complete backup, restore and identity safety

See [WORKSPACE_BACKUP_RESTORE.md](WORKSPACE_BACKUP_RESTORE.md) and [RESTORE_VALIDATION.md](RESTORE_VALIDATION.md).

Backup requires stopped external editors/direct-library writers plus exclusive cooperative quiescence. It inventories all supported ordinary workspace files within declared bounds, online-backs up SQLite, captures sanitized security/job provenance, verifies current/frozen identities and before/after state, then atomically publishes a new archive. Known runtime sidecars/locks and credential-bearing identity state are intentionally replaced/excluded. Unexpected security-store files fail rather than silently vanish. This is not an arbitrary directory copy, but is also not protection against hostile/uncooperative OS writers or change-and-revert attacks.

Restore verifies the trusted whole-archive digest before extraction, exact member inventory/paths/types, file hashes, SQLite consistency, source/config/task identity and frozen snapshots. A new private container is mandatory. Interrupted/failed extraction retains RESTORE_INCOMPLETE without publishing a workspace. Existing targets are never overwritten. A complete independent restored workspace and archive are preserved under `docs/artifacts/phase2/acceptance-v3/`.

Restored identity authority is empty: **0 users, 0 sessions, 0 active receipts, 0 active jobs**. Prior plans/reviews/approvals/audit/job events remain historical provenance, never live authorization. A fresh workspace-bound identity store forces re-provisioning. Regression tests provision a new operator after restore and verify login. Historical run reports and source identities match. Unknown historical jobs must be reconciled explicitly; no restore silently resumes them.

Negative cases cover corrupted/truncated archives, wrong digest, missing/altered sources, rewritten hashes with inconsistent identities, tampered snapshots, schema/manifest errors, extra/duplicate/path-traversal/symlink entries, existing target, hardlinks, interrupted backup/restore and concurrent cooperative writers. Actual killed backup/restore processes leave partial/incomplete markers and no final publication.

Retention categorization is documented; implemented tool is confined, **non-destructive preview only**. Timed retention, credential lifecycle policy, secure erasure, WAL/backup deletion propagation and customer deletion guarantees remain PENDING. No historical development evidence was deleted.

## Test results and measurements

| Run | Actual result |
|---|---|
| Pre-change complete baseline | 448 passed / 20.36 s |
| First focused job tests | 16 passed |
| First focused recovery tests | 15 passed |
| First complete suite | 479 passed / 22.95 s |
| Expanded focused run | **1 failed, 40 passed**; transient SQLite sidecar inventory issue; log preserved |
| Corrected focused run | 41 passed |
| Expanded complete run | 493 passed / 23.55 s |
| Further focused checks | 47 passed |
| Final complete suite | **500 passed / 25.22 s** |

A final code audit found that the old `used` flag conflated receipt consumption with later revocation. Separate durable revocations and actor credential revisions now reject reviewer/operator password reset and same-role changes after submission. Additional focused checks passed 61 tests; the 498-pass intermediate log is retained.

The conservative inventory failure published no successful archive. Its correction processes recognized SQLite sidecars before ordinary file existence checks, with SQLite online capture retaining committed state. No unfavorable log was overwritten. Final tests are 448 preserved baseline plus **52** new parametrized job/recovery cases. These authored cases are not independent deployment certification.

Latest acceptance-v3 local fixture: submit 4.76 ms, duplicate lookup 3.60 ms, offline preflight worker 9.32 ms, backup 8.58 ms, restore 10.39 ms, terminal recovery scan 0.12 ms. Whole probe 0.150 s; peak RSS 62,111,744 bytes. These are one tiny authored local workload on the existing Python 3.13/macOS ARM64 environment, not customer performance, SLA or production RPO/RTO. Earlier acceptance-v1/v2 timings remain available. No operational RPO/RTO guarantee was selected or measured.

Commands executed:

```sh
workspace/design-partner/venv/bin/python -m pytest -q
workspace/design-partner/venv/bin/python -m pytest -q tests/test_phase2_jobs.py tests/test_phase2_recovery.py
workspace/design-partner/venv/bin/python tools/validate_phase2_recovery.py --output docs/artifacts/phase2/acceptance-v3
```

Use a fresh output directory for reproduction. The suite uses fixture sockets/subprocesses, not live model generation. Final log: `docs/artifacts/phase2/full-suite-acceptance.txt`. Acceptance archive/results, restored workspace, original baseline and historical hashes are in `docs/artifacts/phase2/`.

## All-eight-feature preservation

| Capability | Assessment |
|---|---|
| Dataset evaluation | **VERIFIED regression**: registration/scoring/evidence and callback/HTTP adapters retained; authenticated real execution PENDING. |
| Source/document/passage valuation | **VERIFIED regression**: existing ablation/contribution/uncertainty paths retained. |
| Cost-aware optimization | **VERIFIED regression**: quality floors, retrieval policies, usage distinctions retained; new real savings unproven. |
| Data CI | **VERIFIED regression**: declared routing, version/evidence checks, machine-readable strict/incomplete behavior retained. |
| Intent-aware changes | **VERIFIED regression**: immutable plan/diff/source versions and owner-intent uncertainty retained. |
| Evaluation maintenance | **VERIFIED regression**: protected/evidence-only review and narrow source-value suggestions retained. |
| Impact mapping | **VERIFIED regression**: direct/potential/unknown dependencies remain conservative. |
| Diagnosis/isolated repair | **VERIFIED regression**: existing failure hypotheses/interventions preserve original candidate. |

Longitudinal SQLite/source history, CLI, FastAPI, existing dashboard, legacy fixtures/adapters, numerical provenance and native accounting tests also pass. New offline jobs are API/CLI-accessible; a new dashboard job console was not added. No feature was silently removed from the trusted-local path. Full browser or independently operated integration acceptance is not claimed.

## Security assessment, limitations and next phase

[PHASE2_SECURITY_AUDIT.md](PHASE2_SECURITY_AUDIT.md) separates controls from pending work. [PHASE3_HANDOFF.md](PHASE3_HANDOFF.md) is the exact next engineering phase.

**PENDING:** resource-isolated hostile-document parsing for every ingestion route; real authorization-to-job/native accounting integration; authenticated independent semantic-review ingestion; actual provider cancellation/deadline reconciliation; process supervision; large/off-host/encrypted backup drills; retention/erasure; installation/upgrade/rollback across platforms; source-owner authority; independent security review and customer/semantic validation. Raw library/external writers are outside cooperative locking and must be stopped for backup. Backups contain sensitive plaintext evidence and require private storage. Power-loss durability across every filesystem has not been certified.

The earlier 18-generation benchmark and tied conventional comparison are unchanged. No post-fix AI accuracy, independent reviewer, customer value, labor savings, competitive superiority, uptime or enterprise readiness claim follows from these fixtures. Technical/demo and controlled-local-beta evidence advances; production execution readiness does not become automatic.
