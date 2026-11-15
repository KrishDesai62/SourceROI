# Production engineering program: Phase 0 audit and Phase 1 identity boundary

Date: 2026-11-14. Existing standalone SourceROI repository. **448 tests passed; zero new real model generations, zero external spend, no public deployment, no customer data or outreach.** All 897 captured pre-existing historical artifacts/root reports remain unchanged. This staged execution implements a bounded authentication/review phase, not the entire production program.

| Readiness level | Assessment |
|---|---|
| TECHNICAL DEMO READY | **VERIFIED**, within the existing internal/demo scope; historical empirical failures remain disclosed. |
| CONTROLLED BETA READY | **PRELIMINARY**, trusted local documents and operators only. Provisioned HTTP inspection/planning/review is authenticated; model execution in this mode is unavailable. |
| SINGLE-TENANT PRODUCTION READY | **PENDING — not ready.** Durable execution, parser isolation, complete recovery and production acceptance remain blockers. |
| MULTI-TENANT SAAS READY | **PENDING — unsupported**, outside the selected target. |
| ENTERPRISE READY | **PENDING — not established.** No SLA, independent penetration test or certification. |

## 1. Phase 0: architecture and security audit

The latest evaluation-hardening report, its sealed evidence manifest, the full empirical report, production blockers, live API/CLI, storage code, ingestion, adapters, dependency tooling, dashboard and regression tests were inspected. The 415-test baseline is recorded in the unchanged prior full-suite log; it was not treated as a security certification. Current code was then validated by the new complete suite.

Existing architecture: Python 3.13 on macOS ARM64 in the tested environment; FastAPI and a static JavaScript dashboard; CLI; SQLite run/history storage; local source/task/configuration files and snapshots; callback/HTTP v2 integrations; existing local instrumented llama.cpp path and Qwen model. No framework or replacement architecture was introduced.

| Initial finding | Risk / actual change |
|---|---|
| No HTTP authentication; Host/Origin boundary only | Any caller admitted to that boundary could read workspace data or submit operations. **VERIFIED fixed for provisioned mode:** authentication precedes every protected handler. Legacy unprovisioned mode remains explicitly unauthenticated/local-only. |
| Reviewer supplied as a name string | Impersonation and client-created review assertions were possible within the old trusted-local API. **VERIFIED fixed for provisioned review:** server session identity, role checks, registered canonical plan and persistent receipt required. Legacy CLI fixtures remain assertions. |
| Client-supplied semantic-review arguments | They cannot be treated as independent authenticated decisions. **VERIFIED blocked from authenticated execution:** all generation/release endpoints reject before invocation. A durable authenticated semantic-review/execution bridge is still PENDING. |
| Startup calls `db.mark_interrupted` on every running row | A new process could falsely mark another active process's work failed. **VERIFIED removed from API startup.** No lease/recovery implementation is implied; orphaned legacy rows remain visible. |
| In-memory semaphore, daemon job thread, no durable ownership | **PENDING** process-wide job leases, idempotency, cancellation, recovery and partial-outcome reconciliation. An acknowledgment checkbox is not a bounded generation authorization. |
| Parsers execute in the service process | **PENDING** hostile-document isolation/CPU/memory/deadline enforcement. Existing size/archive/path checks are not a sandbox. Even inventory/planning can parse documents. |
| SQLite-only backup | **PENDING** coordinated backup of sources/config/tasks/snapshots/reviews/auth state/history and consistent independent restore. |
| Old readiness/native-accounting text | Kept compatible PENDING for the current service process; added scope explaining that one historical bounded run reconciled. Readiness remains `production_ready=false`. |

Historical empirical evidence is unchanged: 18 reconciled generations, 55,467 tokens, primary supported correctness 3/5 → 2/5, candidate Data CI 0/5 and four software false abstentions before the routing repair. Post-fix offline eligibility is not accuracy. IRS value suggestions remain 0/3. The equally maintained conventional evaluator tied SourceROI on observed regression detection. No model-internal explanation or independent semantic success is inferred.

## 2. Selected trust boundary

Target: **one single-tenant workspace, trusted OS administrator/account, direct loopback HTTP, one service process**. No public listener, reverse proxy, remote users or tenant switching is supported. No service has been deployed by this work.

The OS administrator is the root of trust and can access sources, secrets and the CLI. The application cannot prevent that administrator changing files or running other code. All tenant users share read access to the selected workspace; user-private datasets are not promised. Viewer, operator, reviewer and admin permissions are distinct. A source owner delegates scope to provisioned users out of band; a text declaration does not establish ownership or independence. Workload identity is the OS process, not an attested service credential.

The current authenticated target supports inspection, snapshot/planning and review of **trusted bounded documents**. It deliberately refuses model execution. It is not an end-to-end authenticated production RAG service. The unprovisioned legacy CLI/HTTP workflow remains available for its original trusted local scope and is not protected by these new HTTP roles. Native accounting and explicit generation authorizations remain separate requirements.

Exact role matrix, credential provisioning, startup, revocation and limitations: [authenticated target operations](docs/AUTHENTICATED_SINGLE_TENANT.md).

## 3. Actual code changes / P0 fixes

- **VERIFIED — `sourceroi/live/security.py`:** workspace-bound owner-only SQLite identity store, schema v1, salted scrypt passwords, opaque random sessions, hashed session/CSRF secrets, absolute expiry, server revocation, login throttling, fixed-field audit events, registered plans and server approval receipts. Private paths reject symlinks/hardlinks and permissive mode bits; incompatible or relocated stores fail closed. No external identity framework was added.
- **VERIFIED — FastAPI boundary:** backend authentication and role enforcement on every protected route, loopback peer enforcement in addition to Host/Origin checks, cookie CSRF enforcement, ambiguous credential rejection, HTTP logout, request-correlated auditing and default automatic enforcement once the security directory exists. Partial provisioning and explicit downgrade cannot silently open the service.
- **VERIFIED — review security:** only reviewers/admins may submit; `reviewer` must match the session; only an exact server-registered plan can be reviewed; current source/task/configuration/canonical proposal checks run before approval. Records include the verified local identity/workspace. Existing approval digests bind that metadata. A separate receipt validates expiry, live role, revocation and atomic single-use consumption; it rechecks sources before consumption. Forging a new client digest is insufficient.
- **VERIFIED — CLI:** `auth-init`, `auth-add-user`, `auth-set-role`, `auth-reset-password`, `auth-disable-user`, `serve --require-auth`. Password entry requires an interactive hidden prompt and confirmation; no argument/env password pathway was added. Role/password changes revoke sessions and outstanding approvals. CLI Uvicorn proxy-header trust and access logging are disabled.
- **VERIFIED backend / PRELIMINARY UI — dashboard:** login/logout controls, in-memory CSRF, HttpOnly/SameSite session flow, actionable unauthorized/role errors. JavaScript syntax checked. Authentication is enforced independently of UI state. Full browser/accessibility acceptance remains PENDING; no cosmetic rebuild.
- **VERIFIED — startup safety:** removed unconditional interruption of all running rows. Cross-process regression proves startup preserves an existing running row.
- **VERIFIED — tests/probe:** 33 focused identity tests and a reproducible bounded local identity workload. No generation or customer workload substitute is represented as empirical AI validation.

The identity store is an application trust anchor within a trusted OS account, not a signed external audit service. No MFA, federated identity, password recovery email, distributed rate limiting, TLS/public deployment or independently reviewed cryptography is claimed. The receipt validator is implemented/tested; a durable worker that consumes it is **not implemented**. Authenticated generation remains disabled precisely because that integration is incomplete.

## 4. Authentication and approval evidence

`tests/test_identity_security.py` covers unauthenticated data/mutation denial, invalid credentials, role separation, CSRF, expiry, logout/replayed session rejection, role downgrade, password reset, disabled identities, login throttling, private filesystem permissions, cross-workspace store rejection, no silent downgrade, partial provisioning, authenticated review identity, impersonation, unregistered/stale plans, forged/expired/revoked receipts, concurrent consumption, source edit after review, cross-user logout isolation, client role/session-extension injection, audit secret exclusion and remote peer/forwarded-header bypass attempts.

All six current generation endpoints are denied even for admin with `acknowledge_model_calls=true` or forged semantic-review arguments. No bypass route was introduced and no historical model authorization was reused. A reviewer login proves a local configured identity; it does not prove independent semantic expertise or a real source owner's approval. Fixture identities/reviews are explicitly authored tests.

## 5. Durable jobs, parser isolation and recovery results

| Area | Status and evidence |
|---|---|
| Startup no longer corrupts another process's job status | **VERIFIED:** separate Python process starts against a workspace while a legacy row is running; row remains running. |
| Identity transaction durability | **VERIFIED:** a subprocess commits a role change then is killed; a new store instance sees it. An uncommitted privilege escalation is killed and rolls back. These are actual process terminations, not mocked exceptions. |
| Approval concurrency | **VERIFIED:** two concurrent consumers produce one consumed receipt and one rejection in SQLite. This is not exact-once generation execution. |
| Durable evaluation/release jobs | **PENDING:** leases, idempotent submissions, cancellation, deadline/failure reconciliation, queue recovery and partial results. No real worker crash/recovery or duplicate model-execution guarantee is claimed. |
| Parser isolation | **PENDING:** no new parser worker/resource sandbox. Existing prechecks/regressions still pass. Only trusted bounded documents are admissible to the new boundary. |
| Coordinated workspace backup/restore | **PENDING:** no new complete backup or independent restored workspace. Existing SQLite-only backup tests remain narrower evidence. Identity-store workspace binding deliberately prevents simply copying sessions/approvals to another root. |
| Retention/deletion | **PENDING:** no customer-data policy or automated evidence/audit expiry/deletion implemented. Nothing historical was deleted. |
| Recovery objectives | **PENDING:** target RPO/RTO must be chosen with backup cadence, workload and owner requirements. Neither full-workspace recovery time nor acceptable loss has been measured. |

## 6. Eight-feature production readiness matrix

Every feature retains its implementation and passes the existing complete regression suite. “VERIFIED regression” does not mean production or independent semantic accuracy.

| Requested pillar | Existing operable scope / preservation | Production gate |
|---|---|---|
| 1 Dataset evaluation | **VERIFIED regression:** registered sources/tasks, baseline/candidate grading, callback/HTTP adapters, citation/applicability/version checks, explicit incomplete states and evidence exports. | **PENDING:** durable authenticated execution and independent judgments. |
| 2 Information valuation | **VERIFIED regression:** source/document/passage ablation, task contribution, redundancy, evidence-loss and uncertainty tooling. | **PENDING:** representative independently reviewed contribution/interactions; no invented dollar value. |
| 3 Token/cost optimization | **VERIFIED regression:** top-k/passage/source-subset selection, quality thresholds, deterministic opt-in alternatives and provider/unknown accounting. | **PENDING:** post-fix equal-quality empirical savings. Skipped supported answers are not savings. |
| 4 Data CI | **VERIFIED regression:** shared declared routing, exact evidence/version rules, strict states and CLI outputs. Existing primary/Data CI routing and ablation suites preserved. | **PENDING:** newly authorized inference and authenticated durable execution. |
| 5 Intent-aware changes | **VERIFIED regression:** immutable fingerprints, diffs, owner intent declarations, protected behavior and review-bound plans. | **PENDING:** independently established source-owner authority and production workflow acceptance. |
| 6 Evaluation maintenance | **VERIFIED regression:** frozen benchmarks, changed-answer and evidence-only proposals, corrections/rejections, version-bound narrow suggestions and stale rejection. | **PENDING:** independent equivalence review and generalization; IRS remains 0/3. |
| 7 Impact mapping | **VERIFIED regression:** document/passage/fact relationships, direct/potential/unknown/unrelated explanations; absent history does not discard tasks. | **PENDING:** precision/recall oracle and demonstrated selective equal-quality savings. |
| 8 Diagnosis/repair | **VERIFIED regression:** retrieval/source/citation/scope/numeric failure buckets and isolated candidate-preserving interventions. | **PENDING:** representative causal validation; no automatic production-source repair. |

Longitudinal SQLite history, source versions, legacy fixtures/adapters, CLI and historical experiments remain preserved. Authenticated mode currently restricts execution rather than claiming unverified operability through a new security boundary. Existing trusted-local feature entry points are not removed.

## 7. API, dashboard, deployment and security checks

**VERIFIED:** existing `/api/v2` interfaces, validation, pagination, request IDs and boundary limits pass regressions; new login/session/logout endpoints and protected backend roles are exercised using TestClient. Current native protocol/accounting tests remain intact. The historical native run certifies one bounded execution, not future providers or concurrent workloads.

**PENDING:** mutating-endpoint job idempotency, durable HTTP worker semantics, authenticated semantic-review ingestion, end-to-end secure release execution, customer adapter acceptance, full browser/accessibility tests, process supervision, complete recovery, safe upgrade/rollback and production installation acceptance. No new release archive was created; old sealed distributions are preserved and do not contain these new changes. A production distribution must be rebuilt/versioned only after the later acceptance gates.

**VERIFIED offline supply-chain checks:** `pip check` found no broken requirements (cache-permission warning preserved); existing locked wheel closure verified **27 artifact hashes and installed versions**. This does not attest current source code or absence of vulnerabilities. **PENDING:** network advisories, publisher attestations and independent security review; no offline advisory database is available. No clean vulnerability claim is made. Existing archive safety/package integrity tests pass, but no new hostile-document sandbox was added.

Structured private audit events exclude passwords/session/CSRF tokens, bodies and query strings in tests. They are not tamper-proof off-host logs. Global logs/third-party supervisors are not universally redaction-certified. No secrets or real user identities were provisioned in the actual workspace; all automated provisioning used temporary fixtures.

## 8. Exact tests and measured local workload

Final full suite: **448 passed in 18.37 seconds**, `docs/artifacts/production-phase1/full-suite-release.txt`. Focused identity file: **33 tests**. Existing 415 tests are retained. `node --check sourceroi/live/web/app.js` succeeds.

An initial focused compatibility run had **1 failure, 48 passed** because readiness `native_accounting` was changed from its existing `PENDING` value. The correction preserves that field and adds a scope field; the failed log is retained in `initial-regressions.txt`. Subsequent intermediate full runs: 437 passed, 447 passed; final 448 passed. No unfavorable test log was deleted.

Measured fixture: Python 3.13.9, macOS 26.5.1 ARM64, temporary SQLite identity/history stores, 40 authenticated history reads, 8 concurrent threads, in-process TestClient/ASGI transport. Final probe:

- 40/40 HTTP 200; 46 audit rows; **zero model generations and $0 spend**.
- Median request latency **9.95 ms**, p95 **11.98 ms**, maximum **14.21 ms**.
- Probe HTTP phase **0.052 s**, whole probe **0.201 s**, process CPU **0.232 s**.
- Five scrypt logins: median **19.98 ms**; process peak RSS **80,035,840 bytes**.

This subsecond fixture is not network/TLS/load certification, customer throughput or an SLA. Earlier probe median 13.68 ms is also retained; variation is expected. No capacity conclusion is drawn.

Reproduction, using fresh exclusive-create outputs:

```sh
workspace/design-partner/venv/bin/python -m pytest -q
workspace/design-partner/venv/bin/python tools/measure_identity_boundary.py --output /tmp/sourceroi-identity-probe-NEW.json
workspace/design-partner/venv/bin/python -m pip check
workspace/design-partner/venv/bin/python tools/lock_pilot_dependencies.py verify --wheelhouse workspace/pilot-acceptance/wheelhouse --lock requirements-pilot-py313-macos-arm64.lock --installed
node --check sourceroi/live/web/app.js
```

Artifacts, failure logs, final workload and historical verification: `docs/artifacts/production-phase1/`. Historical manifest comparison confirms **897/897 files unchanged**, including the earlier hardening report/evidence and original empirical/native records. No source corpus/label or conventional comparison methodology was changed by this program execution.

## 9. Investor evidence and exact next phase

**VERIFIED technical evidence:** a real historical bounded native run; unsafe update detection tied with ordinary maintained tests; new deterministic authenticated backend and review-binding evidence; unchanged eight-feature regression coverage. **PRELIMINARY:** trusted local beta usability with a restricted authenticated workflow. **FAILED to establish:** differentiated real-world detection, quality-preserving savings, representative semantic accuracy or customer ROI. **PENDING independent validation:** actual external developer, source-owner/reviewer participation, held-out labels, equal-input three-arm study and measured human effort. Login fixtures and request latency are not customer evidence.

Existing external evaluation kits, independent claim-review tooling, three-arm methodology and feedback/effort templates remain preserved. No fabricated reviewer, participant, human time, customer feedback or outreach was added. Their use with a real participant remains pending. Investor demonstrations must show the execution-disabled boundary and historical failed/tied results honestly; a fresh native experiment requires separate approval.

**Next: Phase 2 — durable execution and coordinated recovery, before enabling authenticated generation.** Implement a SQLite job state machine with durable idempotency keys, explicit workspace ownership/leases and heartbeats, conservative owner-loss handling, no automatic generation retries, deadline/cancellation and partial-result reconciliation. Bind a single-use authenticated approval plus separately recorded generation authorization to immutable inputs at dispatch. Store semantic-review provenance separately from maintenance decisions. Test two live processes, real worker termination, uncertain provider outcomes, duplicate submissions, rollback and cancellation without real inference.

Then implement consistently quiesced source/config/task/snapshot/review/history/identity backup with an inventory manifest, interrupted/corrupt/missing-file tests and complete restore into an independent workspace, explicitly re-provisioning/revoking identity state where required. Define and measure recovery objectives. **Phase 3** must add resource-bounded parser workers and hostile-input tests. **Phases 4–7** then cover all-feature secure execution acceptance, API/dashboard workflow, operations/install/load/security and independently operated pilot evidence. None is marked complete by this report.
