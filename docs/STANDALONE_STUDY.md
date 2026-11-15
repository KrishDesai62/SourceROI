# Standalone SourceROI policy evaluation

SourceROI is independent of Equity Research. This workflow neither imports nor accesses that project. The earlier cross-project bridge and tests have been removed entirely.

## What the new workflow does

`python -m sourceroi --project MY_WORKSPACE study` evaluates actual model responses under different information-selection policies. All policies share the same corpus and initial BM25 candidate pool. The original runner keeps its configured context size. Comparable policies are:

| Family | Development tuning |
|---|---|
| Original | Existing top-k and context settings |
| Fixed top-k | Every k from 1 through the original k |
| Fixed context budget | 128, 256, 512 characters and fractions of the configured/default context ceiling |
| Relevance threshold | Relative score thresholds 0.25, 0.5, 0.75, 1.0 |
| Cheapest source first | Every k; requires explicit source fees, including zero |
| Simple task-aware heuristic | One passage for lookups; development-tuned k for multi-evidence/comparison questions |
| SourceROI | Development-fitted question-type routing among measured qualifying policies, query-coverage selection, normalized-text deduplication, and bounded source-subset exclusions |

The context-budget baseline controls **characters**, not exact tokenizer tokens. Actual prompt/completion tokens always come from the adapter response. SourceROI never reports character counts as measured tokens.

Question types are deterministic pre-answer features: comparison/change terms, multi-evidence terms, or lookup. The selection function receives the question, corpus chunks, configuration, and a frozen policy. It has no access to expected answers, task IDs, benchmark categories, reviewer labels, or held-out scores. Development outcomes select the policy for each type; unseen types fall back to the original policy.

Source selection is bounded by `settings.study_source_candidates` (default 8, range 0–64), and covers enumerated source-exclusion combinations. It is not a global search over every document, passage, source, and budget combination. Documents and passages are selected through retrieval, coverage, exclusions, and deduplication. Cost-aware utilities require explicit fees; unavailable prices are not treated as free.

## Benchmark and split requirements

Each JSONL task retains the existing question/expected/scoring schema and may add:

```json
{"id":"example-1","group_id":"issuer-or-document-family-A","split":"development","question":"Your independently authored question","expected":"Your independently verified answer","scoring":"exact","review_status":"independent","reviewer":"Actual reviewer identity"}
```

Use a different issuer/document family for held-out tasks. Every declared group stays within one split. Explicit group overlap is rejected; automatic splits hash group IDs and keep groups together. Groups must be assigned to keep related questions and near-duplicate documents together; SourceROI does not automatically identify every paraphrase or duplicated filing. These review fields are declarations, not authenticated proof of independent review. Do not mark generated fixtures independent.

All baseline hyperparameters and the learned routing map freeze before the first held-out call. Baselines with no qualifying development setting still get their best observed setting evaluated, with quality failures exposed. Every final policy is compared on identical held-out tasks, with one final pass per frozen policy. No failed held-out result feeds back into selection.

## Semantic groundedness and unsupported claims

Citation format alone does not establish support. This workflow scores semantic support **from explicit human claim adjudications**. It does not pretend to infer entailment from word overlap or quote presence.

The first study exports `REPORT.review.json`, containing exact answer/context snapshots and pending review entries. A reviewer decomposes each answer into non-overlapping character spans covering all non-whitespace answer text, marks each claim supported/unsupported/contradicted, and records exact supporting quotes from actually supplied, cited context. Example completed item:

```json
{
  "key": "retain the generated snapshot hash",
  "status": "complete",
  "reviewer": "actual reviewer identity",
  "claims": [
    {"start":0,"end":14,"verdict":"supported","evidence":[{"id":"report::doc.txt#chunk0","quote":"Revenue is 42."}]},
    {"start":14,"end":28,"verdict":"contradicted"}
  ]
}
```

Offsets refer to the **actual** answer and must be edited accordingly; the illustration is not a valid completed review for arbitrary outputs. `groundedness = supported claims / reviewed claims`; `unsupported_claims` includes unsupported and contradicted claims. Quote validation checks integrity only: the reviewer supplies the semantic judgment. A reviewer can be wrong, so provenance and independent spot checks matter.

Reviews are keyed to the full question, generated answer and supplied context. Changed outputs/evidence require a new review. Partial claim coverage, overlaps, missing reviewer identity, invented quotes and uncited support are rejected. Unreviewed answers remain null. With the default groundedness floor of 0.9, unreviewed studies are inconclusive, never quality-qualified. Setting a null floor through Python/API permits diagnostic experiments without semantic qualification; it does not convert missing groundedness to a measured result.

A completed review packet can be imported with `--reviews REPORT.review.json`. A repeat that generates a different answer/context will need its own review. This workflow is practical for deterministic local models and explicit human evaluation; automated semantic NLI/judge scoring is not implemented.

## No-spend execution

The user's current instruction is **no spending**. No remote provider calls were made. No generation model or provider credentials were available during this work.

Run the complete synthetic mechanics check without network calls, paid APIs, model downloads, or access to another project:

```bash
python tools/validate_study.py --output docs/artifacts/standalone-study.json
```

For an already installed **free local OpenAI-compatible model**, set `model.base_url` to its localhost URL and configure its model name:

```bash
python -m sourceroi --project MY_WORKSPACE study \
  --objective token_budget --quality-floor 0.95 --repeats 2 \
  --allow-model-calls --output workspace/study.json
```

The study command refuses non-loopback endpoints without an explicit approved spend. The optional spending argument exists for a later authorized paid study, but must not be used under the current no-spend instruction. The post-call ceiling is not a hard provider cap and may overshoot on one call.

Set `settings.max_model_calls_per_run` high enough for the preflight estimate, which includes development candidate calls and held-out comparisons across repeats. No calls occur if the estimate exceeds the cap. Timeouts/rate limits fail clearly without automatic retries. Completed experiments survive in a failed report if a later call fails; incomplete runs cannot generate final-comparison exports.

## CLI, API, dashboard, and exports

- CLI: `study`, with quality/objective/repeat controls, optional completed reviews, and JSON/CSV/Markdown/review-packet exports.
- API: `POST /api/v2/studies`, with `acknowledge_model_calls: true`. It shares the existing evaluation semaphore and persistence. Request fields include quality/grounding floors, objective, repeats, and reviews keyed by snapshot hash.
- Dashboard: Experiments → Standalone policy study. The form permits only the free-localhost execution path, shows persisted held-out comparisons, and offers JSON/CSV/Markdown/review downloads. Import reviewed claims through the CLI/API.
- Exports: `GET /api/v2/studies/RUN_ID/export?format=json|csv|markdown|review`.

Reports contain effective/requested configuration, corpus/benchmark/frozen-policy hashes, model identity/settings, per-task selections and answers, prompt/output/total usage, estimated model/data costs, cost per correct answer, mean/median/p95 latency, category and task regressions, elapsed evaluation/fit overhead, and a descriptive Pareto frontier. Paired accuracy comparisons and group-bootstrap objective intervals quantify observed uncertainty. Repeated runs are not counted as independent task groups. A tiny, synthetic, or unreviewed sample cannot establish real-world superiority.

The deployment status stays `requires_further_testing` unless a measured quality failure makes it `rejected`. No production retrieval changes are deployed. An observed advantage is not an externally validated advantage.

## Executed synthetic result

The saved run used four fictional companies, eight tasks grouped by company, two development and two held-out company groups, and two repetitions. All answers, token usage, model prices and model costs came from a deterministic synthetic extractor. **No real LLM inference occurred.** The fixture tests single-document lookups, multi-document dependencies and irrelevant commentary; it does not cover every realistic retrieval failure.

The table is the first held-out repetition, summed across four tasks. Every baseline was tuned on development data. The earlier artifact used repeated held-out runs; current studies repeat development only and run each frozen policy once on held-out tasks.

| Configuration | Accuracy | Simulated total tokens | Simulated cost USD |
|---|---:|---:|---:|
| Original | 1.00 | 452 | 0.000920 |
| Tuned top-k | 1.00 | 396 | 0.000808 |
| Tuned context budget | 1.00 | 316 | 0.000648 |
| Tuned relevance threshold | 1.00 | 396 | 0.000808 |
| Tuned cheapest source first | 1.00 | 396 | 0.000808 |
| Tuned simple task-aware heuristic | 1.00 | 330 | 0.000676 |
| SourceROI development-fitted routing | 1.00 | 290 | 0.000596 |

The earlier version invoked the synthetic adapter 328 times; current v2 uses 300 invocations with one final held-out pass per policy. There were no held-out task losses. Groundedness is unreviewed/null. The observed difference from the strongest simple baseline is 26 simulated tokens. That is a mechanics result from a constructed fixture, not evidence of real-model savings or external superiority. Two structurally similar held-out groups and deterministic simulated outputs yield collapsed bootstrap intervals; those intervals do not establish generalization.

Artifacts: [JSON](artifacts/standalone-study.json), [CSV](artifacts/standalone-study.csv), [comparison](artifacts/standalone-study.md), [pending review packet](artifacts/standalone-study.review.json).

## What remains external evidence

Representative independently reviewed questions and human claim judgments cannot be manufactured by code. Under the no-spend constraint, the next evidence run needs an already available free local generation model. A genuine paid-provider study requires a later change to the user's spending instruction. Until then, real-model savings, independently reviewed held-out quality preservation, and superiority over strong baselines remain **unproven**.
