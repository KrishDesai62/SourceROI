# Try SourceROI with your existing RAG application

This uses the existing source-owner workflow and trusted callback interface. No new RAG app, server, cloud account or paid service is supplied. **No independent customer integration or reviewer was available during development.** The shipped adapter bridge and CLI are exercised with explicitly synthetic test fixtures; your application's compatibility still needs validation.

## 1. Register source versions and authoritative behavior

Run from the SourceROI repository with Python and the existing dependencies installed. For the local PDF dependency setup used in development, `export PYTHONPATH=workspace/.deps`.

```bash
python tools/source_owner_onboarding.py template --output my-owner-bundle.json
```

A real source owner fills this file with original before/after document text, source authority/scope/dates, questions, independently pre-established expected answers, exact supporting quotes, and which behaviors should change or remain protected. The current onboarding format accepts safe text document basenames and up to six tasks for a paired twelve-task pilot. Do not use model answers as labels. For missing evidence, supply an explicit abstention label and absence rationale. This pilot is not an independently hidden final set.

```bash
python tools/source_owner_onboarding.py prepare \
  --input my-owner-bundle.json --output workspace/my-owner-pilot
```

This creates `source/`, a frozen `accepted/`, `candidate/`, `intent.json`, `review-decisions-DRAFT.json` and an onboarding manifest with zero inference. Defaults enforce strict grounded release. The baseline source snapshot is not a claim that the agent's baseline quality is acceptable. Inspect it with `python -m sourceroi --project workspace/my-owner-pilot/candidate doctor` (this does not generate answers).

## 2. Inspect proposed changes, intended behavior and protected behavior

```bash
python -m sourceroi --project workspace/my-owner-pilot/candidate change-plan \
  --baseline workspace/my-owner-pilot/accepted \
  --intent workspace/my-owner-pilot/intent.json \
  --output workspace/my-owner-pilot/change-plan.json
```

Inspect source diffs, impacted questions and evaluation proposals. `intent.json` declares expected/protected task IDs; it does not authorize new answers automatically. Review the source quotes before approving expectation changes. Labels in the frozen baseline remain immutable.

## 3. Explicitly review or reject evaluation proposals

Copy `review-decisions-DRAFT.json` to `review-decisions.json`, then have the real owner review every impacted question. Supply the real reviewer identity and a substantive rationale; remove the DRAFT marker only after actual review. Keep `expected_changes` and replacement `expected_evidence` only for authorized changes. Keep unaffected expectations in `protected_tasks`; use `rejected_tasks` for proposals explicitly rejected by the reviewer. Rejected/unresolved behavior can remain REVIEW; rejection does not make a failed answer correct.

```bash
python -m sourceroi --project workspace/my-owner-pilot/candidate change-review \
  --spec workspace/my-owner-pilot/change-plan.json \
  --decisions workspace/my-owner-pilot/review-decisions.json \
  --output workspace/my-owner-pilot/approved-review.json
```

Stale source/configuration/test versions or altered bound decisions are rejected. Do not edit a frozen snapshot or approved specification to make execution pass.

## 4. Connect your existing application

Implement a trusted local Python function with the signature in [the thin adapter example](../examples/connected_rag/adapter.py). The example's `your_existing_rag` import is intentionally a placeholder for **your existing application**, not an implemented or simulated service. Replace only that import/call; use the real read-only RAG path.

SourceROI passes question/ID, source snapshot root, required manifest, scope and production contracts. It does **not** pass expected answers or annotated answer quotes. Your function must use the supplied frozen corpus, retrieve, generate/abstain and return its actual trace. The application must use the same indexed passage text/IDs (available through `scan_sources(read_config(snapshot_root))`), or provide a validated exact mapping; filename-only mappings or fabricated retrieval IDs are unsafe. If you cannot bind an existing vector index to those versions, stop and build a verified snapshot/index mapping before claiming version-aware evaluation.

Response structure (schema illustration, not a recorded customer result):

```python
{
    "answer": actual_answer,                    # JSON scalar/object per answer contract
    "citations": actual_cited_passage_ids,
    "retrieved_chunk_ids": actually_supplied_passage_ids,
    "knowledge_manifest": observed_document_hashes,
    "knowledge_version": digest(observed_document_hashes),
    "response_complete": True,
    # Optional actual usage; omit unknown values, never put estimates here.
    "usage": {"prompt_tokens": observed_prompt_tokens,
              "completion_tokens": observed_completion_tokens},
    # Required if registered in cfg.agent.execution_identity:
    "execution_identity": actual_model_prompt_retrieval_identity,
}
```

Use `sourceroi.live.data_ci.digest` for the manifest digest. `observed_document_hashes` must come from documents the application actually used, rather than blindly echoing the requested manifest. Assertions are not cryptographic proof against a dishonest application. The bridge checks source drift, exact manifest/version, index membership, response completeness, shape and usage. A valid retrieved citation still requires claim-level support review. Unknown usage stays null.

## 5. Run the strict release check and export CI reports

```bash
python tools/check_external_release.py \
  --baseline workspace/my-owner-pilot/accepted \
  --candidate workspace/my-owner-pilot/candidate \
  --spec workspace/my-owner-pilot/change-plan.json \
  --approval workspace/my-owner-pilot/approved-review.json \
  --adapter examples.connected_rag.adapter:answer \
  --output workspace/my-owner-pilot/release.json \
  --max-calls 12 --max-seconds 120
```

This imports and runs your **trusted application code**. Use only an authorized local/no-spend backend under the current execution constraints. The command does not start services or provide credentials. The release call cap counts logical before/after question executions, not hidden nested provider calls; your application must independently enforce actual generation/spend/time caps. A synchronous callback can overrun an in-flight deadline; the result then cannot ACCEPT. Do not infer billing protection from logical task counts.

Outputs: `release.json`, `release.md`, SQLite history, task-level citation/applicability/evidence checks, and failure causes. The summary includes `verdict`, `exit_code`, `report`, and `semantic_review`. Exit codes: **0 ACCEPT, 3 BLOCK, 4 REVIEW, 5 INCONCLUSIVE; malformed setup exits nonzero**. Use the exit status in local CI/code review. No deployment is performed. In the absence of required independent review, a factual pass is normally REVIEW, never automatic strict ACCEPT. Blocking regressions remain BLOCK. Incomplete execution/provenance is INCONCLUSIVE.

## 6. Review claims and applicability

```bash
python tools/release_review_packet.py export \
  --report workspace/my-owner-pilot/release.json \
  --baseline workspace/my-owner-pilot/accepted \
  --candidate workspace/my-owner-pilot/candidate \
  --output workspace/my-owner-pilot/pending-claims.json
```

Independent reviewers complete exact claim spans/quoted support, answer correctness, citation support, dates/jurisdiction and stale-fact judgments. The operator authorizes real independent identities in a JSON list. Do not certify independence merely by filling an allowlist. Unreviewed dimensions remain null. With completed reviews, rerun the same frozen release into a **new** output using `--review-packet completed-claims.json --reviewers actual-authorized-reviewers.json`; do not mutate sources or replace old reports. This normally executes the application again: freeze generation settings and account for those calls separately. A changed answer/context invalidates its old semantic review. No second application run was fabricated during development.

## 7. Inspect diagnostics and review optional repairs

```bash
python -m sourceroi --project workspace/my-owner-pilot/candidate knowledge-timeline
```

Inspect `release.json` task diagnosis, source changes, next actions and cause hypotheses. Review a proposed repair in an isolated candidate, make a new plan and review, and use the existing `assurance.verify_repair(...)` API with the same trusted callback. It verifies both approved interventions and protected behavior; it does not mutate production. An optional `diagnose --calculation-spec ...` proposal is REVIEW-only. Do not treat a diagnosis as a proven cause or apply it automatically.

## 8. Optional explicit source-calculation mode

Default `settings.answering_mode` is `model`. `source_calculation` is a separately evaluated opt-in built-in sentence-index mode. Each task needs a version-1 `calculation_contract` containing operation and literal subject/predicate/unit/period operands, plus explicit `calculation_authorization` from `facts.authorize(question, scope, contract, reviewer=..., rationale=...)`. The workspace's `calculation_reviewers` allowlist must authorize that operator. A declaration contains no expected values. Authorizations bind the exact question, scope and formula; they assert task intent, not independent semantics. Missing approval, ambiguous/missing/conflicting evidence or unsupported grammar cannot yield a factual calculated answer. Only narrowly supported lookup, two-input add/subtract and comparisons are implemented; arbitrary multi-step formulas are rejected.

Keep calculation and model runs distinct in reports. Changing answering/indexing mode changes configuration identity and needs review. Literal calculation consistency can BLOCK wrong or unrelated cited numerical claims; it does not grant independent semantic approval. Real reviewers, genuinely independent held-out document groups and the existing [three-arm study](ENGINEERING_SPRINT_HANDOFF.md) remain necessary before claiming customer maintenance or reliability advantages.
