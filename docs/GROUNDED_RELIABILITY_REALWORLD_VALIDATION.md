# Grounded reliability and real-world validation

November 13, 2026. Existing standalone SourceROI; no new application, model downloads, cloud resources, external spending or production changes.

**Finding:** explicit answer contracts and evidence preconditions strengthen rejection/reporting, but the model experiment was not a quality success. The model abstained on **all four supported controls**. Software screening removed one empty-context factual hallucination, without recovering valid answers. Independent semantic reliability, customer benefit and competitive advantage remain unproven.

**Accounting correction:** the raw harness printed 10 generation calls but actually executed **11**, because its empty-context raw control bypassed screening without reserving a call. This exceeded the experiment's planned 10-call cap by one, while remaining within the user's 12-call ceiling. The raw result is preserved; [the accounting audit](artifacts/evidence-abstention-accounting-audit.json) corrects the counter and incorrect per-row generation flag. The provider/harness are fixed for future use. No further inference was run.

[Audited summary](artifacts/realworld-validation-summary.json) · [preserved raw experiment](artifacts/evidence-abstention-validation.json) · [prewritten plan](artifacts/evidence-abstention-plan.json).

## 1. Repository audit and implemented fixes

The starting full suite actually passed **204 tests in 6.88 seconds**. Inspected the current provider, engine, release policies, review/diagnosis modules, annotation tools and previous failures. Verified the historical warranty-only answer, numeric-format mismatch, uncalibrated judge and maintained-baseline tie in their archived files. Historical outputs and benchmark labels were not overwritten. No Git metadata is available in this workspace.

Changes extend the existing architecture:

| Change | Behavior and limits |
|---|---|
| `live/answer_contract.py` | Explicit version-1 numeric, text, boolean and closed flat structured-object contracts; no unit stripping or inferred label changes |
| `live/provider.py` | Preserve raw message/decoded value and normalized answer; typed output schema; declared scope/metadata supplied to model; strict empty-context calls cannot bypass abstention through cached traces |
| `live/evidence_contract.py` | Necessary subject-alias groups, explicit date/jurisdiction/policy-scope exclusions and potential same-predicate numerical conflicts; never declares entailment |
| `live/engine.py` | Pre-generation screening before call reservation; distinguish software/model origin, retain excluded/retrieved evidence and actual generation usage |
| `live/assurance.py`, `release_policy.py` | Answer-format gate separate from meaning; required evidence relevance/conflict statuses; preserve raw types in review samples; forbid strict-policy downgrade |
| `live/reliability_review.py`, `diagnosis.py` | Keep format/relevance/version/scope/entailment distinct; software abstention is not mislabeled a model-generation failure |
| Ingestion/grading | Optional task contracts preserve legacy task defaults; explicit `structured_exact` compares declared JSON fields/types, including boolean-vs-number distinction |
| `tools/source_owner_onboarding.py` | No-inference owner bundle → frozen baseline/candidate, intent and review-decision draft; no automatic approval; existing CLI/review tools reused |

Legacy tasks without contracts retain their existing scalar behavior. `legacy_exact` remains available for legacy workspaces; an already configured strict workspace cannot be downgraded by a per-run override, and grounded task flags still add strict requirements. Draft review rationales are rejected until an operator explicitly completes the review.

## 2. Automated verification

**Final full suite: 230 passed in 7.10 seconds.** Focused new suite: **26 passed in 0.15 seconds**. JavaScript syntax and Python compilation passed.

```bash
python -m pytest -q
python -m pytest tests/test_answer_evidence_contracts.py -q
node --check sourceroi/live/web/app.js
python -m compileall -q sourceroi/live tools/source_owner_onboarding.py
```

Tests cover strict downgrade rejection, empty-context cached-trace bypass, numeric units, boolean/text/structured typing, raw preservation, scope filtering, conflict abstention, paraphrase aliases, incomplete relevance, existing release gates, atomic onboarding, protected labels, safe paths and draft approval. Existing CLI/API/dashboard/history, Data CI, diagnosis/repair, source/document/passage ablation, attribution and optimizer tests remain included. Browser interaction and real human review were not automated or fabricated.

## 3. Before/after abstention experiment

One frozen development experiment separated **two exposed cases** from **nine newly authored development cases**. New does not mean independently validated or hidden final. A correct-document-identity/wrong-content case, missing essentials, expired/wrong-jurisdiction sources, conflicting policies, paraphrase, multiple plausible citations, a prohibited-return premise and an incomplete alias contract were included.

The model saw question, available sources, declared answer type, alias alternatives and relevant scope metadata. The raw control deliberately bypassed the deterministic precheck; software-assisted outputs are a **postprocessing/replay** of the same observed answers, replaced by explicit software abstention when necessary conditions failed. They are not a second model experiment or evidence of better model reasoning.

| Measure against authored control expectations | Raw model outputs | Contract-screen replay |
|---|---:|---:|
| Total cases | 11 | 11 |
| Matches authored expected answer | 6/11 | 7/11 |
| Unsupported factual answers | 1/7 unsupported cases | 0/7 |
| Abstentions on unsupported cases | 6/7 | 7/7 |
| False abstentions on supported cases | **4/4** | **4/4** |
| Supported answers produced correctly | **0/4** | **0/4** |

The historical warranty-only control answered `14`. In this run it abstained, but the supported return-policy control also abstained. That is not a general solution to grounded answer generation.

The sole factual output was `30` from the empty-context raw control. Deterministic screening replaced it with `INSUFFICIENT_EVIDENCE`. All other raw outputs were abstentions. The software screen did not recover any correct factual answer. The incomplete alias-contract control demonstrates a configuration risk: missing paraphrase alternatives can reject legitimate support. Necessary conditions require source-owner validation.

Do not interpret 7/11 replay matches as a commercial quality win. Controls are authored; the model's excessive abstention is a severe limitation, and a conventional runner can apply the same necessary-condition checks.

### Prompt and accounting fixes after observation

Investigation found competing string/yes-no wording alongside an explicit numeric contract, plus ambiguous wording about synonym groups. Final code removes those conflicting instructions for declared types and clarifies OR within each alias group. These consistency fixes have deterministic tests but **were not rerun on the model**. Their effect on excessive abstention remains unmeasured.

The empty-context cached-trace bypass and conditional harness reservation caused the counter error. Final code returns software abstention before a provider request even when a cached trace claims screening was bypassed. The future harness also handles empty context before reservation. The preserved as-run code shows the original mistake; the final code snapshot is separate.

The raw `model_generated_only_metrics` subset incorrectly excluded the empty-context model response. Use all 11 raw output rows and the accounting audit, not that subset/counter. No corrected value was silently written into the raw experiment.

## 4. Claim/evidence validity

The pipeline now distinguishes:

- **Citation ID:** membership in actually supplied/retrieved context.
- **Knowledge version:** existing immutable source/version and optional HTTP manifest/identity checks.
- **Applicability:** explicit scope/date metadata, with unknown metadata remaining unresolved.
- **Necessary relevance:** owner-declared alias groups; a positive match never proves support.
- **Potential conflict:** limited same-predicate numerical-shape detection, not general semantic contradiction reasoning.
- **Entailment:** existing externally authorized claim review, not an uncalibrated same-model judge.

All 11 responses in this experiment had **no citations**. There were zero invalid IDs, but with no cited responses that is vacuous—not evidence of successful citation generation. The earlier four-citation smoke remains historical evidence, not a result reproduced here.

Independent semantic/entailment accuracy stays **null**. Inline model probes did not execute the full frozen release pipeline; their recorded `strict_release_eligible=false` is a policy limitation, not a measured zero false-acceptance rate. Full strict-gate behavior is exercised separately by the regression suite. No unsupported inline response is asserted to be a reviewed grounded release.

## 5. Task-specific answer contracts

Example task fields:

```json
{
  "answer_contract":{"version":1,"type":"numeric"},
  "evidence_contract":{"version":1,"subject_aliases":[["return","returns","returned","sent back"]]},
  "requires_grounding":true
}
```

Numeric checks accept only a numeric scalar or a full numeric string; `14 days` is invalid and remains `14 days` in the normalized answer. No extraction of `14` makes it exact-correct. Boolean contracts support booleans / explicit `true` or `false`, not implicit yes/no conversion. Text contracts require text. Structured support is limited to a declared closed flat JSON object with scalar fields and explicit `structured_exact` grading.

Reports preserve `raw_response`, `raw_answer`, `normalized_answer`, format validity/reason and `answer_origin`. Software abstention has no raw model response; it is never invented as model output. External raw preservation covers the answer/citation contract fields, not all HTTP headers/wire bytes.

Deterministic tests reject `14 days` even when a permissive contains/numeric-style grader could find 14. Structured tests distinguish boolean `true` from numeric 1. Semantic equivalence can be reviewed separately; it does not waive a mandatory output contract or silently alter expected labels.

No answer-type violations appeared in the model run, but ten abstentions and one unsupported numeric value do **not** establish successful typed factual generation. Text, boolean and structured generation were tested deterministically, not benchmarked with new model calls.

## 6. Strict release verification

The existing four outcomes remain. Exact answers, formatting, cited support, source/version, applicability, relevance, conflicts, independent semantics, intent and execution completeness remain separate.

- Required format violation: **BLOCK**, even if a permissive answer scorer matches.
- Missing/invalid citations or deterministically violated declared evidence condition for a factual claim: **BLOCK**.
- Valid/necessary evidence matches but unreviewed meaning or abstention appropriateness: **REVIEW**.
- Unavailable provenance, incomplete responses/execution or remaining tasks: **INCONCLUSIVE**.
- Strict **ACCEPT** still requires every mandatory check and authorized independent review; a model judging itself cannot supply it.

A necessary-evidence screen is not an absence-of-all-possible-evidence proof. Strict abstention remains reviewable; the code does not manufacture citations to justify it. Actual independent reviewers were unavailable, and no new independently grounded ACCEPT is claimed.

## 7. Maintained combined baseline

[Equal-authority comparison](artifacts/grounded-reliability-maintained-baselines.json) reran the existing exposed controls with equivalent approved facts, labels, evidence and protected expectations.

| Method | Blocking detected / 8 | Legitimate false blocks / 3 | REVIEW | Equivalent task executions |
|---|---:|---:|---:|---:|
| Maintained combined answer/reference suite | 8 | 0 | 2 | 54 |
| SourceROI | 8 | 0 | 2 | 54 |

The tie remains. This is the registered legacy answer/reference comparison, not independent semantic validation of the new model outputs. A maintained system can apply the same type/schema and evidence prerequisites. No unique detection, verified cost advantage or human maintenance-time saving is established.

## 8. Inference usage, latency and limits

Correct actual generation count: **11**. Planned experiment cap: 10 (exceeded by one due to the harness bug). User ceiling: **12** (respected). Actual tokens across all responses: **4,174**. Experiment elapsed: **7.597 seconds**, below 120. Summed provider model latency: **7,377.81 ms**, mean **670.71 ms per actual response**.

Reused installed local Qwen2.5-1.5B-Instruct Q4_K_M / llama.cpp b12345, seed 1729, temperature 0, localhost only. No paid APIs/credits, commercial credentials or new downloads. External spend **$0**; hardware/electricity/inference dollar costs are unpriced. The server was stopped; the remaining one-call allowance was unused.

The replay estimates four generation calls if the owner screen had run first, but **all 11 actual raw calls were spent**. No actual model calls were avoided in this experiment and no deployed cost saving is claimed.

## 9. Real source-owner onboarding

[Onboarding instructions](SOURCE_OWNER_ONBOARDING.md), [unfilled owner template](artifacts/source-owner-pilot-template.json).

One no-inference command prepares user-supplied before/after text documents, authoritative expectations, evidence, type/scope contracts, a frozen accepted baseline, candidate workspace, declared intent and **draft** decisions for the existing review CLI. It performs no model call, download, automatic approval or production modification. Existing annotation/final-split and human-study tools remain available.

Labels must be independently established before outputs, with owner identity/provenance declarations and correct-version evidence. Declarations are not authenticated human independence. A draft cannot be approved until its rationale is explicitly completed. The tool does not provide a customer dataset or manufacture labels. Real owner input, reviewers and participants remain pending; preparation was exercised with explicitly synthetic unit fixtures only.

## 10. Startup readiness and remaining evidence

Stronger engineering properties are verified: explicit response typing, raw preservation, deterministic preconditions, strict no-downgrade and no-empty-context behavior, separated semantic review, and reproducible onboarding. All eight capabilities remain under the passing regression suite: intent/change detection, evaluation maintenance, impact mapping, Data CI, diagnosis/repair, history, dataset value/ablation and optional optimization. No subsystem was discarded or replaced.

The generation evidence is negative: supported answers were not recovered, citation presence was absent, and accounting itself needed correction. This local model configuration is not validated for reliable unattended grounded answering. A controlled source-owner pilot can test the assurance workflow with real labels and a separately maintained agent; production/semantic approval and customer compatibility are not established.

Highest-value remaining work is independent source-owner data and semantic review, followed by a frozen fresh validation of the final prompt/contracts and measured maintenance work against equally strict maintained testing. Preserve excessive abstention and false rejection as first-class outcomes. No competitor superiority, exclusive innovation, customer result, fabricated review or measured time saving is claimed.

## Reproduction and artifacts

[Current tested implementation archive](artifacts/realworld-validation-current-code.tar.gz) and [file/hash manifest](artifacts/realworld-validation-code-manifest.json) are separate from the as-run archive and identify post-run fixes.

```bash
python -m pytest -q
python tools/audit_evidence_accounting.py docs/artifacts/evidence-abstention-validation.json new-accounting-audit.json
python tools/summarize_realworld_validation.py new-realworld-summary.json
python tools/source_owner_onboarding.py template --output owner-bundle.json
python tools/source_owner_onboarding.py prepare --input owner-bundle.json --output workspace/owner-pilot
```

Output paths must be new. The inference script's fixed paths refuse overwrite; the as-executed raw data/code remain separate from later fixes. [As-run code archive](artifacts/evidence-abstention-as-run-code.tar.gz), [pre-inference code hashes](artifacts/evidence-abstention-code-plan.json). The current harness has corrected empty-context handling and must not be represented as the as-run source of the preserved counter error.
