# Knowledge change assurance: implementation and evidence

This is the historical implementation-phase report. The [subsequent validation sprint](VALIDATION_DIFFERENTIATION_SPRINT.md) repaired numeric-answer parsing, reran the local smoke, and found a tie against properly maintained baselines. Independent semantic/citation validation remains pending.

November 13, 2026. Standalone SourceROI; no Equity Research edits, paid calls, cloud resources, commercial credentials or new model downloads. This is a local developer beta. The full independent validation requested in the brief remains unfinished; the evidence below is explicitly scoped.

## A. Repository audit

[Audit and implementation plan](KNOWLEDGE_ASSURANCE_AUDIT.md). The baseline was **123 passing tests**, verified with localhost access. Source snapshots, ablation, provider accounting, source-level Data CI, diagnosis, temporary rollback, local Qwen and SQLite history already existed. Approved knowledge intent, proposed test revisions, fact/task mappings and four-way release orchestration were missing.

Prior optimization evidence remains unchanged: simple strategies matched or beat the optimizer; fallback could eliminate savings; independent semantic groundedness was pending. This phase adds release assurance rather than another optimizer search. No historical held-out questions were promoted into new unseen validation.

## B. Implementation

`live/assurance.py` extends existing ingestion, snapshots, graders, execution, diagnosis and SQLite persistence:

1. **Stage A, no model calls:** verify immutable baseline, extract sentence/record-line candidate facts, diff versions, preserve document identity, authority/effective-date/scope metadata, detect potential same-shape numerical conflicts, map dependencies and propose expectation edits/new questions.
2. **Explicit review:** named local reviewer, rationale, expected changes, protected tasks, rejected proposals and replacement evidence. Hashes bind decisions to exact source/configuration/test-set versions. Proposal text is never authoritative. Reviewer identities are assertions in this localhost beta, not authenticated enterprise approvals.
3. **Stage B:** bounded paired baseline/candidate execution, original versus reviewed expectation scoring, literal reference coverage, broader negative controls, fail-closed completeness checks and JSON/Markdown reports. An unknown intended change receives REVIEW rather than being silently accepted or declared a confirmed regression.
4. **Release verdict:** ACCEPT only when the full registered suite passes reviewed expectations and measured reference checks; BLOCK for confirmed required expectation/support failure; REVIEW for unknown intent, missing reviewed references, potential conflicts or confounded configuration changes; INCONCLUSIVE for incomplete/subset execution, unavailable models, invalid adapter responses, failures or exhausted budgets. ACCEPT covers these registered exact-answer/reference checks, not universal semantic safety or permission to deploy.
5. **History:** specifications, review events and releases use existing SQLite runs. Baseline/candidate knowledge, agent/model/prompt/retrieval settings and original/reviewed test-set versions remain distinguishable. Candidate causes and fact changes are available in the compact timeline.
6. **Interventions:** `verify_repair` evaluates an explicitly supplied isolated repair against the same frozen baseline, with separately bound review and a shared budget. It requires the registered suite to recover without other registered failures. Existing Data CI temporary rollback and source/document/passage ablations remain available.

No production source files, existing benchmark labels or unrelated projects are automatically changed. Change reports intentionally contain relevant source passages for local review; avoid exporting them outside the authorized environment. Endpoint secrets are not exported; adapter exception text is suppressed. Retrieved passages remain data, not executable instructions.

CLI additions: `change-plan`, `change-review`, `release-check`, `knowledge-timeline`. API additions: `POST /api/v2/knowledge/{plan,review,release}`, `GET /api/v2/knowledge/timeline`, and `GET /api/v2/knowledge/releases/{id}/export?format=json|markdown`. Dashboard Experiments adds proposal/review/release controls and saved release rendering. No database schema rewrite or new service is required.

## C. All eight features: actual status

| Feature | Reused | Implemented and exercised | Limits / unfinished |
|---|---|---|---|
| 1. Intent-aware changes | Immutable Data CI snapshots, original adapters | Hashed facts/passages and metadata, explicit expected/protected/rejected review, unknown intent | Candidate sentences are not a universal fact extractor; date applicability is reviewed, not inferred; live DB/API connectors absent (materialized CSV/JSON supported) |
| 2. Evaluation maintenance | Independent benchmark and graders | Exact edit suggestions with citations, pending candidate questions, review-bound overlay, stale flags and test-version history | New questions need review and labels; 1 known incorrect and 1 ambiguous suggestion in five controls; no independent label-accuracy or labor study |
| 3. Impact mapping | References, IDs, traces | Source→fact→task edges from annotations/history/topics; additions/configuration signals; negative controls | Heuristic and nonexhaustive; full suite required for ACCEPT; no independently validated selector recall |
| 4. Release assurance | Engine, local provider, SQLite, CLI/API/UI | Two stages, four verdicts, incomplete/stale-input guards, exports and local CI example | Exact answer and literal quote checks only; semantic/citation correctness unreviewed; HTTP application version attestation not added |
| 5. Diagnosis and repairs | Existing diagnosis and temporary rollback | New reports reuse diagnosis; reviewed isolated paired repair and shared budget | Joint intervention supports limited causal claims; supplied repair must be isolated; no autonomous repair synthesis/application |
| 6. Longitudinal intelligence | Run history | Proposal/review/release timeline with exact versions, facts, outcomes and repair runs | Compact API/CLI/history view; no automatic causal attribution across confounded changes; no dedicated timeline visualization |
| 7. Dataset value/selection | Source/document/passage ablation, addition, optimization and accounting | Version/task-specific KEEP/REVIEW recommendations and evidence links | No new universal score; new orchestration does not automatically justify REPLACE/REMOVE without controlled evidence; use existing ablations |
| 8. Cost-aware testing/selection | Original optimizer, top-k comparison, provider usage and limits | Calls/avoided task executions, timing, raw usage, targeted scope accounting | Safe full-suite controls saved zero calls; no new quality-preserving optimization advantage; callback model usage may be unknown |

The new regression tests exercise integrity, approvals, pending labels, protected behaviors, missing support, incomplete responses, duplicate results, time/call limits, callback label separation, stale/mutating inputs, conflicts, repair isolation, CLI/API/history and exports. Existing tests continue to cover the preserved capabilities. New browser controls passed syntax checking; browser interaction was not automated.

## D. Executed validation

Commands:

```bash
python -m pytest -q
python -m pytest tests/test_assurance.py -q
node --check sourceroi/live/web/app.js
python examples/knowledge_change/demo.py --output workspace/knowledge-change-demo
python tools/validate_knowledge_assurance.py docs/artifacts/knowledge-assurance-release.json
python tools/summarize_knowledge_assurance.py docs/artifacts/knowledge-assurance-release.json docs/artifacts/knowledge-assurance-release-summary.json
```

Output destinations are immutable: choose new paths to reproduce. The demo executed four deterministic application tasks and returned ACCEPT. The deterministic comparison ran 13 scenarios. These are **authored, exposed regression fixtures**, not independently annotated, document-disjoint unseen final evidence. Intermediate scenario artifacts are retained; filenames containing `final` do not confer held-out status. No claim is made that creating a separate fixture file produces independent validation.

[Full scenario outputs and confusion matrices](artifacts/knowledge-assurance-release.json), [summary](artifacts/knowledge-assurance-release-summary.json), [real-model smoke](artifacts/knowledge-local-smoke.json).

**Final suite: 149 passed in 6.27 seconds; focused assurance suite: 26 passed.** [Current tested code archive](artifacts/knowledge-assurance-current-code.tar.gz) and [hash manifest](artifacts/knowledge-assurance-code-manifest.json) preserve the deterministic validation implementation. This archive is not represented as the earlier smoke's exact code snapshot. Full verification is recorded in STARTUP_VALIDATION.md. Tests do not rerun the real model. Git commits/diffs are unavailable because this workspace contains no Git repository metadata.

## E. Competitive comparison

[Verified documentation comparison](KNOWLEDGE_ASSURANCE_COMPETITIVE.md) distinguishes documented overlap, our implementation, workflow hypotheses and evidence. Source versioning, lineage, evaluation datasets, human review, regression gates and generated tests are industry-standard overlapping capabilities. No competitor software was benchmarked. Documentation silence is not evidence of absent functionality.

Potential differentiation is a compact review-bound knowledge diff → expected/protected test changes → evidence-aware release report → isolated repair workflow. Our controls support its mechanical usefulness, not exclusivity, market differentiation or customer savings.

## F. Experiments, including negative evidence

The deterministic application retrieves values from registered JSON knowledge files. Labels and intended outcomes are explicit authored fixtures, separate from application outputs. Scenarios include legitimate/numerical changes, protected behavior, stale interpretation, effective-date uncertainty, essential/redundant removal, conflicts, multiple-source dependencies, ranking/configuration changes, correct answers without support, new content affecting a task without prior reference linkage, and ambiguous intent.

| Method | Consequential cases blocked / 8 | False blocks on legitimate changes / 3 | REVIEW | Equivalent agent task executions |
|---|---:|---:|---:|---:|
| A. Ordinary old-answer regression | 6 | 2 | 0 | 54 |
| B. Original reference coverage | 8 | 2 | 0 | 54 |
| C. Source diff + full old-label rerun | 6 | 2 | 0 | 54 |
| D. Reference-based task selection + ordinary evaluation | 3 | 2 | 0 | 22 |
| SourceROI with explicit authored review | 8 | 0 | 2 | 54 |

**Full confusion matrices:** each row lists ACCEPT/BLOCK/REVIEW/INCONCLUSIVE predictions. Ground-truth ACCEPT: A/B/C/D `[1,2,0,0]`, SourceROI `[3,0,0,0]`. Ground-truth BLOCK: A/C `[2,6,0,0]`, B/SourceROI `[0,8,0,0]`, D `[5,3,0,0]`. Ground-truth REVIEW: A/B/C/D `[1,1,0,0]`, SourceROI `[0,0,2,0]`.

This comparison gives SourceROI explicit policy-owner decisions while ordinary baselines retain stale expectations. A human-maintained baseline could obtain the same knowledge and avoid the same false alarms. A stronger topic-based selector could also match our candidate mapping. **Evidence detection tied reference coverage, and full-suite execution saved zero calls.** D reduced executions but missed five of eight blocking scenarios; it is not a safe optimization result.

The candidate impact selector missed zero authored affected tasks; the reference-only selector missed three. SourceROI still evaluated the full registered suite in the final comparison, so this is not evidence that targeted execution preserves quality. A separate unit test confirms that targeted passing checks with unexecuted tasks return INCONCLUSIVE.

Five revised-answer suggestions: three match explicit authored decisions, one would wrongly change a protected warranty expectation, one has unknown intent. Among four decidable proposals this is **3/4**, with **1/4 requiring correction/rejection**; the fifth needs interpretation. No suggestion became authoritative automatically. This is a reason to retain review, not claim dependable autonomous evaluation maintenance.

Changed-document localization matched the authored single-document cause at top-1 and top-3 in **7/7** eligible controls. The ranking case also changes configuration and is excluded from source-only localization scoring. These tiny constructed causes are not independently adjudicated real-world root-cause accuracy. One controlled repair restored the complete fixture suite (**1/1**); joint restoration does not identify individual causal contributions in interacting changes.

The comparison reused paired outputs across A/B/C/D, then executed SourceROI separately. Counts in the table are equivalent per-method task executions, not separately billed/model calls. Total actual callback task executions were **116**, including eight for repair; genuine model inference calls in this comparison were **zero**. Latest measured orchestration time is in the summary; it is subsecond deterministic fixture timing, not customer-scale model latency or human time saved.

### Genuine four-call local-model smoke

Reused installed Qwen2.5-1.5B-Instruct Q4_K_M / llama.cpp b12345, localhost 8788, one slot, four threads, context 4096, temperature 0, seed 1729, max output 384. Cap: **four calls / 60 seconds**; actual: **four calls / 1.592846 seconds**, **848 total tokens** (802 input, 46 output), **$0 external API spend**. The local server was stopped. Monetary inference/hardware costs are unpriced, not fabricated as zero operational cost.

The approved return answer changed **30→14**, with literal reference coverage preserved. The unchanged warranty response was a JSON object containing numeric `answer: 365`; the current provider parser retained it as raw text, so the exact-answer check failed both before and after. **Verdict: BLOCK**, because a required registered expectation failed, not because a new warranty regression was proven. Release-layer correct counts were 1/2 before and 1/2 after approved revision. Raw engine candidate accuracy was 0/2 against the original labels; those metric scopes must not be conflated.

No parser/label patch or favorable rerun was used to erase this result. The smoke used authored questions, not unseen independent business tasks. It demonstrates real model execution and conservative gating, not deployment safety, source-change causation or customer benefit. Later deterministic hardening added metadata, conflict checks, history and integrity guards; the real smoke was not rerun under those later changes.

## G. Developer demo and integration

Run from the existing repository:

```bash
python examples/knowledge_change/demo.py --output workspace/my-knowledge-demo
```

This registers a small local JSON retrieval application via `external_agent(cfg, tasks)`, freezes a baseline, changes returns from 30 to 14, explicitly approves the authored policy change, protects warranty and emits SQLite history plus `change.json`, `approval.json`, `release.json`, `release.md`. No LLM, network, external API or infrastructure is required. `tasks` passed to a custom callback contain IDs/questions only. The callback loads the exact baseline or candidate knowledge configuration and returns answer plus canonical retrieved chunk IDs. Replace that callback with your existing application's read-only answer function; ensure it actually switches corpus versions and supplies complete results. This is a working callback integration example, not evidence of customer RAG compatibility across arbitrary stacks. Callbacks are trusted application code, not sandboxed code; they can inspect their workspace and must not load authoritative labels.

CLI workflow for the built-in local model:

```bash
python -m sourceroi --project MY_WORKSPACE freeze --output FROZEN_BASELINE
# Edit knowledge files in MY_WORKSPACE.
python -m sourceroi --project MY_WORKSPACE change-plan --baseline FROZEN_BASELINE --output change.json
# Inspect change.json. Write decisions.json with reviewer/rationale, expected_changes,
# protected_tasks and replacement expected_evidence; do not copy agent outputs into labels.
python -m sourceroi --project MY_WORKSPACE change-review --spec change.json --decisions decisions.json --output approval.json
python -m sourceroi --project MY_WORKSPACE release-check --baseline FROZEN_BASELINE --spec change.json --approval approval.json --output release.json --max-calls 40 --max-seconds 120 --allow-model-calls
python -m sourceroi --project MY_WORKSPACE knowledge-timeline
```

An explicit review example:

```json
{"reviewer":"Policy owner","rationale":"Approved US returns update; warranty unchanged","expected_changes":{"returns":"14"},"protected_tasks":["warranty"],"expected_evidence":{"returns":[{"document_id":"policy::returns.json","quote":"14"}]}}
```

CLI status **0=ACCEPT, 3=BLOCK, 4=REVIEW, 5=INCONCLUSIVE, 2=input/configuration error**. [Local CI entrypoint](../examples/ci/knowledge-release.sh) performs no deployment. Existing HTTP agent integration remains unchanged; the new release CLI directly executes local built-in RAG, while external applications use the Python callback boundary. A remote agent that cannot load/attest baseline versus candidate knowledge remains unsupported for release assurance.

Deadlines bound the built-in model through existing remaining-time request limits. Custom callbacks must honor timeouts themselves: an arbitrary synchronous Python callback cannot safely be preempted. Their elapsed deadline is checked after return, and late runs cannot ACCEPT. Process/OS memory containment and adversarial callback isolation are not provided. The real smoke's four-call cap was fixed before execution; no exhaustive model benchmark was launched.

## H. Startup readiness

- **Can a developer use it for a real update?** Yes, a local controlled pilot with reviewed expectations, registered evidence and a compatible callback/built-in local model. The complete developer demo executed. It is not multitenant or security-audited production SaaS.
- **Less manual evaluation maintenance?** Suggestions are generated; labor reduction is unmeasured. One bad and one ambiguous suggestion show why review remains necessary.
- **Fewer legitimate-update false alarms?** Demonstrated only with explicit authored approval versus unmaintained labels. A manually maintained baseline can match it.
- **Consequential regressions?** Eight authored cases detected; reference coverage matched them. The real smoke blocked an existing format/scoring failure, not a proven new source regression.
- **Less evaluation work without misses?** Not demonstrated. Safe final controls ran the full suite. Targeted results cannot certify unexecuted tasks.
- **Strongest demonstrated value?** Review-bound expectation maintenance and evidence/version-localized release decisions in one reproducible local workflow, plus verified isolated restoration. Unique detection and competitive advantage remain unproven.
- **Customer validation needed?** Independent policy owners, representative changing corpora, realistic source-date/scope conflicts, real external RAG adapters, semantic/citation review, maintenance effort against a human-maintained baseline and missed-task audits.

## I. Highest-value next work

1. Independently annotate and freeze fresh document-group-disjoint development/final scenarios, including paraphrases, conflicting scope/date rules and interacting source changes. Keep this phase's authored examples as regression tests.
2. Run a controlled design-partner update study against **human-maintained** A/B/C and stronger lexical/trace task selection, measuring review corrections, missed tasks and actual review/debug time.
3. Address response-schema robustness with independent protocol tests, and add authenticated reviewer decisions / external knowledge-version attestation before expanding deployment scope. Preserve the failed smoke as historical evidence.

No optimizer superiority, automatic intent correctness, autonomous production repair, time savings or exclusive invention is claimed.
