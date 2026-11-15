# SourceROI final engineering hardening and validation readiness

Executed 2026-11-13 America/Chicago. Standalone existing repository; zero external spending, zero new model downloads, zero live-model requests dispatched, zero new real generations. All model weights remain outside the deliverable.

**VERIFIED:** 299 regression tests pass; owned-runtime controls are exercised against an explicit fake runtime; a single external-evaluation archive was built, extracted and verified; existing callback export/version-binding and budget-configuration defects were repaired.

**PENDING:** native Qwen/llama.cpp request/response reconciliation. The owned runner deliberately refuses live execution until this is verified. Fixture success is not evidence of native accounting. No new real-model benchmark was launched.

**FAILED:** the numerical binder still cannot answer two source-supported table questions. **PENDING:** independent semantic quality, actual external-app adoption, customer effort savings and commercial differentiation.

## 1. Audit and actual changes

**VERIFIED.** Starting suite: **276 passed in 7.66s**. Existing ingestion, retrieval, scope guards, numerical binding, strict release, callback/HTTP v2 adapters, review packets, study logger and historical experiments were inspected. Old discrepancies remain preserved: the grounded-reasoning run captured eleven requests but its runtime completed fifteen; the earlier engineering runtime completed nineteen against eleven captured requests. Those process-local counts are not complete global usage. No old labels, unfavorable results, raw responses or reports were rewritten.

The smallest changes addressing those failures are:

- [experiment.py](sourceroi/live/experiment.py) and [supervisor](sourceroi/live/experiment_worker.py): private authenticated UNIX-socket transport, exclusive runtime/test lease, serialized/fsynced request reservations, raw captures, cancellation/deadline handling, owner/supervisor death cleanup, integrity seals and read-only reconciliation. Native mode fails closed. Only the shipped, copied-and-hashed fake runtime may execute as a fixture; arbitrary programs cannot be mislabeled as fixture validation.
- [provider.py](sourceroi/live/provider.py): an explicit private transport hook. Normal provider behavior remains unchanged; no public proxy or silent fallback into an untracked experiment is introduced.
- [tests/conftest.py](tests/conftest.py): ordinary pytest holds the same exclusive lease and blocks the standard live-model socket. Legacy interactive `local_llm.py serve` now participates in that lease and warns that it has no complete experimental accounting. It remains an interactive path, not a cap-verified runner.
- [local_llm.py](tools/local_llm.py): configuring a local model no longer silently raises the configured call limit to 2,500. Existing limits are preserved; an absent limit defaults to eight.
- [release_review_packet.py](tools/release_review_packet.py): callback rows may omit question text, so export retrieves the canonical frozen benchmark question. Mismatched questions are rejected. Benchmark/configuration/source bindings are checked when recorded. Legacy minimal reports remain compatible but explicitly mark unrecorded bindings; the new handoff builder requires complete bindings.
- [prepare_external_evaluation.py](tools/prepare_external_evaluation.py): packages the existing onboarding, independent protocol, semantic packet, study and adapters together, with source/version checks, implementation/environment hashes and tamper/additional-file detection.

No new numerical grammar, cloud service, major dependency, agent framework, warehouse connector, product application or database migration was added. Numerical generalization was measured rather than tuned to erase unsupported formats.

## 2. Experiment isolation and accounting

**VERIFIED in deterministic fixture tests; PENDING for native inference.**

The owned boundary uses a short private directory with owner-only permissions, an ephemeral local key, a UNIX socket, a unique run ID and a dedicated supervised child. Ordinary clients aimed at localhost:8788 cannot reach it. The lease prevents concurrent ordinary pytest/owned-runtime execution. This is protection against accidental cross-process use, not a sandbox against a malicious process running as the same OS user.

Each permitted generation is reserved durably before dispatch. Failed calls consume budget; retries require a new explicit call. Requests are serialized, capped at **1–8 calls / at most 90 seconds**, and streamed/multiple-completion requests are rejected before dispatch. Denials remain separate recorded attempts. Tokenization is not counted as generation. Canonical request bodies and raw response body/status are preserved without authentication secrets. Missing/inconsistent usage or incomplete terminal evidence remains unknown.

Cancellation, deadline and owner disappearance retire the fixture child; an owner-side watchdog also retires its process group if the supervisor dies. Inherited handles reject a different PID before touching an inherited lock. Reopening an existing output for generation is refused; recovery is audit-only. An interrupted reservation is never silently retried or erased.

### Verified controls

The tests exercise concurrent callers, call exhaustion, HTTP failures and retries, cancellation during a delayed request, runtime crash, supervisor death, unexpected owner termination, deadlines, unauthorized/untracked traffic, missing usage, artifact/event tampering, restart refusal, the runtime/test lease, multiplicity/streaming rejection and provider transport integration. The known test runtime is explicitly a protocol fixture; it loads no model and returns no meaningful factual answer.

Preserved demonstrations:

| Demonstration | Submitted attempts | Forwarded fixture requests | Outcome |
|---|---:|---:|---|
| [Concurrent success fixture](docs/artifacts/final-hardening/fixture-success/reconciliation.json) | 5 | 2 | RECONCILED, 3 denied before dispatch |
| [Failure/retry fixture](docs/artifacts/final-hardening/fixture-failure/reconciliation.json) | 5 | 2 | INCONCLUSIVE, failed usage remains unknown |

The success fixture's fourteen **simulated** tokens are protocol accounting data, not measured Qwen token usage or savings. In the failure fixture, both HTTP error responses are retained, while `response_count` counts successful parsed responses only. Failed-request usage is not filled with zero merely to complete accounting.

Read-only audit:

```bash
python tools/local_experiment.py audit --root docs/artifacts/final-hardening/fixture-success
```

The native binary's read-only help confirms UNIX socket and API-key-file options. That capability check is insufficient to verify server correlation, crash semantics or token accounting for native generation. **Live construction raises an error before launch.** Native log matching remains unverified and cannot yield a complete-accounting claim. Existing interactive model serving should not be used to relabel the historical harnesses as globally budget-enforced experiments.

**VERIFIED:** no real model was started for this sprint; live requests dispatched/generations were zero, within the authorized maximum eight/ninety. **PENDING:** an actual bounded native run demonstrating the full protocol. No paid service or commercial credential was used.

## 3. Numerical generalization beyond IRS

**PRELIMINARY development evidence**, using nineteen frozen, explicitly Codex-authored synthetic cases. [Frozen cases](docs/artifacts/final-hardening/numerical-frozen-cases.json) precede [execution results](docs/artifacts/final-hardening/numerical-results.json). There are no hidden independent labels or LLM judges.

| Category | Result | Interpretation |
|---|---:|---|
| Source-supported numerical questions | **7/9 correct** | Narrow grammar works; two supported formats fail |
| Supported false abstentions | **2/9** | CSV history and Markdown pricing tables |
| Safety/refusal cases | **8/8 expected refusals** | Missing periods, wrong units, conflicting values, jurisdiction/date mismatch, irrelevant numbers, conditional eligibility and unknown applicability |
| Unsupported contracts | **2/2 rejected** | Arbitrary multi-step formula and non-numeric eligibility operation |

Successful supported examples include financial lookup, two-document historical difference, a paraphrased question using an explicit authorized formula, pricing lookup, multi-product addition, comparison and decimal subtraction. Every numerical output uses the existing subject/predicate/period/unit declarations and source provenance. No expected values were added to extraction rules. Paraphrase success does not show automatic language understanding: its intended formula was supplied explicitly.

**FAILED:** a CSV table contains the financial value and a Markdown table contains the price, but the binder abstains. They remain supported-question failures rather than being relabeled as correct safety refusals. Conditional and non-numeric eligibility rules remain outside numerical entailment. The combined case split must not be turned into an inflated “17/19 reliable answers” claim.

**VERIFIED mechanics:** conflicting candidates remain visible, mismatched scope/units do not produce an authorized number, and unsupported operations are refused. **PENDING:** independent semantic reliability and representative real financial/pricing/policy generalization. Zero model calls/tokens were used in this deterministic batch. Recorded source ingestion plus answer/source-recheck wall time totals approximately **12.59 ms**, exploratory on tiny local fixtures; it is not a customer performance benchmark or priced operational cost.

## 4. Correctness, tokens and optimization

**PRELIMINARY offline replay of previously captured development outputs; no new inference:**

| Existing path | Supported accuracy | Supported false abstentions | Captured model calls | Captured total tokens |
|---|---:|---:|---:|---:|
| Fixed BM25 model | 1/3 | 1/3 | 4 | 5,098 |
| Passage model | 1/3 | 1/3 | 4 | 2,529 |
| Predicate model | 1/3 | 1/3 | 3 | 1,559 |
| Explicit source calculation | 3/3 | 0/3 | 0 | 0 |

These are the recorded subset responses, not complete global usage: the historical run's extra untracked generations and incomplete token totals remain unresolved. The one unsupported-period question abstained correctly in each path. Invalid IDs were zero; independent citation/claim correctness remains null. Captured end-to-end means were 1705 / 1020 / 611 / 39.9 ms respectively, with original test contention and different generation counts; no causal latency advantage is inferred.

A fresh **offline source-processing replay** under current code measured approximately 113 / 71 / 38 / 38 ms for the four-task configurations. Those include source ingestion/selection, not generation, and are separate from the historical end-to-end timings. They cannot be added to old wall times or treated as replicated normalized performance evidence. [Comparison](docs/artifacts/final-hardening/offline-comparison.json).

**VERIFIED:** the existing optimizer was executed without model access on one frozen synthetic financial lookup using explicit source-calculation mode. Source removal lost the answer; no valid subset reduction qualified; decision **keep**, status **no_valid_reduction**, deployment **inconclusive**, zero model calls/tokens, approximately 11.18 ms wall time. [Optimizer report](docs/artifacts/final-hardening/deterministic-optimizer.json). It is a different one-task development workload, not a paired win over the historical four-question model paths. The provider boundary was patched to fail if this offline run attempted inference.

**PENDING:** quality-preserving optimization against independently established outcomes. Poor model accuracy and two new structural false abstentions prevent selecting a broadly reliable reference. Zero LLM calls from a different deterministic algorithm is not prompt compression or independently validated cost savings. No configuration was promoted, and local hardware/source-processing cost is unpriced.

## 5. Single external evaluation package

**VERIFIED packaging and reproducibility, PENDING independent evaluation.**

Download [SourceROI-external-evaluation.tar.gz](docs/artifacts/final-hardening/SourceROI-external-evaluation.tar.gz). It contains a frozen snapshot of the same SourceROI implementation, the model-free handoff and `START_HERE.md`; it is not a new repository/application. The archive was extracted to a temporary directory and its verification command executed successfully. [Extraction/verification record](docs/artifacts/final-hardening/package-verification.json).

The canonical [handoff directory](docs/artifacts/final-hardening/external-evaluation-kit/README.md) contains real original before/after IRS documents, preserved release output, twelve pending retrospective claim reviews, an unfilled independent-label protocol, an empty reviewer allowlist and a blank three-arm outcome template. It records implementation hashes and dependency versions. It contains no model weights, SQLite history, credentials, actual participants or fabricated review decisions.

The two lanes are explicit:

1. Retrospective claim/citation review of already exposed documents/outputs. Independent reviewers can judge supported/unsupported/contradicted claims; ambiguity remains pending with an explanatory note.
2. New source-owner-established before/after data and labels, intended/protected changes and disjoint hidden final groups, frozen **before** new final outputs using the existing independent-validation/onboarding tools.

Existing IRS benchmarks in the package are exposed development annotations. Hashes do not authenticate human identity or turn those annotations into independent final truth. No independent person/data was supplied, so semantic/citation metrics, final labels and final benchmark status remain **PENDING**, not successful.

During construction, the package tests exposed and repaired the omitted-question callback export bug and added stale benchmark/configuration rejection. Legacy review exports explicitly retain unrecorded-binding status for old minimal reports; new full handoffs require complete execution versions. Preliminary package builds are retained as intermediate evidence; use the canonical directory/archive above, whose implementation binding matches the final source snapshot.

## 6. Three-arm customer value and external integration

[External kit guide](docs/EXTERNAL_EVALUATION_KIT.md) and [existing-app workflow](docs/CONNECT_EXISTING_RAG.md) provide complete local commands, exact config/response fields, source manifest/identity checks, intent review, strict release invocation, JSON/Markdown export and troubleshooting. The source snapshot in the archive allows a developer to use these tools without editing SourceROI internals, once existing dependencies and their own app/data are provided.

**VERIFIED in synthetic adapter tests:** actual callback schema support, no expected answers passed into evaluated applications, manifest/index validation, unknown usage staying null, strict REVIEW without required judges, immutable outputs, source/config/benchmark drift rejection and package tamper detection. **PENDING:** compatibility with a genuinely independent customer's RAG app. The thin example's application import is deliberately supplied by that developer; it is not a claimed customer integration.

HTTP v2 remains the existing lower-level adapter with exact request/identity/restriction acknowledgments. The strict local built-in release path uses local RAG or a trusted callback; the guide explains how an existing HTTP app is invoked through that callback rather than pretending arbitrary HTTP runners are directly accepted. Assertions do not sandbox a dishonest backend. Callback logical-question limits do not prove hidden model/spend limits, so external apps need their own audited generation boundary.

The existing study has three equal-information arms:

- Maintained conventional full-suite checks.
- The same checks with ordinary source diffs and retrieval traces.
- SourceROI's integrated intent, proposals, review, impact, diagnosis and release workflow.

The kit includes preregistration/counterbalancing instructions, the existing event-logger commands, and blank outcome fields for actual active reviewer/integration time, edits/corrections, missed failures, release correctness, diagnostic correctness/usefulness, audited model calls/tokens and execution overhead. Wall-clock elapsed time is not automatically active labor. No human events were generated; automation stays excluded from human summaries.

**PENDING:** all human effort and integration-value outcomes. The previously audited maintained workflows still tie SourceROI: BLOCK on the historical regression and REVIEW on the calculated no-change case with absent semantic review. No new independent detection or maintenance advantage was manufactured by this hardening work.

## 7. Full tests and eight-feature preservation

**VERIFIED:** starting **276 passed in 7.66s**; final **299 passed in 13.12s**. [Final isolated test record](docs/artifacts/final-hardening/final-tests-isolated.txt). The test record before the last correction is preserved: its owner-death test raced the final supervisor lease release; the test now waits for actual cleanup rather than assuming the exit record instantly releases the lease. Another earlier run exposed legacy packet version compatibility; that behavior was restored while keeping new handoffs strict. No failed run was rewritten into a passing log.

Tests use isolated fake HTTP/UNIX-socket runtimes and explicit synthetic fixtures, not new Qwen experiments. Twenty-three new tests cover runtime accounting/lifecycle, provider transport, budget preservation and handoff integrity. All existing CLI, FastAPI, dashboard, release, review, numerical, study and database tests pass.

| Preserved capability | Exercised evidence |
|---|---|
| Intent-aware changes | Existing reviewed intended/protected behavior tests |
| Self-maintaining evaluation proposals | Immutable-label, proposal correction/rejection tests |
| Fact-to-agent impact | Existing versioned source/dependency mapping tests |
| Pre-deployment Data CI | Source/snapshot/configuration checks and strict release states |
| Diagnosis and isolated repair | Existing failure localization and non-mutating repair verification |
| Longitudinal intelligence | SQLite history, review/timeline/checkpoint tests |
| Dataset valuation and selection | Source/document/passage ablation and retrieval tests |
| Cost-aware optimization | Budget/quality/held-out/unknown-cost tests plus actual zero-model optimizer execution |

This is regression-scope preservation, not eight independent production/customer validations. No default answering/retrieval algorithm was promoted, and strict semantic review remains required. No unrelated project was changed.

## 8. Honest readiness verdict

- **VERIFIED:** existing workflows remain operational under tests; package extraction/integrity succeeds; known callback-export/budget-configuration defects are fixed; the owned control layer detects the tested fixture failures and refuses unverified live execution.
- **PRELIMINARY:** deterministic numerical grammar works on seven of nine newly authored supported examples. Prior source calculations are useful narrow development evidence, not general RAG reliability.
- **FAILED:** supported CSV/Markdown table coverage. Historical inference accounting discrepancies remain failures; they were preserved rather than excused by new tests.
- **PENDING:** native bounded-model accounting, independent hidden evaluation, real external integration, semantic/citation reliability, measured human benefit, production readiness and commercial differentiation.

An independent developer can now inspect/version/review the packaged knowledge update, prepare independent labels, connect their existing app through documented interfaces and run the human-study protocol. Native bounded experiments remain gated; the package must not be sold as verified native-inference infrastructure or independently proven optimization. The next evidence needed is native request-correlated accounting under the same isolated controls, real independently established labels/reviews on unseen documents, and real participants comparing the equally maintained three workflows.

[Final integrity manifest](docs/artifacts/final-hardening/final-integrity.json) separates verified fixture mechanics, zero new real inference, preserved history, generalization failures and pending external outcomes.
