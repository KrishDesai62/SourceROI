# SourceROI implementation audit and validation

Audit date: November 12, 2026. This report describes executed local tests and synthetic integration evidence. No external-provider credentials were available. No paid model calls were made. No real-world model savings or production readiness are claimed.

## A. What was already working

The original suite passed 26 tests before implementation changes, after allowing its localhost fake-model HTTP server to bind. It covers actual HTTP adapter execution against a simulator, source/document exclusion, provider-shaped usage parsing, configured-price arithmetic, corpus regression comparisons, path protection, API evaluation jobs, and basic optimization. Those tests establish integration behavior, not paid-provider performance.

Source and document exclusions filter the corpus before lexical retrieval. End-to-end latency uses a monotonic wall clock. Expected benchmark answers are scored locally and are not included in model/agent requests. Remote endpoints require HTTPS, credentials are read from environment variables, and ordinary evaluation history uses local SQLite.

## B. Bugs and misleading claims discovered

- Missing costs were coerced to zero in objective scoring, allowing unpriced configurations to look cheapest.
- The token objective used prompt tokens alone; missing token values could become zero.
- Aggregate quality floors could accept newly incorrect tasks.
- Citation format validity was labeled groundedness. It does not establish semantic support.
- The optimizer's candidate limit did not reliably limit evaluations, and its search/diagnostics could exceed run call budgets.
- Search did not reserve held-out tasks or compare simple retrieval/source heuristics.
- Missing external data costs became zero, hiding incomplete accounting.
- Optimization GET requests could initiate charged calls; CLI optimization lacked the ordinary run acknowledgment.
- The no-valid-candidate CLI report could reference a missing accuracy field.
- Numeric prices accepted nonfinite values and booleans; reported token validation accepted booleans or negative values.
- Missing-information diagnostics described repair after removing a source as evidence of missing information, although it suggests possible interference.
- Configuration hashes depended on JSON formatting, and data-only regression identity omitted new context controls.

The pasted optimization table from the earlier conversation is not a verified artifact in this repository. It is not reproduced as an externally measured result.

## C. Implemented changes

`live/validation.py` now conducts bounded source-subset experiments with development-only selection. Task splits are explicit or derived deterministically from task IDs. Selection is frozen before held-out evaluation; held-out scores cannot restart the search. Benchmarks smaller than four tasks without explicit splits remain development-only.

Four configurations are reported: original, reduced top-k, fixed source-drop (highest configured source charge first), and SourceROI. The search executes actual adapter calls for each evaluated subset and captures interactions within those subsets. It is bounded subset enumeration, not a global optimum or complete causal attribution method.

Every qualifying candidate must meet accuracy and citation validity thresholds and, by default, introduce no task regressions. Missing costs/tokens cannot win their corresponding objectives. Reports contain repeat-level runs, paired comparisons, category changes, input/output/total usage, mean/median/p95 wall time, source coverage, cost per task/success, hashes, uncertainty, invalid experiments, and deployment status. Semantic groundedness and unsupported claims remain explicitly unmeasured/null.

The deployment gate rejects held-out quality failures. Evidence without sufficient uncertainty bounds or declared real-provider provenance requires further testing. Wilson regression bounds count distinct tasks, not repetitions as independent observations. A collapsed bootstrap interval on a small sample is explicitly not proof of equivalence.

Built-in RAG supports source/document/passage filtering, configurable top-k, a character context budget, and exact normalized-text deduplication. These controls change submitted context; they are not approximate token savings reported as measurements. External adapters retain their existing source/document contract and explicitly reject unsupported passage/context controls. External top-k comparisons are marked unsupported.

Call limits cover optimization and validation together. Cost guards run after each returned call. Failed optimization reports retain completed experiment evidence in SQLite. API optimization uses POST with acknowledgment, validates bounded inputs, and shares the evaluation semaphore. CLI optimization also requires acknowledgment and persists history. Configuration hashing is canonical, and invalid numeric usage/prices are rejected or marked unavailable.

## D. Reproduction and tests

```bash
# All tests; integration fixtures need permission to bind localhost.
python -m pytest -q

# Focused validation tests, no network or paid calls.
python -m pytest tests/test_validation.py -q

# Reproduce the explicitly synthetic four-way report.
python tools/validate_local.py --output docs/artifacts/local-validation.json

# Inspect the supported CLI.
python -m sourceroi optimize --help

# Real configured workspace; intentionally acknowledges possible charges.
python -m sourceroi --project myworkspace optimize --quality-floor 0.9 --objective cost_per_success --max-candidates 8 --repeats 2 --allow-model-calls --json
```

Before changes: 26 passed with localhost access. After changes: 46 passed, including 20 new validation tests. The first sandboxed test attempt produced 15 passes and 11 localhost binding setup errors; rerunning with localhost permission resolved those environment errors.

## E. Actual local execution results — synthetic adapter only

Artifact: [local-validation.json](artifacts/local-validation.json). The workflow executed 40 adapter calls: two repetitions of development search/baselines and held-out comparisons. Each split contains two tasks. Questions are intentionally repeated to test integration mechanics; this fixture does not establish semantic generalization or independent statistical evidence.

The table shows the first held-out repetition, summed over its two tasks. Counts, prices, source fees and answers are simulated. Wall time is measured local execution time and is unsuitable for real-model latency claims.

| Configuration | Correct | Accuracy | Input | Output | Total tokens | Simulated total USD |
|---|---:|---:|---:|---:|---:|---:|
| Original | 2/2 | 1.00 | 250 | 20 | 270 | 0.08058 |
| Reduced top-k | 2/2 | 1.00 | 200 | 20 | 220 | 0.06048 |
| Fixed source-drop | 0/2 | 0.00 | 200 | 20 | 220 | 0.02048 |
| SourceROI (exclude noise) | 2/2 | 1.00 | 200 | 20 | 220 | 0.06048 |

Both repetitions preserve these synthetic correctness/usage/cost results. Local timings vary and are included in the artifact alongside median and p95 values. SourceROI ties top-k on this fixture. Fixed source-drop is cheaper but fails every task, so it fails the quality gate. There is no evidence here of superiority over a quality-preserving top-k baseline or of actual provider/customer savings.

Deployment verdict: `requires_further_testing`. No production configuration was changed.

## F. Remaining incomplete

- Real-provider and external design-partner validation, provider invoices, and representative held-out generalization evidence.
- Semantic groundedness, unsupported-claim grading, and richer task-criticality/category-specific policies.
- Approximate semantic deduplication, adaptive per-task retrieval policies, exhaustive interactions, and document/passage contribution search.
- External-agent top-k, passage and context-budget capabilities; an extended validated adapter contract is required.
- A hard monetary cap: one in-flight call can exceed the post-call cost guard. Use a provider-enforced cap when required.
- Automatic retries: calls fail on rate limits/timeouts rather than risking duplicate charges or agent side effects. No automatic resumable retry workflow exists.
- Partial task-level progress inside an interrupted variant; completed variants are retained, but an incomplete variant is not represented as a valid completed experiment.
- Concurrency protection across multiple server processes, hosted authentication, multitenancy, encryption at rest, security review, and production load testing.
- A dedicated dashboard optimization form; the CLI and POST API expose the workflow, and history stores its report.

## G. Design-partner readiness

Ready for controlled local pilots with representative tasks, independent ground truth, verified adapter filtering, explicit pricing, and human review. Not validated for unattended production changes, broad arbitrary-agent optimization, or claims of real-world superiority. The next proof is a representative external-provider experiment that preserves held-out quality and beats a meaningful quality-preserving heuristic under a deliberately bounded spend.


## Correction to earlier integration scope

The earlier out-of-scope cross-project bridge, tests and artifacts have been removed from SourceROI. They do not count as standalone product evidence. No separate application files were modified.

## Standalone task-aware study completion — no spending

The standalone workflow now lives in `live/study.py`, `live/policies.py` and `live/grounding.py`. It does not access the Equity Research project. Optional cross-project tests skip unless explicitly configured.

Implemented: question-only task classification; development-fitted policy routing; coverage/redundancy-aware passage selection; bounded source subsets; development tuning of stronger top-k/context-budget/threshold/cheapest/task-aware baselines; grouped splits; frozen held-out evaluation; human claim-based semantic grounding scores; grouped bootstrap objective intervals; p95 objective support; descriptive Pareto reporting; CLI/API/dashboard integration; and JSON/CSV/Markdown/review exports. Paid remote study execution requires a separate explicit spending approval. None was provided or used.

Semantic support is adjudicated by an identified reviewer, not inferred from citation frequency. Reviews must cover every answer claim and refer to actually cited supplied evidence. Scores are bound to exact question/answer/context hashes. Unsupported/contradicted claims are counted. Without completed reviews, scores remain null and the default grounding gate is inconclusive.

The reproducible standalone synthetic study executed 328 adapter invocations, with two development and two held-out fictional company groups, two tasks per company, and two repetitions. In each held-out repetition all tuned policies achieved 4/4 task correctness. Simulated total tokens: original 452; top-k 396; context budget 316; threshold 396; cheapest 396; simple task-aware 330; SourceROI 290. No genuine LLM inference, independent human review or paid API calls occurred. Grounding remains unreviewed. These results verify mechanics and do not establish real-model superiority. Collapsed bootstrap intervals on deterministic, structurally similar fixture groups do not prove generalization.

Executed commands:

```bash
python -m pytest -q
python -m pytest tests/test_study.py -q
python tools/validate_study.py --output docs/artifacts/standalone-study.json
python -m sourceroi study --help
node --check sourceroi/live/web/app.js
```

Final suite: 71 passed, 3 skipped (optional separate-project integration). Focused standalone study suite: 25 passed. Browser interaction was not automated; JavaScript syntax and API integration were checked. [Full standalone setup, evidence and limitations](STANDALONE_STUDY.md).

Still unproven: representative independently reviewed benchmark performance, real generation-model token/cost reductions and differentiation beyond strong simple baselines. No provider credentials or installed generation model were available, and the user explicitly prohibited spending. Those external evidence requirements cannot honestly be marked complete by generating synthetic labels or outputs. No production retrieval was deployed.


## Public-document MVP phase — November 12, 2026

[Complete implementation, evidence and setup report](MVP_VALIDATION.md).

Downloaded free, published SQuAD 2.0 and HotpotQA records and imported an immutable 8-task/44-document workspace with original answer/evidence annotations, article-family isolation, attribution, CC BY-SA 4.0 data-license links and SHA256 manifests. No ground truth was generated by the evaluated model. Snapshot tampering is rejected. The new QA grader accepts published answer alternatives.

The real-document retrieval audit used four development and four held-out tasks. Every frozen baseline and the SourceROI retrieval proxy included all annotated supporting quotes for 3/4 held-out tasks (mean quote coverage 0.85). Context characters: original 10,078; top-k 7,566; context-budget 6,854; threshold 5,111; simple task-aware 7,566; cheapest 7,566; SourceROI proxy 6,854. Threshold used less context than SourceROI at equal quote coverage. No token, cost, answer-quality or semantic-grounding advantage was established.

The separate public-document/mock-chat end-to-end workflow made 160 localhost mock requests, returned deliberate abstentions, and reported no fabricated usage. Held-out answer accuracy was 0/4 for every policy; token/cost/grounding metrics were unavailable. Its rejection verdict reflects failure of the configured quality floor, not measured regression of a capable model. Real-provider evaluation remains pending: no provider credentials were configured, and no spending was authorized or incurred.

Added exact v2 restriction/control acknowledgments, a domain-neutral lexical reference agent, effective configuration hashes, reported model identity/drift validation, incomplete-response handling, partial-task retention, SQLite checkpoints, structured content-free progress logs, and actionable offline proposals using the requested three deployment-testing verdicts. Source/document exposure counts remain observational; controlled contribution estimates still require ablations. Studies now repeat development only and evaluate each frozen policy once on held-out tasks.

Removed all earlier out-of-scope cross-project bridge/test/artifact files. SourceROI neither imports nor depends on another application. Existing historical test counts above describe prior phases, not current dependencies.

Final verification: **91 passed** with `python -m pytest -q`; new public/MVP suite **20 passed**. `node --check sourceroi/live/web/app.js` passed. The complete local HTTP v2 reference-agent contract, model protocol, persistence, export and quality gates were executed without paid inference. Browser behavior was not automated.

The product is ready for a controlled local technical pilot, not claims of validated real-model optimization or production SaaS readiness. The next evidence step is a frozen held-out run against a genuinely free local generation model with independent answer/claim review.


## Genuine local generation phase — November 13, 2026

The user explicitly approved the approximately 1.12 GB model and 17 MB runtime download. Installed pinned, checksum-verified **Qwen2.5-1.5B-Instruct Q4_K_M** and **llama.cpp b12345** under `workspace/.local-llm/`, and ran inference only on localhost on the 24 GiB Apple Silicon machine. No commercial credentials, paid APIs, cloud inference or billable free credits were used. The server was stopped after the completed run.

Expanded published evaluation to **96 tasks and 496 unchanged documents**, with 48 development and 48 held-out questions and 36 document groups per split. All article families from the previously exposed eight-task benchmark were excluded. Published answers/evidence/alternatives and licensing were retained; no model-generated ground truth was used. The original eight-task benchmark was not modified.

Found and fixed an ingestion defect: original article titles in provenance had been replaced by hashed filenames in retrieval/prompt metadata. Restored titles uniformly across every strategy. Added numbered citation aliases, mapped to canonical citations, uniformly across the local model comparison. Added true context tokenization with llama.cpp, local-only credential isolation, pinned environment/setup scripts, focused held-out review exports, and a stronger recommendation gate requiring benefits over a qualified simple baseline rather than only the original.

**Completed genuine experiment:** 1,920 generation calls, 47.79 minutes. On 48 held-out questions, original and qualified tuned top-k achieved **22 correct**, with **42,728 total tokens**. SourceROI achieved **21 correct**, with **28,532 total tokens** (33.22% lower), but newly failed **four** original successes and recovered three failures. The no-regression gate rejected it. Median latency was 1,125.88 ms versus 1,359.96 ms original; these are measured localhost times, not universal speed claims. Grouped accuracy delta CI was [-12.77,+8.33] percentage points, so no equivalence or universal accuracy decrease is established. The observed task failures are enough to fail the strict gate.

Threshold filtering scored 21/48 with 40,870 tokens. The simple task-aware fallback scored 21/48 with 16,958 tokens. The latter and context-budget fallback were **not qualifying development configurations**, so they must not be presented as strong quality-preserving comparators. A tuner defect had selected the lowest-token failed setting when a baseline family was infeasible. Fixed this for **future runs** by selecting best measured development quality and explicitly marking infeasible families. The completed experiment was not retuned/rerun on its exposed held-out results, and its exact pre-correction source code is archived.

Groundedness is **pending human review**. SourceROI returned reference-correct answers on three tasks with no retrieved context; correctness alone therefore does not prove evidence support. No monetary model/API pricing was simulated. External API expenditure was zero; hardware/electricity cost is unmeasured.

Verification: `python -m pytest -q` → **98 passed**; `python -m pytest tests/test_local_validation.py -q` → **7 passed**. JavaScript syntax and completed-artifact integrity checks passed. The tests do not secretly rerun the genuine held-out benchmark. [Full measurements, exact setup, caveats and artifacts](LOCAL_LLM_VALIDATION.md).

**Answer to the product hypothesis:** this experiment did not demonstrate better information efficiency while preserving answer quality over strong simple retrieval. The evaluation, source controls, regression gate and reproducible reporting worked; the current optimizer's differentiation remains unproven. Further optimizer changes need fresh document-disjoint held-out data and independently reviewed grounding, not reuse of these exposed failures as untouched validation.


## Reliability-first follow-up — November 13, 2026

Implemented evidence-aware task/source selection, conservative fallback, exact local context-token budgets, frozen-source Data CI, failure diagnosis, temporary repair verification, and bounded CLI/API/dashboard workflows. No changes to Equity Research or other projects were made.

Reused the approved local model/runtime. The complete session made 283 generation calls in 354.75 seconds, within the 320-call/900-second limits; maximum measured model RSS was approximately 1.86 GiB against an 8 GiB guard. External API spend was $0. The server was stopped afterward.

A fresh 24-task, 126-document benchmark used 12 development and 12 held-out questions, with nine article groups per split and prior exposed article families excluded. Held-out original and guarded evidence selection each scored 5/12 with 9,969 total tokens. Fallback ran on all questions and saved no tokens. The qualified simple task-aware strategy scored 5/12 with 5,893 tokens (40.89% fewer), without losing any original successes. Unguarded evidence selection scored 5/12 but lost one original success and recovered another. The fixed previous optimizer scored 6/12 with 7,405 tokens but failed fresh development qualification; this mixed result does not justify promotion after inspecting held-out results. No new optimizer advantage is demonstrated.

A separate four-task, previously exposed source-removal control preserved all answers while losing one annotated reference. Data CI blocked the change, localized the removed document, and model-tested a temporary rollback that restored reference coverage. An ordinary reference-coverage comparator also detected the loss: superiority over that stronger check is not claimed. The source-ablation comparator affected two tasks, showing the narrower scope of the localized intervention. These controls are not fresh held-out evidence or production repair.

Final verification: `python -m pytest -q` → **123 passed**. JavaScript syntax checks passed. Published answer labels remain unchanged; independent semantic groundedness review and representative customer validation remain incomplete. The credible pilot feature is source-version-aware regression diagnosis and repair verification, not a proven uniquely efficient optimizer or production SaaS.

[Full A–H implementation/evidence report](RELIABILITY_VALIDATION.md), [seven-case root analysis](SOURCE_FAILURE_ANALYSIS.md), and linked machine-readable artifacts document scope, uncertainty, raw reports and post-run metadata corrections.


## Knowledge change intelligence and release assurance — November 13, 2026

[Full A–I report and eight-feature status matrix](KNOWLEDGE_CHANGE_ASSURANCE.md), [repository audit](KNOWLEDGE_ASSURANCE_AUDIT.md), [verified competitive-documentation comparison](KNOWLEDGE_ASSURANCE_COMPETITIVE.md).

Verified the starting suite: **123 passed in 6.50 seconds** with localhost permissions. The default restricted sandbox had blocked the mock HTTP listeners; those initial failures were environmental. This directory contains no Git repository metadata, so no Git diff/commit evidence is claimed.

Added hashed knowledge/fact/change proposals, explicit named review and replacement evidence, immutable expectation overlays, annotation/history/topic impact mapping, paired local release checks with ACCEPT/BLOCK/REVIEW/INCONCLUSIVE, proposal/review/release history, diagnostic reuse, isolated reviewed repair verification, task/version-specific source recommendations, CLI/API/dashboard controls and JSON/Markdown exports. Existing ablations, attribution, Data CI, rollback, provider accounting and optimizer remain available. Registered original labels are unchanged; unapproved suggestions do not become truth. No production deployment or source changes are automated.

**Final verification:** `python -m pytest -q` → **149 passed in 6.27 seconds**. New `tests/test_assurance.py` suite → **26 passed** in its focused execution. `node --check sourceroi/live/web/app.js` and `sh -n examples/ci/knowledge-release.sh` passed. The final local callback demo executed four task requests and returned ACCEPT. New UI interactions were not browser-automated; actual external customer RAG compatibility remains unverified.

**Authored deterministic comparison:** 13 exposed scenarios, eight blocking / three legitimate / two ambiguous. SourceROI blocked 8/8, false-blocked 0/3 and returned REVIEW on both ambiguous cases. Ordinary answer regression and full old-label rerun blocked 6/8 and falsely blocked 2/3 legitimate updates. Reference coverage blocked all 8/8 too, while falsely blocking 2/3 legitimate updates against stale references. Reference-only task selection blocked 3/8 with 22 equivalent task executions; SourceROI and full-suite baselines used 54. No safe call reduction was demonstrated. A/B/C/D reused paired outputs; total actual callback task executions were 116 including eight for a repair. These were not LLM calls.

The explicit authored review decisions supplied to SourceROI explain its legitimate-update distinction. Human-maintained baselines could obtain equivalent decisions; no industry superiority is proven. Five answer suggestions included three matching authored decisions, one known wrong proposal and one unknown-intent proposal. Seven eligible constructed source-localization cases matched at top-1/top-3; one isolated repair restored the fixture suite. These tiny authored controls do not establish independent real-world rates, semantic grounding, review labor savings or unseen held-out generalization. No independent final split was fabricated.

**Genuine local model smoke:** reused installed Qwen/llama.cpp, zero downloads/spend/commercial credentials. Four calls under a predeclared four-call/60-second limit completed in 1.592846 seconds, consuming 848 reported tokens. The intended return answer changed 30→14, but the unchanged warranty answer was returned as a numeric-valued JSON object retained as raw text by the parser; exact grading failed before and after. Verdict BLOCK, a required preexisting format/scoring failure, not a proven new warranty regression. Raw outputs remain archived. No favorable rerun or gold-label patch was made; the local server was stopped. Later deterministic hardening was not retrospectively described as the smoke's as-executed code.

Commercial readiness: a controlled local developer pilot can exercise the complete review-bound update workflow. All eight features remain in scope, with partial/unimplemented areas identified in the matrix. Independent policy-owner annotation, fresh disjoint final tasks, semantic/citation review, authenticated approvals, external knowledge-version attestation, production hardening and measured customer effort/recall remain unfinished. Strongest current value is coherent review-bound change/evaluation/release evidence, not exclusive detection, autonomous label correctness or optimizer superiority.


## Validation and differentiation sprint — November 13, 2026

[Full sprint report](VALIDATION_DIFFERENTIATION_SPRINT.md) and [asserted machine-readable summary](artifacts/validation-sprint-summary.json).

Verified the actual starting suite: **149 passed in 6.88 seconds**. Final `python -m pytest -q` with localhost access: **183 passed in 6.69 seconds**. Focused `tests/test_validation_sprint.py`: **34 passed in 0.26 seconds**. JavaScript syntax and Python compilation checks passed. No browser automation was added. Existing CLI/API/dashboard/history/benchmarks and all eight feature families remain operational under the regression suite.

Fixed supported scalar response normalization: nonempty strings, finite JSON numbers and booleans; no bool-to-yes/no or truth-changing coercion. Duplicate keys, unknown answer-object fields, nonfinite values, null/container answers and malformed citations remain invalid/incomplete. Answer-only objects retain legacy support with empty citations, not a claim of evidence support. External completion flags are enforced. No expected labels changed.

Reused installed local Qwen/llama.cpp for a single bounded four-call/60-second follow-up. Original BLOCK artifact is unchanged. Repaired registered-check verdict ACCEPT: baseline 2/2 and reviewed candidate 2/2 versus original 1/2 and 1/2; 848 tokens in both runs; repaired elapsed 1.664400 seconds. Model settings, original labels and baseline document fingerprints matched. All four responses still lack citations. Independent semantic/citation audit remains REVIEW with zero completed reviews. The server was stopped. External spend $0; no downloads, commercial credentials, cloud or production changes.

Fair comparison gave all approaches the same authoritative answer changes, replacement evidence, protected expectations and unresolved-intent information. On 13 previously exposed authored fixtures, updated answer-only regression blocked 7/8 consequential cases; updated coverage-only checks blocked 7/8; maintained full answer-plus-evidence testing and SourceROI each blocked 8/8, false-blocked 0/3 legitimate updates, and returned REVIEW twice. Strong lexical/topic/trace/reference selection also detected all eight, missed zero authored affected-task occurrences and used 32 equivalent task executions versus 54 full-suite executions, but left three partial passing cases INCONCLUSIVE. Safe release-cost savings are not demonstrated. Per-method counts reuse paired outputs; actual combined callback task executions were 108, with zero LLM inference calls in the comparison.

Three approved revised-answer fields were prefilled, but five suggestions needed review, including one known bad protected-warranty edit and one ambiguous proposal. These are fixture-derived text-entry counts, not observed human edits or time saved. No total maintenance advantage over the properly maintained process is established.

Eleven authored semantic/citation integrity controls detect explicit unknown citations and date/jurisdiction mismatches; paraphrase and entailment scores stay unknown. A usable external annotation/freeze/review workflow rejects incomplete labels, split leakage, exposed labels, unauthorized reviewers, changed sample/source versions and invalid claim citations. No independently annotated final evaluation or human semantic judgment was fabricated. Human identity/independence remains operator-attested, not authenticated by these local tools.

Executed a separate-process record RAG application using the existing HTTP v2 adapter, optional version-digest/manifest checks and retained retrieval traces. Results: intended update ACCEPT, protected warranty failure BLOCK, unknown version rejected; 9 HTTP requests under a cap of 10/45 seconds, no model calls. Server rereads and hashes actual files; a unit test rejects an old version after source mutation. The example has no SourceROI imports/benchmark access but was authored by Codex, so it does not satisfy independently authored customer-RAG validation or arbitrary-agent compatibility. The HTTP server was stopped.

Investor assessment: coherent local review/version/release integration is implemented; detection superiority over maintained full-suite testing, semantic reliability, customer integration and net developer labor/quality/cost advantage remain unproven. Next evidence requires independent source owners/reviewers, hidden document-family-disjoint final labels, a separately maintained customer RAG backend and measured editing/review/debug effort against maintained baselines. No additional product expansion or production deployment is justified by these fixtures.


## Reliability, grounding and product differentiation — November 13, 2026

[Full A–J report](RELIABILITY_GROUNDING_SPRINT.md), [integration guide](GROUNDED_AGENT_INTEGRATION.md), [maintenance/annotation study handoff](EVALUATION_MAINTENANCE_STUDY.md), [machine-readable results](artifacts/reliability-grounding-summary.json).

Verified the actual baseline: **183 passed in 6.50 seconds**. Final `python -m pytest -q` with localhost support: **204 passed in 6.78 seconds**. New `tests/test_grounded_release.py`: **21 passed in 0.59 seconds**. JavaScript syntax and Python compilation checks passed. No browser automation or customer study was performed. Two older proposal assertions were updated for the intentional safer behavior; existing benchmark answers were not altered.

The missing-citation acceptance came from legacy answer-only parsing, unconstrained JSON output and a release engine measuring retrieved reference coverage without mandatory cited support/semantic review. Preserved legacy behavior with explicit approval scope, and added versioned strict grounded release requirements. Strict mode separates execution, intent approval, exact answer, reference coverage, citation integrity, applicability, provenance and independent review; pending semantic review cannot authorize it. CLI/API/dashboard/Markdown/history expose individual states, missing checks, blocking reasons, policy hashes and next actions. Old report verdicts were not rewritten.

Implemented citation-aware local schema generation constrained to actual retrieved IDs, with a separate abstention branch; numeric/boolean support and strict malformed-response handling remain. Cited context is checked against annotated support, actual retrieval and version; explicit scope/date/policy metadata is checked without pretending matching numbers establish entailment. Current request/prompt/schema hashes are captured. Strengthened optional external model/prompt/retrieval identity checks, required traces and version/manifest acknowledgment; legacy adapters remain supported.

**Real inference:** eight calls, 2,097 provider-reported tokens, 4.314 seconds combined experiment time, within 12 calls/120 seconds. Reused installed local Qwen/llama.cpp; no downloads, paid APIs/credits, commercial credentials, cloud or production mutation. Both server sessions stopped. Main four-answer smoke retained 2/2 baseline and 2/2 reviewed candidate exact answers while improving citations from 0/4 to 4/4 with zero invalid IDs and complete cited annotated support on candidate tasks. Tokens increased 848→1,080 (+27.36%); mean task latency 414.145→544.185 ms in these tiny nonrandomized runs. Strict verdict REVIEW, not ACCEPT: independent semantic review is absent. No explicit task scope was supplied in the original-style smoke, so no date/jurisdiction validation is claimed from its no-mismatch status.

**Negative inference evidence retained:** the same-model provisional judge said supported for both real return evidence and an unrelated warranty passage. Its judgments never became labels or release authority. The final schema's two additional controls returned “14 days” instead of the exact numeric fixture “14” and answered “14” from unrelated warranty evidence instead of abstaining. Both failures are archived without label repair or favorable reruns. Valid citation IDs therefore do not establish semantic support. No independent strict grounded ACCEPT was obtained; positive human-review unit fixtures exercise the contract, not actual human review.

Proposal guards now require declared expected/protected intent, source-linked evidence, fact/question anchors, whole numeric-token edits, authority and stable constraints for automatic prefilling. Scope/authority changes or conflicts remain ambiguous; protected expectations cannot be revised under the same declaration or bypassed through a conflicting new declaration when already protected by the benchmark. Exposed authored controls: three matching revised-answer proposals, zero incorrect revisions, zero protected expectations incorrectly targeted, three ambiguous review items. Without declared intent there are zero automatic revisions and seven ambiguous items. Eight separate authored development cases matched all eight classifications/revisions; none is independent held-out validation. This is safer suppression with additional intent input, not autonomous business-intent inference.

Equal-authority registered-check comparison still ties maintained full answer/reference testing: both detect 8/8 blocking cases, false-block 0/3 legitimate updates and return REVIEW twice, with 54 equivalent task executions. Stronger selection detects the same failures with 32 replay-equivalent executions but leaves three partial passing cases inconclusive. Staged early-rejection replay uses 38 versus 54 equivalent executions, with zero fixture misses/false blocks; no new inference was executed for the replay and a conventional runner can use the same ordering. No independent quality/cost superiority or safe passing-scope reduction is established.

Maintenance counters on authored decisions show 3 proposed/3 accepted revisions, 0 correction/additional-entry fields, 3 ambiguous items, 8 candidate new tests and 20 protected-expectation occurrences. These are automated field counters, not observed human edits or elapsed work. The new study logger excludes automation from declared-human timing and validates event order/hash chains under a file lock. A preregistered counterbalanced equal-authority study and expanded independent annotation/freeze package are ready for external operators. No participants, human time savings, independent final labels or semantic adjudications were fabricated.

Executed document-oriented HTTP RAG with current/historical/regional/warranty documents, actual lexical scoring, overlap/conflicting values and day extraction: intended candidate REVIEW, bad candidate BLOCK, ranking-identity drift rejected, unknown knowledge version rejected. Ten HTTP requests under 12/45 seconds, no model calls, server stopped. The example is Codex-authored separate-process code, not independently developed/customer validated; a dishonest server still requires trusted instrumentation. Existing callbacks/HTTP protocol and all eight feature families remain under the passing suite, including Data CI, diagnosis, isolated repair, history, dataset/document/passage ablation, valuation and optional optimization.

Startup assessment: strict safety gates and guarded maintenance are stronger than the prior code, but semantic grounding/abstention remain unreliable without independent review, maintained full-suite detection still ties, and actual human effort/customer benefit is unmeasured. Strongest current value is one review-bound source/intent/test/version/release/diagnosis workflow, not unique detection or proved ROI. Next evidence requires independent source owners, hidden document-disjoint labels, an independently maintained customer RAG integration and measured human review/correction/debug work against an equally strict baseline.


## Grounded reliability and real-world validation — November 13, 2026

[Full report](GROUNDED_RELIABILITY_REALWORLD_VALIDATION.md), [real-owner onboarding](SOURCE_OWNER_ONBOARDING.md), [audited summary](artifacts/realworld-validation-summary.json), [accounting correction](artifacts/evidence-abstention-accounting-audit.json).

Actual baseline: **204 passed in 6.88 seconds**. Final `python -m pytest -q`: **230 passed in 7.10 seconds** with localhost support. Focused `tests/test_answer_evidence_contracts.py`: **26 passed in 0.15 seconds**. JavaScript syntax/Python compilation passed. Existing interfaces, histories, benchmarks and all eight feature families remain under the suite; no unrelated project, production data or Equity Research integration was modified.

Added explicit versioned numeric/text/boolean/closed-flat-object answer contracts; preserved raw response/decoded value and normalized answer; no “14 days”→“14” unit stripping. New format gates prevent a permissive scorer from approving a wrong response type. Added owner-declared necessary alias groups, explicit scope/date exclusions and limited same-predicate numerical conflict screening. Positive terms/IDs never prove entailment. Software abstention is separate from model generation and diagnosis; strict required semantics remain reviewed/unknown without independent adjudication. Configured strict workspaces cannot use a per-run legacy downgrade; legacy tasks remain supported.

A frozen 11-case experiment separated two exposed controls from nine newly authored development cases. Raw outputs matched 6/11 authored expectations; software screen replay matched 7/11. Unsupported factual answers changed from 1/7 to 0/7, but **all four supported cases were wrongly abstained on in both pipelines**, recovering zero factual answers. The historical warranty-only failure abstained this time, but the supported numeric case also abstained. All 11 responses had no citations, so zero invalid IDs is vacuous; independent semantic accuracy remains null. These fixtures are not independent final validation or customer data. Inline probes did not execute the complete release pipeline; no strict false-acceptance rate is fabricated from them.

**Counter error:** the raw empty-context control bypassed precheck and invoked the model but was not reserved/counted by the harness. Actual generation responses were **11**, not the printed 10. This exceeded the planned 10-call experiment cap by one, while respecting the user's 12-call ceiling. The raw report/code remain preserved and a separate audit corrects the counter/incorrect row flag. Tokens across all actual responses: **4,174**; experiment elapsed **7.597 seconds**, summed model latency **7,377.81 ms**, mean **670.71 ms**. External API spend $0; hardware/electricity cost unpriced. Existing local Qwen/llama.cpp reused, no downloads, cloud, paid credits or commercial credentials. The server stopped, no further inference ran, and the remaining one-call user allowance was unused.

Final code forbids strict empty-context generation even with a cached bypass trace; future harness handles empty context before reservation. Numeric/string/yes-no prompt conflicts and synonym-group ambiguity were corrected after observation, with deterministic tests only; no model rerun was used to claim those fixes recover valid answers. As-run code was archived before inference; current code is separate. No unfavorable result or authoritative expected label was rewritten.

The maintained combined answer/reference baseline still ties SourceROI on the existing equal-authority exposed controls: 8/8 blocking cases detected, 0/3 legitimate updates falsely blocked, two REVIEW outcomes and 54 equivalent task executions. This is not independent semantic comparison. No actual cost-saving, unique detection or human maintenance benefit is established by necessary-condition screening or replay.

A no-inference onboarding tool accepts a real owner's before/after text documents, authoritative before/after labels, evidence, scope and type contracts; atomically prepares frozen baseline/candidate workspaces and intent; emits only DRAFT decisions, not an approval. It rejects invalid types/quotes/paths, protected label changes and draft rationale approval. The delivered template is unfilled. Identity/independence remain operator declarations; real owner data, hidden final labels, reviewers and human-study participants are absent. Annotation/study tooling is preserved; no user/reviewer/time-saving evidence was fabricated.

Readiness: stronger type/safety/integrity mechanics, but the as-tested local model is not reliable for supported factual answering. Strict semantic approval remains unavailable; customer compatibility and net effort/quality/cost advantage remain unproven. Next work should use real independent source-owner data and an equally strict maintained baseline to validate the final prompt/contracts and false-rejection burden, without interpreting software abstention as improved model reasoning.

## Real IRS end-to-end validation — 2026-11-13

Verified mechanics: full authoritative 2024/2025 IRS PDFs, actual local Qwen RAG through callback, frozen snapshots, explicit Codex technical intent review, strict BLOCK, real-output Data CI replay, impact mapping, diagnosis, source removal, and one top-k generation control. Four focused regression tests repair PDF navigation false-conflict screening and preserve declared numeric scoring; the final full suite passes 234 tests. Historical experiments remain unchanged.

Preliminary development-label accuracy: supported answers 1/5 baseline, 2/5 candidate. Medical regressed from 21 to model abstention despite support. Labels and technical review are Codex-authored, not independent human/source-owner approval. Strict semantic approval remains absent. Verified usage: 11 actual generations, 15,777 provider-reported tokens, 22.370 seconds, no external API spending. Local economic cost is unpriced.

Verified comparator result: maintained combined baseline BLOCK ties SourceROI BLOCK on identical recorded outputs and equivalent requirements. No unique detection or measured human maintenance benefit. Failed quality-preserving top-k control: fewer tokens, lost correct business answer. Existing optimizer declined an insufficient remaining call allocation; general optimization value remains unverified. The real model is not reliable enough for unattended factual service. Controlled technical demonstration is plausible; production/customer/startup differentiation remains unverified. Full evidence, limitations, stress controls and next priorities: [REAL_WORLD_VALIDATION_REPORT.md](../REAL_WORLD_VALIDATION_REPORT.md).

## Reliability and engineering differentiation sprint — 2026-11-13

Verified engineering: optional literal sentence indexing, query-only passage coverage, pre-ranking scope filtering, conflict-preserving context-budget abstention, source-bound review-only Decimal calculation proposals through persisted-run diagnosis, and three distinct study arms. Defaults, existing interfaces and historical evidence remain preserved. Starting suite: 234 passed; final: 247 passed. No frameworks, warehouse connector or new dependencies were added.

Preliminary real local model development results: all three policies score 1/3 supported (2/4 including software scope abstention). Top-k=3 used 4,619 tokens; top-k=1 2,385; passage coverage 2,188. The 52.6% token reduction fails the fixed absolute quality requirement: lookup still abstains and arithmetic is wrong. Post-experiment source-bound proposals 33 and 5 remain REVIEW and do not change those answers or scores. Existing source-subset optimizer ran and kept the original source set; no independently grounded quality-preserving savings are established.

Verified usage: 11 new generation attempts/responses, 11,508 reported tokens, 16.375 seconds, $0 external spending. Same-output replay gives BLOCK for maintained evaluator A, maintained evaluator B with ordinary diffs/traces, and SourceROI; actual CLI returns exit 3 with networking forbidden. No human edits/actions/time savings or independent semantic metrics were manufactured. Twelve review items remain pending, with null semantic/citation correctness. Framework and commercial differentiation remain unverified; durable interrupted-run resume is not claimed. Full results: [ENGINEERING_DIFFERENTIATION_REPORT.md](../ENGINEERING_DIFFERENTIATION_REPORT.md).

## Grounded reasoning sprint and accounting correction — 2026-11-13

Verified engineering: explicit subject/predicate/unit/period fact binding with registered-index provenance, opt-in operator-authorized lookup/add/subtract/comparisons, separate model/calculation modes, cited numerical consistency checks, deterministic-specific diagnosis, trusted existing-app callback bridge and complete CLI onboarding. Final isolated suite: 276 passed in 7.03s. Defaults and all eight capabilities remain covered.

Preliminary development result: model fixed/passage/predicate arms each 1/3 supported; explicit source calculation 3/3 and correct missing-period abstention. Three supported cases comprise two exposed IRS questions and one synthetic financial fixture. No independent semantic judgment or hidden final labels exist. Source calculation is a different algorithm, not improved Qwen reasoning or independently proven optimization. All sixteen output reviews remain pending. Maintained full-suite A/B and SourceROI tie: BLOCK on historical regression, REVIEW on calculated no-change inputs; this time all twelve/eight before/after rows are actually checked.

FAILED execution accounting: process-local harness recorded eleven requests / 9,186 reported tokens, but runtime log confirms fifteen completed generations. Four concurrent regression-test generations bypassed the observer; the twelve-call limit was exceeded. Full failed-attempt/global token totals are unknown. External spend remains $0. The server was stopped and no further inference run. Regression tests now mock unavailable providers and block the standard real-model socket. The previous engineering runtime log similarly shows nineteen generations versus eleven reported harness calls; original artifacts/reports remain unchanged. The earlier IRS runtime log agrees with eleven generations. Do not use process-local ledgers as complete all-process accounting or claim cap compliance.

Strict real release stays REVIEW without independent semantics; wrong-value mutation BLOCKs, incomplete budget is INCONCLUSIVE, and ACCEPT is only demonstrated by the existing clearly synthetic reviewer unit fixture. Customer developer effort, independent reliability, production readiness and commercial differentiation remain unverified. Full evidence/correction: [GROUNDED_REASONING_VALIDATION_REPORT.md](../GROUNDED_REASONING_VALIDATION_REPORT.md).

## Final engineering hardening — 2026-11-13

VERIFIED: starting 276 tests; final 299 passed in 13.12s. Owned fake-runtime control layer exercises private authenticated UNIX sockets, shared test/runtime exclusion, durable serialized reservations, failed/retried/denied request accounting, cancellation, owner/supervisor death, source-artifact integrity and audit-only restart. Native mode remains disabled because native server request correlation is PENDING. No new real-model runtime or generation was launched; external spend $0. Fixture tokens are simulated protocol data, not Qwen usage or cost savings.

VERIFIED fixes: model configuration preserves the user's call limit instead of raising it to 2500; callback review export supports omitted question text using the frozen canonical question; complete new handoffs bind source, benchmark and configuration, while legacy minimal exports mark absent bindings explicitly. Existing eight capabilities, CLI/API/dashboard and history remain covered.

PRELIMINARY numerical coverage: 7/9 source-supported non-IRS synthetic cases; FAILED CSV/Markdown table coverage (two false abstentions). Eight safety cases and two unsupported contracts refuse as expected, separate from supported-answer accuracy. No grammar was expanded to fit outcomes. Existing optimizer executed on one synthetic deterministic lookup with zero model calls and kept the original source set; no broad quality-preserving optimization claim.

VERIFIED packaging: a single model-free source/handoff archive was extracted and verified. It includes real historical before/after documents, twelve pending claims, an empty independent protocol/reviewer list, three-arm study instructions and existing callback/HTTP v2 integration guidance. Independent labels/reviews, actual external-app validation, human timing and commercial advantage remain PENDING. Earlier accounting failures and reports are preserved. Readiness is offline external annotation/integration preparation; bounded native-model readiness and unattended production remain unverified. See [FINAL_HARDENING_REPORT.md](../FINAL_HARDENING_REPORT.md).

## Native verification and tabular evidence — 2026-11-14

VERIFIED: 324 tests pass (10.19s), including 25 focused table/native tests. Opt-in raw table indexing adds CSV header/row and wide-period binding, Markdown value headers, exact cell/header spans, raw-byte hashes and versioned citations. Legacy CSV behavior stays unchanged by default. Config-aware impact/diagnosis, numerical checks, Data CI and isolated repair were exercised. Correct table calculations remain REVIEW without independent semantics; wrong candidate data BLOCKs, and joint repair stays INCONCLUSIVE until full approval. No production source was changed.

PRELIMINARY: identical frozen authored development cases improve supported answers from 7/9 to 9/9, false abstentions from two to zero; eight safety refusals and two unsupported-contract rejections remain unchanged. This is not independent generalization or quality-preserving token optimization.

PENDING native accounting: the approved runtime/archive matches its existing manifest, but actual native request/response correlation is not established. The pinned source's HTTP logger registration is commented out. New deterministic native auditing does not call timing records confirmed completions or accept matching counts as proof. No live startup/smoke was launched; zero new real model calls and $0 external spend. Historical accounting failures remain untouched.

VERIFIED packaging: external kit v2 was extracted, hash-verified and exercised through synthetic CSV import/configure/freeze/source-calculation without internal code changes or provider dispatch. Original packages/manifests are preserved. Genuine external apps, owner-established hidden labels, semantic reviewers and human three-arm results remain PENDING. Full evidence: [NATIVE_TABLE_VALIDATION_REPORT.md](../NATIVE_TABLE_VALIDATION_REPORT.md).


## Production-oriented local beta — 2026-11-14

VERIFIED engineering: baseline 324/324 tests; final 344/344 in 9.79s; 20 new security/storage/readiness/replay checks. Added measured API body/deadline and exact Host/Origin boundaries, bounded history pagination, truthful readiness, external SQLite symlink rejection/rollback and tested database backup/restore, legacy path confinement and parser prechecks. Existing eight pillars, CLI/API/dashboard/history and strict release checks remain covered. No paid services, runtime download, production modification or real generation.

PRELIMINARY evidence remains 9/9 exposed supported calculation cases; safety 8/8 and unsupported refusals 2/2. External v2's 19 registered handoff files verify against its frozen source; the archive is historical and is not the newly hardened service code. No independent customer or participant was invented. The maintained evaluator still ties observed release detection. Native correlation is PENDING and owned live execution remains disabled.

PENDING deployment: authenticated multi-user approvals/tenancy, isolated hostile parsers, durable multi-process/idempotent jobs, complete pinned clean installation and dependency security audit, full-workspace recovery and independent app/semantic/held-out/customer validation. python-docx is declared but absent in the tested environment; DOCX execution was not validated. Technical replay is available; controlled local beta is conditional; public production is not ready. See [production report](../PRODUCTION_READINESS_REPORT.md), [investor evidence](../INVESTOR_EVIDENCE.md), [pilot onboarding](../PILOT_ONBOARDING.md) and [operations](PILOT_OPERATIONS.md).


## Investor demo / external pilot acceptance — 2026-11-14

VERIFIED engineering: two isolated Python3.13/macOS arm64 venvs, a 27-dependency hashed wheel closure plus installed SourceROI wheel, offline installation/pip consistency and installed-file checks. DOCX/PDF/text parser smoke passes in the new environment, resolving that environment prerequisite without rewriting earlier limitations. Canonical suite 349/349 (9.44s), extracted source contract/security/package/HTTP tests 31/31 (1.00s). Source packaging includes tools/examples/evidence; canonical pytest discovery avoids duplicate extracted tests. The immutable synthetic replay is preserved, and fresh verification executes existing evaluation/ablation, modeled selection, intent/impact/review, Data CI/diagnosis/isolated repair and callback release workflows. Correct strict fixture REVIEW, protected regression BLOCK, repaired joint outcome INCONCLUSIVE. Independent semantic review is not fabricated.

VERIFIED handoff: platform-specific offline pilot distribution, exact developer commands, unchanged v2 evaluation archive verified with its frozen source, pending review packets and equal three-arm automation-only logging (no human time inferred). Codex-operated internal checks are not independent adoption. Offline advisory database unavailable; online vulnerability/security checks PENDING. Native correlation remains PENDING, live gate unchanged, actual new model calls 0, external spending $0.

PRELIMINARY controlled local pilot usability; PENDING actual external application, source owner/held-out labels, independent semantic/customer outcomes and production operations. Maintained conventional detection still ties; no competitive advantage or quality-preserving savings claim. Latest reports: CLEAN_INSTALL_REPORT.md, PILOT_ACCEPTANCE_REPORT.md, INVESTOR_DEMO_VERIFICATION.md, PRODUCTION_BLOCKERS.md and FIRST_EXTERNAL_DEVELOPER.md at repository root. Earlier adverse results/reports remain immutable.
