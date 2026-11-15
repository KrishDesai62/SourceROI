# Validation and differentiation sprint

Historical sprint report. The [subsequent grounding sprint](RELIABILITY_GROUNDING_SPRINT.md) adds strict release requirements and citation generation while preserving this sprint's negative results. Independent grounding and human-effort validation remain pending.

November 13, 2026. Existing standalone SourceROI; zero external spending, no new model downloads, cloud resources, paid credits or production changes. This sprint validates the existing workflow rather than expanding its product scope.

**Finding:** supported numeric JSON answers now normalize correctly. With equivalent approved change information, SourceROI **ties a maintained full-suite answer-plus-evidence baseline** on the exposed engineering controls. Reduced total human maintenance effort, independent semantic reliability, customer compatibility and competitive superiority remain unproven.

## 1. Repository verification and changes

The starting suite actually passed **149 tests in 6.88 seconds** with localhost socket access. Reviewed the current provider, HTTP adapter, engine, release orchestration, grounding review, prior fair/unfair reports and original smoke output. Historical claims were not accepted as current measurements. No Git metadata is present in this workspace, so no Git diff/commit claim is made.

Changes:

- `live/provider.py`: explicit scalar answer normalization and strict answer-object/citation validation; malformed objects are incomplete, not apparently successful answers. External scalar normalization and explicit completion flags receive the same protections.
- `live/adapter.py`: optional v2 knowledge-version request digest and acknowledgment. Legacy agents keep their existing contract; version checking requires v2.
- `live/provider.py` / `engine.py`: verify an optional requested file manifest and retain actual external retrieval IDs/version proof in task history. A matching citation ID alone is not invented as a retrieval trace.
- `live/reliability_review.py`: deterministic citation-ID/scope/date integrity separated from externally supplied human semantic/claim adjudication, reusing existing claim-span and quote checks.
- Validation scripts, a standard-library separate-process record RAG example, external annotation/review handoff and adversarial tests. No new dashboard, optimization search, service dependency or architectural rewrite.

All eight existing features remain: intent-aware changes, review-bound evaluation maintenance, impact mapping, release assurance, diagnosis/repair, history, dataset valuation and optional cost optimization. CLI/API/dashboard/history/benchmark regression tests remain in the full suite.

## 2. Response normalization and real-model rerun

Supported answer values are nonempty strings, finite JSON numbers and booleans. Numbers preserve their JSON numeric text; booleans become `true`/`false`, never silently `yes`/`no`. Nulls, arrays/objects as answers, nonfinite values, duplicate keys, unknown answer-object fields and malformed citations fail validation. Whole fenced JSON is supported. No expected label was edited.

For compatibility, answer-only JSON objects remain supported and receive an empty citation list. This is **not** a citation-completeness or entailment pass. Provided citations must be nonempty string IDs; unknown IDs are tracked separately against supplied context. Malformed chat output now has `response_complete=false`, preventing successful grading/release acceptance. External explicit `response_complete=false` is also preserved.

The original result is untouched: [historical failed smoke](artifacts/knowledge-local-smoke.json). The bounded repaired run is separate: [repaired smoke](artifacts/knowledge-local-smoke-repaired.json).

| Measure | Original | Repaired |
|---|---:|---:|
| Registered-check verdict | BLOCK | ACCEPT |
| Baseline exact answers correct | 1/2 | 2/2 |
| Candidate answers correct under approved revision | 1/2 | 2/2 |
| Actual model generation calls | 4 | 4 |
| Provider-reported total tokens | 848 | 848 |
| Measured execution seconds | 1.592846 | 1.664400 |
| Responses with no citations | 4/4 | 4/4 |
| External API spend | $0 | $0 |

The original warranty answer `{"answer":365}` had been retained as raw text. The repaired parser returns `365`. Returns still changes 30→14. Original-label hashes, baseline document fingerprints and recorded model generation settings match; [summary assertions](artifacts/validation-sprint-summary.json) verify these properties. Equal token counts are observations, not an optimization benefit.

Reused installed Qwen2.5-1.5B-Instruct Q4_K_M and llama.cpp b12345 on localhost, one slot, four threads, context 4096, seed 1729, temperature 0, max output 384. The new run was capped at **four calls / 60 seconds** and made no additional model downloads. The server was stopped afterward. Hardware/electricity and inference dollar costs are unpriced; only external API expenditure is zero.

The repaired ACCEPT covers the existing exact-answer and retrieved-reference checks. **Semantic/citation reliability separately remains REVIEW: zero of four outputs have independent claim adjudication, and none contains citations.** This is not permission to deploy or proof of grounding.

## 3. Fair maintained-baseline comparison

[Raw comparison, authority inputs, per-case measurements and full matrices](artifacts/validation-sprint-fair-comparison.json). All five methods receive the **same approved answer changes, replacement references, protected expectations and unresolved-intent information**. The 13 scenarios are previously exposed Codex-authored fixtures, not independent or unseen final validation.

| Approach | Blocking cases detected / 8 | Legitimate false blocks / 3 | REVIEW | INCONCLUSIVE | Equivalent task executions |
|---|---:|---:|---:|---:|---:|
| A. Manually updated answer regression | 7 | 0 | 2 | 0 | 54 |
| B. Reference coverage with approved updates | 7 | 0 | 2 | 0 | 54 |
| C. Maintained full-suite answer + reference checks | 8 | 0 | 2 | 0 | 54 |
| D. Lexical/topic/reference/trace selection + maintained checks | 8 | 0 | 2 | 3 | 32 |
| E. SourceROI reviewed proposal/release workflow | 8 | 0 | 2 | 0 | 54 |

A misses the correct-answer/lost-support control. B misses stale answer interpretation when the new evidence is retrieved. C combines the two ordinary checks and matches SourceROI. D includes new-document topic overlap, prior retrieved passages, reference dependencies and configuration/metadata broadening. It misses zero affected task occurrences on these controls, but passing partial runs cannot certify unexecuted tasks: the three legitimate cases remain INCONCLUSIVE. Its task reduction is **replay-scored**, not a measured separately executed inference-speed improvement or demonstrated safe release-cost saving.

Full confusion matrices below use prediction order **ACCEPT, BLOCK, REVIEW, INCONCLUSIVE**:

| Method | Actual ACCEPT (3) | Actual BLOCK (8) | Actual REVIEW (2) |
|---|---|---|---|
| A | [3,0,0,0] | [1,7,0,0] | [0,0,2,0] |
| B | [3,0,0,0] | [1,7,0,0] | [0,0,2,0] |
| C | [3,0,0,0] | [0,8,0,0] | [0,0,2,0] |
| D | [0,0,0,3] | [0,8,0,0] | [0,0,2,0] |
| E | [3,0,0,0] | [0,8,0,0] | [0,0,2,0] |

A/B/C/D reuse actual paired application outputs; E separately executes its workflow. Actual shared/workflow application task executions total **108**, with **zero LLM calls**. Per-method counts are equivalent task executions, not separately incurred model calls. The raw report records decision, selector, paired-application and whole-workflow timing with their scopes. These are subsecond deterministic controls, not customer latency. SourceROI's timed workflow includes proposal verification and filesystem work omitted from the paired-application-only timing; no normalized overhead superiority claim is justified.

### Expectation maintenance: prefill is not measured labor savings

The fixtures contain three approved revised-answer fields. Existing proposals prefill all three correctly, so this demonstration needs zero additional answer-text overrides. But it also produces **five reviewable suggestions**, including **one known incorrect protected-warranty suggestion and one ambiguous-intent suggestion**. A reviewer must reject/correct the former and interpret the latter.

The script's answer-edit counts model fields that require population without prefill; they are **not observed human actions or elapsed review effort**. Actual human review corrections and total maintenance/debug time are unavailable. The same authoritative decisions supplied to E can be used by ordinary systems. No general reduction in manual evaluation maintenance has been established.

## 4. Independent evaluation protocol

No independent source owner/reviewer or independently pre-established new final labels were available. **No independently validated final experiment was executed.** New authored adversarial controls are also engineering fixtures, not a replacement for independent labels.

[Pending external annotation protocol](artifacts/external-annotation-protocol.json) and `tools/independent_validation.py` provide a concrete handoff:

1. External source owners supply realistic before/after documents and pre-established answers/outcomes, with versioned evidence citations. Required challenge topics include legitimate updates, date/jurisdiction, conflicts, paraphrases, interacting changes, protected behaviors, missing/outdated evidence and new dependencies.
2. The external operator verifies reviewer independence and provenance. The evaluated model's outputs cannot be used to create its own authoritative labels. The protocol requires label timestamps and a declaration that model outputs were not seen by labelers.
3. Separate document families for development and final; keep final documents/labels inaccessible to implementation/tuning. The tool checks family overlap, exact/normalized text overlap and near-duplicate five-word shingles. Semantic/pretraining overlap cannot be ruled out automatically.
4. Freeze approved labels **before** final execution, record the protocol digest and execute final once. Revisions require a new version. Freeze refuses pending annotations, missing coverage, reused destinations and detected split leakage.

```bash
python tools/independent_validation.py template --output external-protocol.json
# External reviewers complete both splits and verify the reviewer declarations.
python tools/independent_validation.py freeze --input external-protocol.json --output frozen-protocol.json
```

The tool cannot authenticate human identities, independently verify attestations, or prove that a final dataset was never previously exposed. A frozen hash is integrity evidence, not independence by itself. The supplied protocol remains pending; unit tests use explicitly synthetic reviewer declarations to verify rejection paths, not to claim human validation.

## 5. Semantic and citation reliability

[Eleven authored integrity controls and pending review items](artifacts/semantic-citation-validation.json) exercise paraphrases, right number/wrong support, contradictory claims, old/future policies, wrong jurisdiction, absent metadata, fabricated citations, missing citations and malformed response contracts.

Verified deterministic findings:

- Fabricated citation IDs are flagged; empty citations are reported separately.
- Explicit US/EU mismatch, expired policy and not-yet-effective policy are marked inapplicable using supplied metadata.
- Missing scope/date metadata stays unknown.
- Paraphrases, a matching number in an unrelated warranty passage and contradictory claim meaning do **not** receive fabricated automatic semantic scores.

Independent semantic accuracy and citation-entailment accuracy remain **null**. No model-based judge or LLM self-judgment was used. These controls demonstrate metadata/integrity checks, not robust semantic entailment.

[The repaired smoke's real-output review packet](artifacts/validation-sprint-smoke-reviews.json) contains four answer/context/citation items. Export verifies that source hashes still match the executed report; imported reviews must match the sample digest, identify an operator-authorized independent reviewer and cover all answer claims with valid spans. Claimed support must quote actually supplied, cited evidence. Positive scope review cannot contradict explicit metadata. Partial reviews remain REVIEW; completed negative findings BLOCK the semantic audit.

```bash
python tools/release_review_packet.py export \
  --report docs/artifacts/knowledge-local-smoke-repaired.json \
  --baseline workspace/knowledge-local-smoke-repaired/accepted \
  --candidate workspace/knowledge-local-smoke-repaired/candidate \
  --output my-review-packet.json
# External reviewers complete the packet. Operator supplies a JSON list of authorized IDs.
python tools/release_review_packet.py score --packet my-review-packet.json \
  --reviewers authorized-reviewers.json --output reviewed-reliability.json
```

A positive audit is an additional reviewed check, not a production deployment action. Reviewer independence remains operator-attested in this local beta. The existing claim-grounding module is reused; no label is silently revised by a judge.

## 6. External HTTP RAG demonstration

[Executed integration report](artifacts/external-rag-validation.json) and [release Markdown](artifacts/external-rag-validation-release-0.md).

`examples/external_record_rag/server.py` is a separate Python process with no SourceROI imports or benchmark/expected-answer access. It performs lexical retrieval over structured JSON records and extracts the retrieved field value. This is a deliberately narrow, model-free record RAG application. **It was authored by Codex in this sprint; independent code boundaries do not imply independent authorship or customer validation.** No separately authored/customer RAG application was supplied or tested.

The application registers approved local corpus roots. Each request selects the requested version by content digest, rereads files and computes their normalized hashes, applies source/document exclusions and returns its manifest plus actual retrieval IDs. The existing v2 adapter binds the version to the request digest and checks acknowledgment, manifest equality and trace membership. A unit test mutates the source file and confirms that the former requested version is no longer available; the executed HTTP demo rejects an unknown version.

Executed flow: create knowledge configurations → freeze accepted baseline → approve 30→14 returns update and protect warranty → request exact baseline/candidate versions → execute release checks → inspect/export reports → introduce a separate protected-warranty failure and block it. Result **ACCEPT then BLOCK**, followed by **unknown version rejected**. Actual requests **9 / cap 10**, time below the **45-second** cap, model calls **0**. The server was stopped on completion.

```bash
python tools/validate_external_rag.py --root workspace/my-external-rag-run \
  --output docs/artifacts/my-external-rag-run.json
```

Use new destinations; outputs are not overwritten. This checks one narrow implementation. It does not establish arbitrary-agent compatibility, enforce policy semantics the application does not implement, or protect against a dishonest server that fabricates hashes. A real integration still needs trusted server instrumentation and exact knowledge/model/prompt/retrieval attestation.

## 7. Tests and reproducibility

**Final full suite: 183 passed in 6.69 seconds. Focused sprint suite: 34 passed in 0.26 seconds.** Full verification is also recorded in STARTUP_VALIDATION.md. Commands executed:

```bash
python -m pytest -q
python -m pytest tests/test_validation_sprint.py -q
node --check sourceroi/live/web/app.js
python -m compileall -q sourceroi/live
python tools/validate_fair_baselines.py docs/artifacts/validation-sprint-fair-comparison.json
python -m tools.summarize_validation_sprint --output docs/artifacts/validation-sprint-summary.json
```

[Tested current-code archive](artifacts/validation-sprint-current-code.tar.gz) and [hash manifest](artifacts/validation-sprint-code-manifest.json) preserve this sprint implementation; they are explicitly not claimed as the exact earlier smoke-time code.

The scripts refuse existing result destinations; use fresh paths to reproduce. Actual local-model commands were `python tools/local_llm.py serve` and `python tools/run_knowledge_smoke.py --root workspace/knowledge-local-smoke-repaired --output docs/artifacts/knowledge-local-smoke-repaired.json`. Serving verifies the installed checksum; no install/download was run. Only the four-call bounded smoke used model inference.

The original failure remains archived; the repaired run is a follow-up, not unseen validation. Later deterministic strict-schema/adapter hardening was covered by tests without additional model reruns. Browser interactions were not automated. All changes are within SourceROI; no Equity Research files were read or changed.

## 8. Startup differentiation assessment

- **Better than human-maintained evaluation?** No measured detection/release-decision advantage over the combined maintained full-suite baseline on the tested controls.
- **Less maintenance work?** Three approved answer fields were prefilled, but five suggestions require review, one is wrong and one ambiguous. Net labor savings are unmeasured and could be negative.
- **Meaningful regressions missed by simpler systems?** Answer-only and coverage-only checks each miss one control; combining them catches everything SourceROI catches here. That combination is conventional, not unique detection.
- **Quality/cost advantage?** None established. E uses the same full-suite task count as C. D reduces replay executions while preserving observed failure detection, but partial successful runs cannot certify release safety. The repaired smoke fixes parsing, not answer quality/token efficiency.
- **Strongest verified value?** A coherent, review-bound source/test/version/release record and tested fail-closed checks. Integration convenience remains a product hypothesis pending developer trials.
- **Unvalidated?** Independent final generalization, semantic/citation correctness, safe selector recall on real updates, authenticated review, independent external/customer RAG integration and actual maintenance effort.

No competitor products were run in this sprint; no competitor superiority or exclusivity is claimed. The [earlier documentation audit](KNOWLEDGE_ASSURANCE_COMPETITIVE.md) remains a documentation comparison only.

## 9. Specific work requiring independent people/data

1. A source owner provides real updates and authoritative date/jurisdiction rules; independent reviewers label a hidden final corpus before outputs exist.
2. A design partner connects its separately maintained RAG application and verifies source-version instrumentation. Include ignored versions, stale caches, conflicting documents, paraphrases and interacting changes.
3. Review real answer claims/citations and measure actual editing/review/debug time against maintained C and stronger D, including correction burden and missed tasks. Continue to report ties and failures.

These are validation prerequisites for a stronger commercial claim, not grounds for another feature expansion or an autonomous production deployment.
