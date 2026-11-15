# SourceROI technical brief — 2026-11-14

SourceROI is a standalone, local-first knowledge change assurance beta for teams running document-grounded agents. Its customer hypothesis: changing a source should trigger a reviewable dependency, expectation, evidence and release workflow rather than an unexplained accuracy delta. No paying customer or independently measured benefit is established.

The workflow registers source versions and tasks, freezes a baseline, proposes an intended update, maps potentially affected tasks, collects explicit expectation decisions, evaluates baseline/candidate behavior, checks citations and numerical contracts, diagnoses failures, tests isolated repairs, and exports a release decision. Strict releases retain independent semantic review requirements.

Architecture: Python CLI and FastAPI dashboard; file-based source/config/task snapshots; BM25 and passage/predicate selection; trusted Python callbacks or HTTP adapters to existing applications; SQLite run history; deterministic provenance and policy checks. No microservices, hosted tenancy or warehouse dependency. CLI binds loopback. New browser Host/Origin/body boundaries strengthen this local model; they do not supply authenticated users or reviewer roles.

Eight pillars remain: dataset evaluation, information valuation through ablation, cost/token optimization, Data CI, intent-aware change detection, reviewed evaluation maintenance, potential fact/task impact mapping, and diagnosis/isolated repair. Longitudinal history is also retained. See the feature matrix in PRODUCTION_READINESS_REPORT.md for limits.

Technical strengths supported by development evidence include exact source/version and table-cell provenance; immutable specification/review bindings; default fail-closed strict checks; explicit deterministic arithmetic with conservative refusals; and preserved adverse experiment results. These are integration capabilities, not a demonstrated competitive moat.

Known limits: exposed authored numerical cases do not establish semantic accuracy; local Qwen experiments performed poorly; historical native generations exceeded harness ledgers; owned native correlation remains PENDING and live execution disabled. Strict semantic review and reviewer identity depend on an external trusted operator. No independent external app, customer ROI, human effort savings or safe optimization advantage has been established. A maintained conventional evaluator tied observed release detection.

Business model assumptions: developer/team subscription or local enterprise licensing may be investigated. No pricing, willingness-to-pay, revenue, dollar dataset valuation or market-size claim is validated.

Next milestones: complete reproducible installation and dependency review; obtain an actual authorized source owner and independently labeled held-out tasks; integrate one existing application without changing SourceROI internals; conduct equivalent three-arm review/diagnosis effort measurements; solve native correlation before any model smoke; then assess authenticated access and tenant isolation if customer requirements justify them. See INVESTOR_EVIDENCE.md and PILOT_ONBOARDING.md.
