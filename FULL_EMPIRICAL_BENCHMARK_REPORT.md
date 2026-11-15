# Authorized full empirical benchmark — 2026-11-14

## Assessment

**Execution: PASS. Answer reliability: FAIL. Differentiated detection advantage: not demonstrated. Independent semantic/customer value: INCONCLUSIVE.**

The existing frozen experiment completed once, including primary before/after evaluation and Data CI. It used **18 actual local Qwen generations**, **55,467 reconciled tokens**, **79.392 seconds of supervised runtime**, **zero retries** and **$0 external spending**. All 40 planned logical question/version evaluations finished: 20 primary and 20 Data CI. Twenty-two logical evaluations abstained in software and did not generate model answers. The authorized ceiling was 40 generation attempts and 90 seconds; it was not increased or reused.

Primary supported accuracy fell from **3/5 (60%)** to **2/5 (40%)**. Business answers remained wrong; the protected charity answer regressed from **14 to 70**. SourceROI and the conventional evaluator both BLOCKed the candidate. An input-parity audit found that the prepared comparison supplied different medical evidence quotations to the two checkers; its apparent extra SourceROI alert cannot count as unique detection. A separately identified, read-only replay using the same unchanged conventional checker and the exact reference requirements used by SourceROI produces the same four blocked task IDs. The original run and comparison are preserved unchanged.

## Authorization and accounting

Authorization: `docs/artifacts/full-empirical-benchmark/authorization.json`, ID `user-approved-full-benchmark-4d8c3029136b4bdabe32285db384fa4c`. It quotes the actual user approval: maximum 40 generation attempts including Data CI, maximum 90 seconds, zero retries, $0 external spend, only the verified local instrumented build/model and no bypass of gates. The authorization ledger is closed and single-use. Unused allowance is not carried into another experiment.

The command was the existing `tools/run_empirical_experiment.py run`, against `workspace/execution-resolution/benchmark-v1`, with the new authorization and fresh output `docs/artifacts/full-empirical-benchmark/run`. No frozen source, label, model/prompt configuration, retrieval rule or comparator implementation was changed. No preparation/package sprint, model download, cloud service, production modification or additional model experiment was performed.

| Accounting observation | Actual |
|---|---:|
| Reserved / dispatched generation attempts | 18 / 18 |
| Native task completions / captured terminal responses | 18 / 18 |
| Failed requests / retries | 0 / 0 |
| Primary generations | 11 |
| Additional Data CI generations | 7 |
| Prompt / completion tokens | 54,828 / 639 |
| Total tokens | **55,467** |
| Native process lifetime | **79.391976 s** |
| Single-use authorization session | **79.469102 s** |
| Authorization timestamp to results-file timestamp | **86.459 s**, including setup and post-generation scoring; an observed wall-span, not a precise process stopwatch |
| Native reconciliation | **RECONCILED**, no failures |
| Process exit / private transport | Exit code 0; PID exit confirmed; private socket directory removed |
| External spending | **$0**; local energy/hardware cost unpriced |

The independent native admission/binding/dispatch/completion/HTTP events match Python reservations, exact raw bodies, response usage and native counters. Stock native slot logs are an additional cross-check, not the basis for correlation. Raw accounting and its seal remain in `run/runtime/`. The earlier two-call smoke is separate historical evidence and is not included in these totals.

## Sources, labels and configuration

The unchanged corpus contains original authoritative [IRS Notice 2024-08](https://www.irs.gov/pub/irs-drop/n-24-08.pdf) and [IRS Notice 2025-5](https://www.irs.gov/pub/irs-drop/n-25-05.pdf), effective from January 1, 2024 and January 1, 2025 respectively. The latter supersedes the former. Their original PDFs, extracted text, hashes, quotations, quote offsets, original retrieval metadata and version-specific development expectations are preserved in the frozen benchmark. PDF hashes are `94545e0c068d2bcb09768975008bdfcc06b4903dbae67236d45439379eefc35d` and `aac49246870a5b943893f9407c7f20094ed887c834341de7ec69ad7a71e67773`.

CURRENT means the registered experimental edition, not the real calendar-2026 tax rate. Annual end-window metadata is the previously declared evaluation applicability window based on annual titles/supersession, not a claimed source-specified legal expiry. Conflicting evidence is the authentic difference between editions, not an invented same-period contradiction. Questions and labels are Codex-authored development annotations from a previously exposed corpus, frozen before these answers; no independent reviewer or source owner adjudicated them.

Model: existing **Qwen2.5-1.5B-Instruct Q4_K_M**, revision `91cad51170dc346986eccefdc2dd33a9da36ead9`, SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`. Runtime: verified instrumented local build from llama.cpp b12345 source archive SHA-256 `6e774abb097960ba5a233559d4035f3f91069cc5cdf33cb9c7874d873abf7b43`; the original installed binary was not replaced. Certificate/library hashes and exact runtime command are in `run/runtime/manifest.json`.

Configuration: temperature 0, seed 1729, output limit 192 tokens, context 4096, one slot, prompt cache disabled, no warmup/context shift, private authenticated UNIX socket, supervised deadline and durable attempt permits. Existing numeric JSON contract and citation-enum schema were retained. No auxiliary tokenizer endpoint was used.

Primary retrieval: existing PDF ingestion and BM25, fixed 1800-character chunks, overlap 200, top 5, context bound 9000 characters. A literal CURRENT question searches the registered current source; cross-version questions search the collection. Scope/evidence prechecks remain enabled. Built-in Data CI intentionally uses its existing broader retrieval and original frozen labels: it is a separately measured path, not an identical-context repeat of the primary application.

## Primary results: actual answers

IE means `INSUFFICIENT_EVIDENCE`. Expected values below are the frozen version-specific development labels. Each actual answer, question, retrieved passage, citation and raw request/response link is retained in the evidence file; no answer has been corrected after generation.

| Question ID | 2024 expected | 2024 actual | 2025 expected | 2025 actual |
|---|---:|---:|---:|---:|
| business — cents/mile | 67 | **21** | 70 | **21** |
| medical — cents/mile | 21 | 21 | 21 | 21 |
| charity — cents/mile | 14 | 14 | 14 | **70** |
| favr — maximum dollars | 62000 | 62000 | 61200 | 61200 |
| depreciation — own-year cents/mile | 30 | **27** | 33 | **26** |
| parking — absent daily amount | IE | IE, software | IE | IE, software |
| canada — jurisdiction mismatch | IE | IE, software | IE | IE, software |
| future — year 2030 | IE | IE, software | IE | IE, software |
| past — year 2020 | IE | IE, software | IE | IE, software |
| cross_version — one identical rate for both years | IE | **67**, model | IE | IE, software |

| Primary metric | Baseline | Candidate |
|---|---:|---:|
| Supported correct | **3/5 = 60%** | **2/5 = 40%** |
| Supported false abstentions | **0/5** | **0/5** |
| Unsupported rejection, whole pipeline | **4/5 = 80%** | **5/5 = 100%** |
| Unsupported model-generated cases | 1, rejected correctly 0/1 | 0; model rejection rate undefined |
| Factual answers with invalid/missing citation IDs | **0/6** | **0/5** |
| Mean latency per actual generation | **3827.43 ms** | **4224.23 ms** |
| Primary prompt / completion tokens | 17,928 / 213 | 15,412 / 178 |
| Primary total tokens | 18,141 | 15,590 |
| Aggregate task accuracy including software abstentions | 7/10 | 7/10 |

The aggregate 70%→70% hides worsening supported-answer quality. All ten supported primary cases generated answers; none abstained. The earlier model-abstention symptom is absent in this primary run, but reliable answering is **not** established: five of ten supported answers are wrong. Nine of ten unsupported primary cases were handled in software, so the strong pipeline rejection numbers do not demonstrate good unsupported reasoning by Qwen.

All 11 factual primary outputs use valid retrieved citation IDs. Six of those 11 factual outputs disagree with frozen answer labels or answer an unsupported question. Citation membership and literal reference coverage therefore cannot be described as semantic citation correctness. Independent claim support/citation review remains null/PENDING.

## Fair conventional comparison and the discovered reference mismatch

The primary checkers consume the same captured answers; SourceROI scoring replays actual traces and makes **no new model calls**. Expected candidate answers are maintained at 70, 21, 14, 61200 and 33, so the baseline is not weakened with stale answer labels. Both methods check answer format, citation membership, source/version identity and evidence requirements, and both lack independent semantic review.

**As-run overall verdict:** SourceROI BLOCK; conventional BLOCK. Both detect the candidate business, charity and depreciation answer failures. The protected charity regression is detected by both. SourceROI also flags medical as a literal evidence-reference loss despite its correct answer.

**Comparison-input audit: FAIL.** The prepared harness updates the conventional evaluator's medical evidence to the 2025 wording, but SourceROI's protected task retains the original 2024 quotation. The 2025 notice explicitly says the rate is unchanged from 2024 and changes the sentence wording. The expected answer remains 21. Consequently, an extra SourceROI medical alert is confounded by unequal reference inputs; it is not unique semantic regression coverage.

The unmodified original reports remain in run/results.json and run/strict-release.json. A **supplementary offline input-parity replay**, clearly separate from the primary frozen run, passes the existing unchanged conventional checker exactly the original protected references and explicitly revised references used by SourceROI. No source, label, model output or scoring algorithm is edited. Both then block the same set: **business, charity, depreciation, medical**. Three are wrong answers; medical is an old literal-reference mismatch. There is no incremental detection coverage under equal requirements.

The original prepared comparison protocol is therefore not unqualified evidence of a perfectly maintained equal-reference trial. The raw answer-test tie is unconfounded; the additional reference alert is explained by the parity audit. Exact inputs/results: `analysis/final/comparison-input-parity-audit.json`.

This also exposes an evaluation-maintenance limitation. Existing review rules tie replacement evidence to expected-change tasks, while the medical task is protected. This run did not independently maintain evidence for unchanged answers whose source wording changed. It must not be sold as automatic self-maintenance or claimed customer time savings.

## Data CI: actual second run and false abstentions

Data CI completed its own 20 logical before/after evaluations using **7 additional native generations**. It returned **blocked**. These are actual additional responses, not a replay presented as fresh inference.

| Data CI metric, against maintained answer labels | Baseline | Candidate |
|---|---:|---:|
| Supported correct | **2/5** | **0/5** |
| Supported false abstentions | 0/5 | **4/5** |
| Unsupported rejection, whole pipeline | 4/5 | 5/5 |
| Actual generations | 6 | 1 |
| Prompt / completion tokens | 18,388 / 213 | 3,100 / 35 |
| Mean latency per generation | 4705.16 ms | 4791.55 ms |

Candidate Data CI abstains on business, medical, FAVR and depreciation **before model generation**, citing potential same-predicate numerical conflicts. The only candidate model-generated supported answer is charity=21, which is wrong. Thus these four supported abstentions are a SourceROI evidence/routing precheck behavior, not four Qwen refusal responses. Broader retrieval brings current and archival annual values together; its conflict screen does not resolve these CURRENT questions as the primary application's source restriction does.

The built-in report identifies medical and FAVR as newly failed answers and literal evidence warnings on other tasks. Its originally graded aggregate accuracy is 60%→50%, while the maintained-supported metric above exposes the actual supported failure. Original unchanged-label Data CI is not the maintained-label conventional comparator, and its different retrieval means it cannot be used as a reproducibility repeat of the primary answers. Its shorter aggregate latency comes mostly from not generating supported answers; it is **not** quality-preserving optimization.

**Assessment:** Data CI's execution and fail-closed blocking operate, but supported-answer preservation on this mixed-edition path **FAILS**. Its end-to-end equivalence to the primary application's CURRENT routing is **INCONCLUSIVE/not established**. No unique regression advantage over the equally equipped conventional evaluator follows.

## Why 21 appears for business: trace-based investigation

The raw question asks the business standard mileage rate in the CURRENT annual notice. The correct 67/70 quotation is present in the supplied context in both primary versions. The same context also contains the medical value 21. Qwen emits a complete valid numeric JSON response with 21 and cites all five passages. It is not truncated, malformed, an empty retrieval result, a version mismatch or a false abstention.

The data demonstrate a wrong predicate/value association despite available business support. They do **not** reveal the model's internal causal mechanism. The corresponding candidate charity answer=70 reuses the business value, and the depreciation answers 27/26 select historical values rather than the notice's own year. These observations are consistent with poor subject/year selection in multi-value context, not proof of a particular attention or schema defect.

SourceROI classifies the three candidate wrong supported answers as `generation_or_scoring_failure`, with all required reference quotes supplied. This is a useful automatic diagnostic bucket and provenance trail; it is a hypothesis, not a verified causal repair. The conventional checker plus the same retrieved evidence can establish the same support-present/wrong-answer facts. No prompt change, schema relaxation, relabeling, answer correction, ablation or extra generation was performed to make the results improve.

## Impact mapping, maintenance and observed overhead

One registered current document changes. SourceROI flags **all 10 tasks** as potentially affected, including **3/3 declared changed-answer tasks** and the observed protected charity regression. This verifies broad document-linked coverage; it does not establish precise fact-level impact. No independent dependency oracle exists and all tasks were selected, so no test-reduction or impact-precision advantage is demonstrated over a maintained full suite.

The three intended changed-answer proposals remain **AMBIGUOUS_REVIEW** with null suggested values: **0/3 automatic value suggestions**. The experiment supplies the frozen source-derived development decisions through a record explicitly naming Codex technical review, not a real independent reviewer or source owner. Strict release reports execution PASS, exact answers BLOCK, citation/reference checks blocked/reviewable, source version PASS and independent semantic review REVIEW. Its intent-approval PASS is an internal bound development assertion, not authenticated human approval. No genuine strict ACCEPT is invented.

Recorded SourceROI full scoring/replay overhead was **4592.83 ms**, after native shutdown. The separately timed identical-requirement conventional replay is retained in the analysis artifact. Those scopes differ—SourceROI includes additional workflow/provenance/diagnosis—and single ordered measurements do not establish comparative labor or performance savings. Human integration, maintenance and review time were not observed. There is no independent customer, willingness-to-pay or ROI evidence.

## PASS / FAIL / INCONCLUSIVE by capability

| Tested capability or claim | Assessment | Evidence / practical limit |
|---|---|---|
| Authorized real retrieval and local generation | **PASS** | All primary/CI logical cases complete; 18 real native calls |
| Call/deadline accounting and shutdown in this run | **PASS** | Reconciled exact identities/usage, 18<40, 79.392<90 s, exit 0 |
| Frozen source/version and raw-trace preservation | **PASS** | Inputs unchanged; all 18 native requests/responses matched to actual task rows |
| Supported primary answer reliability | **FAIL** | 3/5→2/5; wrong business/year associations and protected charity regression |
| Primary supported false-abstention avoidance | **PASS for these cases** | 0/10; does not compensate for wrong answers |
| Unsupported pipeline rejection | **FAIL as complete coverage** | 9/10 total; all nine correct rejections are software prechecks |
| Model-only unsupported rejection | **FAIL / very limited sample** | One generated unsupported answer, wrong; candidate n=0 |
| Citation-ID integrity | **PASS** | 11/11 factual primary answers have valid IDs |
| Semantic citation correctness | **INCONCLUSIVE** | No independent reviews; valid IDs accompany wrong claims |
| Known answer-regression release blocking | **PASS** | Charity 14→70 caught; both evaluators BLOCK |
| Incremental detection beyond strong conventional checks | **FAIL to demonstrate** | Answer-test tie; identical-requirement replay tie |
| Prepared comparison's initial reference-input parity | **FAIL** | Medical quote differs; raw comparison preserved and confound disclosed |
| Automatic fact-level impact precision or test savings | **INCONCLUSIVE** | 10/10 selected; 3/3 intended changes covered, no independent oracle |
| Automatic changed-value maintenance | **FAIL to demonstrate** | All three changed-value suggestions null/ambiguous |
| Protected unchanged-answer evidence maintenance | **FAIL in this workflow** | Medical wording drift remains a stale literal reference |
| Data CI supported answering on mixed annual sources | **FAIL** | Candidate 0/5; four software false abstentions |
| Diagnostic provenance/bucket generation | **PASS, narrow mechanics** | Support-present wrong-answer bucket recorded; causal repair unverified |
| Quality-preserving token/cost optimization | **INCONCLUSIVE / not tested** | No optimization arm; skipping supported answers is not safe savings |
| Independent semantic/customer/commercial value | **INCONCLUSIVE** | No independent reviewers, participants or customer outcomes |

## Raw evidence and reproducibility

All paths below are under `docs/artifacts/full-empirical-benchmark/`:

- `authorization.json`: actual approval and unique one-use budget.
- `run/accepted-*.json`, `run/candidate-*.json`: all 20 primary question/task/answer/retrieved-passage records.
- `run/runtime/requests/`: all 18 exact model request JSONs and raw HTTP response bodies/statuses.
- `run/runtime/native-events.jsonl`, events.jsonl, worker-exit.json, authorization-ledger.json, reconciliation.json, seal.json: independent server/client accounting and exit evidence.
- `run/data-ci.json`: all 20 additional CI task outputs/citations and change/diagnosis results.
- `run/strict-release.json`, technical-development-review.json, diagnosis.json, results.json: untouched as-run evaluation reports.
- `analysis/final/all-40-logical-task-traces.json`: full questions, raw answer rows, actual source/chunk passages before/after prechecks, citations, frozen/maintained expectations and exact native request/task mapping for every generated row. All 18 body/response hashes and token associations are checked; software abstentions have no invented native request.
- `analysis/final/phase-metrics.json`, comparison-input-parity-audit.json, failure-investigation.json, impact-audit.json and summary.json: explicit read-only derived analysis.
- `experiment-history.sqlite3` and history-backup.json: consistent backup of the two actual experiment history records; no production database involved.
- `historical-integrity.json` and evidence-manifest.json: final integrity checks/hashes. Frozen input identity and existing execution methodology were checked before and after the run. Existing historical results are preserved.

The offline analyzer is `tools/analyze_full_empirical_run.py`; it never calls a model or provider. No additional synthetic tests or preparation milestones are offered as empirical evidence. The last prior regression result remains 387 passing tests; this turn changed no product/inference code and did not substitute test counts for the real run.

## Conclusion and exact remaining work

The execution and accounting architecture operated within the authorized budget, preserved auditable real-model evidence and safely blocked a bad candidate. The current RAG answers are not reliable enough to claim preserved quality. SourceROI exposes useful integrated lineage and diagnostic context, but this experiment demonstrates **no detection advantage over an equally maintained conventional evaluator** and measures no human-effort or customer benefit.

Before stronger claims: resolve the protected-evidence maintenance and comparison-input parity issue in a separately scoped change; align Data CI with actual application routing in a newly frozen experiment; perform any prompt/context/model ablations only under new authorization; and obtain independently established labels/reviews and real developer effort observations. None of those changes or additional calls were made here. This authorized run is complete, the process is stopped and its authorization is consumed.

Final integrity audit: **787 pre-existing artifact/report files unchanged**; frozen benchmark and all native certificate-bound files unchanged. All 18 raw generation records map to actual task outputs; shutdown and closed authorization confirmed. No further generation occurred during read-only analysis.
