# External pilot acceptance report — 2026-11-14

## Verdict

**VERIFIED:** isolated installation, parser availability, dependency identity, extracted-distribution synthetic demo, callback onboarding/protected regression, local HTTP protocol tests, review-package integrity and automated three-arm logging. **PRELIMINARY:** a controlled single-user external pilot is mechanically supportable under the documented constraints. **PENDING:** actual independent developer acceptance, application-specific compatibility, independent semantic results and production readiness. No external participant was invented.

## Scope and implementation

Existing standalone SourceROI retained. Changes are packaging and acceptance tooling: a complete platform-specific wheel/hash lock, MANIFEST.in for runnable source distributions, parser/installed-file/lock verification tools, a labeled synthetic application adapter, existing-CLI onboarding/demo acceptance harnesses, fresh output/workspace options for table verification, and canonical pytest testpaths. No SourceROI core API, engine, database schema, release policy or native gate changes were required for the tested callback contract. Historical reports and archives remain immutable.

## Evidence

- Clean venv uses Python3.13/macOS arm64, no user/system-site packages, 27 locked dependency wheels and one non-editable SourceROI application wheel. DOCX/PDF/text parser smoke and pip check pass. See CLEAN_INSTALL_REPORT.md and installed-parsers.json.
- Fresh source distribution demo runs the original replay plus existing evaluation/ablation/optimization, intent/impact/review, Data CI/diagnosis/repair and release paths. See INVESTOR_DEMO_VERIFICATION.md. The 22/22 legacy fixture result is not model accuracy.
- Existing source-owner helper → source freeze → change-plan → DRAFT rejection → synthetic reviewed decisions → trusted callback bridge → strict REVIEW → claim export → package build/verify all execute. A separate protected warranty regression produces BLOCK. Four pending baseline/candidate claim-review items remain unfilled. No internal SourceROI modification was needed; adapter-side mapping uses the existing documented index/manifest contract. This is Codex-operated internal integration, not external adoption.
- HTTP v2 is exercised against the real loopback deterministic reference server in test_reference_agent_v2_over_actual_local_http, with no LLM. Callback tests reject forged manifests and preserve label separation. Full suite evidence includes both boundaries.
- Existing v2 archive is included unchanged; it verifies against its own frozen implementation. The new pilot distribution is an installation/demo handoff, not relabeled independent evaluation or a rewrite of that archive. Fresh pending packages/review exports also verify under current code.
- Automation-only start/complete events exercise maintained_full_suite, maintained_with_diff and sourceroi; all three are excluded from human sessions and time_savings remains null. Independent review/protocol negatives retain version/identity requirements. No human timings or advantage are simulated.
- Existing SQLite backup/restore, native gate, cancellation/failure and strict-release regression tests pass. High-risk remaining operations are audited in PRODUCTION_BLOCKERS.md; no production-readiness declaration follows.

The full clean-environment suite and five new acceptance-tool regressions are recorded under docs/artifacts/pilot-acceptance/. Initial duplicate test collection failed because a source distribution was extracted under workspace; testpaths fixes the demonstrated discovery defect. The initial failure log is preserved alongside subsequent passing runs. Exact final counts, artifact hashes, final bundle verification and historical integrity are in summary.json.

## Eight-pillar acceptance matrix

| Feature | Internal acceptance evidence | Independent / production status |
|---|---|---|
| Dataset evaluation | VERIFIED 22/22 legacy fixture plus existing full suite | PENDING representative independent quality |
| Information valuation | VERIFIED source/document ablation and task-loss reports | PENDING causal/interaction and economic validation |
| Token/cost optimization | VERIFIED existing modeled quality-floor selection and optimizer tests | Historical real quality FAILED; safe real savings PENDING |
| Data CI | VERIFIED bad candidate blocked; suite checks incompleteness/provenance | PENDING real app/infrastructure |
| Intent-aware changes | VERIFIED versioned plans, intended/protected tasks and diffs | PENDING real owner authorization |
| Evaluation maintenance | VERIFIED draft refusal, explicit synthetic review, immutable originals | PENDING authenticated independent human review |
| Impact mapping | VERIFIED deterministic document/task proposal outputs | PENDING semantic precision/coverage oracle |
| Diagnosis/repair | VERIFIED causes recorded; isolated repair never auto-ACCEPTs missing review | PENDING independently established causal correctness |

Longitudinal SQLite history, CLI, FastAPI, dashboard and legacy adapters remain covered by the suite. No new product pillar/framework was added.

## External acceptance requirements

The first actual developer follows FIRST_EXTERNAL_DEVELOPER.md and supplies their own authorized application/source/labels. Record any app-side index mapping or adapter work, active integration effort, failed instructions and report usefulness in PILOT_FEEDBACK.md. Independent reviewers judge exact frozen claim packets. Conduct equal-authority three-arm sessions only with real consented participants and actual timing. Until these occur, independent usability, quality, benefit and willingness-to-pay remain PENDING.

External spending $0; real generations 0; no new models/runtime, cloud deployment, customer data or production database mutation. Historical adverse Qwen results and incomplete native usage remain intact.


## Final acceptance evidence

VERIFIED: complete clean-environment suite **349/349 passed in 9.44s**; extracted-distribution contract/security/package/HTTP tests **31/31 in 1.00s**; five new tooling regressions passed. A second empty venv installed all 28 distribution wheels offline with required hashes, and its parser/demo/onboarding checks passed. Native model calls and external spend remain zero.

VERIFIED final distribution: [SourceROI-pilot-py313-macos-arm64.tar.gz](docs/artifacts/pilot-acceptance/SourceROI-pilot-py313-macos-arm64.tar.gz), SHA-256 `4f6668101c87777d202df3d4a77f014bb570cb1766e211d1c2387147a5d9acf3`. The source bundled at build time is frozen; these post-build results and final manifests are companion evidence under docs/artifacts/pilot-acceptance/. Verify archive contents before creating caches or working files; executing Python/tests adds unregistered bytecode/state to a working extraction and must not be mistaken for the sealed archive.
