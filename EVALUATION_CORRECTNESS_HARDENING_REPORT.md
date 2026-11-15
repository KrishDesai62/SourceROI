# Evaluation correctness and release assurance hardening

Date: 2026-11-14. Scope: standalone SourceROI, offline engineering and read-only replay. **No new model generations, external spending, authorization reuse, production changes or new distribution.** Historical empirical evidence remains authoritative for observed model performance.

| Classification | Result |
|---|---|
| VERIFIED | Shared declared routing, protected evidence-only review, pre-dispatch canonical validation and comparator parity checks implemented and exercised offline. |
| VERIFIED | Full regression suite: **415 passed**. All 877 files captured in the pre-change historical evidence manifest remain unchanged. |
| PRELIMINARY | Counterfactual routing matches primary retrieval on 20/20 preserved tasks; eliminates four supported candidate software abstentions at the eligibility stage. No subsequent model answers were generated. |
| PRELIMINARY | Narrow source-bound proposals cover 3/3 supported frozen authored cases, with 0 wrong proposals and 3/3 negative abstentions. This is development coverage, not independent generalization. |
| FAILED | Earlier real candidate primary accuracy remains 2/5 supported; earlier candidate Data CI remains 0/5. No quality-preserving optimization or competitive superiority has been established. |
| PENDING | Independent semantic review, newly authorized post-fix inference, customer validation, maintenance-effort measurements and shared production security. |

## Audit of the actual failures

The audit uses all **40 logical task traces** in `docs/artifacts/full-empirical-benchmark/analysis/final/all-40-logical-task-traces.json`, the unchanged full empirical report, frozen 2024/2025 IRS documents, application helper, engine, source preflight, change planning and strict release code. Existing labels are Codex-authored development labels, not independently adjudicated truth.

1. **Different retrieval behavior.** The earlier experiment helper removed `archive` for literal CURRENT questions. Built-in Data CI called the shared engine without this restriction. Both 2024 and 2025 sources were therefore eligible in candidate Data CI when tasks did not specify an annual `as_of` restriction. Its necessary-evidence preflight reported `potential_same_predicate_numeric_conflict` for business, medical, FAVR and depreciation and abstained before dispatch. This is a routing/contract inconsistency, not four failed Qwen generations. Different values in different annual editions are not necessarily contradictory active facts; source selection must be explicitly declared. The generic numerical preflight is conservative and does not prove temporal contradiction.
2. **Protected answer, changed quotation.** Medical stays 21, but the source adds “for 2025 is unchanged from 2024.” Historical SourceROI review could replace evidence only for changed-answer tasks. Protected medical consequently retained a stale literal quotation with reference coverage 0. The original conventional preparation replaced that quotation, producing an unequal comparison. The separate historical equal-requirement analysis tied. Neither original result is rewritten.
3. **No supported IRS value proposals.** Line/chunk fragments, multiple changes within paragraphs, historical-year numerical series, and annual source metadata changes do not satisfy the narrow exact-edit/explicit source-binding conditions. These cases remain AMBIGUOUS_REVIEW with 0/3 automatic suggestions. Broadening extraction to guess a desired answer is unjustified.
4. **Broad impact is real document linkage, not demonstrated precision.** The five supported tasks reference the changed current document; other tasks share topic or configuration dependencies. The old selection included all ten. No independent task-impact oracle exists for computing precision/recall or savings.
5. **Wrong model answers persist in preserved evidence.** Primary business answered 21 instead of 67/70, although business evidence was retrieved along with medical 21. Candidate charity answered 70 instead of 14; depreciation selected a historical rather than requested annual value. These are observed answer/evidence-selection failures. Context crowding or predicate/year confusion are hypotheses; hidden model reasoning is unknown. Primary supported correctness is still 3/5 → 2/5, with zero supported false abstentions; Data CI is still 2/5 → 0/5, with candidate false abstentions 4/5. Unsupported rejection and raw citation-ID checks are not semantic accuracy.

The original run remains **18 reconciled native generations, 55,467 provider tokens, 40 logical evaluations**, within its consumed authorization. Those counts are not new activity this sprint.

## Implemented fixes and validation

### Declared routing

`sourceroi/live/routing.py` introduces version 1 literal question/source rules, validated in configuration and applied in `engine.evaluate_variant` before ranking. Built-in application evaluation, ablation and Data CI consequently share the same mechanism. Routing is configuration-bound and appears in selection traces and execution identities.

Example for a **newly declared/frozen** application configuration:

```json
{"retrieval_contract":{"version":1,"rules":[{"contains":"CURRENT","source_ids":["current"]}]}}
```

This restricts sources only when the declared selector matches. It does not infer newest dates or authority. Multiple matching rules intersect. No match retains all registered sources. Unknown source IDs fail configuration validation. Scope, authority metadata, required evidence subjects, genuine active-source conflicts and out-of-scope abstentions remain enforced. External adapters reject this built-in contract rather than silently ignoring it; their own routing remains their responsibility. Existing adapters without the new contract remain operational.

Tests cover valid annual changes, an additional conflicting current document, wrong jurisdiction/date, bad routing declarations, and application/Data CI context identity. The existing frozen empirical configuration and labels are unchanged; future live experiments must explicitly register and freeze their routing contract rather than silently changing the old experiment.

Read-only replay with an explicitly different in-memory declared configuration matches historical primary retrieved IDs on **20/20** tasks. Candidate generation eligibility becomes 5/5 supported; all five unsupported tasks still abstain in software. The four false abstentions disappear at preflight only. No new answer correctness, token saving or empirical quality improvement is claimed.

### Evidence-only protected maintenance

`sourceroi/live/maintenance_evidence.py` proposes exact replacement quotations with original and replacement source fingerprints, text offsets and stable proposal IDs. Answer expectations stay frozen. Proposed equivalence is UNKNOWN. Named explicit equivalence decisions and rationale are required; changed numerical values, unrelated text, unknown/inapplicable sources, ambiguous candidates, and detected changed qualifications fail conservatively. Lexical screens are necessary checks, not semantic proof.

`assurance.review(..., evidence_updates=...)` permits protected evidence-only updates without changing the expected answer. Updates are specification-bound, and `validate_release_inputs` recomputes canonical source-bound proposals before dispatch. Stale or forged updates fail before callbacks. Evidence-only review does not substitute for independent strict semantic review. Reviewer names remain local assertions, not authenticated identities.

In the preserved primary-answer replay, an **explicitly labelled internal fixture decision** updates medical evidence, keeps expected 21, restores medical reference coverage **0 → 1**, and yields medical citation-integrity PASS. Medical semantic review remains REVIEW. Overall citation integrity remains REVIEW for other unresolved cases; it is not promoted to universal PASS. Both evaluators still BLOCK business, charity and depreciation. No real human review or new approval is asserted by this fixture.

### Fair comparison before dispatch

`sourceroi/live/evaluation_inputs.py` materializes reviewed tasks once and creates versioned input packets covering source/configuration identities, source metadata, frozen and maintained tasks, expected answers, approved intent/evidence updates, scope, citation requirements, release policy and review requirements/status. Any mismatch fails closed.

The empirical harness validates canonical inputs and packet parity **before creating an experiment runtime**. It requires a supplied pre-execution review record for a full run and does not approve draft decisions after observing outputs. Both methods consume the same maintained inputs. Conventional evaluator logic was not changed. This protects the harness; it does not prove arbitrary future third-party evaluators consume their declared packets honestly.

Regression tests alter each authority dimension, reproduce the historical medical evidence mismatch, and assert no runtime startup on a mismatch. Replayed identical real answers give BLOCK/BLOCK with the same three blocking answer failures. This remains a tie.

### Narrow value proposals and impact explanations

The existing literal fact/CSV/Markdown calculation binder is reused for explicit-contract source-value proposals. Candidate values come from source operands, never gold-label replacement. Both before and after bindings must be supported, authoritative, different and unambiguous. Source facts retain document versions, quotes/cells and units/periods. Proposals remain review-only. The legacy narrow single-numeric source-edit suggestion likewise takes its candidate value from the source edit.

`frozen-proposal-cases.json` was recorded before implementation: literal lookup, CSV lookup, Markdown lookup, conflicting values, unsupported narrative and unchanged value. The replay deliberately substitutes a wrong task gold (`999999`) while retaining the source contract. Results: **3/3 positive suggestions; 0 wrong suggestions; 3/3 negative abstentions**. Full operands/provenance are preserved in `replay-v1/proposal-coverage.json`. These six authored cases support only narrow development claims. IRS 0/3 remains unresolved.

Impact records now explain `confirmed_direct`, `potential`, `unknown`, or `unrelated_registered_evidence`. Direct means document/reference or recorded retrieval dependency, not semantic fact causality. Unrelated classification requires unchanged registered evidence and a valid exact quotation; absence of retrieval history alone is insufficient. Unknown dependencies remain potentially affected. Full release retains all tasks. Tests cover unknown history and independently supported unchanged evidence. Actual IRS mapping remains five document-direct and five potential; all ten are retained. Precision/recall and call savings remain unmeasured.

## Regression and evidence preservation

Commands executed (existing Python 3.13 environment):

```sh
workspace/design-partner/venv/bin/python -m pytest -q
workspace/design-partner/venv/bin/python tools/replay_evaluation_hardening.py \
  --output docs/artifacts/evaluation-hardening/replay-v1
```

The replay output is exclusive-create. Reproduction must choose a fresh output directory. It patches generation dispatch to capture eligibility without inference and reuses preserved answers for release comparisons.

Final full-suite log: `docs/artifacts/evaluation-hardening/full-suite-release.txt`: **415 passed**. Focused hardening file has 28 tests, including routing/Data CI parity, preserved active conflict, strict REVIEW, protected evidence updates, stale/forged review rejection, scope/authority negatives, comparator mismatches before startup, unknown dependencies and the six-case proposal protocol. Existing suites exercise strict ACCEPT only with bound review, protected BLOCK, missing review REVIEW, incomplete execution INCONCLUSIVE, source-version checks, citation integrity, native protocol gates and public interfaces. Fixtures are not empirical inference.

Intermediate logs are retained, including the earlier 404-pass and 415-pass runs. No failing regression run is omitted. `historical-integrity-verification.json` verifies **877/877** captured historical artifacts/root reports unchanged. Old packages, raw native events, frozen sources/labels and empirical reports are intact. No historical native authorization was reused; native accounting implementation was not changed.

| Original capability | Preservation assessment |
|---|---|
| Intent-aware knowledge changes | VERIFIED regression coverage; canonical version-bound plan/review checks retained. |
| Evaluation maintenance | VERIFIED offline regression coverage; evidence-only path and narrow source proposals added. |
| Impact mapping | VERIFIED conservative explanatory classifications; semantic selectivity PRELIMINARY. |
| Data CI | VERIFIED shared declared routing and existing regression tests; post-fix real inference PENDING. |
| Diagnosis/repair | VERIFIED regression coverage; source-bound hypotheses, no automatic production repair. |
| Longitudinal intelligence | VERIFIED existing SQLite/history regression coverage; no historical rewriting. |
| Dataset valuation | VERIFIED existing source/document/passage ablation and valuation regression coverage. |
| Cost-aware optimization | VERIFIED existing optimizer regression coverage; new quality-preserving savings PENDING. |

CLI, FastAPI, dashboard, callback/HTTP adapters and SQLite compatibility are assessed through the existing automated suite. No fresh manual UI certification, independent integration or production certification is implied.

## Remaining blockers and investor evidence update

**PENDING production/security:** authenticated reviewer/operator identities and tenant authorization; hostile-parser process isolation; durable cross-process job ownership/resume; complete source/config/database backup/restore; log retention/redaction and dependency advisory/security review. Earlier production reports remain historical snapshots: their old native-accounting PENDING statement predates the successful real benchmark. That isolated native run is verified, not universal provider/concurrency certification.

**PENDING experimental:** independent owner-reviewed labels and evidence equivalence; a separately authorized post-fix inference run on a newly declared/frozen configuration; held-out generalization; genuine customer integration; semantic citation/claim review; representative maintenance time and ROI measurements. The previous authorization is consumed. This sprint grants no new execution permission.

Investor-facing evidence now supports a controlled local release-assurance beta with reconciled prior inference, deterministic safeguards and a reproduced rejection of an unsafe update. It does **not** support superior detection over an equally maintained conventional system, independent semantic accuracy, autonomous maintenance, demonstrated model-call savings, customer value or enterprise production readiness. The equally maintained comparison ties. The engineering fixes address demonstrated evaluation defects; their effect on real post-fix model quality is still unmeasured.
