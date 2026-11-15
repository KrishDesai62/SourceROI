# Downstream analytical isolation — closure evidence

Status: **VERIFIED internally for fixed supported operations; PRELIMINARY security assurance.** No independent sandbox assessment or semantic validation.

`analysis_boundary.py` reuses the existing parser worker, steward, macOS profile and resource supervisor. Fixed dispatch now covers BM25 search, context policy selection, reference/evidence prechecks, Data CI coverage, source inventory/diffs, intent/change impact proposals and diagnosis. Existing isolated regex grading and source-bound numerical/table extraction remain in place. Ablation exclusion membership uses sets; optimization and Data CI invoke the bounded shared operations. Control-plane persistence, authenticated principals, approval receipts and semantic judgments remain in the parent.

Each worker has CPU limits 8/9 seconds, wall deadline 15 seconds, file size 48 MiB, descriptors 64 and core dumps disabled. Input documents are at most 12 MiB each; combined source/request input is bounded at 128 MiB; JSON request/output is at most 48 MiB. Analytical chunk lists are limited to 50,000. Parent serialization and bounded bookkeeping still occur outside the sandbox. Memory is sampled process-group RSS at 512 MiB, **not a hard allocation guarantee** on macOS. Cache limits are 256 entries and 32 MiB of serialized results per process, not aggregate parent-memory quotas.

Selected passages must retain their exact registered fields and identities; scores must be finite, duplicates are rejected. Coverage is range checked. Prechecks cannot assert semantic entailment. Change proposals are checked against independently loaded frozen tasks, original source identities, configuration hashes, protected intent and pending-review semantics before returning to trusted review code. Source snapshots use descriptor-relative traversal with no symlink following; both original source roots are inaccessible to the shared analysis worker.

Trusted local Python tokenizer callbacks remain a compatibility exception and execute in the trusted parent. The declared authenticated/fixture path sets strict isolation and rejects these callbacks. This is not a claim that arbitrary locally supplied Python code is sandboxed.

Acceptance: `tests/test_closure_resources.py` includes an actual expensive 4,000-chunk retrieval interrupted at a 0.15-second deadline, oversized input rejection, forged-evidence rejection, unsupported operation rejection, protected-root enforcement and directory-substitution denial. Existing eight-feature tests invoke these common boundaries. See `docs/artifacts/phase3-closure/final-boundary-tests.txt` and the final full-suite log.

Remaining blockers: independent review of worker contracts/profile exceptions; hard aggregate memory protection on the supported deployment platform; validation with larger independently selected workloads. These tests do not prove semantic accuracy or quality-preserving optimization.
