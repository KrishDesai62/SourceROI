# Reliability-first evidence selection and Data CI

November 13, 2026. This is a standalone SourceROI phase. It reused the approved local Qwen2.5-1.5B-Instruct Q4_K_M model and llama.cpp b12345 runtime. No new model/runtime downloads, paid APIs, billable credits, cloud resources, or commercial credentials were used.

## A. Root causes of the prior failures

[The seven-case evidence-backed analysis](SOURCE_FAILURE_ANALYSIS.md) preserves all original questions, accepted answers, outputs and retrieved passage IDs. [Structured analysis](artifacts/source-failure-analysis.json) includes complete baseline/candidate contexts.

Three of the four previous exact-score regressions involved destructive context filtering:

- A 512-character budget dropped the Steam_engine passage containing “solar” and retained an unrelated short passage.
- A 128-character budget removed all context for the Local H / For Against comparison. The baseline itself had incomplete annotated support, so its reference-correct answer was not proven fully grounded.
- A 512-character budget removed the Phil Spector/song evidence entirely; the model answered Bob Dylan without context.

The fourth failure retained the reference passage and changed “provide…” to “Provided…”. It is a plausible tense-only scoring ambiguity requiring independent review, not a missing-information finding. The gold labels and original exact-match result were not changed.

Of three recoveries, one restored complementary Euromarché/Carrefour evidence, one changed distractors while retaining the same civil-disobedience evidence, and one answered correctly with no context. They therefore do not all demonstrate improved information selection or grounding.

## B. Engineering changes

### Evidence-aware selection and fallback

`live/evidence.py` is a modular pre-answer selector. It uses question terms, entity anchors, multipart/comparison signals, configured source reliability priors, query coverage, passage novelty, exact/near-duplicate text, numerical/negation disagreement signals and temporal-scope warnings. It attempts to retain complementary documents and both sides of possible conflicts. Different quantities or negation prevent near-duplicate deletion.

The scores are heuristics, not semantic entailment or proof of evidence sufficiency. Reliability values are operator-supplied priors, not inferred authority. Date/conflict signals trigger conservative preservation/review; the system does not declare an older or disagreeing source false merely because it is inconvenient.

An optional measured context-token cap uses the actual local tokenizer. Unsupported tokenizer capability fails explicitly; character estimates are not represented as actual token counts. If a strict budget cannot contain selected evidence, the trace records infeasibility rather than silently exceeding the cap.

The fallback variant returns to original top-k context when requirement coverage, entity anchors, complementary-document coverage or conflict/time handling is uncertain. Fallback occurs **before generation**, with **zero extra generation calls**. Empty-context evidence policies return `INSUFFICIENT_EVIDENCE` without invoking the model; skipped generation is labeled explicitly rather than inventing provider usage.

Every selection records requirements, selected/ranked IDs, duplicate removals, uncertainty signals, fallback reason, tokenizer measurement and selection-check overhead. It does not receive benchmark answers, task IDs, published hop labels, or held-out feedback as runtime selection features.

### First-class Data CI

`live/data_ci.py` freezes configuration, original documents, benchmark and version hashes into an immutable snapshot. It verifies source stability during copying and before evaluation. Model/retrieval settings and benchmark identity must remain controlled across the data-only comparison.

The workflow detects added, removed and changed documents and source metadata, runs paired baseline/candidate evaluations, classifies task/evidence regressions and severity, stores machine-readable reports, and identifies plausibly related changed documents. Reference-based affected-task shortlisting is optional; full/bounded/explicit-subset scope and untested-task counts are disclosed.

A bounded controlled rollback restores changed data only in a temporary copy and re-evaluates affected tasks. Suggested actions are reviewable proposals tied to frozen versions, never automatic production mutations. Associations are not universal causal contribution scores. Whole-source ablation remains available as an explicit broader comparator.

### Diagnosis and reliability controls

Post-failure diagnosis distinguishes missing reference quotes, information present but not retrieved, ranked evidence filtered out, and generation/scoring failures despite supplied reference evidence. Original-document checks prevent chunk-boundary losses from being mislabeled as source absence. Reference annotations may be incomplete; equivalent evidence elsewhere is not ruled out.

Available registered source-addition tests execute both configurations rather than speculating about buying data. They never purchase anything.

Shared model-call and wall-time guards cover the session; per-request timeouts are clipped to remaining time. No automatic inference retry duplicates work. Completed configurations/tasks survive failed runs. Existing outputs cannot be silently overwritten by the bounded evaluation driver. Local inference ignores commercial credentials and proxy environment routing for loopback requests.

CLI, API, dashboard history and exports expose Data CI and reliability reports. No cosmetic redesign or new infrastructure service was added.

## C. Bounded genuine local evaluation

The new benchmark contains **24 published tasks and 126 original documents**: 12 development and 12 held-out questions, with nine document groups per split. SQuAD questions sharing an article remain grouped; HotpotQA supplies multi-document questions and distractors.

All article families from both prior exposed workspaces were excluded. A data-only audit found no shared document IDs across splits, no prior article-title overlap, and no five-word-shingle Jaccard matches at or above 0.9 across partitions/prior documents. These lexical checks cannot rule out all semantic or pretraining leakage. No test cases were removed after observing outcomes. [Split audit](artifacts/reliability-split-audit.json).

The frozen plan permitted at most **320 generation calls**, **900 seconds**, one model slot, 4,096 context tokens, four CPU threads, and an 8 GiB process-RSS check before generation. RSS is not complete OS/GPU memory accounting. A four-call development pilot forecast approximately 318 seconds for the remaining work before the main run started.

Actual session: **283 generation calls in 354.75 seconds**, maximum observed server RSS **1.86 GiB**, external spend **$0**. The model server was stopped afterward. Calls comprised four pilot calls, 264 fresh-study calls, 13 Data CI calls and two source-addition calls. The raw completed study originally counted the four pilot calls in its study total; the scoped metadata was corrected without changing model outputs, and the as-executed JSON was retained.

Every baseline had development-only tuning. The fixed previous optimizer was included as a transfer comparator, not fitted using the new test. Frozen configurations each received one held-out pass. The quality gate was zero newly failed tasks against the original, not a claim that the original's low absolute accuracy is production-ready.

| Policy | Correct / 12 | Prompt | Completion | Total tokens | Context tokens | New losses | Fallback |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original | 5 | 9,670 | 299 | 9,969 | 7,574 | 0 | 0% |
| Tuned top-k (5) | 5 | 9,670 | 299 | 9,969 | 7,574 | 0 | 0% |
| Tuned context budget (2,000 chars) | 5 | 7,634 | 300 | 7,934 | 5,538 | 0 | 0% |
| Threshold (0.5)* | 5 | 6,361 | 304 | 6,665 | 4,265 | 0 | 0% |
| Strong simple task-aware (lookup 2, otherwise 5) | 5 | 5,593 | 300 | 5,893 | 3,497 | 0 | 0% |
| Fixed previous optimizer* | 6 | 7,121 | 284 | 7,405 | 5,025 | 0 | 0% |
| New evidence-aware* | 5 | 7,573 | 303 | 7,876 | 5,477 | 1 | 0% |
| New evidence-aware + fallback | 5 | 9,670 | 299 | 9,969 | 7,574 | 0 | 100% |

*No setting in these families passed the predefined development task-preservation gate. The best observed development quality was retained for diagnostic comparison and explicitly marked infeasible. Their held-out outcomes cannot retroactively qualify them or select them for deployment.

| Policy | Mean ms | Median ms | p95 ms |
|---|---:|---:|---:|
| Original | 1,380.70 | 1,417.95 | 1,642.36 |
| Top-k | 1,481.40 | 1,527.03 | 1,797.57 |
| Context budget | 1,167.93 | 1,126.33 | 1,362.44 |
| Threshold | 1,124.30 | 1,005.35 | 1,792.84 |
| Strong simple task-aware | 1,150.68 | 1,169.91 | 1,574.26 |
| Fixed previous optimizer | 1,203.77 | 1,206.17 | 1,720.95 |
| Evidence-aware | 1,193.45 | 1,127.97 | 1,707.21 |
| Evidence-aware + fallback | 1,496.58 | 1,496.70 | 1,910.01 |

These are actual local end-to-end wall times, including selection/tokenizer/resource-check overhead, not universal latency guarantees. The fallback's selection checks totaled 468.733 ms across 12 tasks (about 39 ms/task); its higher overall latency also includes uncontrolled runtime variation. No extra generation retry was used.

## D. What passed, failed, and remains uncertain

The bare evidence-aware selector lost one original success while recovering a different task: equal 5/12 aggregate accuracy hid a regression. On the D1NZ oversteering question, it answered “past life regression” instead of “drifting”. Runtime signals included a missing entity anchor and possible conflict. The fallback restored original context and preserved the correct answer.

That is one observed fallback benefit on an unseen task, not a zero-regression guarantee. Fallback triggered on **all 12** questions, kept original token usage, and added overhead. It therefore did **not** demonstrate efficient information selection. The qualified simple heuristic used **40.89% fewer tokens** with the same five successes and no new task losses in this small sample.

The previous optimizer scored 6/12 with 25.72% fewer tokens than original on this new sample, despite failing new-development qualification and the prior 48-question test. This mixed result is retained, not hidden. It illustrates variability and a possible tradeoff; it is not grounds to reverse the earlier rejection or promote a policy after inspecting test outcomes. The strongest qualified simple heuristic still used fewer tokens, with one fewer correct answer.

The fallback-versus-original grouped accuracy/token intervals collapse to zero because their outputs/context were identical. This is **not proof of equivalence on future tasks**. The bare selector's grouped accuracy interval spans approximately [-25,+27.27] percentage points. Nine held-out groups are too few for a strong safety or superiority claim.

Groundedness remains **pending independent claim review**. Complete reference-quote inclusion was 9/12 for original and fallback, 9/12 for bare evidence-aware, and 7/12 for the simple heuristic. Quote inclusion does not establish semantic support. Published exact-match labels may reject acceptable paraphrases; accepted alternatives were retained unchanged.

Verdict: **Inconclusive / insufficient evidence** for the new guarded optimizer, with no production recommendation. The bare policy failed the no-new-loss gate. There is no demonstrated new efficiency advantage over the qualified simple baseline.

## E. Data CI differentiation: controlled evidence loss

A separate control used four **previously exposed** questions, not the fresh test. It removed one published Steam_engine document in a candidate copy and held benchmark/model/retrieval settings fixed.

| Check | Observed result |
|---|---|
| Ordinary answer-accuracy regression | No new failures; 4/4 answers remained correct |
| Nonempty-retrieval check | No failure; retrieval stayed nonempty |
| Reference-evidence coverage | Detected one loss, from 1.0 to 0.0 on the heat-source task |
| SourceROI Data CI | Blocked the change and localized the removed document/version |
| Temporary single-document rollback | Restored reference coverage to 1.0; generated answer remained correct |
| Existing whole-source ablation | Removing the entire SQuAD source failed two tasks, a broader intervention |

The tested value beyond answer-only/nonempty checks was identifying a loss of supplied support even when model answers stayed correct. **A strong reference-coverage check caught the same evidence loss.** SourceROI did not demonstrate additional detection superiority over that comparator. Its added workflow was version localization, a bounded model-tested repair, persisted evidence and an actionable review/rollback proposal.

The repair was performed only in a temporary copy. The controlled candidate remains missing its file; original sources were untouched. The result does not establish unique source causality for arbitrary multi-change incidents or competitor superiority.

A separate available-source addition test on the exposed heat-source question changed the answer from incorrect to correct when SQuAD was included. This is a one-task controlled result, not a dataset-purchase recommendation or a generalization claim.

## F. Product use and verification

Existing installation:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
```

The already approved local model can be started with:

```bash
python tools/local_llm.py serve
```

An ordinary source-change workflow:

```bash
python -m sourceroi --project MY_LOCAL_WORKSPACE freeze --output MY_FROZEN_BASELINE
# Change registered data only. Keep model/retrieval settings and benchmark frozen.
python -m sourceroi --project MY_LOCAL_WORKSPACE data-ci --baseline MY_FROZEN_BASELINE --max-tasks 12 --max-seconds 300 --max-regressions 0 --max-evidence-drop 0 --repair --allow-model-calls --output workspace/data-ci.json
```

Exit code 3 blocks a detected regression/evidence failure. Errors/incomplete runs do not pass. Partial/bounded task coverage is explicit; untested tasks are not silently claimed safe. Use `--affected-only` only when reference-based shortlisting is acceptable; unannotated added distractors can affect tasks outside that shortlist.

Failure diagnosis without inference:

```bash
python -m sourceroi --project MY_LOCAL_WORKSPACE diagnose --run-id RUN_ID --output workspace/diagnosis.json
```

A bounded evidence-aware comparison on a **new frozen dataset**:

```bash
python -m sourceroi --project MY_NEW_LOCAL_WORKSPACE reliability-study --previous-policy docs/artifacts/local-llm-96.json --max-calls 320 --max-seconds 900 --allow-model-calls --output workspace/new-reliability.json
```

Use a local-only llama.cpp model with its tokenizer configured. Arbitrary external-agent evidence policies are not claimed supported. Existing external HTTP source/document controls remain available through their established adapter contract; the new Data CI execution helper is deliberately local-RAG-only for this zero-spend phase.

API routes:

- `POST /api/v2/data-ci/freeze` creates an immutable workspace-local snapshot.
- `POST /api/v2/data-ci` requires its snapshot ID and explicit local-call acknowledgment; threshold/time/task bounds are validated.
- `POST /api/v2/reliability-studies` requires an explicitly supplied previous policy and local-call acknowledgment; call/time limits are validated.
- Existing run-history APIs return persisted reports. Dashboard Experiments provides Data CI controls and renders saved reliability/CI results; JSON, CSV, Markdown and pending-review exports are available.

[Self-hosted GitHub Actions example](../examples/ci/source-data-ci.yml) uses an existing local runner and model. It was provided as an example, not executed or provisioned. No GitHub-hosted/cloud compute is created.

Executed evaluation commands:

```bash
python tools/analyze_source_failures.py
python -m sourceroi public-benchmark --squad workspace/.cache/public-qa/squad.json --hotpot workspace/.cache/public-qa/hotpot.json --per-dataset 12 --tasks-per-article 2 --exclude-prior-workspace workspace/public-validation --exclude-prior-workspace workspace/local-llm-96 --output workspace/reliability-24
python -u tools/run_reliability_validation.py
python tools/audit_reliability_split.py
python tools/summarize_reliability.py
python -m pytest tests/test_reliability.py -q
python -m pytest -q
node --check sourceroi/live/web/app.js
```

The executed driver protected the pilot/main/CI session with a shared call/time budget and RSS checks. It now refuses existing output/snapshot destinations before inference; replays require new paths and must not be called untouched validation. The complete suite before changes was 98 tests. Final test counts are recorded in STARTUP_VALIDATION.md. Browser interaction and GitHub Actions were not automated/executed; API, CLI, persistence and JavaScript syntax were checked.

## G. Startup assessment

The credible demonstrated capability is a **source-version-aware evidence regression gate with localized, model-tested repair context**. In this controlled example it caught a loss of document support that answer accuracy and nonempty retrieval missed. That is a useful design-partner workflow to test.

There is no proof of competitor superiority, unique detection beyond a strong coverage check, or a consistently superior optimizer. The conservative fallback preserved observed quality by retaining original information, not by becoming more efficient. The strongest simple heuristic remains a serious baseline. Do not market this phase as universal autonomous optimization or production-grade quality guarantees.

## H. Remaining blockers

- Independent factual/claim review, higher-quality representative agent tasks, and sufficient fresh groups for calibrated safety/efficiency claims.
- Better-calibrated runtime requirements and conflict/recency signals; the current guard fell back on every test query.
- Independently adjudicated contradiction/outdated-source stress tests; current warnings and structural unit tests are not evidence of semantic conflict resolution.
- Broader multi-source interaction/causal experiments; citation/exposure/rollback associations alone are not universal source importance.
- Natural customer incidents, measured operator value, and comparison with the customer's actual evaluation/coverage tooling.
- Cross-process concurrency, hosted authentication/security review, private-data encryption and production load testing.

The next milestone should be a controlled local design-partner Data CI pilot with independently reviewed support requirements and actual source-change incidents. Any optimizer iteration needs new document-disjoint final data, not retuning on the exposed test cases above.

## Artifacts

- [Seven-case failure analysis](artifacts/source-failure-analysis.json).
- [Frozen bounded plan](artifacts/reliability-local.plan.json), [pilot](artifacts/reliability-local.pilot.json), [session limits/results](artifacts/reliability-local.session.json).
- [Completed fresh comparison JSON](artifacts/reliability-local.json), [CSV](artifacts/reliability-local.csv), [Markdown](artifacts/reliability-local.md), [pending claim review](artifacts/reliability-local.review.json).
- [Post-run summary and coverage/uncertainty diagnostics](artifacts/reliability-summary.json).
- [Data CI control](artifacts/reliability-local.data-ci.json), [source addition](artifacts/reliability-local.source-addition.json), [overlap audit](artifacts/reliability-split-audit.json).
- [Exact as-executed code archive](artifacts/reliability-local-code.tar.gz).

Raw as-executed study/CI JSON files are retained separately. Only call-scope and task-scope metadata were clarified afterward; model answers, selected policies, token/latency measurements and gold labels were unchanged. Future-only fixes improve partial-run accounting, baseline snapshot validation and overwrite protection; they were not used to rerun the held-out experiment.
