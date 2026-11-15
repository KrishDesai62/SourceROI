# Integrate an existing RAG/agent runtime

The bundled `rag_chat` engine uses lexical retrieval + OpenAI-compatible chat. For **real production agent experiments**, you should evaluate your current pipeline rather than replacing it with SourceROI's BM25 retriever.

## Workspace config

In the workspace `project.json`, set:

```json
{
  "runner": "http_agent",
  "agent": {
    "url": "https://your-internal-agent.example.com/sourceroi/evaluate",
    "api_key_env": "SOURCEROI_AGENT_API_KEY",
    "timeout_seconds": 90
  }
}
```

All other fields, including `benchmark`, `sources` and `settings`, remain in the project. Environment variable contents never appear in config or API responses.

### POST request sent by SourceROI

```json
{
  "task_id": "f01",
  "question": "What was FY2025 reported revenue?",
  "allowed_source_ids": ["filings", "industry"],
  "excluded_source_ids": ["earnings"],
  "excluded_document_ids": ["filings::old_report.pdf"],
  "request_filter_ack": true
}
```

For valid source ablation, **your adapter must enforce all exclusions during retrieval, tool calls, external data acquisition, and any memory/cache reads**. You cannot simply accept the filter parameters and return an unfiltered cached answer. Disable or partition caches appropriately, and make sure hidden prompts and agent memory cannot reintroduce excluded information.

### Expected response

```json
{
  "answer": "920",
  "citations": ["filings::annual_report.pdf"],
  "filter_applied": true,
  "model": "your-company-research-agent-v3",
  "usage": {
    "prompt_tokens": 1850,
    "completion_tokens": 175,
    "model_cost_usd": 0.0011,
    "data_cost_usd": 0.03
  }
}
```

- `answer` (string) and `filter_applied: true` are required.
- `citations` should identify actual evidence, when your adapter can provide them.
- `usage` is optional. Report missing costs as missing, rather than guessing.
- `data_cost_usd` should reflect actual paid-source calls, if observable.
- Latency is independently measured by SourceROI around the HTTP call.
- The `filter_applied` acknowledgment is a **contractual/integration assertion**, not cryptographic proof. Validate it with deliberate negative tests before trusting results.

## Important pitfalls

1. **Cached data leakage:** A filtered source may still appear in an answer generated from a cached prior retrieval.
2. **Stateful agents:** One evaluation can change memory or tool state for another. Use isolated or resettable runs.
3. **Tool side effects:** Evaluations should run in a non-destructive sandbox. Never allow test tasks to make real purchases, send emails, or mutate production records without explicit controls.
4. **Different task distributions:** Your benchmark must represent high-value real workloads, not easy questions selected to make one source look useful.
5. **License rights:** Check external data providers' allowed AI use and evaluation conditions before sending content to a model service.

The adapter is an integration contract, not a fake working connection to a system you haven't supplied. You will need to implement its request handler in your actual backend.


## Optimization validation contract

Set `measurement_kind` in project.json to `external_provider` for a real endpoint or `local_test_adapter` for a simulator. The default is `unverified_endpoint`. This is operator-declared provenance, not independent verification.

Use representative tasks with explicit `split` values (`development` / `heldout`) and independent answer keys. SourceROI sends only question/task ID and filtering constraints; expected answers and split scores are never sent to the agent. Source selection is frozen before held-out execution. Baseline and candidate runs must use isolated agent sessions with equivalent execution settings.

Citations may be allowed source IDs or document/chunk IDs prefixed by an allowed source ID (`filings::annual_report.pdf#chunk0`). Citations to excluded documents or sources are invalid. Valid identifiers do not establish semantic support.

The legacy v1 HTTP contract supports source/document exclusions only. Version 2 adds capability-scoped top-k, context-budget, deduplication and passage-exclusion controls with exact acknowledgments, described below. Arbitrary task-aware study policies remain unsupported on external agents; the optimizer does not claim to apply those policies merely because an agent supports top-k.

The built-in `rag_chat` runner supports `settings.max_chunks`, `settings.max_context_chars` (a character budget, not a tokenizer budget), and `settings.deduplicate_passages` (exact normalized-text duplicates). The Python `evaluate_variant(..., exclude_passages=[chunk_id])` interface filters passages before retrieval. These controls affect actual submitted context. Only returned usage counts as observed tokens; character budgets are never reported as actual token savings.

Requests use configured timeouts and fail on rate limits or provider errors. There are no automatic retries: ambiguous completion timeouts can already have incurred charges, and arbitrary external-agent calls may have side effects. Rerun an isolated experiment after inspecting failures. Partial optimization reports are persisted with failed status; they never produce deployment approval.

Configure a small `settings.max_estimated_model_cost_usd` and explicit model token rates before a paid experiment. The guard checks reported costs after every call and stops further requests, but cannot enforce a hard provider spending limit for the in-flight call. Use a provider-enforced budget if a strict monetary cap is required.


## Standalone built-in RAG policy studies

For the independent SourceROI task-aware workflow, grouped benchmark schema, human semantic grounding review, no-spend local execution and exports, use [the standalone study guide](STANDALONE_STUDY.md). Policy studies require `rag_chat`; arbitrary external HTTP agents do not yet expose the required retrieval-policy capabilities. They fail explicitly instead of silently claiming to apply those policies.


## Version 2: capability-scoped retrieval controls

The v1 `filter_applied: true` contract is preserved. For stricter experiments, set `agent.protocol_version` to 2 and declare a `capabilities` list drawn from `max_chunks`, `max_context_chars`, `excluded_passage_ids`, and `deduplicate_passages`. Request controls through `settings.agent_retrieval_controls`. Built-in external evaluations also forward explicit context/deduplication settings and passage exclusions when v2 supports them. Unsupported controls fail before a request.

V2 adds `protocol_version: 2`, a `retrieval_controls` object, and a SHA256 `request_id` over task/question/restriction/control fields. The response must return the same request ID, `filter_applied: true`, `enforced_restrictions` containing the exact requested allowed/excluded source and excluded document lists, and `retrieval_controls_applied` containing exactly the requested controls. An omitted, stale, partial, or mismatched acknowledgment invalidates the experiment. Identical acknowledgments are assertions by the adapter, not independent proof of enforcement.

`examples/agent/server.py` is a domain-neutral, loopback-only reference implementation that applies exclusions before retrieval and enforces declared controls. It extracts original passages without model inference; usage is omitted rather than fabricated. Its full HTTP contract is exercised by automated tests. Setup and an example merged configuration are in [the MVP developer guide](MVP_VALIDATION.md#f-vs-code-developer-setup).

An existing application's integration must also isolate/reset caches, memory and tool state; filtered-out information must not re-enter through hidden paths. Arbitrary `study` policy selection remains unsupported by the external HTTP interface. Supporting top-k/context controls is not universal support for SourceROI's coverage or learned-routing policies.
