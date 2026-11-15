# Phase 4 entry verdict and next Codex handoff

**Conditional entry for remaining engineering and acceptance work only. Production acceptance PENDING. Phase 3 is not unconditionally complete.** Preserve the existing architecture, eight features, historical reports and consumed native authorizations.

Read `PHASE3_CLOSURE_REPORT.md`, `CLOSURE_SECURITY_MATRIX.md`, `ANALYTICS_ISOLATION_REPORT.md`, `CLOSURE_OPERATIONS_REPORT.md`, `BROWSER_ACCEPTANCE_REPORT.md`, `NATIVE_FIXTURE_CLOSURE_REPORT.md` and `EIGHT_FEATURE_CLOSURE_MATRIX.md`. Raw new evidence is under `docs/artifacts/phase3-closure/`. Earlier Phase 3/Phase 4 reports are historical, not overwritten current verdicts.

Next implementation/acceptance steps, in order:

1. P0: obtain independent security assessment of the scoped macOS profile, required runtime/code exceptions, typed analytical worker validation, trusted-parent bookkeeping, descriptor races and termination guarantees. Codex-authored tests do not satisfy independent acceptance.
2. P0: establish the actual deployment memory requirement and demonstrate a hard aggregate boundary with an appropriate supported OS primitive. Current 512 MiB sampled group RSS plus two shared slots is not sufficient evidence of hard memory isolation. Retain failure-closed gates if required protection cannot be demonstrated.
3. P1: implement vetted authenticated encryption/key custody around complete backups, with wrong-key/tamper/truncation/crash tests and restoration that preserves provenance and revokes live authority. Perform genuine offline/off-host recovery acceptance without customer uploads. Preserve existing plaintext historical archives rather than relabeling them encrypted.
4. P1: run sustained representative larger-corpus and multiple-service/CLI workload acceptance, including resource-pressure cleanup, forensic retention and restart. Test actual deployment OS/Python versions; current evidence is one Mac/Python combination.
5. P1: obtain real operator/source-owner/reviewer participation. Record delegation and independently verified semantic authority without auto-promoting a reviewer login. Complete full keyboard/screen-reader/accessibility and operator usability acceptance beyond the 17 browser checks.
6. Keep generation routes disabled. Any actual llama.cpp run needs separately reviewed execution/security gate and fresh explicit single-use budget approval. Native-style fixtures and their synthetic counters are not real model evidence. Never reuse the consumed prior empirical approval.

Reproduction commands (existing verified environment, no inference):

```sh
workspace/design-partner/venv/bin/python -m pytest -q
workspace/design-partner/venv/bin/python tools/validate_closure_browser.py --output /private/tmp/NEW-browser-output
workspace/design-partner/venv/bin/python tools/validate_phase3_acceptance.py --output /private/tmp/NEW-acceptance-output
workspace/design-partner/venv/bin/python tools/validate_closure_platform.py --help
```

Output directories must be new. Review fixture scripts before running; browser needs installed Chrome and local process/socket permissions. `validate_closure_install.py` uses local locked wheels and a current test wheel; it must not overwrite a sealed historical artifact. Before schema upgrade stop writers, take a complete trusted backup, then use explicit `auth-migrate`; supported older auth-aware builds reject the new store, so rollback requires a reviewed restore/reprovisioning plan rather than disabling authentication.

Maintain REVIEW for missing semantic review, BLOCK for protected regressions and INCONCLUSIVE for unknown execution. Do not infer independent semantic accuracy, customer ROI, competitive advantage, public deployment readiness or new native verification from this sprint.
