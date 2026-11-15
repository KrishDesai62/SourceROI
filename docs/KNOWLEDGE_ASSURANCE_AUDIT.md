# Knowledge change assurance repository audit

November 13, 2026. Inspected before implementation: `live/{config,ingest,retrieve,policies,provider,adapter,engine,db,data_ci,diagnosis,reliability_study,cli,api}.py`, dashboard and prior reports/tests. This workspace has no `.git` directory, so no Git diff or commit claim is possible. No applicable AGENTS.md was found in the repository.

Baseline `python -m pytest -q`: restricted sandbox produced 111 passes, 11 localhost socket errors and one endpoint-startup failure. Repeating with localhost access produced **123 passed in 6.50 seconds**. This was an environment restriction, not evidence of 12 product regressions.

| Area | Verified existing capability | Missing before this phase | Implementation decision |
|---|---|---|---|
| Sources | Text/PDF/DOCX/HTML/JSON/CSV ingestion; document IDs/hashes; chunks; immutable Data CI snapshot | Explicit business intent and fact-version proposal | Extend snapshot/ingest with a review-bound specification |
| Evaluation | Independent labels, exact/QA/numeric grading; source/document/passage ablations; measured usage | Approved versioned expectation revisions | Keep original benchmark immutable; approved overlay and hash |
| Data CI | Source diff, literal evidence-loss checks, full/subset runs, temporary rollback | Intent-aware four-way release verdict | Add a small orchestration module over existing engine/DB |
| Adapters | Local chat, HTTP v2 restriction contract, lexical example | A minimal callback release example | Question-only trusted callback; preserve HTTP support |
| Persistence | Local SQLite run/checkpoint history | Proposed intent/review/fact timeline | Reuse runs table with new event kinds; no database replacement |
| Interface | Existing CLI/FastAPI/dashboard/history/export | Change proposal/review/release controls | Extend existing interfaces |
| Local inference | Installed Qwen2.5-1.5B GGUF and llama.cpp, pinned manifests, loopback controls | New workflow execution check | Four-call/60-second smoke, no downloads |
| Prior evidence | Archived 48-task and 12-task held-out reports, four lost/three recovered analysis | Independent groundedness/customer evidence | Preserve negative findings; do not relabel them as current differentiation proof |

Implementation plan: (1) add hashed source/fact/test-change proposals and explicit review; (2) map annotated/history/topic dependencies with broader controls; (3) execute bounded paired release checks and persist exact versions; (4) expose CLI/API/dashboard, repair and timeline; (5) run adversarial deterministic tests, requested baseline comparisons, one small local-model smoke and document limitations.

Historical artifacts were present and inspected. Their reported failed optimizer/no-savings findings remain historical evidence; this phase did not rerun or independently review their full held-out outputs. Existing optimization, attribution, Data CI and ablation workflows remain operational under the final regression suite.
