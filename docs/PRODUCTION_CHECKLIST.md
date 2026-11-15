# Production-readiness checklist (not yet complete)

SourceROI v0.2 is a **functional, local-first beta**, suitable for hands-on experiments and engineering evaluation in a controlled environment. It is **not** ready to store regulated customer records on an internet-facing SaaS.

## Already implemented

- [x] Real file ingestion (PDF/DOCX/CSV/JSON/text/HTML) with file size and corpus limits
- [x] OpenAI-compatible live model runner and user-operated HTTP agent adapter
- [x] Dataset/document ablations, ground-truth scoring, run comparisons
- [x] Actual end-to-end task latency and provider-reported token counts
- [x] Explicit unknown-vs-estimated USD pricing semantics
- [x] SQLite persisted runs and source/content fingerprints
- [x] Model-call limit, explicit paid-call confirmation, optional estimated-dollar guard
- [x] Environment-based secrets, validated project-relative files, localhost-only server
- [x] Offline/HTTP integration tests and automated GitHub Actions workflow

## Required for external production customers

- [ ] Authentication and enterprise SSO with real session management
- [ ] Organization isolation, fine-grained permissions, audit logs
- [ ] Encrypted storage, managed secrets, retention policies, deletion procedures
- [ ] TLS termination, deployment network controls, CSRF protection and rate limiting
- [ ] Distributed workers/queue, cancellation, retries, idempotency and durable job recovery
- [ ] Hosted LLM and data-provider licensing/privacy review with explicit customer permissions
- [ ] Support for private cloud deployments and vendor DPAs/security questionnaires
- [ ] High-volume vector, SQL and object-store connectors with source-level entitlements
- [ ] Verified instrumented traces, reproducible stateful agent sandboxes and tool side-effect controls
- [ ] Stable schema migrations, backups/restores, telemetry and alerting
- [ ] Load tests and fault injection for high task volumes/concurrent users
- [ ] Human-validated open-ended benchmarks, repeated-run confidence and drift detection
- [ ] Independent security review and penetration testing
- [ ] Actual customer integration/usage showing improved reliability beyond existing eval tools

## Local operating advice

Keep this beta on **localhost**, use only data you are licensed and permitted to process, protect your workspace files and SQLite database, and do not paste credentials into `project.json`. Use a dedicated test dataset and budget-capped API account for experiments.
