# Source-owner pilot: no SourceROI internals to edit

Status: **waiting for a real source owner, independently established labels and reviewers**. This guide is a reproducible handoff, not a customer result. No model runs or downloads occur during preparation.

## 1. Fill the input bundle

```bash
python tools/source_owner_onboarding.py template --output owner-bundle.json
```

A real owner fills `before_documents`, `after_documents` and 1–6 tasks, alongside owner identity, label timestamp and a declaration that labels were not derived from the evaluated model. Each document has a stable `source_id`, safe `.txt` basename, text and authority/jurisdiction/date/policy-scope metadata. Use separate source groups for documents with different metadata. Limit: 50 documents per version; 6 MB input bundle.

Each task supplies question, unmodified authoritative `expected_before`/`expected_after`, `intended_change`, version-specific evidence and optional answer/evidence contracts and scope. Protected behavior cannot contain a changed expected value. Numeric labels must satisfy a numeric contract; the tool will not change `14 days` to `14`. Structured expectations are JSON strings under a closed flat schema and explicit `structured_exact` grading.

Example task shape (illustrative only, not independent labels):

```json
{
  "id":"returns",
  "question":"What is the applicable return period?",
  "expected_before":"30",
  "expected_after":"14",
  "intended_change":true,
  "answer_contract":{"version":1,"type":"numeric"},
  "evidence_contract":{"version":1,"subject_aliases":[["return","returns","returned","sent back"]]},
  "scope":{"jurisdiction":"US","as_of":"2026-11-13","policy_scope":"online"},
  "evidence_before":[{"document_id":"policy::returns.txt","quote":"30 days"}],
  "evidence_after":[{"document_id":"policy::returns.txt","quote":"14 days"}]
}
```

Evidence quotes must occur in the correct supplied version. An independently established abstention label can use empty evidence only with a nonempty `absence_rationale_before` / `absence_rationale_after`; this declaration still needs review and is not a proof of absence. Necessary alias groups use OR within a group and AND across groups. Validate synonym completeness: aliases can reject real paraphrases and never prove entailment.

## 2. Prepare a local pilot

```bash
python tools/source_owner_onboarding.py prepare --input owner-bundle.json \
  --output workspace/owner-pilot
```

This atomically creates:

- `accepted/`: immutable baseline with source/test/config hashes.
- `candidate/`: after documents, with the **same original benchmark** as baseline.
- `intent.json`: owner-declared expected versus protected task IDs.
- `review-decisions-DRAFT.json`: explicit owner-supplied after expectations, unapproved.
- `onboarding.json`: bundle/provenance digest and pending review status.

No `approval.json` is produced. No model is called or started. Local model settings reference the existing approved localhost Qwen runtime; preparation does not install it. Budget defaults are 12 paired generation calls / 120 seconds, so the pilot supports up to six questions. Identity/independence declarations require operator verification.

## 3. Inspect and explicitly approve

```bash
python -m sourceroi --project workspace/owner-pilot/candidate change-plan \
  --baseline workspace/owner-pilot/accepted --intent workspace/owner-pilot/intent.json \
  --output workspace/owner-pilot/change.json
```

Inspect actual fact changes, proposals, protected behavior, source authority, scope/date conflicts and original evidence. Complete the draft review rationale after a real review; a `DRAFT` rationale is deliberately rejected.

```bash
python -m sourceroi --project workspace/owner-pilot/candidate change-review \
  --spec workspace/owner-pilot/change.json \
  --decisions workspace/owner-pilot/review-decisions-DRAFT.json \
  --output workspace/owner-pilot/approval.json
```

This is the existing explicit approval boundary, not a generated label becoming truth automatically. Protected benchmark behavior cannot be silently overridden.

## 4. Run and inspect strict checks

After starting the already-installed local model yourself, or connecting a compatible existing agent:

```bash
python -m sourceroi --project workspace/owner-pilot/candidate release-check \
  --baseline workspace/owner-pilot/accepted --spec workspace/owner-pilot/change.json \
  --approval workspace/owner-pilot/approval.json --policy strict_grounded \
  --max-calls 12 --max-seconds 120 --allow-model-calls \
  --output workspace/owner-pilot/release.json
```

Review raw/normalized answers, type violations, retrieval/citation IDs, software-versus-model abstention, applicability, conflicts and required semantic review. Strict cannot be silently downgraded. Empty-context generation is disabled. A valid citation or alias is never semantic approval. An over-abstaining model can still block a legitimate update; inspect that failure rather than changing labels to fit it.

## 5. Independent review and studies

Export actual answer/context packets through `tools/release_review_packet.py`, obtain authorized independent claim adjudication and use the existing `--semantic-reviews` / `--reviewers` inputs. Different answers/context require a matching review. Actual human review is absent from this delivered template.

See [grounded agent integration](GROUNDED_AGENT_INTEGRATION.md) for existing callback/HTTP version and identity checks, and [maintenance study](EVALUATION_MAINTENANCE_STUDY.md) for equal-authority human workflows. The pilot bundle is not an independently validated hidden final set; use the separate annotation/freeze protocol for that. No production deployment or repairs are automatic.
