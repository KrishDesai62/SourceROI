# Authenticated fixture execution acceptance — Phase 3

**VERIFIED deterministic protocol path; no real model execution is enabled.** This extends the existing `Jobs` worker and private SQLite store. It does not replace Phase 2 or create a second scheduler.

An operator/admin requests `/api/v2/fixture-authorizations` for an exact server plan. Scope is always `deterministic_fixture_only`, with 1–40 total attempts, 1–60 seconds, zero retries and zero spend. A client cannot turn that record into native/model authority. Submit `operation=fixture_release` through the existing job endpoint with the fixture permit and explicit baseline/candidate response map. Those responses are authored fixtures, not LLM outputs or independently reviewed answers.

Job creation atomically consumes both the maintenance receipt and fixture authorization. Existing actor revisions, reviewer revocations, idempotency, source/task/config identity, leases, fencing, deadlines and cancellation remain. Provider attempts are separately capped, not inferred from logical task counts.

The foreground worker runs actual registered retrieval through the isolated index, the existing provider transport and strict `assurance.execute`. Runtime transport is fixed to a local Python fixture subprocess; no arbitrary URL/command/provider is accepted and no socket/model is opened. The runtime identity is explicitly `deterministic-fixture-NO-MODEL`. Strict grounded policy is applied in the fixture path; fixture scope/payload identifies this conservative override of a legacy configured policy.

Each attempt commits RESERVED before DISPATCHED, with a unique attempt ID, task/version, exact request, request digest, and timestamps. A terminal echo must match attempt/task, identify itself as a fixture, and report no child calls. Raw terminal text, known usage and partial rows are retained in private SQLite. Missing/partial usage, timeouts, failed/lost output or extra child-call reports are UNKNOWN and job INCONCLUSIVE; no retry occurs. Counts labelled `fixture_reported` are synthetic protocol data, never measured LLM tokens.

Terminal reconciliation checks budget, every request digest, request/terminal correlation, child-call status, usage equality and completed state. A versioned reconciliation seal binds request, terminal and usage digests to the job. Changed terminal evidence invalidates later assessment. Lost owners cannot commit results; owner-loss recovery marks unresolved attempt rows UNKNOWN and never redispatches. The process steward terminates fixture children when a worker dies.

Tests cover missing/expired/revoked permission, attempt cap independent of logical tasks, duplicate submissions, competing workers, owner fencing, cancellation, actual worker kill after fixture dispatch, partial/missing terminal/usage, child-call violation, raw evidence, source staleness, full recovery and seal tampering. Earlier Phase 2 lifecycle tests remain. This is **not** native/server-level reconciliation of a real provider, nor exactly-once external execution certification.

Latest acceptance: four fixture attempts, synthetic prompt/completion counts 12/4, job COMPLETED with strict release **REVIEW**, zero real generations. An explicit authored semantic assertion still leaves REVIEW because independence is unverified and the run is a fixture. Protected/known answer failures remain BLOCK; incomplete attempts remain INCONCLUSIVE. No fixture can authorize production ACCEPT.

All original authenticated generation endpoints remain 403, even for admin with acknowledgment or client semantic-review data. The historical native authorization remains consumed. A real provider requires separate fresh authorization, provider/native binding and independent security/semantic acceptance.
