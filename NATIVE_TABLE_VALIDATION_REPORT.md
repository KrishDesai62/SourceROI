# SourceROI native accounting and tabular evidence validation

2026-11-14, America/Chicago. Existing standalone repository only. Zero external spending, no downloads/builds of models or native runtimes, no cloud or production changes, and **zero new live model calls**.

**VERIFIED:** optional CSV/Markdown evidence extraction, exact cell/source provenance, strict-release integration and 324 passing tests. **PRELIMINARY:** the unchanged supported development cases improve from **7/9 to 9/9**, with false abstentions falling **2 → 0**. **PENDING:** native request-correlated accounting, independent semantic validation and customer value. Native execution remains gated; no live smoke was launched.

## 1. Repository audit

The starting suite passed **299 tests in 9.25 seconds**. Existing owned-runtime controls, native reconciliation, ingestion, numerical contracts, citation checks, intent/evaluation maintenance, Data CI, diagnosis/repair, adapters, history and handoff tooling were inspected.

The two table failures were real: CSV ingestion flattened headers/rows into text, while the numerical binder accepted only supported sentence grammar. Markdown tables lacked a typed header/value relationship. Neither was an independently validated semantic benchmark. Prior source-calculation success of 7/9 and all historical accounting failures remain unchanged in the original artifacts.

Changes are limited to the existing evidence/release pipeline: a small literal table parser, optional raw table indexing, table-derived numerical facts, configured extraction reuse in impact/diagnosis, deterministic native-log auditing and versioned documentation/handoff. No new product/application, framework or inference dependency was added.

## 2. Native accounting result: PENDING

**VERIFIED artifact audit:** installed `llama-server` and its server implementation library match the previously approved cached runtime archive. The archive SHA-256 matches the pinned b12345 manifest. Read-only native help confirms private UNIX sockets, API-key-file authentication and JSONL logging options. No server startup or generation was attempted.

**PENDING correlation:** the pinned upstream HTTP source leaves the request/response logger registration commented out. This does not establish that no alternative instrumentation is possible, but the available runtime artifacts do not provide a verified server-side mapping from each reserved client request to its actual response. Task totals cannot supply that missing evidence. [Pinned upstream source](https://github.com/ggml-org/llama.cpp/blob/b12345/tools/server/server-http.cpp#L245).

The owned runner's native audit now distinguishes generation task launches, timing records and cancellations. It does **not** report timing records as confirmed completions. Matching counts still yield PENDING; extra tasks/child generations are flagged. Prompt-like text cannot masquerade as a recognized slot-launch line. Deterministic protocol tests cover plain/JSONL logs, equal-count false assurance, untracked tasks, cancellation and child generations. Existing owned-runtime tests retain concurrency, failed/retried requests, interruptions, shutdown, leases and immutable evidence checks.

[Native audit](docs/artifacts/native-tables/native-audit.json) records the actual binary/archive checks and the source limitation. The source-to-binary build was not independently reproduced. Legacy log audits still find 11 / 19 / 15 generation task launches for the IRS / engineering / grounded runs; the latter two exceed their eleven captured harness requests. These are diagnostic counts, not complete request/response or usage reconciliation.

**Gate decision:** native request correlation is unverified, so live construction remains refused. No two-call/30-second smoke was launched. New real model requests/generations were zero; there is no new measured native provider usage or latency to report. Fixture protocol usage must not be substituted for Qwen usage. Missing historical usage remains unknown.

## 3. Table implementation and provenance

Enable `settings.table_evidence: true` only in a new reviewed configuration. Default CSV extraction/fingerprints remain unchanged; legacy projects do not silently switch representations. Source-calculation answering remains separately explicit and authorized.

Supported literal layouts:

- Long CSV: unambiguous subject, attribute, period, value and unit columns.
- Wide history: explicit period columns, subject/attribute and unit.
- Markdown tables with a valid alignment row and an explicit predicate/unit value header, such as `Price USD`.
- Product/plan subjects bound exactly from header plus cell, such as `Plan` + `Pro`; no fuzzy entity guessing.

Every table fact retains source ID/version, raw file-byte SHA-256, exact full-table quote, stable content/offset-bound passage ID, header/cell quotes and character spans, normalized value, unit, period, authority and source applicability metadata. CSV quoting and multiline fields, escaped Markdown pipes, Unicode and CRLF provenance are tested. Character offsets refer to UTF-8-sig decoded document text with original newlines; they are not byte offsets. A separate byte hash binds the physical source file.

Missing/duplicate/ambiguous headers, malformed row widths, missing cells, nonnumeric expressions, conflicting rows/units and unrecognized nonempty qualification columns fail closed. Nearby qualification language is conservatively escalated rather than silently ignored. Conflicting candidate rows remain visible. Units/periods are supplied by source columns/headers rather than guessed from the requested answer. Unrelated malformed tables cannot supply or replace the target fact.

Whole literal tables participate in the normal index. Oversized tables are not partially selected or sent wholesale to a model; `excluded_oversized_table_ids` records the exclusion. Large/nested/multilevel tables, arbitrary captions, row-level applicability semantics, OCR and broader financial-table meaning remain unsupported or unverified. Nearby qualification screening can cause legitimate false rejections.

The engine resolves header/cell subject separation only from source-validated, operator-authorized bound table subjects. It does not relax necessary evidence checks for unrelated subjects or grant semantic approval. The same calculation is reconstructed from **actually cited** table context for numerical consistency checks.

Main files: [tables.py](sourceroi/live/tables.py), [ingest.py](sourceroi/live/ingest.py), [facts.py](sourceroi/live/facts.py), [engine.py](sourceroi/live/engine.py), [release_policy.py](sourceroi/live/release_policy.py), and [configuration guide](docs/TABLE_EVIDENCE.md). Config-aware extraction is reused by impact mapping and diagnosis, so raw CSV reference evidence is not incorrectly searched in the old flattened representation.

## 4. Before/after numerical results

**PRELIMINARY, frozen development cases only.** The earlier nineteen authored cases, source files, labels and task operations were replayed unchanged in fresh workspaces. Only the explicit table option differs between before/after. No expected values or question-specific rates were added to extraction rules. No labels were rewritten after output inspection.

| Metric | Table support off | Table support on |
|---|---:|---:|
| Supported answers correct | 7/9 | **9/9** |
| Supported false abstentions | 2/9 | **0/9** |
| Safety cases refused as expected | 8/8 | 8/8 |
| Unsupported contracts rejected | 2/2 | 2/2 |
| Live model calls | 0 | 0 |
| Independent semantic quality | null | null |

The two recovered cases are the historical CSV lookup (1350) and Markdown pricing lookup (24). Values come from the unchanged source cells; they are not parser constants. The remaining financial/pricing arithmetic, comparison and decimal cases retain their results. Unsupported nonnumeric eligibility and arbitrary multi-step formulas remain rejected, rather than being described as semantic successes.

[Final replay](docs/artifacts/native-tables/final-replay/comparison.json), [frozen replay plan](docs/artifacts/native-tables/final-replay/replay-plan.json), [as-run source hashes](docs/artifacts/native-tables/final-replay/code-freeze.json), and [as-run code](docs/artifacts/native-tables/final-replay/as-run-code.tar.gz) preserve the evidence. Exact source/table/cell quote spans were checked during replay. The current implementation matches the recorded as-run hashes.

These are exposed Codex-authored development cases, not independent generalization. Nine successful supported cases do not establish general financial or pricing reliability, quality-preserving optimization, or customer value. This sprint did not rerun/tune the Qwen benchmark or promote any optimizer configuration.

## 5. Evidence integrity and release safety

**VERIFIED through deterministic integration tests and an explicitly synthetic source update.** Table facts participate in source/version integrity, metadata applicability, reference coverage, actual retrieval/citation membership, numerical evidence checks, intent proposals and source-change impact.

The [table workflow proof](docs/artifacts/native-tables/table-workflow-summary.json) exercises the existing pipeline with a synthetic intended numerical update:

- A source matching the explicitly reviewed numerical target passes exact/numerical checks but remains **REVIEW** without independent semantic judgments.
- The wrong candidate source value produces **BLOCK**; Data CI also flags the changed frozen expectation/evidence.
- An isolated correction restores numerical expectations, while strict semantic status stays **REVIEW**. Joint repair is **INCONCLUSIVE**, because the existing repair gate requires full acceptance; it does not manufacture that missing approval.
- The original candidate remains unchanged. There is no automatic production repair or fabricated source-owner approval.

[Strict release](docs/artifacts/native-tables/table-release.json), [Data CI](docs/artifacts/native-tables/table-data-ci.json), and [isolated repair](docs/artifacts/native-tables/table-isolated-repair.json) retain the complete results. All provider access was blocked during these executions. The reviewers/task authors are labeled synthetic/Codex development fixtures, not independent humans.

Independent claim/citation review is still required. Correct cell values, valid IDs or arithmetic consistency cannot independently authorize strict ACCEPT. Legacy strict, BLOCK/REVIEW/INCONCLUSIVE, adapter and repair tests all remain passing.

## 6. Full regression results and preserved capabilities

**VERIFIED:** final complete suite **324 passed in 10.19 seconds**. [Full record](docs/artifacts/native-tables/final-tests.txt). Focused table/native protocol suite: **25 passed in 0.17 seconds**. [Focused record](docs/artifacts/native-tables/focused-tests.txt). Ordinary pytest kept live-model access blocked and held the runtime/test lease.

The new tests cover long/wide CSV, Markdown, quoted/multiline data, escaped pipes, Unicode/CRLF, source/cell hashes and spans, missing/ambiguous cells/headers, wrong entities/units/periods, conflicts, surrounding conditions, oversized tables, tampered cell maps, date/jurisdiction mismatch, opt-in legacy compatibility, header/cell subject checks, strict numerical review, Data CI and conservative native-log auditing.

All eight existing capabilities remain operational within regression/integration scope:

| Capability | Preservation evidence |
|---|---|
| Intent-aware changes | Existing tests plus the table change plan |
| Evaluation maintenance | Reviewed changed expectations/evidence; original labels remain frozen |
| Fact-to-agent impact | Config-aware source extraction and existing dependency tests |
| Data CI | Existing tests plus the table regression |
| Diagnosis/repair | Config-aware full-source evidence and isolated table repair |
| Longitudinal intelligence | SQLite history/timeline/checkpoint tests and recorded runs |
| Valuation/selection | Existing ablation tests; table candidates use existing selection paths |
| Cost-aware optimization | Existing budget/quality/held-out tests; no unsupported new savings claim |

CLI, FastAPI, dashboard, existing adapters and SQLite behavior remain covered. A changed extraction configuration must be explicitly reviewed; data-only comparison requires matching settings. No unrelated project or prior report was changed.

## 7. External evaluation kit v2

Verified extraction/index changes require a new package version. Earlier archives and integrity manifests remain intact. The new [versioned archive](docs/artifacts/native-tables/SourceROI-external-evaluation-v2.tar.gz) includes the same SourceROI implementation snapshot, original real before/after review documents, pending semantic packet, blank independent-label protocol, empty authorized-reviewer list, three-arm study instructions and table integration guide.

The archive was extracted into a separate temporary source directory. Verification, onboarding-template generation and integration CLI help were executed there without modifying SourceROI internals. [Package verification](docs/artifacts/native-tables/package-verification.json). This demonstrates packaging/tool execution, not compatibility with a real customer's application.

[Handoff README](docs/artifacts/native-tables/external-evaluation-v2-ready/README.md), [table guide](docs/TABLE_EVIDENCE.md), and [external workflow](docs/EXTERNAL_EVALUATION_KIT.md) explain source manifests, citation/index IDs, intent review and strict JSON/Markdown export. External apps must use the actual table index or a verified exact mapping. The thin app import remains a developer-supplied existing application, not a fabricated independent integration.

The existing three-arm maintained-evaluation comparison remains unchanged: conventional evaluation, the same evaluator with ordinary diffs/traces, and SourceROI receive equivalent authoritative information. No new participants/events/timings were generated; detection superiority and human maintenance/integration savings remain unmeasured. Independent semantic/citation review, hidden final labels and customer validation remain **PENDING**.

## 8. Result categories and next requirements

- **VERIFIED:** optional literal table parsing/provenance; integrated numerical/release checks; preserved interfaces and all 324 tests; archive extraction/tool execution; historical evidence integrity.
- **PRELIMINARY:** 9/9 supported development answers with table support, versus 7/9 off. This is a small, exposed, authored grammar validation.
- **FAILED (historical, preserved):** the fifteen-versus-eleven and nineteen-versus-eleven accounting discrepancies. No new native smoke failed, because none was launched. Broader unsupported/qualified table forms can still refuse legitimate questions; native request verification remains PENDING.
- **PENDING:** native accounting result, independent semantic quality, real external RAG integration, hidden final evaluation, customer-effort advantage and commercial differentiation.

The native result requested for this sprint is **PENDING**. Further native work needs an approved, independently auditable request/response correlation mechanism before any bounded smoke. No larger model, new runtime download, cloud service or paid API was used to bypass that gate.

Independent users still need genuine source-owner-established labels on new document groups, actual claim/applicability judgments, and real participants in the equal-authority three-arm study. Neither successful tables nor an independent evaluator's ability to run the package proves commercial value. No independent accuracy or quality-preserving optimization claim is made.

[Integrity manifest](docs/artifacts/native-tables/final-integrity.json) and [summary](docs/artifacts/native-tables/summary.json) distinguish the verified table mechanics from the still-pending native and independent outcomes.
