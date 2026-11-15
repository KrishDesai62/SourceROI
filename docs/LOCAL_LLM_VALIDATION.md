# Genuine local-model validation — November 13, 2026

This phase uses actual local generation, not the earlier mock adapter. No paid APIs, billable free credits, cloud inference, commercial credentials, or other applications are used.

## Frozen setup

- Model: Qwen2.5-1.5B-Instruct, official Q4_K_M GGUF, Apache 2.0 license. Revision and SHA256 are pinned in `tools/local_llm.py`.
- Runtime: official llama.cpp b12345 macOS arm64 binary, verified against the release archive SHA256.
- Machine: Apple Silicon, 24 GiB physical memory. Model and runtime were downloaded only after explicit user approval and are stored under ignored `workspace/.local-llm/`.
- Endpoint: `http://127.0.0.1:8788/v1`; one 4096-token slot; GPU layer offload requested with `--n-gpu-layers 99`; temperature 0; seed 1729; JSON output; maximum 384 completion tokens; prompt cache disabled.
- Both model generation and tokenizer calls are restricted to localhost. Local-only requests never look up or send configured commercial credentials.
- Commercial token prices are null. External API spend is zero; electricity/hardware cost is not estimated.

Official model files and license: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF. Official runtime releases: https://github.com/ggml-org/llama.cpp/releases.

## Benchmark

`workspace/local-llm-96` contains 96 published SQuAD/HotpotQA tasks and 496 unchanged source documents: 48 development and 48 held-out questions, with 36 document groups in each partition. Two SQuAD questions can share an article, but their entire article family stays in one split. HotpotQA brings multi-document questions and original distractors.

The workspace excludes all article families from the previously exposed eight-question benchmark. The original benchmark is unchanged. Published answer alternatives, evidence references, dataset licenses, input hashes and selection rules are retained. Task selection does not use model success, model-generated ground truth, or the prior held-out results.

This is a larger public test, not a representative customer workload or 96 statistically independent observations. Model pretraining contamination is unknown. It does not supply a comprehensively reviewed contradiction/outdated-document stress suite.

## Root cause of the earlier threshold result

The already exposed eight-question audit was reproduced before the ingestion fix and retained separately. Threshold filtering at 0.5 times the top BM25 score used 5,111 characters, versus 6,854 for the proxy, at the same 3/4 complete-quote task coverage.

The proxy was a keyword-based route among static policies: lookup questions used coverage with Hotpot excluded; multi-evidence questions used a 2,000-character budget. Coverage could keep adding overlapping passages after covering all query terms because normalized BM25 relevance still made their utility positive. It stopped at k or negative utility. Exact-text deduplication did not remove semantic overlap. Four development questions were too few to justify source selection by such coarse question types.

An additional ingestion defect was found: public documents used hashed filenames as titles despite their original article titles being available in provenance. Ingestion now restores those titles for every strategy. Local prompts also use short numbered citation aliases, mapped back to canonical document/chunk IDs, to avoid generating hash-heavy source identifiers. These adapter/metadata changes are shared by all policies and are not credited as a SourceROI selection advantage.

No new pruning heuristic was adopted merely to force a win on the exposed held-out questions.

## Protocol and quality constraints

Every baseline is tuned on development tasks. The frozen policies each receive exactly one held-out pass. The experiment uses the measured total-token objective. It requires no newly failed development tasks against the original when selecting a policy. The explicit absolute accuracy floor is zero for this diagnostic **relative-preservation** experiment; it is not a statement that low absolute accuracy is deployment-ready. Held-out regressions reject the proposal.

Semantic grounding is not automatically verified: generated claims and cited context are exported for independent review. Quote coverage and citation validity are reported separately. Exact-match scoring retains published alternatives but can reject valid paraphrases; reviewable answers are preserved.

Positive recommendation gates additionally require a measured benefit over a qualified simple baseline without new failures against that baseline. A reduction relative to the original alone is insufficient. Small-sample uncertainty and pending human grounding review remain explicit.

## Reproduction

```bash
# Inspect the pinned plan without downloading.
python tools/local_llm.py plan

# Only after explicit permission for the approximately 1.13 GB download:
python tools/local_llm.py install --download-approved

# Fresh benchmark; existing published inputs are cached locally.
python -m sourceroi public-benchmark --squad workspace/.cache/public-qa/squad.json --hotpot workspace/.cache/public-qa/hotpot.json --per-dataset 48 --tasks-per-article 2 --exclude-prior-workspace workspace/public-validation --output MY_FRESH_LOCAL_WORKSPACE

python tools/local_llm.py configure --project MY_FRESH_LOCAL_WORKSPACE
python tools/local_llm.py serve
# In a second terminal:
python -u tools/run_local_validation.py --project MY_FRESH_LOCAL_WORKSPACE --output docs/artifacts/MY_LOCAL_RUN.json
python tools/summarize_local_validation.py --project MY_FRESH_LOCAL_WORKSPACE --input docs/artifacts/MY_LOCAL_RUN.json --output docs/artifacts/MY_LOCAL_SUMMARY.json
```

The study is checkpointed in SQLite after each completed configuration. Do not change model/adapter settings or tune against held-out answers while it runs. The default 96-task plan uses up to 1,920 generation calls plus tokenizer requests; runtime depends on the machine. No paid-service prices or savings are inferred.

## Completed genuine results

The study completed 1,920 actual local generation calls in **47.79 minutes** (plus two development-only adapter probes before the run). All six baseline families were tuned on development only. Each frozen baseline and SourceROI received one pass over the same 48 held-out questions. The local inference server was stopped afterward; downloaded files remain for reuse.

| Configuration | Correct / 48 | Prompt tokens | Completion tokens | Total tokens | Context tokens | Median ms | p95 ms | Newly failed vs original |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Original | 22 | 41,547 | 1,181 | 42,728 | 33,103 | 1,359.96 | 1,680.77 | 0 |
| Tuned top-k (k=5) | 22 | 41,547 | 1,181 | 42,728 | 33,103 | 1,415.66 | 1,771.69 | 0 |
| Context-budget fallback (128 chars)* | 9 | 8,874 | 825 | 9,699 | 263 | 473.49 | 660.86 | 15 |
| Tuned threshold (0.25) | 21 | 39,684 | 1,186 | 40,870 | 31,240 | 1,478.32 | 1,789.69 | 1 |
| Simple task-aware fallback (k=1)* | 21 | 15,857 | 1,101 | 16,958 | 7,414 | 735.59 | 955.80 | 4 |
| Cheapest source (all fees zero, k=5) | 22 | 41,547 | 1,181 | 42,728 | 33,103 | 1,344.48 | 1,740.16 | 0 |
| SourceROI | 21 | 27,431 | 1,101 | 28,532 | 18,966 | 1,125.88 | 1,637.03 | 4 |

*Neither the context-budget nor simple task-aware family had a qualifying development configuration under the per-task no-regression constraint. A defect in the archived tuner selected the lowest-token failed setting as its fallback. These rows are **unqualified diagnostics**, not strong quality-preserving comparators. This defect is now fixed for future runs: infeasible families retain their best measured development quality and are explicitly marked unqualified. The completed held-out experiment has **not** been retuned or rerun; its original code is archived for exact reproduction.

### Answer to the critical question

**This experiment did not demonstrate quality-preserving optimization over simple retrieval.** SourceROI reduced total tokens by **33.22%** relative to the original but scored **21/48 (43.75%)**, versus **22/48 (45.83%)**. It newly failed four original successes and recovered three original failures. The strict no-regression gate correctly rejected it.

Tuned top-k selected k=5 and exactly tied the original answers/token counts. SourceROI's lower token count therefore came with quality losses against a qualified simple baseline. Threshold filtering also lost a task. The simple task-aware fallback tied SourceROI's aggregate accuracy while using fewer tokens, although both failed the original task-preservation requirement. No overall win is claimed.

The SourceROI-versus-original group-bootstrap accuracy-delta interval was **[-12.77, +8.33] percentage points**. The objective interval was **[-18,662, -10,066] total tokens**. These support an observed token reduction, not proof of accuracy equivalence. This sample does not establish a universal accuracy decrease either; the deployment rejection is based on the four observed unacceptable task regressions.

### What the selected policy actually did

The frozen route was:

- Comparison questions: fixed 128-character context budget.
- Lookup questions: greedy query coverage, k=5, no source-cost penalty.
- Multi-evidence questions: fixed 512-character context budget.

This is genuinely question-dependent selection among measured static policies, but it is not a learned semantic information-value model. The broad keyword types and small per-type development samples did not generalize reliably. The budget branches could strip away necessary evidence, and query-coverage utility is not the same as multi-hop evidence sufficiency. No optimizer change was fitted to these held-out failures.

### Grounding and prior knowledge

Groundedness remains **pending independent claim review**. Reference correctness is not enough: SourceROI answered three questions correctly when it had no retrieved context. Its selected configuration supplied no context for five tasks and returned a non-abstaining answer for four of them. The 128-character fallback supplied no context for 42 tasks and still scored seven of those correctly. Prior knowledge, question clues or guessing can therefore inflate apparent success without document support.

Full published-support quote inclusion was 32/48 for original/top-k and 27/48 for SourceROI. This is a retrieval diagnostic, not a semantic grounding score; long quotes can cross chunk boundaries. The held-out review packet includes actual answers, citations, accepted gold answers, contexts and reference evidence so these cases can be adjudicated. Exact-match negatives can also contain acceptable paraphrases, so individual failures remain reviewable rather than being silently relabeled.

### Costs, latency and overhead

External API spend was **$0**. No simulated provider rates were configured or applied. Electricity/hardware costs are unknown; there is no claim that total physical compute is free. Raw monetary model-cost fields remain null instead of inventing an invoice.

SourceROI mean task latency was 1,067.17 ms versus 1,386.80 ms for original; medians/p95 are above. These are actual sequential localhost wall times, including retrieval, context-tokenizer requests and generation. Hardware thermal/cache conditions were not controlled like a laboratory experiment, so latency differences are descriptive, not universal causal claims.

Total evaluation elapsed time was 2,867,646.45 ms. Summed task wall time was 2,865,500.73 ms; recorded non-task overhead was 2,145.72 ms, including 2.84 ms for fitting the routing table. Most expense was the development search itself. Duplicate effective settings, such as cost-weight variants when all fees are zero, were evaluated separately; this is avoidable future search overhead, not an information-quality advantage.

### Recommendation

**Rejected due to quality regression.** No production retrieval changes were applied. The experiment shows real token reduction, but not the required preservation of answer quality or an advantage over quality-preserving tuned top-k. Pending semantic review and low absolute accuracy further prevent deployment claims.

The useful demonstrated capability is the evaluation/regression gate: it exposed reductions that looked efficient but lost tasks, and it distinguished reference correctness from evidence support. Source/document ablation, versioned comparisons and reproducible reports remain useful even though this optimizer did not establish differentiation.

## Executed verification

Before changes: `python -m pytest -q` → 91 passed. After adding the local-only adapter, benchmark grouping and gates: 97 passed. After the future-only fallback correction: **98 passed**. Focused local-validation tests: **7 passed**.

```bash
python -m pytest -q
python -m pytest tests/test_local_validation.py -q
python tools/analyze_retrieval_gap.py --input docs/artifacts/local-phase-retrieval-reproduction.json --output docs/artifacts/local-phase-root-cause.json
python tools/local_llm.py plan
python tools/local_llm.py install --download-approved
python tools/local_llm.py configure --project workspace/local-llm-96
python tools/local_llm.py serve
python -u tools/run_local_validation.py
python tools/summarize_local_validation.py
```

The inference commands were actually executed after explicit download/inference approval. The final regression tests mock their inference dependencies and do not rerun or retune the held-out benchmark.

## Artifacts

- [Environment and checksums](artifacts/local-llm-environment.json).
- [Earlier audit reproduction](artifacts/local-phase-retrieval-reproduction.json).
- [Earlier root-cause analysis](artifacts/local-phase-root-cause.json).
- [Frozen plan](artifacts/local-llm-96.plan.json).
- [Raw completed study](artifacts/local-llm-96.json), [CSV](artifacts/local-llm-96.csv), [report](artifacts/local-llm-96.md).
- [Summarized actual measurements](artifacts/local-llm-96-summary.json), [comparison table](artifacts/local-llm-96-summary.md).
- [Focused held-out human review packet](artifacts/local-llm-96-summary.review.json).
- [Exact pre-correction code archive](artifacts/local-llm-96-code.tar.gz), whose core module hashes match the original study.

To replay the **archived original experiment**, start the pinned local server, extract the code archive into a fresh directory, and invoke its `tools/run_local_validation.py` with absolute paths to the existing workspace and `--root` model directory. The installed code includes the future-only baseline fallback correction, so it intentionally need not reproduce the flawed fallback selection from the archive. A replay is reproduction of an exposed test, not new held-out evidence.

## Remaining limits and next experiment

This single small local model, 48 held-out questions and 36 held-out groups do not establish effects on larger models, customer agents, other domains, or production traffic. Published questions may occur in model pretraining. Human factual-support review is pending. The dataset includes distractors and overlapping passages but is not a comprehensively adjudicated conflicting/outdated-information stress suite.

Do not tune an optimizer on these held-out failures and then call the same set untouched. The next meaningful experiment needs a newly frozen, document-disjoint benchmark, the corrected baseline fallback, and independently reviewed support judgments. No further model or paid-service spending is implied or authorized by this report.
