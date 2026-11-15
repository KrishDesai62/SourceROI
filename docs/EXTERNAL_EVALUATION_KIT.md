# External evaluation: one package, two distinct review lanes

Status: **PENDING real source owners, independent reviewers and participants**. Existing IRS questions are exposed development examples. A package hash is file integrity, not authenticated reviewer identity or semantic truth.

## Build and verify the handoff (no model calls)

From the SourceROI repository, with existing dependencies installed:

```bash
export PYTHONPATH=workspace/.deps
python tools/prepare_external_evaluation.py build \
  --baseline workspace/irs-e2e/accepted \
  --candidate workspace/irs-e2e/candidate \
  --release docs/artifacts/irs-e2e/release.json \
  --output workspace/my-external-evaluation
python tools/prepare_external_evaluation.py verify --root workspace/my-external-evaluation
```

The builder verifies source versions, copies only registered documents/configuration/benchmark/snapshot, exports the existing claim packet, includes an unfilled independent protocol, and creates the three-arm study handoff. It excludes SQLite history, model weights, private runtime files and credentials. Do not edit the sealed package; copy templates to a separate working directory. The package requires this repository's tools at the recorded implementation hashes. It is not a second application or a fake independent evaluation.

## Lane 1: review existing exposed outputs

Set `BUNDLE` to your package path and `WORK` to a fresh review workspace; create `$WORK` before writing outputs. Inspect `retrospective/baseline`, `retrospective/candidate` and the original release. The benchmark's answers are development annotations, not your independent final labels.

Copy `retrospective/pending-claims.json` to `$WORK/claims.json`. Real reviewers inspect actual source statements, claimed values and citations, applicability and stale facts. Complete claim spans and exact quoted support with `supported`, `unsupported` or `contradicted`. For **ambiguous** claims, keep the item `status: pending` and add a review note explaining the ambiguity; do not force a supported judgment merely to finish a packet. Complete all required semantic dimensions only when justified.

The operator verifies actual reviewer identity/independence and supplies an authorized-reviewer JSON list in `$WORK/reviewers.json`. No real identity or approval is supplied by SourceROI.

```bash
python tools/release_review_packet.py score \
  --packet "$WORK/claims.json" --reviewers "$WORK/reviewers.json" \
  --output "$WORK/reviewed-score.json"
```

Unreviewed dimensions stay null. This is retrospective independent adjudication of exposed outputs, **not unseen final evaluation**. Do not change answers/context beneath a review; sample hashes bind them.

## Lane 2: establish new authoritative labels before final outputs

Copy `independent/annotation-template.json` into `$WORK/new-protocol.json`. A real owner supplies new original before/after documents, authoritative answers, acceptable responses/absence judgments, exact source support, periods/jurisdiction, intended changes and protected behavior. The existing protocol has required challenge topics and disjoint development/final document groups. Authoritative labelers must not see evaluated outputs before establishing final labels. Codex-generated labels or a hidden directory are not independent truth.

```bash
python tools/independent_validation.py freeze \
  --input "$WORK/new-protocol.json" --output "$WORK/frozen-independent-protocol.json"
python tools/source_owner_onboarding.py template --output "$WORK/owner-bundle.json"
# The real owner transfers approved pilot documents/tasks into the owner bundle.
python tools/source_owner_onboarding.py prepare \
  --input "$WORK/owner-bundle.json" --output "$WORK/owner-pilot"
```

Prepare the intended/protected declaration, inspect the change plan, approve or reject evaluation revisions, and connect your actual application using [the complete callback workflow](CONNECT_EXISTING_RAG.md). Freeze labels before final inference. Do not tune on the final document group. No independent final run is possible until these external inputs exist.

## Integration schema and version registration

The normative validators are `sourceroi/live/config.py`, `adapter.py`, `provider.py`, and `assurance.py`. The callback entrypoint accepts a local workspace containing:

```json
{
  "id": "external-pilot",
  "runner": "rag_chat",
  "benchmark": "benchmark.jsonl",
  "model": {"name": "YOUR_LOCAL_MODEL", "base_url": "http://127.0.0.1:8788/v1", "local_only": true},
  "settings": {"max_chunks": 3, "chunk_chars": 1100, "overlap_chars": 150,
    "max_model_calls_per_run": 8, "max_run_seconds": 90,
    "release_policy": {"version": 1, "name": "strict_grounded"}},
  "sources": [{"id": "policy", "path": "sources/policy", "authority": "REAL_OWNER",
    "jurisdiction": "US", "policy_scope": "YOUR_SCOPE"}]
}
```

`id`/source IDs must be simple identifiers; paths must be relative inside the workspace; source directories and benchmark must exist. Numeric limits must be positive/in-range. Configure explicit effective dates when questions require them. Independent answers/evidence are benchmark fields, never inputs to your evaluated app.

Create a baseline with `python -m sourceroi --project SOURCE freeze --output ACCEPTED`; create a separate candidate with the same immutable benchmark and changed source files. The existing onboarding tool does this automatically. Snapshot identity covers documents, benchmark, settings/model/agent and source metadata. Do not mutate ACCEPTED. A knowledge source version is not merely a filename or operator-chosen date.

### Callback contract

Use `tools/check_external_release.py` and the thin `examples/connected_rag/adapter.py` example. The real app receives question/ID, snapshot root, required manifest, scope and production contracts; it must report actual retrieved/cited passage IDs, observed document manifest/version, completeness and actual usage (or omit unknown usage). The exact function/response schema and strict command are in [CONNECT_EXISTING_RAG.md](CONNECT_EXISTING_RAG.md). Existing app import is intentionally supplied by the developer, not a shipped fake customer service.

### HTTP v2 contract

The existing lower-level evaluator also supports `runner: http_agent` with:

```json
{"agent": {
  "url": "http://127.0.0.1:YOUR_PORT/evaluate",
  "protocol_version": 2,
  "capabilities": ["max_chunks", "max_context_chars", "excluded_passage_ids", "deduplicate_passages"],
  "knowledge_manifest": {"policy::policy.txt": "ACTUAL_64_CHARACTER_CONTENT_FINGERPRINT"},
  "execution_identity": {"model": "ACTUAL_MODEL_ID", "prompt": "PROMPT_HASH", "retrieval": "RETRIEVAL_HASH"},
  "timeout_seconds": 60
}}
```

This is a schema illustration: replace placeholders with actual values. Remote endpoints require HTTPS; HTTP is allowed only on loopback. Capability names must match controls actually enforced. Secrets, if ever needed outside the current zero-spend/local constraints, belong in environment variables named by `api_key_env`, never config literals.

The request includes `protocol_version`, `task_id`, `question`, `allowed_source_ids`, `excluded_source_ids`, `excluded_document_ids`, `retrieval_controls`, version/identity and a restriction-bound `request_id`. The response must return matching `request_id`, `filter_applied: true`, exact `enforced_restrictions`, `retrieval_controls_applied`, actual `knowledge_manifest`/`knowledge_version`, actual retrieval IDs/citations, `execution_identity`, `response_complete`, typed `answer` and optional observed usage. `restriction_digest`/`check_acknowledgment` implement the exact acknowledgment rules; echoing them does not prove an honest application actually obeyed.

HTTP v2 is the existing low-level adapter, not a new customer integration. The strict built-in `release-check` path runs local `rag_chat` or a **trusted callback**. To use your existing HTTP app for strict release, supply a callback that invokes the existing `run_external` with the correct per-snapshot manifest and maps its observed response into the documented callback schema. Do not claim the CLI natively accepts arbitrary HTTP backends or fabricate a trace mapping. Callback task limits count logical questions; your app must enforce its own actual generation budget.

## Three-arm customer-value study

Use `study/protocol.md` and `study/outcomes-template.json`. An external operator preregisters independent people, comparable disjoint cases, counterbalanced arm order, task/source hashes, clock/exclusion rules and scoring judges. All arms receive the **same authoritative facts and review requirements**:

- `maintained_full_suite`: maintained answer/evidence checks.
- `maintained_with_diff`: those checks plus ordinary document diffs and retrieval traces.
- `sourceroi`: integrated intent, proposals, review, impact, diagnosis and release.

Use the existing event logger; the following commands are instructions for **actual participants**, not generated study evidence:

```bash
python tools/maintenance_study.py record --log "$WORK/events.jsonl" \
  --protocol-id PREREGISTERED_HASH --session-id REAL_SESSION \
  --participant-id REAL_PARTICIPANT --origin human --workflow maintained_with_diff \
  --change-id EXACT_SOURCE_TEST_HASH --event start
# Record actual review/edit actions with the same identifiers; --edit-count for actual edits.
# Finish with --event complete.
python tools/maintenance_study.py summarize --log "$WORK/events.jsonl"
```

Record integration time, active reviewer time with interruptions excluded, edits/corrections, missed failures, release correctness and diagnostic usefulness/correctness in a working copy of the outcomes template. Attach the real application's audited model calls/tokens and actual end-to-end overhead separately. Validate participant identity/activity and judge outcomes independently. Wall-clock elapsed time is not automatically active work; automation events cannot count as human sessions. No participant, timing or saving was generated by this hardening sprint.

## Failure/troubleshooting and inference gate

- **Manifest/index mismatch:** rebind your app to the actual frozen source/index; never replace observed hashes with requested hashes just to pass.
- **DRAFT/stale review:** inspect the new plan and explicitly reapprove. Do not edit an approved hash or frozen baseline.
- **REVIEW:** independent semantic/absence/reference requirements remain incomplete; numerical consistency does not confer approval.
- **INCONCLUSIVE:** incomplete execution, unknown provenance/accounting or insufficient task cap; preserve evidence and diagnose, never treat as ACCEPT.
- **Unrelated citation:** valid IDs alone do not support a claim; review exact predicate, period, units and applicability.
- **Unit/grammar/table refusal:** record the false abstention or unsupported structure. Do not relabel an answer to match the tool.
- **Runtime/test lease occupied:** do not run regression tests concurrently with an owned experiment. Ordinary tests block live model access.

Native bounded inference remains **disabled** in the new owned runner pending native server request/response correlation. `tools/local_experiment.py fixture` demonstrates controls using a clearly fake runtime only; `audit` is read-only and never repeats inference. A fixture reconciliation does not establish live Qwen accounting. No live inference is required to build, inspect, label, verify or review this package. Do not use the legacy interactive runtime/process-local historical harnesses as proof of a global generation cap.


## Table evidence in the versioned kit

The opt-in table setting, supported CSV/Markdown layouts, cell provenance and
refusal boundaries are documented in [TABLE_EVIDENCE.md](TABLE_EVIDENCE.md).
Enable it only in a new reviewed configuration. Earlier packages remain frozen;
use the matching versioned source snapshot and implementation hashes. Native
accounting is still PENDING; no live smoke was launched merely because table
validation improved. The pinned native HTTP logger registration is disabled in
the audited source, so task totals alone do not authorize a complete-accounting
claim or open the owned-runtime gate.
