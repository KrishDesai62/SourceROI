# First real-app design partner quickstart

**VERIFIED internal mechanics; PENDING independent adoption.** Use this as the single complete onboarding guide. SourceROI is a trusted single-user, single-process local beta. The commands below do not authorize paid or native model calls. Preflight and dry-run never import or call your application. The optional release step imports trusted application code and requires your explicit execution authorization and independently controlled generation/spend limits.

## 1. Verify and install the offline distribution

Tested target: Python 3.13/macOS ARM64. Other platform locks are PENDING. Obtain the new `SourceROI-design-partner-py313-macos-arm64.tar.gz`, the standalone `verify_pilot_archive.py`, and the archive's trusted SHA-256 from the operator through a trusted channel. The verifier must be obtained before executing archive-supplied code. The SHA comes from the trusted publisher; do not calculate a digest from an unknown download and treat it as authorization. No new runtime/model is included.

Start in a private directory containing the archive and trusted verifier. Read the digest from your trusted channel when prompted. The destination must not exist:

```bash
read -r -p 'Trusted archive SHA-256: ' PILOT_ARCHIVE_SHA
python3.13 verify_pilot_archive.py --archive SourceROI-design-partner-py313-macos-arm64.tar.gz --sha256 "$PILOT_ARCHIVE_SHA" --output verified-bundle
cd verified-bundle
python3.13 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links wheelhouse --require-hashes -r requirements.lock
.venv/bin/python -m pip check
BUNDLE_ROOT="$PWD"
PILOT_PY="$BUNDLE_ROOT/.venv/bin/python"
SOURCE_ROOT="$BUNDLE_ROOT/source/sourceroi-0.2.0"
"$PILOT_PY" "$SOURCE_ROOT/tools/verify_pilot_install.py" --output "$BUNDLE_ROOT/parser-check.json"
```

The extractor checks the trusted digest before parsing or writing, bounds gzip expansion and tar contents, rejects traversal/noncanonical paths, all links/devices, duplicates/collisions, unexpected files/directories and checksum mismatches, then creates a fresh private extraction. Verify before executing Python or creating working files; later bytecode/job state is not part of the sealed archive. Hashes do not certify publisher identity or absence of vulnerabilities. Never install with --system-site-packages or a PYTHONPATH pointing at the author’s machine.

For zsh, use `read -r 'PILOT_ARCHIVE_SHA?Trusted archive SHA-256: '` instead of the Bash `read -p` line, or run this command sequence in Bash. Keep the quoted path variables in the same shell session.

## 2. Start optional event recording

Use a new private working directory outside the sealed source tree. These programmatic events measure execution milestones, not human active time. They record no source text, labels, secrets or customer feedback.

```bash
PILOT_WORK="$BUNDLE_ROOT/operator-work"
mkdir "$PILOT_WORK"
cd "$SOURCE_ROOT"
"$PILOT_PY" -c 'import json,sys; json.dump({"event":"setup_started","origin":"automation","session_id":"local-onboarding"},open(sys.argv[1],"x"))' "$PILOT_WORK/event.json"
"$PILOT_PY" tools/pilot_events.py record --log "$PILOT_WORK/events.jsonl" --input "$PILOT_WORK/event.json"
```

Actual operator events are optional; copy PILOT_METRICS_TEMPLATE.json into a new working file, fill the event/session/operator and only genuinely observed fields, then use the same record command with that new file. Operator timing/identity/participation are declarations, not authenticated or independently verified facts. Never use setup elapsed time as active developer effort. See step 10.

## 3. Register your authorized sources, tasks and intended changes

Generate the unfilled owner input, then have the actual source owner edit it:

```bash
"$PILOT_PY" tools/source_owner_onboarding.py template --output "$PILOT_WORK/owner-input.json"
```

Required owner fields:

- `owner`, `labels_established_at` (actual ISO timestamp), `labels_from_evaluated_model: false`.
- `before_documents` and `after_documents`: safe `source_id`, `.txt` basename `name`, exact original `text`, and actual authority/jurisdiction/policy_scope/date metadata. Same-source documents must share metadata.
- `tasks` (1–6 for a paired pilot): stable `id`, question, pre-established `expected_before`/`expected_after`, explicit `intended_change`, exact before/after evidence `{document_id: "source_id::name.txt", quote: "literal original quote"}`, and relevant scope/answer/evidence contracts. Protected tasks keep identical expectations; missing support requires the explicit INSUFFICIENT_EVIDENCE label and absence rationale.

Do not copy synthetic demo labels or use model answers as ground truth. No independent label claim is established by the owner declaration itself. The text helper creates a fresh project; original CSV/Markdown instead uses the existing importer/opt-in table guide in docs/TABLE_EVIDENCE.md, before freezing. Do not flatten tables into unsupported facts.

Prepare and inspect without generation:

```bash
"$PILOT_PY" tools/pilot_preflight.py dry-run --owner-input "$PILOT_WORK/owner-input.json" --output "$PILOT_WORK/project"
PILOT_PROJECT="$PILOT_WORK/project"
"$PILOT_PY" -m json.tool "$PILOT_PROJECT/dry-run.json"
"$PILOT_PY" -m json.tool "$PILOT_PROJECT/accepted/snapshot.json"
"$PILOT_PY" -m json.tool "$PILOT_PROJECT/change.json"
```

This registers the before/after source files, freezes original task/label/config/source identities in accepted/, prepares candidate/, intended/protected task IDs in intent.json, evaluation proposals in change.json, and unapproved DRAFT decisions. It reports NOT_EXECUTED, no release verdict, pending review and zero model calls. It cannot certify application quality or release safety. Existing paths are rejected; failures exit nonzero with the failing boundary. Do not reuse a partially prepared directory after a failed command; inspect it and choose a fresh output path.

## 4. Inspect impact and review evaluation proposals

Read change.json source diffs, potentially affected tasks, evaluation proposals and protected expectations against the owner’s exact source evidence. The dry-run already generated the plan through the existing assurance API. To explicitly regenerate it into another new file, use:

```bash
"$PILOT_PY" -m sourceroi --project "$PILOT_PROJECT/candidate" change-plan --baseline "$PILOT_PROJECT/accepted" --intent "$PILOT_PROJECT/intent.json" --output "$PILOT_PROJECT/change-second.json"
```

Use the original change.json consistently for the remaining commands. Copy the draft; have the actual owner/reviewer supply their identity, substantive rationale, approved expected_changes/expected_evidence, protected_tasks and rejected_tasks. DRAFT is intentionally rejected. This is a manual decision, not merely a required string edit:

```bash
cp "$PILOT_PROJECT/review-decisions-DRAFT.json" "$PILOT_PROJECT/review-decisions.json"
# The real reviewer edits review-decisions.json now; do not run review until done.
"$PILOT_PY" -m sourceroi --project "$PILOT_PROJECT/candidate" change-review --spec "$PILOT_PROJECT/change.json" --decisions "$PILOT_PROJECT/review-decisions.json" --output "$PILOT_PROJECT/approval.json"
```

Original accepted labels stay frozen. Approval binds the exact specification; changed sources/config/tasks require a new plan and decision. These local names/allowlists are operator assertions, not authenticated reviewer roles.

## 5. Connect your existing RAG application

Implement your own importable `MODULE:FUNCTION` matching examples/connected_rag/adapter.py. Replace that example’s placeholder import/call with your existing read-only function. No SourceROI internal change is required for the tested callback contract. Do not use examples/connected_rag/synthetic_pilot_adapter.py as customer evidence.

The callback receives question/task_id, snapshot_root, required knowledge_manifest, scope and production contracts, not expected labels. It must return actual answer, retrieved_chunk_ids, citations, observed knowledge_manifest/version, response_complete and only observed usage. See docs/CONNECT_EXISTING_RAG.md for the complete schema. Trusted callbacks run with operator permissions and may execute code during import. Prepare mapping offline before importing the app into SourceROI.

## 6. Validate the actual offline source/index mapping

The dry-run produced mapping-template.json. Supply an **offline export from your application’s real index**, with:

- `version: 1`, actual `adapter: "your_module:answer"`, `protocol: "callback_v1"`.
- The template’s exact registered configuration_version/task_version; an actual observed `knowledge_manifest` mapping registered document IDs to fingerprints; `knowledge_version` computed with `sourceroi.live.data_ci.digest` of that observed manifest.
- `passages` mapping every registered passage ID to SHA-256 of the exact UTF-8 passage text your application has indexed. Include execution_identity if registered.

The application must use SourceROI’s registered passage identities/text or a separately verified exact index mapping; filename matches or blind manifest echoes are insufficient. This preflight supports **exact mapping only**; different chunking needs a validated mapping before proceeding. Do not generate your claimed “observed” export merely by copying SourceROI’s requested values. The tool checks declarations, not the truth of a dishonest application.

Save the real export as `$PILOT_WORK/application-index-export.json`, then:

```bash
"$PILOT_PY" tools/pilot_preflight.py check --project "$PILOT_PROJECT/candidate" --mapping "$PILOT_WORK/application-index-export.json" --output "$PILOT_PROJECT/preflight-candidate.json"
"$PILOT_PY" -m json.tool "$PILOT_PROJECT/preflight-candidate.json"
```

Repeat `template --project "$PILOT_PROJECT/accepted" --output "$PILOT_WORK/baseline-mapping-template.json"` and `check` with a separate actual baseline index export and a fresh preflight-baseline.json. Both versions must map correctly. Preflight scans registered local files/tasks but never imports customer code, starts a model or calls generation/tokenization/HTTP endpoints. Runtime application behavior remains PENDING. For HTTP declarations use protocol=http_v2 only with runner=http_agent and agent.protocol_version=2 in a separately reviewed registration; static mapping is not a live HTTP handshake. Changing configuration invalidates the earlier plan/review; register that config before step 3/freeze.

## 7. Run a release only after explicit execution authorization

STOP here unless the actual operator has authorized the trusted application import/execution and independently controlled nested model calls, spend, deadlines and read-only data access. Logical task caps do not enforce hidden provider generations. Native SourceROI execution remains gated; paid calls remain unauthorized. The following is an explicit operator action, not an instruction to bypass those gates.

When authorized, with your actual importable module (replace the adapter value), run:

```bash
"$PILOT_PY" tools/check_external_release.py --authorize-execution --baseline "$PILOT_PROJECT/accepted" --candidate "$PILOT_PROJECT/candidate" --spec "$PILOT_PROJECT/change.json" --approval "$PILOT_PROJECT/approval.json" --adapter your_module:answer --output "$PILOT_PROJECT/release.json" --max-calls 12 --max-seconds 120
PILOT_RELEASE_EXIT=$?
printf 'Release command exit: %s\n' "$PILOT_RELEASE_EXIT"
```

No flag means refusal **before customer import**. Invalid paths/specification/review or adapter imports produce actionable nonzero errors. The flag expresses explicit dispatch consent, not native accounting proof, human semantic approval or paid-spend authorization. Exit 0=ACCEPT, 3=BLOCK, 4=REVIEW, 5=INCONCLUSIVE; setup failures are nonzero. Do not treat a policy exit as transport success or change a verdict to finish onboarding. Missing semantic reviews remain REVIEW, protected regressions BLOCK, incomplete execution is INCONCLUSIVE where applicable. Use fresh paths for every authorized rerun.

## 8. Export independent claim review and inspect reports

Only after an actual release artifact exists:

```bash
"$PILOT_PY" tools/release_review_packet.py export --report "$PILOT_PROJECT/release.json" --baseline "$PILOT_PROJECT/accepted" --candidate "$PILOT_PROJECT/candidate" --output "$PILOT_PROJECT/pending-claims.json"
"$PILOT_PY" -m json.tool "$PILOT_PROJECT/release.json"
"$PILOT_PY" -m json.tool "$PILOT_PROJECT/pending-claims.json"
"$PILOT_PY" -m sourceroi --project "$PILOT_PROJECT/candidate" knowledge-timeline
```

Open release.md for the human-readable explanation. Inspect executed/unexecuted tasks, exact versions, citations, source/cell evidence, protected regressions, diagnosis hypotheses, required/missing checks and next actions. A successful export is not semantic approval. Actual independent reviewers complete pending claim/span/support/applicability fields; the operator supplies a real authorized reviewer list. Keep absent reviewers/feedback unfilled. Review packet scoring and any authorized rerun are documented in docs/CONNECT_EXISTING_RAG.md; reruns use new outputs and separately authorized/accounted executions. Never silently revise frozen labels or reuse stale semantic reviews.

## 9. Finish setup or record an error

After the actual offline setup/preflight succeeds, record setup_completed with the same origin/session, using a new event input file. Record integration_error details if a command failed, and adapter_edit with actual edit count when known. Do not include secrets or source/answer contents in event logs. Use release_result only for an observed report verdict, not a planned outcome.

```bash
"$PILOT_PY" -c 'import json,sys; json.dump({"event":"setup_completed","origin":"automation","session_id":"local-onboarding"},open(sys.argv[1],"x"))' "$PILOT_WORK/setup-complete.json"
"$PILOT_PY" tools/pilot_events.py record --log "$PILOT_WORK/events.jsonl" --input "$PILOT_WORK/setup-complete.json"
"$PILOT_PY" tools/pilot_events.py summarize --log "$PILOT_WORK/events.jsonl"
```

## 10. Optional real operator feedback and remaining limits

PILOT_METRICS_TEMPLATE.json is unfilled. Operator fields support explicit active_seconds, adapter_edits, report_usefulness, source_owner_participated, reviewer_participated and actual release_verdict. Use event=active_time for genuinely measured nonoverlapping active intervals; no automatic elapsed-time inference occurs. Use event=report_feedback or participation only after actual participation. Start a distinct operator-origin session with setup_started and the actual operator declaration before recording those events. Automation cannot populate human time, usefulness or participation. Summaries distinguish declared active time from independently verified time (still null), do not infer savings, and do not infer adoption from a log entry. Keep the existing equal-input three-arm study unchanged; human studies require real participants.

Read docs/PILOT_OPERATIONS.md and PRODUCTION_BLOCKERS.md before any service use: no authenticated multi-user access, no tenant isolation, no parser process sandbox, no durable multi-writer/idempotent jobs, no complete full-workspace disaster-recovery proof, no verified native correlation. Keep one trusted local operator/process, reviewed bounded sources and private storage; no production/public deployment. Real application compatibility, independent semantic quality, customer value and comparative superiority remain PENDING until actually measured.
