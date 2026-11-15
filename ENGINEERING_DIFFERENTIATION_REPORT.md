# SourceROI reliability and engineering differentiation sprint

2026-11-13 America/Chicago (frozen experiment 2026-11-14 00:13 UTC). Standalone SourceROI only; no paid APIs, downloads, external services or production changes.

**Result:** smaller context and better numerical diagnostics are implemented, but the local RAG still fails the reliability requirement. Three fresh supported questions yield **1/3 correct with every policy**. Passage selection uses **52.6% fewer total tokens** than top-k=3 but does **not** qualify as reliable quality-preserving optimization. Independent final evaluation and human effort advantage remain **PENDING**. The maintained workflows tie SourceROI on the recorded unsafe update.

Classification: **Verified** = artifact-backed mechanism/count; **Preliminary** = small development-label observation; **Failed** = attempted objective not met; **Pending / Unverified** = independent evidence absent.

## A. Implementation audit and actual changes

**Verified — starting point.** The initial full suite passed **234 tests in 7.06s**. Original IRS ledger/report/source hashes were checked: 11 calls, 15,777 tokens, BLOCK; supported accuracy 1/5 before and 2/5 after under Codex development labels. Raw authoritative PDFs, benchmarks, raw responses, labels and the [historical report](REAL_WORLD_VALIDATION_REPORT.md) remain unchanged. See [before hashes](docs/artifacts/engineering-sprint/before-hashes.json) and [final integrity](docs/artifacts/engineering-sprint/final-integrity.json).

The audit followed existing PDF/text/CSV ingestion, BM25 and source filters, provider schema/usage parsing, necessary-evidence guards, human claim review, intent proposals, Data CI/strict release, diagnosis/isolated repair, SQLite history/checkpoints, bounded optimizer, CLI, FastAPI and dashboard. Existing deterministic tests establish these mechanisms; they do not establish external model reliability, semantic truth or startup value. The earlier four-supported-question all-abstention run is preserved, as is the later medical false abstention on the real IRS corpus.

**Verified — incremental changes, no new architecture:**

- `ingest.py` adds opt-in `chunk_strategy: sentences`: literal extracted-document spans, immutable offset/content-bound IDs, common abbreviation/decimal handling, adjacent caveat retention, and explicit oversize-fragment flags. Default fixed chunking is unchanged.
- Existing `evidence.py`/`policies.py` add question-only `passage_coverage`, comparison-operand opportunities and exact-text deduplication within sources. Competing numeric predicates are retained; a character budget that would hide a retained side causes empty-context abstention. Heuristics do not confer semantic approval.
- `engine.py` applies explicit scope metadata before optional passage ranking, while retaining post-selection evidence checks. Experiment identity includes the indexing strategy; strict execution identity reports it. Unknown applicability remains unknown.
- Existing evidence and diagnosis modules add optional **review-only numerical proposals**, exposed through `diagnose --calculation-spec`. Literal subject/unit/period operands and Decimal arithmetic retain both inputs and source spans. They never replace agent answers, auto-repair data, grant semantic review, or change release outcomes.
- Existing maintenance logger adds `maintained_with_diff`, distinguishing the requested third study arm. Human timing stays null without actual participants.
- New bounded validation/replay scripts and 13 generic regression tests exercise these paths. No mandatory dependency, service, model download, framework or connector was added. Existing CLI/API/dashboard behavior remains compatible under the regression suite.

The [plan](docs/artifacts/engineering-sprint/PLAN.md), [frozen plan](docs/artifacts/engineering-sprint/plan.json), [code/configuration freeze](docs/artifacts/engineering-sprint/freeze.json), and [as-run archive](docs/artifacts/engineering-sprint/as-run-code.tar.gz) precede inference. Numerical proposal support, conflict-budget hardening and execution-identity reporting were completed after observing the run and tested deterministically. The [final archive](docs/artifacts/engineering-sprint/final-code.tar.gz) is separate; final-code inference was not rerun. Those later diagnostics are not rescored as model improvements.

## B. Retrieval and answer reliability

**Verified — actual experiment.** Reused the full original [2025 IRS Notice 2025-5](https://www.irs.gov/pub/irs-drop/n-25-05.pdf), its previously verified provenance, existing Qwen2.5-1.5B-Instruct Q4_K_M / llama.cpp b12345, BM25, seed 1729, temperature 0, output cap 384, one slot, four threads, context 4096, localhost 8788, prompt cache disabled. No expected values or annotated quotes enter selection/generation. Exact requests/responses, retrieved contexts and checks are retained in [sprint artifacts](docs/artifacts/engineering-sprint/). Fixed chunking indexes nine chunks; sentence strategy indexes 33 passages. The full text is unchanged.

Four questions were frozen before outputs: FAVR maximum automobile cost, 2025 depreciation portion, 2025 minus 2023 depreciation portion, and a Canadian FAVR authorization absent from this US collection. These are **new development questions on the already exposed IRS document family**, not independent or hidden final cases. Existing unrelated-subject/decimal/quarter-period regressions are newly authored engineering tests, not authoritative external benchmarks. See [frozen tasks](docs/artifacts/engineering-sprint/frozen-tasks.json).

**Preliminary — same frozen tasks, source version, settings and labels:**

| Task | Source-derived expected | Top-k=3 | Top-k=1 | Passage selection |
|---|---:|---:|---:|---:|
| FAVR ceiling, dollars | 61200 | 61200 | 61200 | 61200 |
| 2025 depreciation portion, cents/mile | 33 | IE | IE | IE |
| 2025 minus 2023 depreciation portion | 5 | 4 | 3 | 7 |
| Canadian FAVR unavailable here | IE | IE | IE | IE |

IE = `INSUFFICIENT_EVIDENCE`. The Canadian case is software scope abstention, zero generation in every arm. Each arm generated three actual responses, got **1/3 supported answers correct**, and falsely abstained on **1/3** supported questions. Including the guard case gives **2/4** registered answers correct. All three supported tasks have full literal annotated support retrieved in every arm; only two have full cited support because the lookup abstains without citations. Invalid cited IDs: zero in every arm. Independent semantic and citation correctness: **null**.

**Failed — numerical and abstention reliability.** The required depreciation evidence is present, even after localization; the model still refuses lookup and miscalculates the difference. A passage contains several annual numbers, so sentence-level indexing alone cannot isolate the right value. Passage coverage also supplies irrelevant rate sentences for the arithmetic question: lexical coverage is not predicate entailment. These failures were not hidden by the aggregate 2/4 score. The supported-accuracy Wilson interval is roughly **6.2%–79.2%** for 1/3; this tiny development sample supports no general quality claim. Repeated configurations share tasks and are not independent samples.

**Preliminary — exposed IRS retrieval replay.** Without new inference, previous versioned tasks retain the same reference recall: 4/5 baseline and 5/5 candidate under both policies. The baseline multi-passage task still has only half its annotated support. Smaller context has not solved multi-evidence coverage generally. See [historical retrieval replay](docs/artifacts/engineering-sprint/historical-retrieval-replay.json); it contains no new answer-accuracy measurements.

**Verified — post-experiment diagnosis, not improved RAG scores.** On the recorded failed passage responses, explicit development declarations bind depreciation/unit/2025 and depreciation/unit/2023. The narrow extractor finds 33 and 28 in the actually supplied source span, returning lookup proposal **33** and subtraction proposal **5**, both **REVIEW**. This demonstrates source-bound literal extraction and decimal calculation, not independent semantic correctness or a production-ready answerer. The main responses remain IE and 7. The mechanism rejects missing/ambiguous values, specified negation/qualifications, unknown requested applicability and unit conversions; it does not claim to understand arbitrary prose. [Diagnosis](docs/artifacts/engineering-sprint/numeric-diagnosis.json), [execution](docs/artifacts/engineering-sprint/numeric-diagnosis-execution.json), and [post-experiment declarations](docs/artifacts/engineering-sprint/post-experiment-calculation-declarations.json) retain provenance and phase separation.

## C. Quality-preserving optimization

**Verified usage; Preliminary development comparison:**

| Configuration | Prompt tokens | Completion tokens | Total | Reduction vs original | Supported correctness | Mean task latency |
|---|---:|---:|---:|---:|---:|---:|
| Original top-k=3 | 4534 | 85 | 4619 | — | 1/3 | 1512 ms |
| Top-k=1 | 2312 | 73 | 2385 | 48.4% | 1/3 | 917 ms |
| Passage coverage | 2106 | 82 | 2188 | 52.6% | 1/3 | 818 ms |

Latency averages all four tasks, including the zero-generation guard, in a single ordered run; these are not replicated normalized performance estimates. Passage selection uses 8.3% fewer total tokens than top-k=1. All arms preserve the one correct FAVR answer, but the preregistered requirement was **all supported tasks correct, no lost successes, full support recall, no invalid IDs or false abstentions**. All three configurations **FAIL**. Unchanged poor accuracy is not reliable quality preservation. Independently grounded optimization remains **Pending**; local hardware cost is unpriced and USD savings cannot be inferred.

**Verified — existing optimizer actually executed.** One explicitly identified fresh development task (FAVR) was used within the cap, with source subset, top-k reduction and fixed source-drop controls. Its baseline used 1,520 tokens and answered correctly; top-k used 796 and answered correctly on that single task. Removing the only source caused software abstention with zero tokens. The existing optimizer searches source subsets, reports **no_valid_reduction**, keeps all sources and leaves deployment **inconclusive**, with no held-out tasks. It records the top-k control but does not promote a passage policy. Its task-level observation is not broad or independent optimization proof. [Full result](docs/artifacts/engineering-sprint/results.json).

**Verified — global accounting.** [Ledger](docs/artifacts/engineering-sprint/execution-log.json): **11 actual generation attempts/responses, 11,508 provider-reported total tokens, 16.375 seconds elapsed**, under the shared maximum **12 new calls / 120 seconds**. Main comparison: nine calls, 9,192 tokens; optimizer: two calls, 2,316 tokens. Empty-context subset evaluations made no generation calls. Failed attempts would count before dispatch; there were no failed requests or retries. Actual generation HTTP boundaries sum to 15.854 seconds (model/server/HTTP/logging, not pure GPU time). All destinations were loopback; paid expenditure **$0**. No further generation was used for replay, handoff, final fixes or diagnostics. Server stopped after execution.

## D. Semantic validation

**Pending / Unverified.** Independent final labels, source-owner approval, human semantic/citation judgments and customer-agent results are absent. The existing reviewer infrastructure remains in use; no same-model judge was substituted for truth. The [12-item output packet](docs/artifacts/engineering-sprint/pending-semantic-reviews.json) retains exact version-bound contexts, answers and citations. Scoring the untouched pending packet yields **REVIEW, zero completed reviews, null independent semantic/citation rates**. [Score](docs/artifacts/engineering-sprint/pending-review-score.json).

The [handoff](docs/ENGINEERING_SPRINT_HANDOFF.md) contains ready commands, an unfilled external-label protocol, authorized-reviewer setup, source-owner onboarding and a three-arm study template. Correct numbers with unrelated citations still require explicit claim-level adjudication; literal references and source IDs are not approval. Strict policy cannot be downgraded; missing review, wrong formats, incomplete execution, stale configuration or source versions cannot silently confer strict ACCEPT. Existing strict-release tests remain passing.

## E. Equal-authority competitive baseline

**Verified — same-output replay, three-way tie.** All approaches receive the historical real before/after outputs, approved development expectation changes, version-specific references and equivalent citation, scope, schema, provenance and missing-independent-review requirements. Baseline B additionally gets ordinary original-document diffs and the same retrieval traces. The conventional checkers share deterministic primitives with SourceROI; this is not independent implementation verification.

| Arm | Verdict | Replayed task rows | New model calls/tokens | Single replay wall time |
|---|---|---:|---:|---:|
| A: maintained full-suite evaluator | BLOCK | 12 | 0 / 0 | 244 ms |
| B: maintained evaluator + ordinary diffs/traces | BLOCK | 12 | 0 / 0 | 197 ms |
| SourceROI integrated workflow | BLOCK | 12 | 0 / 0 | 1524 ms |

No unique failure-detection win was observed. Different bookkeeping/reporting, cache state and sequential execution mean these timings are not a fair normalized performance ranking. SourceROI incurs additional integrated work in this replay. B's diff/trace packet is [preserved](docs/artifacts/engineering-sprint/baseline-b-diffs-and-traces.json); SourceROI supplies intent, proposals, impact, diagnostics and release records, but useful packaging is not measured labor savings.

Actual CLI `release-check` was exercised with recorded real outputs at the evaluator callback boundary and provider networking forbidden: **BLOCK, exit code 3**, JSON and Markdown emitted. [Command/execution evidence](docs/artifacts/engineering-sprint/ci-execution.json). This verifies CI rejection/control flow, not fresh inference. Inherited response tokens in the replay report are not new usage. The current SourceROI counters show three manual answer-entry fields, three ambiguous items, 37 proposed tests and three protected expectations; those are automation counters, not actual edits/review decisions, independently confirmed missing tests, or time saved. Accepted/rejected/corrected suggestions remain the recorded mechanical counters, not fabricated human acts. Incorrect-diagnosis rate and user-rated diagnostic usefulness remain unmeasured.

**Pending:** real human edits, accepted/rejected/corrected suggestions, reviewer actions, missed-test confirmation, diagnostic correctness and active effort. [Three-arm template](docs/artifacts/engineering-sprint/three-arm-study-template.json) is unfilled. The logger supports all three arms and excludes automated sessions from human summaries. No human events were recorded by this sprint. No superior detection, reduced developer effort or competitive moat is established.

## F. LangGraph assessment

**Verified decision: not added.** Existing SQLite stores runs/proposals/reviews, study checkpoints and partial evidence; startup marks orphaned running jobs failed. Source/test/config hashes bind reviews; incomplete execution cannot ACCEPT. These are useful safety/history mechanisms, **not a complete durable resume engine**. Automatic restart from an exact task checkpoint without duplicated in-flight inference remains unverified and is not claimed equivalent to LangGraph.

The sprint's completed-run re-entry guard was exercised: it rejects a repeat command before generation, leaving the count at 11. [Evidence](docs/artifacts/engineering-sprint/repeat-execution-guard.json). That is not interrupted-run recovery. A LangGraph integration would require a real restart use case, exactly-once/idempotency semantics at the provider boundary and measured overhead/complexity against the current path. No demonstrated benefit justified introducing it here; no graph benchmark or zero-duplicate recovery claim was fabricated.

## G. OpenTelemetry assessment

**Verified decision: not added.** Existing per-task retrieval/model/end-to-end timings, selection traces, provider request hashes/usage, source manifests and SQLite run IDs locate the observed failures and account for inference. The actual ledger shows 15.854 of 16.375 seconds at generation HTTP boundaries; fresh evidence is supplied in the failing cases, localizing the problem beyond simple document absence. That does not isolate GPU performance or prove causal diagnosis.

No local exporter or tracing dependency was added because additional debugging value over these records was not demonstrated. OpenTelemetry improvement remains **Unverified**. No external telemetry endpoint, credentials, secret/source export or observability SaaS was introduced. Raw public source/request preservation is opt-in experiment evidence, not a new default telemetry export.

## H. Snowflake / data-engineering decision

**Verified decision: no connector, account, credits, warehouse or compute.** Existing materialized CSV/JSON/JSONL ingestion and manifest-aware callback/HTTP boundaries already allow local result snapshots as documents. This is not a live warehouse integration. SQLite continues to handle the small experiment history; DuckDB is unjustified by this workload.

The [handoff](docs/ENGINEERING_SPRINT_HANDOFF.md) documents only a narrow future read-only, immutable query-result interface: result/version fingerprints, schema/column provenance, snapshot time, stable row/time changes, task relationships and frozen comparisons. Actual warehouse semantics/usefulness remain **Unverified**. No implementation claim is made.

## I. Full regression tests

**Verified:** starting **234 passed in 7.06s**; final **247 passed in 7.62s**. New focused suite: **13 passed in 0.12s**. Full command: `PYTHONPATH=workspace/.deps python -m pytest -q` with localhost permission for existing fixture servers. Local fake HTTP fixtures are deterministic test infrastructure, not counted as real Qwen validation. No extra inference runs were made for the final tests. The as-run model comparison preceded later deterministic diagnostic/guard additions; final-code model inference remains unverified.

Generic new regressions cover literal offsets/content-bound IDs, default compatibility, abbreviations/decimals/caveats, explicit fragments, non-IRS multi-predicate retrieval, competing sources, conflict preservation under target-k/character caps, pre-ranking scope exclusion/unknown metadata, third-arm automation exclusion, decimal arithmetic/provenance/ambiguity/negation/units, persisted-run CLI diagnosis and review-bound strategy changes.

## J. Preservation of all eight features

**Verified within regression scope; not eight independent customer validations:**

| Capability | Preserved mechanism and exercised evidence |
|---|---|
| Intent-aware changes | Existing intent declarations and hash-bound reviews; `test_approved_change_preserves_unrelated_expectation` |
| Evaluation proposals | Existing proposed/corrected/stale-reference workflow; `test_changed_fact_proposal_never_changes_benchmark` |
| Fact-to-agent impact | Existing source facts/dependency mapping; `test_new_content_impacts_without_history`; real IRS replay |
| Data CI / release | Existing controlled comparison/strict gates; stale-config test; actual same-output CLI BLOCK/3 |
| Diagnosis / isolated repair | Existing failure localization and isolated intervention; `test_repair_intervention_does_not_mutate_candidate`; new review-only numerical CLI |
| Longitudinal intelligence | SQLite history/review/checkpoint/timeline; `test_review_history_and_release_exports`; new experimental run IDs |
| Source valuation / ablation | Existing source/document ablations; `test_live_source_ablation_and_document_ablation`; real empty-source optimizer controls |
| Cost-aware optimization | Existing quality/budget/unknown-cost constraints; optimizer actually executed; `test_unknown_cost_cannot_win` |

No endpoint, dashboard or existing orchestration path was replaced. Optional configuration must be explicitly enabled in a newly reviewed version. Passing tests cannot certify every production integration or supported document format.

## K. Startup readiness and defensible claims

- **Failed:** meaningful RAG factual reliability improvement was not demonstrated. Fresh supported accuracy stays 1/3; numerical proposals improve inspectable diagnosis, not model correctness.
- **Preliminary:** smaller context preserves the observed single correct answer and reduces usage. **Failed:** the fixed absolute quality rule; **Unverified:** independent quality-preserving optimization.
- **Pending:** semantic and citation reliability, independently labeled held-out tasks, genuine source-owner authorization and external customer-stack evaluation.
- **Verified:** tie on the recorded unsafe-update detection. **Unverified:** reduced human work, more correct diagnoses, maintenance advantage or superior economics relative to maintained A/B.
- **Verified engineering scope:** implemented opt-in provenance-bound passage retrieval, fail-closed conflict-budget handling, source-bound arithmetic diagnosis, a three-arm study logger, repeat-run guard, CI replay rejection, and 247 passing regression tests. No framework benefit is claimed because no framework was added.
- **Defensible resume wording:** “Implemented provenance-bound passage retrieval and review-only numeric diagnostics in a local AI knowledge-change assurance beta; validated strict release rejection and 247 regression tests. Measured a 52.6% token reduction in a small real-document development experiment, which failed absolute answer-quality requirements.” Do not shorten the latter into quality-preserving savings, independent validation or production/customer impact.
- **Preliminary demo readiness:** a controlled technical demo can show real negative answers, traceable sources, review proposals and BLOCK/REVIEW behavior. **Unverified:** unattended production readiness, product-market fit or commercial differentiation.

Next priorities are independent source-owner labels/reviews on fresh document families, a reliable reference answering configuration with predicate/period binding validated beyond these exposed cases, and a preregistered human three-arm maintenance study. A larger inference experiment needs separate size/budget approval; none was silently launched while the user was away.

### Reproduction and evidence boundaries

[Prepare/run tool](tools/validate_engineering_sprint.py), [no-inference analysis](tools/analyze_engineering_sprint.py), [numerical replay](tools/replay_numeric_diagnosis.py), [summary](docs/artifacts/engineering-sprint/summary.json), [handoff](docs/ENGINEERING_SPRINT_HANDOFF.md), and [integrity manifest](docs/artifacts/engineering-sprint/final-integrity.json). Existing destinations are immutable; scripts refuse to rerun model experiments over them. Replay has zero new usage. Generic tests, exposed development labels, real local generation, post-experiment repair proposals, and pending independent evaluation are separate evidence classes. Historical unfavorable results and original labels were preserved.
