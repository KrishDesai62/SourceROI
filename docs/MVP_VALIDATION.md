# SourceROI: public-data MVP validation

November 12, 2026. SourceROI is a standalone, domain-neutral evaluation product. No other application is imported or required. No money was spent; no paid provider calls or genuine model inference occurred in this phase.

## A. Implementation

- Added public SQuAD 2.0 and HotpotQA import/download, retaining original questions, accepted answers, evidence references, text, attribution, license links and hashes.
- Built a frozen small workspace with 8 externally annotated tasks, 44 original documents, two collections, four development and four held-out tasks. Article titles and normalized exact-text duplicates cannot cross task families. SQuAD covers single-document questions; HotpotQA provides published multi-document questions and distractors.
- Added QA exact-match normalization with multiple published accepted answers. Neither question answers nor reference evidence enter model requests or runtime policy selection.
- Added a retrieval-only audit so real-document evidence coverage can be checked without any model API. It explicitly reports answer accuracy, tokens, model costs and groundedness as unknown.
- Studies tune policies on development only; development may repeat, but every frozen policy now runs exactly once on the held-out tasks.
- Added version-2 external-agent requests with capability declarations, exact source/document/control acknowledgments and a request hash. Legacy v1 remains supported. Missing or mismatched acknowledgments invalidate affected experiments. Arbitrary policy studies remain unsupported on external agents; supported controls can be exercised through ordinary runs/ablations.
- Added a domain-neutral local reference HTTP agent. It performs source-filtered lexical extraction, not model inference, and invents no usage.
- Added actionable offline proposals: source inclusion/exclusion by question type, retrieval settings, token/cost/accuracy/grounding/latency differences, task regressions, changed passages, document exposure observations, uncertainty and an explicit deployment-testing verdict. Exposure is never presented as causal contribution.
- Improved effective configuration hashing, model identity reporting/drift detection, truncated-response rejection, usage/type validation, URL/timeout validation, partial-task retention, durable checkpoints and safe structured progress events.
- Removed the old cross-project bridge, tests, report, and setup guide. No separate application files were modified.

## B. Executed tests and commands

Before changes: `python -m pytest -q` → **71 passed, 3 skipped**. Those three skipped tests belonged to the removed optional cross-project bridge.

Final verification: `python -m pytest -q` → **91 passed**. The new public/MVP suite has **20 passing tests**. HTTP tests bind localhost and require an execution environment that permits sockets. No fixture uses paid inference.

```bash
python -m pytest -q
python -m pytest tests/test_public_mvp.py -q
python -m pytest tests/test_study.py tests/test_validation.py -q
node --check sourceroi/live/web/app.js

# Executed free public-data import; output must be a fresh directory.
python -m sourceroi public-benchmark --download --per-dataset 4 --output workspace/public-validation

# Executed retrieval-only real-document audit.
python -m sourceroi --project workspace/public-validation audit-retrieval --output docs/artifacts/public-retrieval.json

# Executed public-document/local MOCK chat HTTP end-to-end integration.
python tools/validate_public_protocol.py --project workspace/public-validation --output docs/artifacts/public-protocol.json

# Executed synthetic policy mechanics regression check.
python tools/validate_study.py --output docs/artifacts/standalone-study.json
```

The import command has already populated `workspace/public-validation`; rerunning it there intentionally refuses to overwrite the benchmark. Use a fresh output directory to rebuild.

## C. What is real, mocked, estimated, and pending

| Evidence | Status |
|---|---|
| SQuAD/HotpotQA source text and original questions/answers/evidence | Downloaded, imported and integrity-checked |
| Retrieval on that real document subset | Executed locally |
| Chat endpoint request/response integration on that subset | Executed against an explicitly identified local mock |
| Mock protocol outputs | Deliberate abstentions, no reference answers or invented usage |
| External agent v2 protocol | Tested over actual localhost HTTP using the generic lexical example |
| Genuine LLM inference | Not performed |
| Observed real-model token usage/cost savings | Unavailable |
| Groundedness of generated model answers | Unreviewed/unavailable |
| Production deployment | Not performed |

SQuAD is distributed under CC BY-SA 4.0 and supplies crowdworker questions/answer annotations: https://rajpurkar.github.io/SQuAD-explorer/. HotpotQA is distributed under CC BY-SA 4.0 with multi-hop questions and sentence-level supporting facts: https://hotpotqa.github.io/. Raw source acquisition URLs and SHA256 hashes, article attribution, adaptations, and limitations are recorded in the workspace's `provenance.json` and `ATTRIBUTION.md`. Code licensing does not replace the data license.

The HotpotQA download is a bounded first-100-row slice of the official `hotpotqa/hotpot_qa` Hugging Face validation dataset, served by its public dataset server; the local SHA256 freezes what was retrieved. The importer also supports the original raw JSON. A small deterministic first-disjoint-family subset is not a representative customer workload. Dataset annotations are independent of the evaluated model, but are not a fresh independent customer review. Unknown model pretraining overlap remains a limitation.

## D. Baseline comparison: real-document retrieval only

Every comparison uses the same four held-out tasks. Each baseline's parameters were selected using development evidence coverage, then frozen. The SourceROI retrieval proxy uses development evidence coverage too; **this is not the measured-model optimizer**. The diagnostic counts complete published supporting quotes contained in retrieved chunks.

| Policy | Tasks with all supporting quotes | Mean support-quote coverage | Context characters |
|---|---:|---:|---:|
| Original | 3/4 | 0.85 | 10,078 |
| Tuned top-k | 3/4 | 0.85 | 7,566 |
| Tuned context budget | 3/4 | 0.85 | 6,854 |
| Tuned relevance threshold | 3/4 | 0.85 | 5,111 |
| Tuned simple task-aware | 3/4 | 0.85 | 7,566 |
| Tuned cheapest-source | 3/4 | 0.85 | 7,566 |
| SourceROI retrieval proxy | 3/4 | 0.85 | 6,854 |

**No SourceROI advantage was demonstrated.** Threshold filtering preserves the same measured quote coverage with fewer characters than the proxy. Characters are not tokens, quote coverage is not answer accuracy or semantic groundedness, and complete-quote absence can result from chunk boundaries. No monetary savings can be inferred.

Artifact: [public-retrieval.json](artifacts/public-retrieval.json).

## E. Optimization/protocol report

The public-document mock chat integration executed 160 HTTP requests, with all candidate policies tuned on development and one held-out pass per frozen policy. The stub returns `INSUFFICIENT_EVIDENCE` without consulting gold answers. All six baseline families and SourceROI scored **0/4** correct on held-out tasks, with tokens, model costs and groundedness unknown. The quality floor fails, so the report says **Rejected due to quality regression** (here, failure of the required quality floor, not evidence that SourceROI worsened a capable model).

This is a successful protocol/persistence/gating test, **not a model-performance or optimization success**. End-to-end latency measures actual localhost execution, not model inference. The persisted report includes per-task answers and incomplete-response flags, effective/requested configuration hashes, model identifiers/settings, source versions, frozen policies and uncertainty. Its usage/cost columns remain null rather than reporting invented values.

Artifacts: [JSON](artifacts/public-protocol.json), [CSV](artifacts/public-protocol.csv), [human-readable report](artifacts/public-protocol.md), [pending claim-review packet](artifacts/public-protocol.review.json).

The separate synthetic mechanics test still produces simulated advantages under its artificial extractor; it is labeled `local_test_adapter` and is not promoted to real-world evidence. Current v2 executes 300 synthetic adapter invocations because held-out policies are evaluated once.

Reports choose exactly one offline proposal verdict:

- **Recommended for further deployment testing**: declared real-model evidence, qualified held-out results, reviewed semantic support, observed objective improvement, and at least ten held-out groups.
- **Rejected due to quality regression**: a measured quality threshold fails or a newly incorrect task appears.
- **Inconclusive / insufficient evidence**: missing reviews/usage, insufficient groups, incompatible model versions, mock measurements, or inadequate evidence.

Even the positive verdict is permission to investigate deployment separately, not proof of equivalence, customer ROI, or automatic approval to change production. Small-sample intervals may collapse; exposure/citations do not establish causal source importance.

## F. VS Code developer setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q

# Reuse the already imported public workspace, or build a new one:
python -m sourceroi public-benchmark --download --per-dataset 4 --output my-public-workspace
python -m sourceroi --project my-public-workspace audit-retrieval --output workspace/retrieval-report.json
```

Without network access, obtain the published SQuAD 2.0 development JSON and HotpotQA distractor development JSON independently, retain their original files/licenses, and use:

```bash
python -m sourceroi public-benchmark --squad /path/to/dev-v2.0.json --hotpot /path/to/hotpot_dev_distractor_v1.json --per-dataset 4 --output my-public-workspace
```

For a genuine model run, edit `my-public-workspace/project.json` to identify an **already installed free localhost OpenAI-compatible model** and its `/v1` URL. Do not use the `CONFIGURE_LOCAL_MODEL` placeholder. Set `measurement_kind` to `external_provider` only when actually running a model; it is an operator declaration, not authenticated proof. Configure valid explicit token prices only if applicable; null prices yield unknown cost.

```bash
python -m sourceroi --project my-public-workspace doctor
python -m sourceroi --project my-public-workspace study --quality-floor 0.95 --objective token_budget --repeats 2 --allow-model-calls --output workspace/model-study.json
python -m sourceroi --project my-public-workspace serve
```

The study command blocks remote model URLs unless a maximum spend is explicitly approved. Under the current instruction **do not approve spending or make paid calls**. A localhost endpoint can itself proxy a paid service; use a genuinely free local model. A provider hard cap is needed for any future strict monetary limit, because the software guard checks cost after each call and can overshoot on one in-flight request.

The default semantic grounding floor leaves unreviewed results inconclusive. Follow [the claim-review procedure](STANDALONE_STUDY.md#semantic-groundedness-and-unsupported-claims), complete the generated review packet independently, then import it with `--reviews workspace/model-study.review.json`. Changed answer/context snapshots need new reviews. The review's semantic judgments are human-supplied; quote checks alone do not infer entailment.

To connect an existing agent, implement [the adapter contract](AGENT_ADAPTER.md). A free domain-neutral reference server is included:

```bash
python examples/agent/server.py --project my-public-workspace --port 8777
```

For a separate evaluation workspace configuration targeting it, set:

```json
{
  "runner":"http_agent",
  "agent":{
    "url":"http://127.0.0.1:8777/evaluate",
    "protocol_version":2,
    "capabilities":["max_chunks","max_context_chars","excluded_passage_ids","deduplicate_passages"],
    "timeout_seconds":90
  },
  "settings":{
    "agent_retrieval_controls":{"max_chunks":3,"max_context_chars":2000}
  }
}
```

Merge these fields into a valid source/benchmark configuration; this partial example is not a complete project file. The lexical reference server does not generate concise model answers or token usage. It demonstrates enforceable source restrictions, controls and acknowledgments. Then run ordinary baseline/source/document ablation commands with acknowledgment:

```bash
python -m sourceroi --project my-agent-workspace run --allow-model-calls
python -m sourceroi --project my-agent-workspace run --ablate --allow-model-calls
```

Source/document ablations are controlled contribution estimates on the same tasks; they are distinct from report exposure counts. Arbitrary task-aware `study` policies cannot be executed against external agents until those policy semantics are implemented in the adapter. The system fails explicitly instead of claiming universal framework support.

Dashboard: Experiments shows persisted study results and offline verdicts; Run History opens stored evidence. Exports remain available as JSON, CSV, Markdown and claim-review packets. Progress and completed configuration evidence are checkpointed in SQLite; failed runs retain completed tasks/configurations and identify an unvalidated active request. Progress logs carry IDs/counts/phase/error types, not question text, document content, answers or keys. Requests use bounded timeouts and no automatic retries to avoid duplicating potentially billed or side-effecting requests.

## G. Remaining product gaps

- No genuine model validation or customer-specific independently reviewed benchmark has been executed.
- No real token/cost advantage over tuned baselines is established; the real-document retrieval audit favors the threshold baseline on context size.
- Public historical snapshots/distractors cover some overlap and irrelevant material, but there is no comprehensively adjudicated outdated/contradictory-document stress suite. Duplicate controls are tested structurally; this small subset is not broad robustness evidence.
- Grouping excludes identical titles/exact normalized text; it does not detect every paraphrase, entity connection, or pretraining leak.
- Semantic groundedness requires human adjudication; automatic semantic judging is not implemented.
- Causal contribution still requires controlled ablations; report passage/exposure findings are observational.
- The adapter acknowledgments are contractual assertions. A dishonest agent or hidden cache can still violate the intended experiment; run independent negative tests.
- No cross-process distributed concurrency guard, hosted authentication/multitenancy, provider hard monetary cap, encryption at rest, production load validation, or deployment automation.
- Browser interaction was not automated. API workflows, persisted exports and JavaScript syntax were verified.

## H. Next milestone

Run the frozen public workspace against a genuinely free local generation model, independently review answer/support judgments, and report the held-out tradeoff against tuned threshold/top-k/context baselines—even if SourceROI ties or loses. That is the highest-impact evidence step available without changing the no-spend instruction.
