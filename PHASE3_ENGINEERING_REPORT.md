# Phase 3 engineering report — isolated ingestion, fixture execution and review security

Date: 2026-11-14. Existing standalone SourceROI; Phase 2 is preserved within its declared offline scope. **No real model/native Qwen generation, paid API, external spend, download, public deployment, customer data or invented independent reviewer.** All new answers/judgments are explicitly authored fixtures.

| Assessment | Classification |
|---|---|
| Pre-change regression baseline | **VERIFIED:** 500 passed in 24.40 seconds before code changes. |
| Shared isolated document ingestion | **VERIFIED internal tests:** extraction/chunking/tables, benchmark/published-dataset JSON and numerical binding use bounded subprocesses. |
| macOS resource/security controls | **VERIFIED tested mechanisms:** process steward, CPU/file/fd limits, sampled RSS, constrained sandbox and two-slot ingestion capacity. Not a universal container/hard-memory guarantee. |
| Durable fixture release evaluation | **VERIFIED:** existing authenticated jobs perform retrieval/provider protocol/strict release through deterministic subprocess fixtures, with attempt accounting and reconciliation seals. |
| Authenticated semantic record integrity | **VERIFIED fixture scope:** source/result/job/task/reviewer-bound immutable judgments; external independence always unverified. |
| API/dashboard | **VERIFIED backend and syntax; PRELIMINARY UI:** actual submit/poll/cancel and assigned-reviewer APIs; full browser acceptance PENDING. |
| Final complete suite | **VERIFIED:** **557 passed in 82.31 seconds**, versus 500 initially. |
| Historical preservation | **VERIFIED:** **1,014 captured pre-existing artifact/root/doc files unchanged**. |
| Broad Phase 3 acceptance | **PRELIMINARY:** downstream analytical CPU bounds, full browser/adjudication UX and independent security acceptance remain incomplete. No unqualified Phase 3/production completion claim. |

## 1. Audit and architecture

Read the Phase 3 brief, current Phase 2 reports/design/recovery documentation and actual source. Ran the entire existing suite first. The audit found document parsing in the API process through `_extract`, `scan_sources`, direct extraction helpers and dataset JSON loads; silent character/PDF-page truncation; no verified parser resource boundary; an offline-preflight-only durable worker; and no authenticated claim-adjudication store. Existing Phase 2 idempotency, receipts, actor revisions, fencing, recovery and quiesced backup were retained rather than reimplemented.

The production target remains one authenticated tenant/workspace on the tested macOS ARM64 host, direct loopback, trusted OS administrator and explicit foreground workers. No shared/public service was installed. No new framework/scheduler/frontend application was added. Legacy trusted-local features remain available on this supported platform; unverified parser platforms now fail closed instead of claiming equivalent isolation.

## 2. Exact code changes

| Files | Actual implementation |
|---|---|
| `parser_boundary.py`, `parser_worker.py`, `parser_steward.py` | Read-only immutable input copies, fixed JSON operations, per-process capacity, cache bound to bytes/settings, source rechecks, OS limits/profile, RSS supervision and parent-death process-group cleanup. |
| `ingest.py` | Shared isolated extraction/scan/benchmark entry points; worker-only raw parser; no silent extraction/page truncation; explicit JSON/record/ZIP/page bounds. |
| `facts.py`, `grade.py` | Source-bound numerical/table computation and regex grading isolated. Existing opt-in contracts, provenance, abstentions and grading rules preserved. |
| `datasets.py`, `public_audit.py` | Published JSON decoding/prior-source extraction and audit reference reads use the shared boundary. No external dataset was downloaded. |
| `fixture_execution.py`, `fixture_provider_worker.py`, `durable_jobs.py` | Additive fixture permits/attempt tables, fixed subprocess provider, atomic permit+receipt/job binding, per-attempt cap, partial rows, unknown outcomes, exact correlation and sealed terminal reconciliation. Job schema initialization serialized. |
| `semantic_store.py`, `security.py`, `api.py` | Authenticated assigned-reviewer packets/judgments, source/result digests, revocation checks, semantic assessment and typed APIs. Client reviewer/independence substitution rejected. Original generation routes stay disabled. |
| `web/index.html`, `web/app.js` | Existing dashboard gets real backend fixture submit/inspect/poll/cancel controls and evidence/status output. No new UI framework or fabricated metrics. |
| `workspace_recovery.py` | Sanitized historical exports include fixture permissions/attempts and semantic records; none become live authority after restore. |
| New tests and `tools/validate_phase3_acceptance.py` | Adversarial parser/process tests, durable fixture/semantic/API/recovery tests, eight explicit feature paths, reproducible measurements. |

## 3. Ingestion route coverage and provenance

Detailed matrix: [PARSER_ISOLATION_VALIDATION.md](PARSER_ISOLATION_VALIDATION.md).

Raw document decoding, text extraction, chunk construction, CSV/Markdown table parsing, benchmark validation and numerical source binding execute in the common child worker. Shared callers cover project inventory, source preflight, version/snapshot checks, plans, impact/maintenance evidence, citation/source verification, evaluation/ablation/optimization preparation, Data CI and diagnosis/repair. Registration copies bytes; first interpretation uses the isolated helpers. Dataset import JSON and public audit's previous direct text reads were included. Trusted control-plane config/SQLite and customer callbacks are distinct trust boundaries.

Original source IDs, extracted-content SHA-256 fingerprints, chunk IDs, exact quotations, extracted-character offsets, raw table hashes and registered applicability/authority metadata are preserved. Raw byte SHA-256 and descriptor identities are checked around snapshot/acceptance; changes to file contents, aliases or source sets reject, including on cache hits. Version semantics remain the existing extracted-content/source-metadata identities; this does not silently redefine historical manifests as raw-file hashes. Cache results are immutable-data results, never authority/review state.

Worker output cannot write trusted configuration/identity/approval state, and it is neither executed nor unpickled. Source instructions remain text. Tests include malicious instruction-like source content and actual denied host effects, not just prompt filtering. This does not establish immunity to future LLM prompt injection.

**Boundary limit:** downstream BM25 query scoring, source diffing and some reference/diagnostic analysis still run over bounded extracted data in the main process. They do not all have independent hard CPU limits. This prevents an unqualified claim that every analytical operation or hostile end-to-end ingestion workload is isolated.

## 4. Actual resource enforcement and termination

On tested macOS: 15-second parser wall deadline plus independent steward deadline; worker CPU soft/hard 8/9 seconds; output file limit 48 MiB; descriptor limit 64; core dumps disabled; source 12 MiB/file, 2,500 files/64 MiB snapshots; parsed 400,000 characters/document and 12 million/corpus; page/ZIP/JSON/record limits. Two active ingestion operations per process bound source snapshot allocation; capacity waiting is bounded separately to 15 seconds.

The parent samples total steward/worker RSS at a 512-MiB threshold. **This is not a hard macOS memory limit and may overshoot.** Actual allocation stress validates detection/termination; independent hard memory enforcement remains PENDING. Process counts are also checked. The macOS profile denies network, fork, writes outside private temp, and protected original-workspace/home data reads with explicit trusted code/runtime exceptions. Missing sandbox support, unsupported platforms and a workspace inside those exceptions fail closed. This profile is constrained, not deny-default or security-certified.

A trusted separate steward, not a parser thread, observes original-parent death/deadline and kills the process group. Actual supervisor kill, hangs, busy loops, allocation pressure, oversized writers, child processes and malformed parsers are tested. Successful exit without complete terminal output is rejected; partial parsed documents are not accepted. SIGKILL may leave private temporary evidence directories; automatic orphan retention/cleanup remains pending.

## 5. Durable authenticated fixture execution and reconciliation

See [AUTHENTICATED_EXECUTION_ACCEPTANCE.md](AUTHENTICATED_EXECUTION_ACCEPTANCE.md).

The existing job lifecycle supports `fixture_release` in addition to offline preflight. An explicit fixture-only authorization specifies 1–40 attempts, 1–60 seconds, no retries and $0 spend; this is not native/model permission. Atomic submission binds actor revision, plan/maintenance receipt, source/task/config/policy identity, fixture inputs and permit consumption. Existing leases/fences, stale/revoked checks, cancellation and recovery remain.

The foreground worker runs real registered retrieval and the existing strict evaluator/provider interface against a fixed Python fixture subprocess. It cannot select an arbitrary command, URL or model. Request/terminal evidence, unique attempt/task/version identities, RESERVED before DISPATCHED, synthetic known usage, partial rows and terminal outcomes persist in private SQLite. Attempts are capped separately from logical evaluations. Missing usage, partial/lost responses, timeout, provider failure or unexpected child-call declaration becomes UNKNOWN/INCONCLUSIVE with no retry. A killed worker after fixture dispatch is recovered conservatively; no replacement attempt occurs.

Reconciliation verifies all request digests, terminal correlation, child-call status, usage equality, budget and completed states, then seals those identities into the terminal job result. A tampered terminal invalidates semantic assessment. These are fixture accounting tests, not independent native/server-level reconciliation of a newly executed model. The earlier bounded native 18-generation/55,467-token result remains historical and unchanged.

All original authenticated real-generation routes stay **403**, including admin acknowledgment attempts. No consumed native authorization is reused. A fixture assessment cannot authorize production ACCEPT.

## 6. Semantic review and strict decisions

See [SEMANTIC_REVIEW_SECURITY.md](SEMANTIC_REVIEW_SECURITY.md).

New records bind authenticated assigned reviewer, exact frozen answer, retrieved context/citations, task, source/config identity, job/result identity, policy, claim spans, decision, dimensions, rationale, authorization basis, timestamp and immutable digest. Supported/unsupported/contradicted/uncertain/applicability-failure judgments are distinct. Literal support quotes and complete claim spans are checked; positive declarations require consistent explicit dimensions. Reviewer name/independence fields cannot be supplied by clients.

**External independence is always recorded false in this phase.** A login and a claimed authorization basis establish neither expertise nor independent source-owner review. Automated test/probe assertions explicitly identify themselves as authored fixtures; no real human review is claimed.

Missing review stays REVIEW; contradictory/unsupported/applicability failure or protected answer failure BLOCK; missing/unknown execution, ownership or reconciliation is INCONCLUSIVE. Stale source/output/review binding and revoked/revised identities cannot establish approval. Immutable replay/overwrite is rejected. New assessment preserves the original release evidence rather than rewriting its results. No new fixture route can return production ACCEPT; existing legacy assertions remain within their historical trusted-local scope.

## 7. API, dashboard, recovery and installation

Verified actual API flows: fixture authorization/submission, idempotency, actor-scoped job inspect/cancel, assigned-reviewer packets, semantic submission and assessment. Existing Host/Origin/loopback/CSRF/role protections remain. Raw fixture prompts/responses are private evidence, not ordinary operational logs. No credential body or query-string logging was added.

The existing dashboard now uses those real job APIs and displays actual state, owner/fence, pending/errors and evidence JSON. `node --check` passes. **Full browser/keyboard/accessibility testing is PENDING:** no installed Playwright/browser runtime was available and none was downloaded. Semantic adjudication currently has an authenticated API, not a completed browser form. Backend/syntax checks do not certify UI usability.

Phase 2 complete recovery was exercised after malformed parsing and a failed fixture, and separately after a reconciled fixture with a semantic record. Sources, frozen snapshots, source/task/config identities, release history and historical security provenance survive independent restore. Restored active users/sessions/receipts/jobs/fixture authorizations/semantic judgments are all zero; old unknown jobs do not resume. Source/semantic history remains provenance, not authority. Backup still requires cooperative quiescence and stopped external writers. Encryption/off-host handling is **not implemented or verified**.

A fresh temporary Python environment installed locked local wheels and a newly built SourceROI test wheel without network. Running outside the source checkout with `-I` verified the installed module and sandboxed TXT/PDF/DOCX ingestion. The final source wheel was reinstalled and smoke-tested after the last code changes. This is a local test wheel (same beta version), not a new published production distribution or overwritten sealed pilot archive. Dependency closure verification checked 27 locked artifacts/installed versions; advisories/publisher attestations remain PENDING. Rollback/large operational deployments are not certified.

## 8. Eight-feature acceptance

[EIGHT_FEATURE_ACCEPTANCE.md](EIGHT_FEATURE_ACCEPTANCE.md) describes eight new explicit cold-parser paths: dataset evaluation; source/document/passage ablation; optimizer keep-baseline safety; frozen Data CI; intended/protected source changes; immutable reviewed expectations; conservative impact; and source-backed diagnosis/isolated source addition. Each verifies isolated execution and detects a later changed source fingerprint. Existing callback/HTTP adapters, numerical provenance, longitudinal SQLite, native gates, CLI and dashboard regressions also pass.

Fake HTTP answers/costs in these tests are fixtures, not real model token/cost savings. No grading was weakened to manufacture a reduction, semantic success or competitive advantage.

## 9. Tests, failures and measured conditions

Final complete log: `docs/artifacts/phase3/full-suite-acceptance.txt`: **557 passed in 82.31 s**. Original baseline: **500 passed in 24.40 s**. Added parametrized cases: **57**. Intermediate full suites: 520, 532, 553, 554 and 555 passed. They are preserved; no unfavorable history was deleted.

Failed development checks are retained: four semantic test helpers incorrectly assumed a retrieved/cited passage for a changed property-key fixture; the actual unsupported path remained blocked and tests switched to the genuinely cited warranty task. An optimizer test expected the wrong result contract rather than its legitimate keep-baseline result. A race monkeypatch needed the new boundary keyword. An experimental deny-default sandbox failed to start Python and was not represented as working. The constrained macOS profile and corrected actual contracts then passed. See the security audit for limits.

Final local authored probe (`docs/artifacts/phase3/acceptance-final/measurements.json`):

| Measurement | Observed internal fixture value |
|---|---|
| OS/Python | macOS 26.5.1 ARM64, Python 3.13.9 |
| Parser corpus | 22 documents / 82 chunks |
| Cold isolated scan | 105.42 ms |
| Identical-byte verified cache scan | 4.98 ms |
| Foreground fixture release | 0.341 s; four subprocess attempts |
| Synthetic fixture usage | 12 prompt / 4 completion tokens; **not LLM usage** |
| Strict verdict / real model calls / spend | REVIEW / 0 / $0 |
| API | 20 in-process authenticated reads; median 2.64 ms, max 4.25 ms |
| Quiesced backup / independent restore | 10.25 / 12.10 ms |
| Active restored authority | All six measured identity/session/approval/job/fixture/semantic counts zero |
| Whole probe / parent peak RSS | 1.315 s / 81,428,480 bytes |

This is a small single-host sample, not customer throughput, latency percentiles, an SLA, independent semantic evidence or RPO/RTO. Child RSS enforcement is tested separately; parent peak RSS is not a claim of total child memory. Earlier acceptance samples are preserved.

Reproduce with fresh output directories:

```sh
workspace/design-partner/venv/bin/python -m pytest -q
workspace/design-partner/venv/bin/python tools/validate_phase3_acceptance.py --output /tmp/sourceroi-phase3-NEW
node --check sourceroi/live/web/app.js
```

## 10. Readiness and exact next gates

| Level | Verdict |
|---|---|
| Technical demo | **VERIFIED**, existing evidence scope. |
| Controlled local beta | **PRELIMINARY**, declared macOS/trusted-OS limits and explicit fixture operations. |
| Authenticated fixture execution | **VERIFIED internal acceptance**, synthetic answers/usage and no production ACCEPT. |
| Real model execution | **PENDING/disabled**; fresh authorization plus native/provider acceptance required. |
| Single-tenant production | **PENDING — not ready**: independent security acceptance, end-to-end analytics bounds, browser/adjudication workflows and operational drills remain. |
| Multi-tenant SaaS / enterprise | **PENDING — unsupported/unproven**. |

Unresolved P0/P1 items include sampled-memory limitations and parser/runtime exception review; hard limits for downstream analytics; global multi-process resource policy; crash temp retention; authenticated externally verified reviewer authority; real provider/native authorization/reconciliation/cancellation integration; full browser/accessibility acceptance; encrypted/off-host recovery and operational rollback; dependency advisories and independent security assessment. No hostile public deployment is authorized.

[PHASE4_HANDOFF.md](PHASE4_HANDOFF.md) lists remaining Phase 3 acceptance before broader production work. The earlier real Qwen candidate correctness (2/5), candidate Data CI correctness (0/5), IRS value suggestions (0/3) and tied maintained conventional comparison are unchanged. No independent semantic/customer reliability, ROI, quality-preserving savings or competitive superiority has been established by these fixtures.
