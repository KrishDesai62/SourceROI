# Eight-feature closure matrix

All eight paths remain implemented and are exercised by `tests/test_isolated_eight_features.py::test_isolated_feature_and_source_version_boundary` (eight parameterized cases), alongside the full regression suite. These cases use authored fixtures/fake HTTP model responses, cold isolated ingestion and source-change identity assertions. They prove internal compatibility, not model quality or independent value.

| Feature | Actual acceptance path | Authentication / production limit |
|---|---|---|
| Dataset evaluation | `dataset`: manifest identities and task evaluation | Bounded ingestion/retrieval; native generation remains gated |
| Information valuation / ablation | `valuation`: source, document and passage exclusions | Isolated retrieval, set membership preparation; no new empirical ROI claim |
| Token/cost optimization | `optimization`: bounded candidates, quality filter and keep decision | Isolated policy/retrieval; trusted tokenizer callback rejected in strict path; synthetic usage only |
| Data CI | `data_ci`: freeze and baseline/candidate identity comparison | Isolated coverage/retrieval; durable fixture execution does not grant ACCEPT |
| Intent-aware changes | `intent`: expected versus protected task declaration | Pure worker proposals checked by parent; maintenance review remains mandatory |
| Reviewable evaluation maintenance | `maintenance`: explicit reviewed proposal and preserved frozen labels | Server identity/receipt binding; no inferred independent owner authority |
| Fact-to-agent impact mapping | `impact`: source changes and dependency classes | Source versions checked; heuristic impact coverage requires independent validation |
| Diagnosis / isolated repair | `diagnosis_repair`: full-source evidence diagnosis and bounded source-addition comparison | Isolated analytical diagnosis; explicit repair experiment, no automatic purchase |

Longitudinal SQLite history, CLI, FastAPI, dashboard, callback/HTTP contracts, citation/source identity, table/numerical evidence and strict release policies retain regression coverage (`test_live`, `test_api`, `test_design_partner`, `test_tabular_evidence`, `test_grounded_release`, `test_assurance`, `test_study`, identity/durable suites). Legacy trusted local interfaces remain available. Authentication does not grant unlimited generation authority: the authenticated durable route is fixture-only. General production native execution is deliberately unavailable until separately authorized and verified.

Shared blockers for all eight: independent sandbox/security acceptance, hard aggregate memory guarantees on deployment platform, appropriate source-owner/semantic authority, representative external validation. Test preservation is **VERIFIED internally**; semantic correctness/customer value/competitive advantage remain **PENDING**.
