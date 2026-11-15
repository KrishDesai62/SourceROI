# SourceROI grounded reasoning, reliability and readiness

2026-11-13 America/Chicago. Incremental standalone SourceROI changes; no paid services, downloads, commercial credentials or production mutations.

**Observed improvement, development scope:** explicit source-calculation mode answered **3/3 supported questions correctly**, versus **1/3** for all three local-model retrieval configurations, and correctly abstained on the missing-period question. Its source quotes, operands, units, periods and formula are retained. This is a separately enabled deterministic answering mode, not improved Qwen reasoning or independent semantic validation.

**Execution constraint failure:** the experiment harness captured **11 generation attempts**, but the server log confirms **15 completed generations**. Concurrent regression tests bypassed the process-local observer and made four additional generations. The twelve-call limit was exceeded. Full failed-attempt and token accounting outside the harness is unavailable. The server was stopped, the test was repaired, and regression isolation was added. No additional inference was performed. See [accounting audit](docs/artifacts/grounded-reasoning/generation-accounting-audit.json). No budget-compliance or complete global-usage claim is made.

**Independent reliability, hidden final evaluation, genuine customer adoption and human maintenance savings remain PENDING.** Maintained conventional workflows still tie SourceROI on release outcomes.

Classification: **Verified** = observed mechanism/count; **Preliminary** = small development-label result; **Failed** = unmet objective/constraint; **Pending / Unverified** = missing independent evidence. Verified computation is not independent semantic truth.

## A. Repository audit

**Verified:** starting full suite **247 passed in 7.88s**. Existing ingestion, fixed/sentence indexing, BM25, passage selection, metadata filtering, local provider/schema parsing, quote/reference coverage, human claim adjudication, intent/proposal/impact workflow, strict release, source/document ablation, quality-constrained optimization, isolated repair and SQLite history were inspected. CLI/FastAPI/dashboard and their regression coverage remain in place.

Historical real IRS questions had relevant literal support but wrong numerical answers and a supported false abstention. The earlier engineering experiment's 1/3 supported accuracy and 4,619 / 2,385 / 2,188 per-configuration token totals are supported by its captured responses. The 33/5 diagnostic proposals were implemented after that inference, and remain historical proposals rather than observed model improvements. Prior raw sources, responses, labels, reports and archives are unchanged.

**Failed historical accounting claim, corrected separately:** the earlier engineering report's eleven calls describe its process-local harness; its preserved runtime log shows **19 generations**, not eleven. The earlier IRS end-to-end runtime log shows eleven and agrees with its ledger. Older reports are preserved; this correction does not invent missing raw responses, provider usage or paid costs. The previous three-arm artifact also labeled conventional checks as twelve task executions although that checker inspected six candidate rows. This sprint's [full-suite audit](docs/artifacts/grounded-reasoning/maintained-full-suite-audit.json) actually checks all before/after rows for A/B and records the correction.

**Preliminary failure localization:** complete support in retrieval and valid output shape rule out simple evidence absence and formatting as sufficient explanations for the exposed depreciation failures. Necessary-evidence screens allowed generation. The model itself returned IE or the wrong arithmetic value. A list of several years/amounts in one sentence remains a reasoning/selection hazard even with smaller context. These observations do not prove the internal reason the model refused or chose a particular number. Literal IDs/quote matches do not establish correct predicate/period association or entailment.

## B. Implemented engineering fixes

**Verified — optional and backward compatible:**

- [facts.py](sourceroi/live/facts.py) implements conservative literal binding for declared **subject + predicate + unit + period**. Supported forms include `SUBJECT PREDICATE is NUMBER UNIT for PERIOD` (including contiguous period/value lists) and `SUBJECT PREDICATE for PERIOD is NUMBER UNIT`. It does not scan arbitrary numerical tails or infer values from an unrelated paragraph.
- Each fact retains source/document/version, passage ID, exact quote and original-document offsets, quote/passage hashes, value/unit/period, subject/predicate, authority, effective dates, jurisdiction/policy scope, applicability state and conflict/ambiguity information. Calculations rebind supplied context against the actual registered index, rather than trusting a recomputed span ID alone.
- The `predicate` retrieval policy uses explicit production task contracts and metadata, never expected answers or annotated gold quotes. All matching/conflicting candidates are retained; missing/ambiguous support and insufficient context budgets fail closed. The default fixed and passage paths remain available.
- `settings.answering_mode: source_calculation` enables a **separate non-LLM path** only with the built-in sentence index. Per-task `calculation_contract` and `calculation_authorization` bind question, scope and operation; the operator configures `calculation_reviewers`. Approval is an operator assertion, not authenticated independent human review. Changing a label cannot change the calculated answer; changing the question/scope/formula invalidates authorization.
- Supported operations: lookup, two-input addition/subtraction, greater-than/less-than/equality. Decimal arithmetic retains every operand. Units must match; implicit conversion, arbitrary multi-step expressions, qualified/non-numeric assertions, unsupported grammar and ambiguous/conflicting bindings cannot silently produce an answer. Missing approval abstains. Normal model answers are never silently replaced.
- Release checks separately expose `numeric_evidence_status` using **actually cited** predicate/period-bound support. Wrong values or unrelated citations can BLOCK under an authorized numerical contract. A literal PASS does not supply independent semantics. Numeric checks become required for tasks declaring calculation contracts; strict review cannot be bypassed by deterministic arithmetic.
- Existing numerical diagnosis accepts explicit predicate contracts through the same component. Legacy subject-proximity proposals remain REVIEW-only and are explicitly labeled as weaker; they cannot be promoted into the answering path. Diagnosis distinguishes deterministic calculation/label mismatch from model-generation failure.
- [adapter.py](sourceroi/live/adapter.py) adds a trusted callback bridge requiring observed source manifests, actual index membership, completeness and explicit usage (unknown stays null). [External release CLI](tools/check_external_release.py) exports strict JSON/Markdown and exit codes without inventing app answers, citations, identities or metrics. No independent application is simulated as a customer.
- [Test isolation](tests/conftest.py) blocks the real standard localhost model socket; the unavailable-model test now explicitly mocks the provider. Fake HTTP fixtures use ephemeral ports. This guards the tested default endpoint; it is not runtime authentication or a universal cross-process billing control.

All changes reuse existing config, benchmark, ingestion, release, diagnosis, callback, CLI and persistence interfaces. No framework, database, model, dependency or service was added. Main inference uses the [pre-inference archive](docs/artifacts/grounded-reasoning/as-run-code.tar.gz). Later diagnosis labeling, operand-input validation, test isolation and external CLI pending-review handling are deterministic follow-up fixes; [final code](docs/artifacts/grounded-reasoning/final-code.tar.gz) is archived separately. Final-code inference was not rerun.

## C. Numerical reliability: controlled execution

**Verified design:** [plan](docs/artifacts/grounded-reasoning/PLAN.md), [frozen tasks/contracts](docs/artifacts/grounded-reasoning/frozen-tasks.json), [configuration/code freeze](docs/artifacts/grounded-reasoning/freeze.json), [execution plan](docs/artifacts/grounded-reasoning/plan.json). Labels and declared operations were frozen before outputs. Operations were selected from explicit question wording, never reverse-engineered from expected values. All four configurations use the same questions, expected values and source versions. Predicate/calculation modes exploit explicit operator declarations; they are not automatic interpretation of arbitrary questions.

Sources: complete original historical 2025 IRS Notice 2025-5, with [existing provenance](workspace/irs-e2e/raw/provenance.json), plus a file explicitly headed **Synthetic engineering fixture, not a real company report**. Two IRS supported questions are exposed development material; the financial case is a newly authored synthetic development example; missing 2027 evidence is a development negative. No hidden independent final set exists.

The model remains existing Qwen2.5-1.5B-Instruct Q4_K_M / llama.cpp b12345: localhost, seed 1729, temperature 0, context 4096, one slot, four threads, maximum output 384, prompt cache disabled for harness requests. Raw request JSON preserves exact prompts/schemas/settings. Default fixed chunks use 1,100 characters / 150 overlap; other arms use the existing sentence index. The financial fixture supplies quarterly values; it is not an external financial-services validation.

**Preliminary — frozen source-derived development labels:**

| Question | Expected | Fixed BM25 model | Passage model | Predicate model | Source calculation |
|---|---:|---:|---:|---:|---:|
| Depreciation portion, 2025 | 33 | IE | IE | IE | 33 |
| 2025 depreciation minus 2023 | 5 | 4 | 7 | 7 | 5 |
| Synthetic ExampleCo revenue Q2 minus Q1 | 140 | 140 | 140 | 140 | 140 |
| Depreciation portion, unsupported 2027 | IE | IE | IE | IE | IE |

IE means `INSUFFICIENT_EVIDENCE`. Model arms: supported **1/3**, lookup **0/1**, arithmetic **1/2**. Calculation arm: supported **3/3**, lookup **1/1**, arithmetic **2/2**. This improvement was observed in the frozen explicit answering mode, **not** merely proposed after inference. All calculation values and quoted inputs are in [source-calculation output](docs/artifacts/grounded-reasoning/source_calculation.json); unchanged model failures are in [fixed](docs/artifacts/grounded-reasoning/fixed.json), [passage](docs/artifacts/grounded-reasoning/passage.json), and [predicate](docs/artifacts/grounded-reasoning/predicate.json).

Development supported-accuracy Wilson intervals: 1/3 approximately **6.2%–79.2%**; 3/3 approximately **43.9%–100%**. Three cases, two exposed and one synthetic, cannot establish generalization, statistical superiority or independent correctness. The two arithmetic tasks each use a declared two-value operation, not arbitrary multi-step reasoning.

**Failed:** a credible general model-only reference was not established. Predicate context selection reduced irrelevant context but did not recover the exposed model failures. **Preliminary:** source-calculation mode qualifies under the frozen *development* criterion only for its narrow grammar/task contracts. It remains ineligible as an independently grounded production reference.

## D. Abstention results

**Preliminary:** false abstentions on supported tasks were **1/3 in every model arm, 0/3 in source calculation**. Unsupported factual assertions on the missing-period question were **0/1 in every arm**. Fixed/passage actually generated IE for the unsupported question; predicate selection abstained in software, and source calculation abstained due to the missing declared period. These are different mechanisms, not four independent model hallucination measurements.

Preflight confirms the model lookup was not blocked by alias requirements, generic conflict screening or schema failure: relevant support reached generation. It still returned IE. Calculated lookup avoids this refusal through authorized literal binding; it does not establish that the model learned to reason better. Missing, conflicting, ambiguous, negative/qualified, out-of-scope, stale, unit-mismatched, unauthorized and incorrectly typed cases are covered by synthetic deterministic tests. Their success does not calibrate a real-world false-rejection rate.

**Unverified:** a broad unsupported-answer rate, optimal abstention balance, and independent appropriateness of either model or software abstentions.

## E. Retrieval, evidence and citation quality

**Verified literal measurements:** full annotated support was retrieved on **3/3 supported tasks in every configuration**. Full cited support was **2/3 in model arms** (the false abstention cites nothing) and **3/3 in calculation mode**. Invalid citation IDs: **zero** across these four arms. Independent citation correctness and semantic grounding remain **null**.

The new numerical check reports BLOCK for the wrong passage/predicate-model depreciation calculation despite full literal reference coverage. The fixed-chunk numerical check remains REVIEW because the new binder deliberately requires the sentence index/provenance contract; it does not pretend to verify arbitrary chunks. Standard expected-answer checks still reject the fixed wrong value. A synthetic regression proves that the correct result with an unrelated valid citation BLOCKs, while correct bound numerical consistency stays separate from semantic REVIEW.

Fact extraction retains conflicting values rather than choosing by ranking. It flags qualified/negative clauses and refuses unrelated predicates, unknown requested applicability, tampered versions/spans and unsupported grammar. Scope/date checks use explicit metadata; the historical IRS notice contains older values within its current annual document, so an explicit operand period is distinct from source-level effective dates. Source-level dates do not automatically resolve every fact's temporal applicability. Non-numeric eligibility claims and complex prose remain unsupported by the numerical binder.

**Unverified:** universal fact extraction, independent entailment, paraphrase coverage, semantic conflict resolution and general numerical grounding. Input clauses, missing metadata, abbreviation/sentence boundaries and legitimate qualifications can still cause conservative false rejections.

## F. Tokens, latency and optimization

**Verified captured experiment usage, not complete global usage:**

| Path | Captured model calls | Prompt tokens | Completion tokens | Total | Supported accuracy | Mean task wall time |
|---|---:|---:|---:|---:|---:|---:|
| Fixed BM25 | 4 | 4994 | 104 | 5098 | 1/3 | 1705 ms |
| Passage model | 4 | 2427 | 102 | 2529 | 1/3 | 1020 ms |
| Predicate model | 3 | 1488 | 71 | 1559 | 1/3 | 611 ms |
| Explicit source calculation | 0 | 0 | 0 | 0 | 3/3 | 39.9 ms |

These are single ordered measurements averaging all four tasks, including software abstention. Concurrent test activity contaminated runtime contention and global usage. They are not normalized performance benchmarks. Predicate selection also avoided the unsupported-question call, so its usage difference combines context reduction and necessary-evidence abstention. No meaningful independently established quality-preservation claim follows from unchanged 1/3 model accuracy.

Calculation mode's zero model tokens is an actual separate algorithm path, not an LLM compression technique or measured paid-cost saving. Source scanning/CPU/hardware/energy cost is unpriced. Existing optimizer remains operational under the regression suite; **no further optimization search was launched**, because no independently reliable reference had been established and the global call limit was already violated.

### Accounting failure and correction

The [process-local ledger](docs/artifacts/grounded-reasoning/execution-log.json) records **11 requests, eleven response files, 9,186 provider-reported tokens, 14.009 seconds** for the experiment. All its observed requests succeeded. The [preserved server log](docs/artifacts/grounded-reasoning/local-server-as-run.log) instead shows **15 completed generations**. Four extra generation timing rows have 212 evaluated prompt/decode tokens, but cached prefixes can be omitted from those timing counters. Their raw requests/responses and complete billed/provider prompt counts were not captured. Therefore **full token usage and full actual/failed attempt count are unknown; at least fifteen completed generations are confirmed**. Do not simply add 212 to 9,186 and call it complete usage.

Summed server prompt/decode timing is approximately **13.120 seconds** for the fifteen completed generations, below 120 seconds of logged model computation. That does not rescue the **Failed twelve-call limit** or prove a complete all-process wall/attempt ledger. Concurrent full-suite execution reached the real unkeyed default model through the test that assumed an unavailable provider. A process-local monkeypatch was not a global safeguard. The old engineering server similarly shows nineteen completions against eleven reported harness requests; prior files were not rewritten.

The server was stopped immediately after audit, and no more inference was run. The unavailable-provider test now explicitly mocks failure, and an autouse socket guard blocks localhost:8788 in regression tests. Final tests passed with that guard. This prevents the observed test path, not arbitrary untrusted clients on another port. Future real experiments need a dedicated isolated runtime/producer and server-level reconciliation before claiming cap compliance. **External paid spending: $0**, throughout; local cost remains unpriced.

## G. Strict release verification

**Verified, zero-new-inference replay:**

| Condition | Observed outcome | Evidence boundary |
|---|---|---|
| Frozen calculated answers replayed with development intent review | REVIEW | Missing independent semantic/absence evidence remains unresolved |
| Explicit controlled mutation from 33 to 34 | BLOCK | Synthetic output mutation; not a new model response |
| Insufficient logical execution cap | INCONCLUSIVE | Preflight only; required tasks unexecuted |
| Required complete reviews supplied in the existing automated reviewer fixture | ACCEPT in unit fixture | Not genuine independent human approval |

[State record](docs/artifacts/grounded-reasoning/release-states.json), [REVIEW replay](docs/artifacts/grounded-reasoning/strict-review-replay.json), [controlled BLOCK](docs/artifacts/grounded-reasoning/strict-block-controlled-mutation.json), [INCONCLUSIVE](docs/artifacts/grounded-reasoning/strict-inconclusive-replay.json), [four fixture checks](docs/artifacts/grounded-reasoning/release-state-fixture-tests.txt). No real strict ACCEPT was manufactured. The current strict policy also leaves unsupported-question reference/absence coverage unresolved; correct IE alone cannot establish its semantic suitability. This conservative limitation is retained rather than silently relaxed to obtain ACCEPT.

Configured strict policy cannot be downgraded. Operator approval of a calculation formula is not independent review of the resulting claims. Changing expected labels, formula bindings, cited sources, configuration or source versions cannot silently reuse stale decisions.

## H. Fair maintained-workflow comparison

**Verified — ties in actual same-output replay:**

| Scenario | A: maintained full suite | B: same + ordinary diffs/traces | SourceROI | Rows per arm |
|---|---|---|---|---:|
| Historical real IRS regression | BLOCK | BLOCK | BLOCK | 12 |
| New calculated no-change case, missing reviews | REVIEW | REVIEW | REVIEW | 8 |

Both conventional arms now actually inspect baseline and candidate rows with equivalent approved facts, references, formula contracts, citation/scope/version/numerical checks and missing-review requirements. Baseline B receives ordinary document diffs/traces. They share deterministic primitives with SourceROI; this is not independent implementation validation.

Single replay times: historical A/B/SourceROI approximately **424 / 384 / 1481 ms**; new case **551 / 552 / 662 ms**. Different orchestration/reporting/cache work makes these exploratory system overhead observations, not normalized workload, labor or product-value estimates. SourceROI adds an integrated intent/proposal/impact/diagnosis/release record; packaging alone is not evidence of superior detection or saved review effort.

[Full audit](docs/artifacts/grounded-reasoning/maintained-full-suite-audit.json) records twelve/eight row checks, the earlier counter correction, lost-task tracking and unknown human metrics. Extra model calls for this replay: zero. Actual human edits, accepted/rejected/corrected review actions, missing-test confirmation, incorrect-diagnosis rates and active human time are **unmeasured**. Existing proposal counters are automation counters, not human actions. No participant was invented. The existing three-arm logger and handoff remain available.

## I. Independent validation status

**PENDING:** real independent owner labels, hidden final document groups, semantic/citation judgments, calibrated review specificity and real customer outcomes. The [16-output packet](docs/artifacts/grounded-reasoning/pending-semantic-reviews.json) keeps model and calculated responses distinct. [Scoring the untouched packet](docs/artifacts/grounded-reasoning/pending-review-score.json) yields **REVIEW, zero completed reviews, null semantic/citation correctness**. The [independent-final template](docs/artifacts/grounded-reasoning/independent-final-template.json) is unfilled. The development reviewer is explicitly Codex, not an invented source owner or human expert.

No same-model judge, hidden-folder assertion or three successful calculations supplies independent truth. Final labels must be supplied and frozen by real independent operators on unseen document families, before outputs, without repeated tuning.

## J. Developer onboarding

[Connect an existing RAG application](docs/CONNECT_EXISTING_RAG.md) supplies full commands for owner input, baseline snapshots, candidate updates, intended/protected behavior, proposal review/rejection, callback connection, strict release, JSON/Markdown/CI exit codes, claim review and isolated repair. [Thin adapter example](examples/connected_rag/adapter.py) deliberately imports the developer's existing app; it is not a new or simulated backend. [Runnable release tool](tools/check_external_release.py) uses the existing callback/assurance APIs.

**Verified in synthetic integration fixtures:** manifests/index membership, no expected labels sent to the app, null unknown usage, stale-version rejection, strict REVIEW without independent judges, JSON/Markdown output and immutable report destinations. **Unverified:** actual external backend compatibility, developer integration effort and independent adoption. Logical callback task limits are not hidden provider/spend limits; the real application must enforce its own actual generation accounting, and synchronous in-flight callbacks can overrun a deadline. The documentation states these limits rather than pretending the adapter is a sandbox or billing gateway.

## K. Full regression tests

**Verified:** starting **247 passed in 7.88s**. Final isolated complete suite **276 passed in 7.03s**. New fact/bridge/isolation file: **29 tests**; combined focused run with the explicitly unavailable-provider test: **30 passed in 0.34s**. Full command: `PYTHONPATH=workspace/.deps python -m pytest -q`, with localhost permission for ephemeral fake-provider fixtures. The standard live-model port is blocked by the new fixture. [Final integrity/test manifest](docs/artifacts/grounded-reasoning/final-integrity.json).

Coverage includes subject/predicate distinction, period-list/front-period grammar, unrelated matching numbers, Decimal lookup/add/subtract/comparisons, multi-document operands, conflict retention, missing periods, dates/jurisdiction, unit mismatch, qualifiers/non-numeric eligibility refusal, unsupported multi-step formulas, exact source spans/version tampering, label-independent output, changed authorization bindings, typed comparison answers, provenance-aware citation checks, model-path preservation, numerical diagnosis classification, callback/CLI behavior and live-model socket isolation. These are clearly synthetic engineering regressions, not independent generalization benchmarks.

## L. Eight-feature preservation

**Verified within automated/integration-test scope:**

| Existing feature | Preserved evidence |
|---|---|
| Intent-aware change detection | Existing approved/protected review tests and historical source-change replay |
| Evaluation proposals | Existing immutable-label/proposal correction/rejection tests |
| Fact-to-agent impact mapping | Existing new-content/dependency impact tests; versioned source facts remain intact |
| Pre-deployment Data CI | Existing source/config/snapshot tests and strict release states |
| Diagnosis and isolated repair | Existing controlled repair tests; new deterministic-vs-model cause classification |
| Longitudinal intelligence | Existing SQLite history, review, timeline and checkpoint tests; sprint run IDs persisted |
| Dataset valuation/ablation | Existing source/document ablation tests; no source-value claims inferred from ranking |
| Cost-aware optimization | Existing quality/held-out/call/unknown-cost tests; experimental optimizer retained |

CLI, FastAPI, dashboard and existing orchestration remain compatible. No legacy feature was removed; new numerical/retrieval modes require explicit configuration. Automated coverage is not certification of all production stacks or document formats.

## M. Startup and resume readiness

- **Preliminary:** narrow, explicitly contracted deterministic answers improved development correctness and reduced supported false abstention without an observed unsupported answer on the single negative. **Failed:** model-only reliability stayed 1/3.
- **Unverified:** independently grounded quality-preserving token optimization. Zero-token source calculation is a different answering algorithm; smaller model contexts still preserve weak quality only.
- **Verified:** source-bound facts, review-bound operations, numerical citation checks, deterministic-vs-model diagnosis, source/version integrity checks and callback onboarding were implemented and exercised. **Unverified:** independent diagnostic usefulness, real integration simplicity, reduced human burden or startup differentiation.
- **Verified:** maintained workflows tie the current release decisions. **Failed:** global experiment-call cap and complete inference accounting; this is material to any infrastructure/readiness claim. The unit isolation fix is tested, but no new real run was authorized or performed to erase the failure.
- **Defensible resume statement:** “Built opt-in provenance-bound numeric reasoning and citation checks in an AI knowledge-change assurance beta; expanded regression coverage to 276 tests. A controlled development comparison improved supported correctness from 1/3 model-only to 3/3 with declared deterministic calculations; independent validation remains pending.” Do not describe that as general RAG reliability, independent quality-preserving cost savings, a production release, or a cap-compliant benchmark.
- **Preliminary demo readiness:** a controlled technical demo may show literal facts, declared operations, unchanged model failures and strict REVIEW/BLOCK/INCONCLUSIVE behavior. **Unverified:** unattended production readiness, external customer value, commercial differentiation or investor-grade validation.

Highest-value next work: obtain genuine owner-established hidden labels and independent claim reviews; validate the narrow grammar/reference behavior on separate new document families with a dedicated isolated inference runtime and reconciled all-process accounting; run the preregistered three-arm human maintenance study. No additional model experiment or inference followed the accounting audit.

### Evidence boundaries

[Prepare/run](tools/validate_grounded_reasoning.py), [analysis](tools/analyze_grounded_reasoning.py), [full-suite comparison](tools/audit_grounded_workflows.py), [raw artifact directory](docs/artifacts/grounded-reasoning/), [audited summary](docs/artifacts/grounded-reasoning/validated-summary.json), [server reconciliation](docs/artifacts/grounded-reasoning/generation-accounting-audit.json). Captured main requests/responses, exposed development labels, synthetic fixtures, separately executed source calculations, controlled mutations, missing independent judgments and untracked server activity are distinct. Historical evidence is not rewritten; incomplete accounting is not presented as a complete measured outcome.
