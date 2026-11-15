# SourceROI production-oriented engineering report — 2026-11-14

## 1. Executive summary

VERIFIED: incremental security and reliability improvements are implemented in the existing standalone repository. No architecture replacement, unrelated project change, new framework, paid API, deployment, model download or real generation occurred. Historical evidence is preserved. SourceROI is ready for an accurately labeled technical demonstration. Controlled external beta use remains conditional on a trusted single-user local operator and verified application/label inputs. Public or multi-user production readiness is **PENDING**, not established.

## 2. Initial repository audit

The initial suite passed 324/324 in 9.28s; see docs/artifacts/production-beta/baseline-tests.txt. An earlier restricted run could not bind test sockets; it was rerun with localhost fixture permission. The suite's production-runtime lease and port isolation remained in force. No real runtime was used.

Source inspection covered package/module boundaries, FastAPI request models/routes, CLI and importer, dashboard rendering, ingestion/table/fact paths, SQLite and legacy store, provider/HTTP/callback adapters, strict release and review binding, owned experiment gate, optimizer/study, history, tests, CI and external handoff. This is an engineering source audit, not a complete adversarial penetration test or line-by-line proof. AUDIT_PLAN.md and historical-hashes.json under the sprint artifact directory predate code changes. There is no git repository here; no commit is claimed.

## 3. Implementation inventory

| Area | Classification | Location and evidence |
|---|---|---|
| CLI and local FastAPI/dashboard | IMPLEMENTED | sourceroi/live/{cli,api}.py and web; test_live.py; no identity/tenancy |
| Document ingestion and indexing | PARTIAL | ingest/config/retrieve; supported format tests; DOCX dependency missing; parser process budget absent |
| Dataset/source/document/passage evaluation | IMPLEMENTED | engine, datasets, public_audit, grade; live/public/study tests; deterministic scores distinct from semantics |
| Marginal valuation and constrained optimizer | EXPERIMENTAL | engine, validation, policies, assurance.source_value; ablation/optimizer tests; no independent economic or quality validation |
| Knowledge/version intent and evaluation maintenance | IMPLEMENTED | assurance; immutable spec/approval/version tests; operator review assertions |
| Impact mapping | PARTIAL | assurance inventory/proposals; lexical/document and registered fact signals, not semantic dependency precision |
| Data CI and strict release | IMPLEMENTED | data_ci, release_policy; grounded release and assurance tests; independent semantic review remains external |
| Diagnosis and isolated repair | PARTIAL | diagnosis, assurance.verify_repair; hypotheses and authored repair fixtures; no independently established causal coverage |
| Longitudinal history | IMPLEMENTED | db, timeline, maintenance; tests; no durable multi-writer scheduler/retention |
| Table/source-bound calculations | EXPERIMENTAL | facts/tables; 9/9 supported authored examples, narrow opt-in grammar |
| Callback / HTTP integration | PARTIAL | adapter/provider + external tools; synthetic protocol tests, no independently validated customer app |
| Owned fixture accounting | IMPLEMENTED | experiment/worker; deterministic failure/cancel/concurrency tests |
| Owned native accounting | UNVERIFIED | live execution refused; native audit PENDING |
| Authenticated multi-user SaaS | NOT IMPLEMENTED | intentionally restricted single-user loopback |
| Quality-preserving real-model optimization | UNVERIFIED | earlier model quality FAILED; independent final evaluation PENDING |

## 4. New production-oriented changes

Added a pure ASGI boundary that validates loopback Host and exact browser Origin, rejects duplicate boundary headers/cross-site requests, enforces a measured streamed 1 MiB body cap and 15-second receive deadline, requires JSON mutation bodies and generates request IDs. Existing route response shapes remain intact. Run listing adds bounded limit/offset. Readiness reports actual configuration/storage checks without claiming production readiness. The legacy local HTTP service also gains Host/Origin and negative length checks.

SQLite paths reject external .sourceroi resolution and database/WAL/SHM symlinks; connections explicitly roll back exceptions. Added exclusive private online backup, integrity verification and separate-directory restore regression. Legacy benchmark/document/baseline paths are confined; benchmark bytes/task count bounded. PDF signature and DOCX archive/expansion preflight checks precede parsing. Asynchronous API job errors retain exception class rather than raw exception text. The dashboard identifies the local deployment and pending independent quality/native accounting and calls labels registered expectations rather than automatically user-verified answers.

## 5. Security findings and remediations

Severity describes this local beta and becomes higher if exposed. Tests verify specific boundaries, not absence of all attacks.

| Finding | Severity | Status and evidence |
|---|---|---|
| Unexpected Host / DNS-rebinding surface and alternate localhost-origin mutations | High if browser can reach local service | VERIFIED remediation: HTTP guard exact origin/Host; legacy guard; negative ASGI and helper tests |
| Unbounded ASGI body / slow body | High availability risk | VERIFIED measured cap/deadline before route JSON; streamed and timeout regression tests; connection floods still PENDING |
| SQLite/legacy file symlink escape | High under untrusted local workspace | VERIFIED external path/symlink refusal tests; same-account TOCTOU/hardlink defense not established |
| ZIP-based DOCX expansion without preflight | High availability risk | VERIFIED declared-entry/size/structure checks and adversarial ZIP test; parser CPU/memory isolation PENDING |
| Legacy benchmark/document traversal; oversized benchmark | High local confidentiality / medium availability | VERIFIED confined paths/limits; legacy negative tests |
| Raw asynchronous exception persistence | Medium confidentiality | New API run errors class-only; existing source/answer artifacts intentionally sensitive; complete log redaction audit PENDING |
| No authenticated reviewer, role or workspace authorization | High for shared/public deployment | PENDING; not concealed; single trusted operator only, no SaaS approval |
| Multi-process run ownership, request idempotency, durable cancellation | High for unattended execution | PENDING; documented single-process restriction |
| Parser/resource exhaustion beyond prechecks | High for hostile uploads | PENDING; reviewed local sources only; no parser sandbox claim |
| Arbitrary trusted callbacks / config-directed endpoint egress | High if treated as untrusted | PENDING sandbox/egress policy; only operator code/config is supported |
| Dependency vulnerability and supply-chain audit | PENDING severity assessment | No network scan; no claims of clean advisories; DOCX dependency missing |

Existing protections inspected: parameterized SQL, no shell=True or pickle deserialization in application paths, remote endpoint HTTPS/credential URL validation, no redirect following in provider POST, no customer-supplied URL ingestion endpoint, environment-variable credentials, no answer keys passed to callback, citation/version checks and independent-review requirements. Configuration remains trusted code/egress authority. These observations are not general SSRF or injection immunity. Documents are untrusted evidence and cannot call review/label APIs through model output; prompt guidance alone does not solve prompt injection.

## 6. Architecture and data flow

Operator config + registered files → bounded extraction/index → frozen source/task/config identities → intent specification → explicit review → trusted application/built-in execution → deterministic evidence checks + separately supplied semantic judgments → release verdict/SQLite/export. Data, model output and reviewer assertions remain distinct. No source diff alone authorizes expectation changes. A trusted account can still edit local files/hashes; no cryptographic identity or authenticated append-only storage is claimed.

## 7. API and customer integration

Existing v2 routes and callback/HTTP contracts are preserved. Pagination is additive with the same list shape. Oversized bodies now 413, slow body 408, wrong content type 415, forbidden host/origin 403; clients must use the exact bound origin and application/json. Readiness can return 503. New X-Request-ID correlates HTTP requests only. Unknown model usage remains null. No automatic HTTP retries or new mutating idempotency guarantee were introduced. PILOT_ONBOARDING.md links the existing nine-stage workflow, source-owner templates and real app callback boundary. Application indexing/version mapping and nested calls must be validated by its developer.

## 8. Dataset evaluation and source valuation

Existing evaluation, source/document/passage ablation and marginal contribution paths are retained and covered by the full suite. Scores depend on configured reference labels and scorers. Ablation effects may interact/non-add and do not establish monetary value. Corpus/source-name overlap does not establish semantic causality. Independent groundedness and representative tasks remain PENDING.

## 9. Data CI and release assurance

Existing strict policy, citations, source/config/test versions, formula approvals, numeric checks, protected expectations, independent review, incomplete execution handling and no-downgrade behavior are unchanged. Historical synthetic strict table release remains REVIEW, bad candidate CI blocked, isolated repair after REVIEW/overall INCONCLUSIVE. New tests do not substitute for independent semantic review. Synthetic accept fixtures elsewhere are not genuine externally approved releases.

## 10. Optimization and quality

No new optimization claims or model experiments. The new deterministic replay preserves before table flag 7/9 → after 9/9, false abstentions 2 → 0, safety 8/8 and unsupported refusals 2/2 across 19 exposed authored cases. This demonstrates the earlier narrow table fix mechanically, not independent semantic accuracy. Historical Qwen 1/3 supported performance and incomplete accounting defeat a quality-preserving savings claim. No operating-cost or customer savings measurement exists. See INVESTOR_EVIDENCE.md.

## 11. Native inference accounting

PENDING. Existing approved runtime and source audit artifacts are retained: tagged HTTP request logger registration is disabled; native slot/task/timing evidence lacks verified request-to-terminal-response identity. The owned runner still refuses native execution. No new native build source or dependencies were available/used; no runtime replacement was attempted. Exact next native work: instrument the request dispatch with an authenticated per-request ID carried through each generation/child task, record terminal outcome and observed usage, fsync durable server-side events, validate failure/retry/cancel/parent death against independent raw responses, then run the authorized at-most-two-generation/30-second smoke only if the gate is justified. Ledger/slot totals/private socket alone are insufficient. This sprint starts 0 native processes, dispatches 0 real generations, spends $0 externally; full native usage remains unknown, not fabricated zero historical usage.

## 12. Storage, reliability and recovery

Original runs table schema retained; existing primary key provides run identity, no new relational tables needing foreign keys. Parameterized writes, WAL/busy timeout, explicit rollback and online backup tested. No full migration framework, automatic retention, immutable terminal-write enforcement, durable queue/resume or multi-process ownership. Startup mark_interrupted is unsafe with multiple writers; do not run them. Run history/checkpoints do not imply exact-once execution. Database-only restore tested; complete source/task/config-consistent disaster recovery PENDING. New runbook documents operational limits without deploying services.

## 13. Tests and limitations

Final suite: **344/344 passed in 9.79s** (docs/artifacts/production-beta/final-suite.txt); focused new tests: **20/20 in 0.46s** (security-tests-final.txt). New tests cover origin/Host variants, body/content type, streamed limits/timeouts, pagination bounds, request IDs, readiness failure/success, SQLite and legacy escapes, rollback/pagination, backup restore/no overwrite, PDF signature, DOCX expansion and explicit synthetic replay. Test definitions are authored in-repo, not independent attack coverage. No real model, production database, external app, human review, load test or target-platform clean install occurred. One full intermediate run passed 341 tests before the final three regression tests; its log is preserved.

## 14. External beta readiness

PRELIMINARY/conditional. Existing v2 archive SHA and its 19-file handoff verify under its included frozen implementation in an extracted temporary directory. No package contents were changed; old code is archival, not the current hardened service recommendation. Existing historical mechanical onboarding smoke remains labeled synthetic. No separate human developer has yet followed the workflow with a real app. Current source security changes are in this checkout and separately frozen sprint evidence; neither makes old archive/current-code identity interchangeable.

## 15. Independent validation requirements

Actual source owner; approved data rights and intent; independently established answer/evidence/scope labels before output exposure; disjoint held-out document groups; genuine reviewer identities/independence authorized outside local assertions; representative supported and abstention/regression cases; reconciled app/provider usage; independent security and operational review. Do not create synthetic participants or fill feedback on their behalf.

## 16. Competitive differentiation evidence

PRELIMINARY: maintained evaluation tied SourceROI on observed release detection. Preserve equivalent full maintained labels, authoritative diffs, retrieval traces and review conditions in all three arms. Existing maintenance-study event schema/hash logger remains; human active effort, integration time, missed dependencies and diagnostic correctness need genuine observed sessions. Product integration/differentiation remains a hypothesis.

## 17. Investor demo

INVESTOR_DEMO_RUNBOOK.md supplies a 3–5 minute replay. tools/investor_demo.py checks four preserved report hashes and labels every result synthetic/historical, with no live inference or fabricated strict ACCEPT. The technical brief/evidence table and unfilled feedback protocol separate observations, failures and unknowns.

## 18. Remaining production blockers

Authentication/authorization/tenancy if shared; hostile-parser isolation; dependency lock/security scan and missing DOCX environment; native/external actual-call reconciliation; durable job ownership, cancellation/idempotency and transactional immutable approval/history storage; complete backup/restore/retention; infrastructure/load/security testing; actual application integration and independent semantic/held-out quality evidence. No certification, SLA or public deployment claim is justified.

## 19. Deployment recommendation

Technical demonstration: VERIFIED mechanical replay, clearly authored. Controlled external beta: PRELIMINARY, trusted single-user local workflow with reviewed inputs and a validated app boundary; missing independent outcomes remain visible. Unattended/public/multi-user production: PENDING, do not deploy. Keep owned native inference gated until independently reconciled.

## 20. Exact next actions

1. Verify a clean supported-OS installation, install/test the declared DOCX parser if needed, and create an artifact-hashed dependency lock plus security scan.
2. Obtain one authorized real source owner/application and independently freeze labels/holdout groups; collect actual integration feedback without inferring customer value.
3. Establish auditable native request/terminal mapping (or separately verified actual app/provider accounting); only then authorize bounded real execution.
4. Run equal-input maintained/full-diff/SourceROI sessions with real participants and preregistered outcomes; report ties and failures.
5. Before broad access, implement/test identity, workspace permissions, parser resource isolation, durable job ownership/idempotency and complete disaster recovery; commission independent security review.

## Feature preservation matrix

“Tested” refers to authored automated tests, not independent efficacy. Production-ready is PENDING for each pillar as part of the deployed product.

| Feature | Implemented | Tested | Independently validated | Production-ready | Remaining work |
|---|---|---|---|---|---|
| Dataset evaluation | VERIFIED core | VERIFIED suite | PENDING | PENDING | representative independent labels and scoring validity |
| Information valuation | PRELIMINARY ablation | VERIFIED suite | PENDING | PENDING | interactions/attribution, customer value measurement |
| Token/cost optimization | PRELIMINARY engine | VERIFIED fixtures; real quality FAILED | PENDING | PENDING | strong baselines, full usage, held-out quality constraints |
| Data CI | VERIFIED core | VERIFIED suite | PENDING | PENDING | real-app pilot, operational integration |
| Intent-aware change detection | VERIFIED core | VERIFIED suite | PENDING | PENDING | human authorization/real scope validation |
| Evaluation maintenance | VERIFIED reviewed proposals | VERIFIED suite | PENDING | PENDING | authenticated review, real effort study |
| Fact/task impact mapping | PRELIMINARY partial | VERIFIED fixtures | PENDING | PENDING | independent dependency oracle/coverage |
| Root-cause/repair assurance | PRELIMINARY partial | VERIFIED isolated fixtures | PENDING | PENDING | independent causal diagnosis and repair quality |
| Longitudinal history | VERIFIED core | VERIFIED suite | PENDING | PENDING | concurrent ownership, retention, complete recovery |
| CSV/Markdown numerical evidence | PRELIMINARY narrow grammar | VERIFIED 9/9 exposed | PENDING | PENDING | broader independent cases, semantics/parser isolation |
| CLI/API/dashboard/SQLite/legacy | VERIFIED preserved core | VERIFIED suite | PENDING | PENDING | identity, API durability, deployment validation |
| Owned native accounting | PENDING | VERIFIED fixture gate only | PENDING | PENDING | server request/terminal correlation; no live smoke |

Evidence and source snapshots are indexed under docs/artifacts/production-beta/. Statuses do not equate passing tests with security or product readiness.
