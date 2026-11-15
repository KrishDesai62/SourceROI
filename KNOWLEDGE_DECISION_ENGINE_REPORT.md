# Knowledge Decision Engine — Phase 4 vertical slice

**VERIFIED internally: working retrieval/evidence-only decision workflow. Real-model quality/cost claims, independent validation and production readiness remain PENDING.** No generation route was enabled; zero new model generations and $0 external spending.

## Repository audit and implementation

The audit read the Phase 3 closure/security/isolation/feature reports and existing methodology, assurance, evaluation-maintenance and standalone-study documentation. Current code confirmed existing generated source/document/passage ablations, quality-constrained policy search, provider accounting, source versioning, Data CI, impact prediction, diagnosis/repair, authenticated maintenance/semantic review, durable fixture jobs and shared isolated workers. The missing piece was a persisted, reviewable recommendation/alternative record. See `docs/KNOWLEDGE_DECISION_PLAN.md` for the implementation plan; no new architecture or framework was added.

`sourceroi/live/knowledge_decision.py` adds strict request, alternative and evidence-requirement models. It verifies a frozen baseline, identical full registered tasks, source/configuration versions and protected IDs. Alternatives may use the baseline or candidate corpus and explicitly exclude one/multiple sources, documents or passages, or select an existing retrieval policy. Replacements are supplied as current workspace versions, never written by the engine. The original configuration and labels remain unchanged. Source state is rechecked after analysis; stale inputs cannot publish a successful result.

The fixed `knowledge_measure` analytical operation reuses existing question-only policy selection, routing, applicability/conflict screening and literal Data CI coverage inside the existing resource-isolated worker. The parent checks experiment/task identities, known evidence IDs, intervention exclusions, bounded coverage and context accounting, then attaches exact registered passages/document versions. Historical ablation comparison also runs in the existing bounded worker. Security identities, sessions, approvals and semantic judgments never enter these operations. Existing resource/admission/sandbox limits remain unchanged; this does not solve the documented hard-memory blocker.

## Transparent decision policy

There is no opaque ROI score. Rules, in priority order:

1. **KEEP** when a direct individual ablation loses registered protected evidence.
2. **REVIEW** when potential contradictory evidence prevents a safe recommendation.
3. **UPDATE** for a verified source/version difference requiring reviewed replacement; newer does not imply authoritative/correct.
4. **REMOVE**, as a potential-redundancy proposal only, when a direct individual baseline ablation preserves complete registered reference coverage without uncertainty or evidence loss. This never implies that multiple such removals are safe together.
5. **REVIEW** otherwise, including missing coverage or an entity with no direct tested intervention.

Recommendations carry source/document/passage identity, before/candidate document versions, referenced/exposed/affected tasks, individual versus joint observations, exact experiment links, lost-reference tasks, estimated context difference, uncertainty and optional historical ablation links. Answer-quality effect and total monetary impact stay UNKNOWN. Version-change flags remain visible even when protected-evidence KEEP takes precedence.

Existing completed source/document ablations may be linked with `ablation_run_ids`; full corpus, configuration and task-set identities must match. Their original provenance/usage labels and comparisons remain explicitly historical, not newly executed or independently authenticated evidence. Mismatched/partial histories are rejected, and historical token categories are not merged into this run's zero generations.

## Quality, accounting and release semantics

Evidence requirements configure minimum literal reference coverage, maximum reference regressions and protected tasks. Explicit reference-version pins and scope mismatches cannot silently pass. Missing/empty references are never treated as semantic support; invalid nonempty references fail validation, absent annotations stay unknown. Per-alternative BLOCK records failed evidence requirements/protected losses; unknown annotations produce INCONCLUSIVE; otherwise the result remains REVIEW. Positive literal matches cannot produce ACCEPT.

Every report has `release_authorized: false` and `automatically_applied: false`. The overall REVIEW is a recommendation packet, not approval of all alternatives: a current candidate replacement can be BLOCK while an alternative on the original corpus remains reviewable. No maintenance receipt, semantic judgment, generation authorization or release authorization is fabricated.

Prompt/completion/total provider usage, answer accuracy, model cost and cost per question are null without generation. Estimated context tokens are the sum of `ceil(passage characters / 4)` and explicitly exclude prompt scaffolding/output. If an input price is configured, a separate **estimated context-input cost only** is calculated; this is not total cost or measured savings. Real quality-constrained generation remains in the existing separately gated study/release interfaces and was not executed. Historical exploratory savings are unchanged and do not qualify this workflow.

## Persistence and product integration

No schema migration was needed: the existing `runs` table stores immutable content-bound `knowledge_decision` reports. Repeated identical submissions reuse the original result; SQLite insert-or-ignore preserves one persisted result under concurrent equivalent completion. This is result idempotency, not a claim of cross-process deduplication of all retrieval computation. The report identity binds request, exact versioned change specification, both manifests, full task hash and linked historical report hashes. Existing history, backup and knowledge timeline retain these records.

- API: `POST /api/v2/knowledge/decisions`; authenticated operator/admin mutation, existing CSRF/audit/workspace boundary and local evaluation semaphore. Viewer/reviewer submission is denied. Read through existing `/api/v2/runs/{id}` and history/timeline.
- CLI: `sourceroi --project WORKSPACE knowledge-decide --request REQUEST.json`. `snapshot_id` selects an existing `.sourceroi/snapshots/<id>`; request uses the same typed schema as the API. No model-call acknowledgement is requested because the operation cannot generate.
- Dashboard: **Knowledge Change Review** supplies snapshot, explicit alternatives and requirements, renders recommendations/quality uncertainty/estimated differences, and exposes the exact persisted JSON. Existing history reloads the same decision. It offers no apply/delete/approve button.

Example alternative: `{"name":"remove_pair","corpus":"baseline","exclude_sources":["sourceA","sourceB"]}`. Combined effects are measured directly; individual losses are not added. Existing reviewed evaluation maintenance remains separate from this frozen-label comparison.

The bounded offline endpoint is synchronous. A disconnected request does not constitute cancellation of a durable job; long-running asynchronous decision-job integration remains incomplete. Worker errors fail the request, retain existing supervised crash evidence and cannot publish an approval. Existing durable execution cancellation/fencing/unknown-outcome semantics and real-generation denial remain covered separately.

## Execution and tests

Commands actually executed (outputs under `docs/artifacts/knowledge-decision/`):

```sh
workspace/design-partner/venv/bin/python -m pytest -q
workspace/design-partner/venv/bin/python -m pytest -q tests/test_knowledge_decision.py
workspace/design-partner/venv/bin/python tools/benchmark_knowledge_decision.py --output docs/artifacts/knowledge-decision/benchmark-v3
workspace/design-partner/venv/bin/python tools/validate_closure_browser.py --output docs/artifacts/knowledge-decision/browser-final
node --check sourceroi/live/web/app.js
workspace/design-partner/venv/bin/python -m sourceroi --project docs/artifacts/knowledge-decision/benchmark-v3/redundant knowledge-decide --request docs/artifacts/knowledge-decision/cli-request.json
```

Baseline: **577 passed in 212.78 s**. An intermediate expanded full run passed **593 in 230.72 s**. Final code-frozen full regression: **594 passed in 245.04 s**, recorded in `full-complete.txt`. The 17 added cases exercise redundancy, protected and joint interventions, consistent update/conflict, missing annotations, document/passage provenance, malformed/unknown IDs, forged reinsertion, changed labels, source races, pinned versions, scope mismatch, estimated versus unavailable actual cost, history binding, authenticated roles and actual CLI dispatch. Original eight feature paths and strict release tests remain in the full suite.

Installed Chrome 157.0.8103.78 passed **20 actual browser checks**, including the new decision form and viewer submission denial. This remains authored fixture/browser acceptance, not independent usability or full accessibility certification. The final offline benchmark is documented in `KNOWLEDGE_ROI_BENCHMARK.md`; it ties a strong conventional workflow and records an impact false alarm.

Failure evidence is preserved: `focused-first.txt` caught the incorrect development UPDATE expectation in a conflicting fixture; conflict policy was retained. `cli-stderr.txt` caught a missing scoped `secure_path` import on actual CLI dispatch; it was fixed and a CLI regression added. `cli-invalid-contract.txt` records actionable request-schema rejection. Earlier successful/failing runs were not overwritten.

The previous closure install probe used unsupported `require_auth` and accepted TypeError, so its service-rollback subcheck alone was insufficient evidence. The corrected probe uses `authenticated` and requires actual ValueError refusal. Fresh final-source local-wheel results under `install-complete/installed-upgrade-results.json` verify both default and explicit unauthenticated rollback refusal, explicit migration/session revocation, and TXT/PDF/DOCX smoke. Earlier reports/packages remain unchanged. This is a test wheel, not a new sealed release.

Changed implementation: `knowledge_decision.py`, `analysis_boundary.py`, `db.py`, `assurance.py`, `api.py`, `cli.py`, dashboard HTML/JS; new `tools/benchmark_knowledge_decision.py` and `tests/test_knowledge_decision.py`; browser acceptance tool extended; install probe corrected. No provider/native/semantic approval safety gate was relaxed.

## Limits and final judgment

Implemented/tested: the evidence-only vertical slice, saved recommendations, explicit alternatives, conventional comparison and actual dashboard. Implemented but not independently verified: recommendation usefulness and source/task impact coverage. Fixture-only: all new quality and action observations. Real-model results: **none authorized or executed**. Independent held-out/semantic/customer validation: **PENDING**.

The platform can now expose and test a reviewable knowledge decision; it has **not demonstrated that this decision is better than a strong conventional process**. Phase 3 hard aggregate memory, encrypted/off-host recovery and independent security requirements remain unresolved. No production-readiness or commercial-advantage claim is justified.

Historical preservation: `historical-verification.json` checks **1,256 pre-existing root/docs reports and artifact files with zero mismatches**. New failure logs, benchmark protocols, raw evidence and test wheels remain separate; historical Phase 3 results were not rewritten to correct the earlier probe's scope.
