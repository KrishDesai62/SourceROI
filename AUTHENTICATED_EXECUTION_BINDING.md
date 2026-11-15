# Authenticated approval → durable offline job binding

**VERIFIED for offline orchestration; real dispatch remains disabled.** Existing session, CSRF, viewer/operator/reviewer/admin roles, workspace binding and source-version review validation are preserved. Reviewer names supplied by clients are insufficient.

A server-registered plan links an immutable spec to a frozen snapshot. A provisioned reviewer/admin reviews that exact plan after canonical input checks. Its approval digest includes authenticated local identity and workspace metadata. A server receipt records the spec, reviewer, expiry and used flag. A login authenticates a configured local identity; it does not establish independent semantic expertise or source-owner authority.

`Jobs.submit` binds the active operator/admin, exact plan, receipt, baseline/candidate source/configuration hashes, frozen benchmark, approved maintenance decisions, release policy, operation and resource limit. Receipt validation and job creation use the **same private SQLite transaction**. This avoids cross-database consumption/creation gaps. The existing run-history DB is separate and is not the transactional queue.

Failed creation rolls back receipt consumption, job and events together. Concurrent duplicates cannot spend a receipt twice. A different idempotency key cannot reuse a consumed receipt. A same-key lookup can return its existing job, but does not renew expiry or authorize dispatch. The worker rechecks source identities and live actor/reviewer authority. Revocation, expiry or stale versions prevents work or yields INCONCLUSIVE. A stale fence cannot commit success.

This phase supports only the fixed offline preflight operation with `generation_authorization=null`. Requests for another operation fail before dispatch. Original authenticated generation endpoints remain disabled even with boolean acknowledgment, fabricated semantic review or an admin session. The implementation does not mint native authorizations or reuse the consumed historical benchmark permission.

**PENDING before model execution:** an independently recorded generation authorization with call/deadline/retry/spend limits; binding that authorization to durable reservations and native accounting; a worker that reconciles actual provider outcomes; hardened parser isolation; authenticated semantic adjudication storage; security acceptance. Maintenance approval is not semantic release approval. This phase's offline worker always returns release verdict INCONCLUSIVE and reports zero generation attempts with unavailable token usage; it cannot turn missing evidence/review into ACCEPT.

Rejected canonical-input submissions have a private audit event. HTTP request outcomes/IDs are audited by the existing identity boundary, including role/validation denial; SQL rollback leaves no partial successful submission event. No passwords, session/CSRF values, request bodies or query strings are added to audit logs.

Consumed and revoked states are stored independently: revocation of a receipt already consumed by a queued job remains effective. Actor credential revisions also bind submitted authority; credential/role reset invalidates queued authority even when the role name is unchanged. These additive migrations preserve schema-v1 identities and existing history.
