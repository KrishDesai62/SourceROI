# Reliability, grounding and product differentiation sprint

Historical sprint report. The [subsequent validation](GROUNDED_RELIABILITY_REALWORLD_VALIDATION.md) adds explicit contracts and owner onboarding but records excessive abstention and a separately audited inference-counter error. Prior successes and failures below remain historical.

November 13, 2026. Existing standalone SourceROI. Zero external spending, no new model/data downloads, no cloud or production changes. Eight real local-model calls used **2,097 provider-reported tokens**; combined experiment time was **4.314 seconds**, within the 12-call/120-second sprint limit. Both model server sessions and the document RAG server were stopped.

**Result:** the main four-answer smoke now includes valid retrieved citations in **4/4 responses**, compared with 0/4 before. Required semantic review prevents strict ACCEPT. The known protected-warranty proposal is guarded by declared intent. However, the final two model controls exposed a failed abstention and an exact-format mismatch; the same-model semantic probe also accepted unrelated evidence. Reliable independent semantic grounding and a human-effort advantage are **not demonstrated**.

[Machine-readable summary](artifacts/reliability-grounding-summary.json), [integration guide](GROUNDED_AGENT_INTEGRATION.md), [human-study and annotation handoff](EVALUATION_MAINTENANCE_STUDY.md).

## A. Implementation audit

The actual starting suite was **183 passed in 6.50 seconds**; the verified timing is also recorded in STARTUP_VALIDATION.md. Inspected provider/parser, HTTP contract, engine, assurance, grounding/review, diagnosis/ablation, SQLite history, interfaces, local model scripts and previous reports. This workspace has no Git metadata; no Git diff/commit claim is made.

Why answers without citations passed:

- The system prompt asked for citations, but legacy JSON-object generation did not require the field.
- `_parse_answer` intentionally accepted answer-only objects and supplied an empty citation list for compatibility.
- Retrieval was present: both supporting documents were supplied in the previous numeric smoke.
- Reference coverage measured retrieved context, not cited context or claim entailment.
- The release engine required exact answers/references but did not integrate mandatory semantic/citation checks.
- Independent claim review existed as an offline facility rather than a required release condition.

The smallest implementation plan was to preserve that explicit legacy behavior, add a strict policy through the existing engine/interfaces, constrain and verify grounded outputs, make proposed revisions depend on declared intent, strengthen the existing adapter and instrument maintenance. Implemented directly; no replacement application or architecture.

Key files:

| Area | Changes / reused functionality |
|---|---|
| `live/provider.py`, `engine.py` | Grounded prompting, schema-constrained actual retrieved IDs, safe abstention branch, existing scalar normalization, context/citation mapping; prompt/request/schema hashes |
| `live/release_policy.py` | Versioned `legacy_exact` / `strict_grounded`, separate check states, missing checks, reasons, actions and policy-definition hash |
| `live/assurance.py` | Integrated citation/semantic review, intent-aware proposal classifications, protected constraints, explicit maintenance counters, policy/history/Markdown output |
| `live/reliability_review.py`, `ingest.py` | Reused claim adjudication, task scope/grounding flags, explicit jurisdiction/date/policy-scope checks; old task defaults remain unchanged |
| `live/adapter.py`, `provider.py`, `engine.py` | Optional requested model/prompt/retrieval identity, version/manifest acknowledgment, required trace handling and persisted provenance |
| `live/maintenance.py`, study tool | Field/decision counters and serialized, hash-linked study events; no simulated-human timing evidence |
| Existing CLI/API/dashboard | Policy selection, intent declaration, imported authorized reviews, per-check verdicts, hashes and next actions; existing components reused |
| Validation tools / examples | Authored proposal controls, staged replay, document-oriented RAG, external annotation extensions, bounded model runs and preserved artifacts |

Historical failure/results files were not rewritten. Existing saved legacy ACCEPTs retain their historical meaning. The current UI labels historical/legacy policy rather than treating old accuracy as complete grounding. Later request-hash capture and explicit completeness display were tested without repeating model runs.

## B. Full automated verification

**Final full suite: 204 passed in 6.78 seconds. Focused grounded-release suite: 21 passed in 0.59 seconds.** JavaScript syntax and Python compilation passed. Results are also recorded in STARTUP_VALIDATION.md. Commands:

```bash
python -m pytest -q
python -m pytest tests/test_grounded_release.py -q
node --check sourceroi/live/web/app.js
python -m compileall -q sourceroi/live tools/independent_validation.py examples/document_rag
```

New tests cover actual matching-number/wrong-topic evidence, missing/fabricated citations, cited reference coverage, scope/date violations, semantic veto and required review, provenance, incomplete targeted scope, declared protected behavior, unknown intent, partial numeric edits, model/schema constraints, request identities, document ranking, proposal development controls, event integrity and CLI/API selection. Explicit positive/negative review objects in unit tests are **synthetic contract fixtures**, not human review evidence. Two old assertions expecting unapproved automatic suggestions were updated for the intentional safer proposal behavior; no answer labels were changed.

Browser interactions were not automated. Existing adapter/provider, Data CI, source/document ablation, optimizer, history, ingestion, public benchmark and API tests remain included. No unrelated project or Equity Research integration was read or modified.

## C. Citation generation and real-model evidence

Reused the approved installed Qwen2.5-1.5B-Instruct Q4_K_M and llama.cpp b12345, localhost only, one slot/four threads, context 4096, seed 1729, temperature 0. Questions and authoritative answer labels from the earlier smoke were retained. Explicit strict policy and citation prompting/response constraint were the treatment changes.

The pinned runtime documents schema-constrained chat responses, including the wrapper used here. This was verified against the [b12345 server documentation](https://github.com/ggml-org/llama.cpp/blob/b12345/tools/server/README.md#post-v1chatcompletions-openai-compatible-chat-completions-api). A grammar constraint restricts IDs to supplied passages; the model still chooses which evidence to cite. It does not establish entailment.

| Measure | Prior repaired numeric smoke | New grounded main smoke |
|---|---:|---:|
| Baseline exact correct | 2/2 | 2/2 |
| Candidate correct under approved revision | 2/2 | 2/2 |
| Responses citing evidence | 0/4 | 4/4 |
| Invalid/fabricated IDs | 0 (no citations) | 0 |
| Cited annotated support coverage | unavailable without citations | 1.0 for both evaluated candidate tasks |
| Generation calls | 4 | 4 |
| Total tokens | 848 | 1,080 |
| Mean measured task latency | 414.145 ms | 544.185 ms |
| Registered verdict | legacy ACCEPT | strict REVIEW |
| Independent semantic reviews | 0 | 0 |

Actual new citations are `policy::returns.json#chunk0` and `policy::warranty.json#chunk0`, matched to retrieved context/source identity. The return answer changes 30→14; warranty stays 365. New tokens are **27.36% higher**, not a token/cost optimization. Latency is one small nonrandomized local comparison, not a universal speed result. API spend is zero; model/hardware/electricity dollar costs are unpriced.

The original-style numeric tasks supplied no explicit date/jurisdiction query scope. Their scope PASS records no configured mismatch, **not** independent date/applicability verification. Scope/date violations are exercised separately with actual metadata in deterministic tests and the document application.

[Prior numeric artifact](artifacts/knowledge-local-smoke-repaired.json), [new main smoke and provisional probes](artifacts/grounded-model-validation.json), [pending actual-answer review packet](artifacts/grounded-model-review-packet.json).

### Negative model findings retained

Two provisional checks using the same installed model returned `supported` for both:

1. “Products may be returned within 14 days.”
2. “Warranty coverage lasts 14 days.”

The second does not establish the return claim. These are uncalibrated same-model judgments, never independent ground truth and never used to update labels or authorize release. This experiment is evidence against trusting that lightweight judge automatically.

The final response grammar gained an explicit abstention/empty-citations branch so it does not force an answerer to cite irrelevant context. Two predeclared follow-up controls under that final schema produced:

| Authored control | Intended fixture answer | Actual output | Citations | Finding |
|---|---|---|---|---|
| Supporting return policy | `14` | `14 days` | valid supplied ID | Exact numeric-only format failed; semantic equivalence not independently reviewed |
| Only unrelated warranty evidence | `INSUFFICIENT_EVIDENCE` | `14` | valid supplied ID | Failed abstention; valid IDs did not establish relevant support |

Both unfavorable outputs are preserved in [the final-schema control](artifacts/grounded-abstention-validation.json), with [the plan](artifacts/grounded-abstention-plan.json) written before inference. No labels were repaired and no favorable rerun was sought. This is a separate two-control result, not a claim that final-schema production reliability matches the earlier four-answer smoke. Total new generation calls: **4 main + 2 provisional probes + 2 final-schema controls = 8**. Token total **2,097**, combined measured experiment time **4.314 seconds**. Later metadata/display hardening did not trigger further inference.

## D. Evaluation proposal accuracy

The old generator applied a text substitution from a changed source without first knowing whether that task was supposed to change. A legitimate factual edit and an unintended warranty regression can look structurally identical. Inferring business approval from either is unsafe.

Version-2 proposals require source-linked old evidence, meaningful fact/question anchors, full numeric-token replacement, known authority, stable constraints and **declared expected versus protected behavior** before prefilling an expected revision. Conflicts and changed source constraints stay reviewable. This is not semantic/business-intent inference. Every revision still requires separate explicit approval.

Classification: `PROPOSED_CHANGE`, `PROTECTED_UNCHANGED`, `AMBIGUOUS_REVIEW`, `NO_SUPPORTED_CHANGE`, alongside the existing pending approval status. Reports retain old/suggested expectations, candidate facts, quotes, reason and uncertainty. A protected task cannot be revised under the same intent specification.

[Full old-control and separate development results](artifacts/proposal-v2-final-validation.json):

- Previously exposed controls with declared authored intent: **3 revisions matching that intent, 0 incorrect proposed revisions, 0 protected expectations incorrectly proposed**. The old warranty candidate remains visible as evidence of a source change but is classified protected and not offered as a new expected answer.
- **3 ambiguous review items** across the exposed set: the known unknown-intent return case plus two affected behaviors under the effective-date metadata change.
- Without declared intent: **0 automatic revisions, 7 ambiguous items**. This reduces automation and moves intent work explicitly to the source owner.
- Eight separate authored development cases: **8/8 classification matches and 8/8 expected-revision matches**, including partial numeric digits, protected coverage, unchanged values sharing digits, unrelated same-number fields, scope changes, missing authority, conflicting facts and unknown intent.

These are authored/exposed engineering cases, not independent final accuracy. The before/after comparison changes available **up-front declared intent**; it does not prove that the generator learned to infer that intent. Independent reviewers and actual human correction counts remain absent. The known warranty mistake is guarded **when protection is declared**; unknown protection is not magically inferred.

## E. Release-decision safety

Strict grounded policy separates execution completeness, approved intent, exact answers, retrieved/cited reference coverage, citation identity, scope applicability, version provenance and semantic review. It preserves each result, missing requirement and reason rather than combining them into one accuracy metric. Scope/date checking uses explicit metadata; matching words or numbers do not prove meaning.

| Outcome | Verified condition |
|---|---|
| ACCEPT | Existing legacy answer/reference demo remains explicitly scoped; strict positive unit fixture requires every mandatory check and authorized bound claim review |
| BLOCK | Missing/fabricated citations, cited wrong annotated document even with the correct number, explicit scope/date violations, protected answer failure, or completed negative semantic review |
| REVIEW | Valid answer/citation/reference checks but missing required independent semantic interpretation (actual main smoke and good document update) |
| INCONCLUSIVE | Required provenance/execution unavailable, incomplete responses, changed identities/versions, or passing targeted checks with remaining tasks unexecuted |

Positive strict semantic unit fixtures test the contract only; **no real strict human-grounded ACCEPT was empirically obtained**. Actual independent semantic correctness/entailment scores remain null. Current code prevents both unreviewed meaning and missing required execution from authorizing strict release. A same-model judge cannot override trusted labels.

The default remains versioned `legacy_exact` for compatibility. Strict policy is opt-in through project/CLI/API; a task can explicitly require grounding. Stored policy requirements and definition hashes retain historical interpretation. No old report was rescored or rewritten. CLI, API, Markdown, SQLite history and the existing dashboard expose overall status, per-check statuses, missing checks, blocking reasons, source/test/model hashes and next actions. Policy scopes make a legacy exact pass visibly different from a full grounded approval.

## F. Fair baselines and staged testing

[Latest equal-authority comparison](artifacts/grounding-final-fair-comparison.json) retains equivalent approved labels, references, expected/protected intent and unresolved information for all approaches. It uses the registered **legacy exact/reference** check policy for comparability; it is not an independent semantic benchmark.

| Approach | Blocking cases detected / 8 | Legitimate false blocks / 3 | REVIEW | INCONCLUSIVE | Equivalent task executions |
|---|---:|---:|---:|---:|---:|
| Maintained answer-only regression | 7 | 0 | 2 | 0 | 54 |
| Approved reference coverage | 7 | 0 | 2 | 0 | 54 |
| Maintained full answer + reference suite | 8 | 0 | 2 | 0 | 54 |
| Strong lexical/topic/trace selection | 8 | 0 | 2 | 3 | 32 |
| SourceROI | 8 | 0 | 2 | 0 | 54 |

**SourceROI still ties the properly maintained combined baseline.** Required semantic review is a stronger release condition than the old exact-only policy; a conventional workflow can require the same review. These results do not establish unique detection or superior reliability versus an equally strict maintained process. Full matrices and method inputs are preserved in JSON.

[Staged scheduling replay](artifacts/grounding-final-staged-replay.json): deterministic screen → high-risk tasks → negative controls → all remaining checks before acceptance. Early confirmed BLOCK can stop testing a release that will be rejected. On these exposed controls, projected paired executions are **38 versus 54**, with zero missed fixture failures and zero legitimate false blocks. This is **replay**, with zero newly executed agent/model calls; it is not observed inference/cost savings. A maintained conventional runner can use identical early rejection. Passing strict targeted checks still need remaining execution and required reviews; default full-suite evaluation is preserved.

## G. Maintenance effort and independent readiness

Integrated `maintenance` counters on the final fair controls: **3 proposed / 3 accepted authored suggestions, 0 revised-answer correction fields, 0 additional answer-entry fields, 3 ambiguous items, 8 candidate new tests and 20 protected-expectation occurrences preserved**. These are simulated fixture decisions and field counts—not participant interactions, true human accept/reject events or measured human labor. The guarded warranty candidate is no longer a proposed revision; reducing the count partly reflects suppression/intent input.

Actual human edits, review elapsed time and time savings remain **null**. New test questions remain candidates without authoritative generated labels.

[Study instructions](EVALUATION_MAINTENANCE_STUDY.md) describe preregistered equal-authority maintained-vs-SourceROI workflows, external source owners, counterbalanced independent case groups, editing/review/debug time, quality and interruptions. The event logger stores origin, workflow, participant, protocol/change hashes, edits, ordering, timestamp and hash-chain integrity under a process lock. Automated sessions cannot count as human study evidence. Participant identity, clock/activity validity and independence need external verification; raw declared timing is not a causal savings estimate.

[Pending independent annotation package](artifacts/grounding-external-annotation.json) supports before/after documents, approved factual updates with correct-version quotes/authorized approvers, protected behaviors, scope/date metadata, independent expected answers, reviewer declarations and separate frozen document/label versions. Existing split/exposure/citation safeguards remain. No external source owner/reviewer was available; no independently annotated hidden final set or customer results were fabricated.

## H. Document RAG integration

[Executed document application report](artifacts/document-rag-validation.json). The separate process uses actual lexical scoring over current, historical, regional and warranty documents, followed by day-count extraction. It contains overlapping and contradictory facts and no SourceROI imports or expected-answer access. It is Codex-authored—not independently developed or customer validated.

The existing v2 contract now optionally binds exact model/prompt/retrieval identities as well as knowledge manifest/version. Missing required retrieval traces, stale versions, changed ranking identity, malformed/incomplete outputs and mismatched acknowledgments fail strictly. The example rereads files and reports actual hashes/IDs; it does not merely echo a requested version. A dishonest server still requires trusted instrumentation/audit; attestation is not cryptographic honesty proof.

Executed **10 HTTP requests under 12 / 45 seconds**, zero model calls: intended update **REVIEW** for required semantic adjudication; bad candidate **BLOCK**; changed retrieval-ranking identity rejected; unknown knowledge version rejected. The server stopped after execution. Unit tests also verify actual current-vs-archive ranking produces different retrieved answers.

[Developer integration instructions](GROUNDED_AGENT_INTEGRATION.md). Legacy adapters and callbacks remain; optional fields strengthen rather than replace the architecture. No arbitrary-agent compatibility claim follows from this example.

## I. All eight capabilities preserved

| Capability | Reused and strengthened | Evidence / limits |
|---|---|---|
| Intent-aware change detection | Frozen source/fact diffs plus explicit expected/protected declaration | Existing and new tests; business intent remains owner-supplied |
| Evaluation maintenance | Existing reviewed overlays, stronger classification and counters | Three correct authored revisions; independent/human correction study pending |
| Fact-to-agent impact | Existing annotations/history/topic mapping; staged replay | Nonexhaustive; full required scope remains default |
| Data CI / release assurance | Existing paired engine/CI plus strict policy gates | All four outcomes tested; real semantic review pending |
| Diagnosis / counterfactual repair | Existing diagnosis, isolated rollback/repair and ablations retained | Original tests still run; no production repair |
| Longitudinal intelligence | Existing SQLite runs now expose policy and separate checks | Exact historical reports preserved; no causal certainty from timeline |
| Dataset value / selection | Existing source/document/passage ablation and source addition retained | No new universal score or removal claim |
| Cost-aware testing / optimization | Existing provider accounting and optional optimizer retained | New main smoke uses more tokens; scheduling savings only replay, not unique benefit |

## J. Startup differentiation assessment

- **More reliable than before?** Engineering gates are stronger: strict mode no longer treats missing citations or pending semantic review as full acceptance, and version/configuration drift is checked. This is test-backed behavior, not a measured customer failure-rate reduction.
- **Meaningful failures simpler baselines miss?** Answer-only and coverage-only checks each miss an exposed control; their conventional combination ties SourceROI. Strict required semantic review can prevent unsafe approval, but a maintained process can apply the same requirement.
- **Still ties maintained full-suite testing?** Yes on the equivalent-authority registered-check controls. Independent semantic comparison is unavailable.
- **Fewer review corrections?** The known protected-warranty proposal is suppressed when intent is declared; three authored prefilled values need no correction. Actual reviewer correction/time reduction is unmeasured, and unknown intent reduces automation.
- **Lower human maintenance effort?** No evidence yet. Instrumentation and a usable study handoff exist; real participants do not.
- **Grounding ready for customer testing?** Suitable for a controlled technical pilot with independent review and explicit release requirements. Valid IDs are achievable, but the failed abstention and wrong provisional judgment rule out unattended semantic approval.
- **Strongest current advantage?** A coherent, review-bound knowledge/intended-behavior/test/version/release/diagnosis record. Integration convenience is implemented; commercially superior effort, accuracy, cost or exclusive differentiation is not established.
- **What remains unproven?** Independent hidden-final generalization, semantic/citation entailment, reliable abstention, safe task-selection recall, customer RAG integration, authenticated independent review and net maintenance labor benefit.

Highest-value next evidence: a real source owner supplies independently labeled document changes, a separately maintained customer RAG application attests source/model/prompt/retrieval state, and independent participants run the counterbalanced maintenance/grounding study. Preserve failures and compare against an equally strict maintained baseline. No further optimizer feature expansion or autonomous production deployment is justified by these controls.

## Reproduction

[Tested current-code archive](artifacts/grounding-sprint-current-code.tar.gz) and [file/hash manifest](artifacts/grounding-sprint-code-manifest.json) preserve the final implementation, with explicit limits on matching earlier model-time snapshots.

Use fresh output paths; scripts refuse existing result files. Model scripts have fixed evidence paths and intentionally refuse reruns over prior artifacts.

```bash
python tools/validate_proposals_v2.py docs/artifacts/my-proposal-validation.json
python tools/validate_fair_baselines.py docs/artifacts/my-maintained-comparison.json
python tools/validate_staged_workflow.py docs/artifacts/my-maintained-comparison.json docs/artifacts/my-stage-replay.json
python tools/validate_document_rag.py --root workspace/my-document-rag --output docs/artifacts/my-document-rag.json
python tools/summarize_grounding_sprint.py docs/artifacts/my-grounding-summary.json
```

Actual model commands were `python tools/local_llm.py serve`, `python tools/validate_grounded_model.py` and the separately planned `python tools/validate_grounded_abstention.py`, followed by server shutdown. No install command or download was run. Raw main/probe/final-schema results remain separate; no later metadata additions are represented as an exact earlier execution snapshot.
