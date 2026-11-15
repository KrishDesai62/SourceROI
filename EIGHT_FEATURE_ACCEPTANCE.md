# Eight-feature acceptance through isolated ingestion — Phase 3

**VERIFIED authored fixture paths**, not empirical AI effectiveness. `tests/test_isolated_eight_features.py` explicitly clears the parser cache for each pillar, records actual isolated executions, performs the feature's operation, then changes source bytes and checks document-version drift. The existing complete regression suite remains separate evidence.

| Pillar | Meaningful new acceptance path |
|---|---|
| Dataset evaluation | Actual evaluation engine loads registered tasks/sources through child workers; result manifest matches parsed versions and task count. |
| Information valuation | Source and document ablation plus passage exclusion; excluded passage does not enter retrieved evidence. |
| Cost/token optimization | Existing optimizer runs on a deterministic local fake HTTP model. No valid reduction preserves the baseline (`decision=keep`), rather than inventing a saving. |
| Data CI | Frozen and current registered data pass through isolated parsing; equal source manifests stay equal in the controlled comparison. Shared-routing regressions also remain. |
| Intent-aware changes | Source edit produces a version-bound plan with explicit intended/protected task distinctions. |
| Evaluation maintenance | An explicit authored revision changes a materialized expectation while the frozen benchmark remains unchanged; exact source reference is retained. |
| Impact mapping | Changed-source plan retains explained direct/potential/unknown dependency fields and potentially affected tasks. |
| Diagnosis and isolated repair | Full-document evidence hit is found through isolated extraction; controlled registered-source addition improves the authored fixture result without modifying the original file or purchasing anything. |

All eight cases verify cold isolated execution and a subsequent changed source fingerprint. Their fake HTTP responses and costs are test data, not model usage, customer ROI, independent semantic labels or demonstrated optimization savings. An early optimizer test expected an incorrect success/None contract; it was corrected to assert the existing conservative keep-baseline behavior. The failed logs remain.

The broader suite preserves callback/HTTP v2 adapters, longitudinal SQLite history, numerical/table provenance, strict verdicts, protected evidence updates, native accounting gates, CLI and existing dashboard behavior. New authenticated fixture jobs use actual strict release evaluation with child-process protocol fixtures. Existing legacy trusted-local feature paths are retained on the tested macOS platform.

PENDING: genuine post-fix model performance, independent labels/reviewers, representative ablation interactions, customer workflow/effort, competitive advantage and full hostile-corpus downstream analytics bounds. SourceROI still tied the maintained conventional evaluator on the earlier real experiment; these tests do not overturn that result.
