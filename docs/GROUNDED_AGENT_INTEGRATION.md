# Grounded agent integration

For explicit answer/evidence contracts and the new real-owner pilot package, see [source-owner onboarding](SOURCE_OWNER_ONBOARDING.md). The [latest measured validation](GROUNDED_RELIABILITY_REALWORLD_VALIDATION.md) reports excessive abstention; this guide is an integration workflow, not a model-quality guarantee.

Use the existing Python callback or HTTP v2 adapter. No paid service, new dependency or production mutation is required. The examples are Codex-authored engineering demonstrations, not independently implemented customer systems.

## Release policy

The default remains `legacy_exact`: the registered answer/reference conditions apply. Its ACCEPT is explicitly scoped and does not mean semantic grounding was verified. Configure a strict workspace with:

```json
{"settings":{"release_policy":{"version":1,"name":"strict_grounded"}}}
```

Merge this setting into the existing project; do not replace other settings. `release-check --policy strict_grounded` and API `policy: "strict_grounded"` provide explicit per-run selection. Each saved report contains its policy version, resolved requirements and definition hash. Historical reports are not rewritten.

Strict release requirements include completed execution, approved intent, exact answers, required reference coverage, citation integrity, provenance, applicability where scope permits checking, and independent semantic review. An individual benchmark task can explicitly set `requires_grounding: true` while retaining the workspace's legacy policy for unrelated tasks. Optional task metadata:

```json
{"scope":{"jurisdiction":"US","as_of":"2026-11-13","policy_scope":"online"},"behavior_constraint":"protected"}
```

Source metadata supports `authority`, `jurisdiction`, `policy_scope`, `effective_from` and `effective_to` (exclusive end). Missing applicability metadata remains unresolved when task scope requires it. With no task scope, absence of a detected mismatch is not a date/jurisdiction validation claim; independent review must still establish applicability before strict acceptance.

## Provider response contract

Use actual retrieved IDs such as `current::policy.txt#chunk0`, not invented IDs:

```json
{"answer":14,"citations":["current::policy.txt#chunk0"]}
```

Strings, finite numbers and booleans remain supported. Unknown fields, duplicate keys, empty/null/container answers, nonfinite numbers and malformed citation lists fail parsing. Legacy answer-only objects remain supported only as an explicit legacy capability; strict policies BLOCK their missing citations.

For local llama.cpp grounded calls, schema-constrained generation requires citations drawn from supplied passage IDs, with a separate `INSUFFICIENT_EVIDENCE`/empty-citations branch. The model selects the IDs; SourceROI does not append evidence it did not cite. Numbered aliases map back to canonical IDs. A valid ID is **not** semantic support. The final grammar's negative controls show that a model can cite an irrelevant warranty passage rather than abstain.

Prompt, request-shape and response-schema hashes are retained by the current provider/engine. These are integrity/configuration identifiers, not entailment scores. Existing source/model/retrieval and benchmark hashes remain in release reports.

## HTTP v2 source and execution identity

Use the existing `agent` registration with optional strengthened fields:

```json
{"agent":{"url":"http://127.0.0.1:YOUR_PORT/evaluate","protocol_version":2,"capabilities":[],"api_key_env":"","execution_identity":{"model":"APP_MODEL_ID","prompt":"PROMPT_HASH","retrieval":"RETRIEVAL_CONFIG_HASH"}}}
```

The evaluation callback supplies `agent.knowledge_manifest`, mapping canonical document IDs to the exact normalized-content fingerprints of the requested frozen/candidate configuration. The v2 adapter binds `knowledge_version` and optional `execution_identity` into the request digest. The application must:

1. Actually load the requested knowledge version rather than reusing a stale cache.
2. Apply exact source/document restrictions and supported retrieval controls.
3. Return `answer`, `citations`, explicit `retrieved_chunk_ids`, `knowledge_version`, `knowledge_manifest`, `execution_identity`, restriction acknowledgments and a boolean completion flag.
4. Reject unavailable versions and unsupported controls. If model/prompt/ranking changes, return the new actual identity; do not echo a requested identity without enforcing it.

The client rejects wrong versions/manifests, missing required traces, changed identities, malformed answers and incomplete responses. Legacy registrations without these optional fields keep their earlier contract, but cannot claim unprovided attestation. A dishonest server can fabricate hashes and traces; trusted instrumentation or external verification remains necessary.

## Runnable document example

```bash
python tools/validate_document_rag.py --root workspace/my-document-rag \
  --output docs/artifacts/my-document-rag.json
```

Choose new paths. The script creates four current/historical/regional/warranty documents, freezes a baseline, starts a read-only local process, declares intended/protected behavior and uses actual lexical ranking and day-count extraction. It exports good-candidate REVIEW (semantic review pending), bad-candidate BLOCK, and rejects a ranking-identity drift and unknown version. It stops the server. Bound: 12 HTTP requests / 45 seconds, zero model calls. This is a narrow document retrieval application, not a general semantic RAG implementation or arbitrary-agent compatibility claim.

## Review and approve intent

```json
{"expected_tasks":["returns"],"protected_tasks":["warranty"],"declared_by":"Policy owner","rationale":"Returns intentionally changes; warranty must remain correct"}
```

Use `change-plan --intent intent.json`. This declaration guides proposed revisions but does not authorize labels. Inspect `PROPOSED_CHANGE`, `PROTECTED_UNCHANGED`, `AMBIGUOUS_REVIEW` and `NO_SUPPORTED_CHANGE`, then use the existing `change-review` command with a named reviewer, rationale and explicit answer/reference decisions. A declared protected behavior cannot be revised under the same specification; change and review the intent instead. Source authority and source constraints still require review.

## Semantic review and release

```bash
python tools/release_review_packet.py export --report RELEASE.json \
  --baseline FROZEN_BASELINE --candidate CANDIDATE --output review-packet.json
# Independent reviewers complete answer claims, evidence and applicability decisions.
python -m sourceroi --project CANDIDATE release-check \
  --baseline FROZEN_BASELINE --spec CHANGE.json --approval APPROVAL.json \
  --policy strict_grounded --semantic-reviews reviewed-packet.json \
  --reviewers authorized-reviewers.json --output reviewed-release.json \
  --max-calls 12 --max-seconds 120 --allow-model-calls
```

Reviewers are an operator-authorized JSON list of IDs. Reviews are bound to exact answers, context and source versions; supported claims must quote actually supplied cited evidence and cover the full answer. Different generated outputs need fresh review. These local identity/independence declarations are not authenticated enterprise approvals. No real independent reviewers were available in this sprint.

The CLI/API/dashboard show overall verdict, separate checks, missing requirements, blocking reasons, policy/version hashes and next review actions. Exit codes remain 0 ACCEPT, 3 BLOCK, 4 REVIEW, 5 INCONCLUSIVE, 2 invalid input/configuration. Strict ACCEPT never bypasses required remaining tasks; an evaluated early failure can BLOCK before the remainder completes. No release command deploys changes or applies production repairs.
