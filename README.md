# SourceROI — knowledge change intelligence and release assurance

**Version 0.2 · live evaluation beta · built for VS Code**

SourceROI helps review what should change, what must remain correct, and whether an agent's knowledge update passes its registered release checks. It also measures how an AI agent's answers, task completion time, and cost change when you add, remove, or update real data sources. It compares source and document ablations, records experimental runs in SQLite, and flags newly incorrect benchmark answers after the corpus changes.

**The live product contains no fictional datasets or precomputed results.** It begins with an empty workspace. Connect your documents and a real model/agent, provide independently checked answers, then execute a benchmark to see *actual* measured runtimes, provider-reported tokens, and task correctness. The legacy offline synthetic demonstration remains available separately.

> **Scope:** A working, local-first **product beta**, not a security-audited, multitenant production SaaS. Live external calls have not been tested against a paid production model without your credentials. Hosted usage, independent enterprise validation, and real-world accuracy are **not claimed**.

## Latest pilot acceptance

**349 tests pass**, plus **31 extracted-distribution contract tests**. A Python3.13/macOS arm64 [offline pilot bundle](docs/artifacts/pilot-acceptance/SourceROI-pilot-py313-macos-arm64.tar.gz) includes hashed dependency wheels, installed application, source tools/examples and preserved replay evidence. Clean installation now verifies DOCX/PDF/text parsers. The synthetic demo and callback/HTTP boundaries are mechanically tested; no independent adoption, semantic quality, customer value or production readiness is claimed. Start with [exact developer commands](FIRST_EXTERNAL_DEVELOPER.md), [clean install report](CLEAN_INSTALL_REPORT.md), [pilot acceptance](PILOT_ACCEPTANCE_REPORT.md), [demo verification](INVESTOR_DEMO_VERIFICATION.md), [production blockers](PRODUCTION_BLOCKERS.md) or the [investor summary](INVESTOR_PILOT_SUMMARY.md). Native inference remains gated. Earlier reports/archives remain unchanged.

## Latest production-oriented beta hardening

**344 automated tests pass**, including 20 new trust-boundary, storage, readiness and replay checks. API Host/Origin/body limits, database confinement/rollback, parser prechecks and tested SQLite backup/restore strengthen the restricted single-user local beta. Native accounting remains **PENDING**, with **zero new real generations**. Independent quality/customer benefits and production readiness are not established. Start with [pilot onboarding](PILOT_ONBOARDING.md), [production readiness and feature matrix](PRODUCTION_READINESS_REPORT.md), [investor evidence](INVESTOR_EVIDENCE.md) or the explicitly [historical synthetic demo](INVESTOR_DEMO_RUNBOOK.md). Existing archives and adverse results are preserved.

## Latest native/table validation

**324 tests pass.** Optional CSV/Markdown source and cell evidence fixes the two demonstrated table failures: the unchanged development cases improve **7/9 → 9/9**, with false abstentions **2 → 0**. Independent semantic quality remains pending. Native request correlation is still **PENDING**, so no live smoke was launched. The versioned [external kit v2](docs/artifacts/native-tables/SourceROI-external-evaluation-v2.tar.gz) was extracted and its synthetic importer/freeze/calculation workflow verified without model access. See [the full report](NATIVE_TABLE_VALIDATION_REPORT.md) and [opt-in table guide](docs/TABLE_EVIDENCE.md). Earlier evidence/packages remain intact.

## Earlier hardening

**299 tests pass.** Runtime accounting controls now use an owned authenticated socket, test/runtime lease, durable reservations, cancellation supervision and integrity audits. These controls are verified with explicit fake runtimes; **native inference remains disabled pending native request correlation**. No new real model calls were made. New synthetic numerical fixtures score **7/9 supported answers**, with table formats still failing. A single [external evaluation archive](docs/artifacts/final-hardening/SourceROI-external-evaluation.tar.gz) contains real versioned sources, pending review/label templates, a three-arm study and the existing-app integration kit. Independent reliability and human benefit remain pending. See [the hardening report](FINAL_HARDENING_REPORT.md).

## Earlier grounded-reasoning sprint

**276 tests pass.** Explicit opt-in source-calculation mode answered **3/3 supported development questions** versus **1/3** for each local-model path, and abstained on the missing-period case. This is a narrow declared-grammar calculation mode; independent semantic validation remains pending. **Accounting failed:** the harness captured 11 calls, but the runtime log confirms 15 generations, exceeding the twelve-call limit. Full usage is unknown; external spending was $0. Test isolation was repaired. The earlier engineering runtime log also shows 19 completions against its reported eleven harness calls; historical evidence is preserved. See [the full report](GROUNDED_REASONING_VALIDATION_REPORT.md) and [existing-app onboarding](docs/CONNECT_EXISTING_RAG.md).

## Earlier engineering sprint (preserved report; accounting correction above)

**247 tests pass.** Opt-in source-bound passage indexing/selection and review-only numeric diagnosis are implemented. On fresh IRS development questions, supported correctness remained **1/3** for all policies; passage selection used **52.6% fewer tokens but failed the fixed quality requirement**. Independent semantic validation and human effort savings remain pending. Three maintained workflow arms tied on the historical unsafe update. **11 new local generation calls, 11,508 tokens, $0 external spend.** See [the engineering sprint report](ENGINEERING_DIFFERENTIATION_REPORT.md) and [external-review handoff](docs/ENGINEERING_SPRINT_HANDOFF.md).

## Earlier real-document validation

**234 tests pass.** A real local-Qwen run on official 2024/2025 IRS PDFs found supported-answer accuracy of **1/5 before and 2/5 after**, against frozen Codex-authored development labels. SourceROI blocked a protected medical-answer regression; an equally maintained conventional checker also blocked it. Top-k reduction saved tokens on one question but lost correctness. **11 generation calls, 15,777 tokens, $0 external API spend.** Independent semantic review, quality-preserving optimization, and differentiated customer value remain unverified. See [the full real-world validation report](REAL_WORLD_VALIDATION_REPORT.md).

## Earlier grounded validation (preserved historical result)

**230 automated tests pass.** Explicit numeric/text/boolean/flat-object contracts now preserve raw answers and reject format violations; owner-declared evidence requirements can trigger clearly labeled software abstention. Configured strict releases cannot be downgraded.

The local experiment was negative on supported answers: **0/4 answered, 4/4 abstained**. Screening changed one empty-context hallucination to an abstention, but recovered no valid answers. The harness initially reported 10 calls; the preserved-report audit found **11 actual calls**, within the user limit of 12 but one over the planned 10. External spend was $0. No human-effort or competitive advantage is established.

[Measured results and accounting audit](docs/GROUNDED_RELIABILITY_REALWORLD_VALIDATION.md) · [Real source-owner onboarding](docs/SOURCE_OWNER_ONBOARDING.md).

## Grounded release reliability

**204 automated tests pass.** An explicit **strict grounded policy** now requires citation integrity, provenance, complete required checks and independent semantic review. Legacy exact/reference checks remain available with their approval scope labeled.

The main local smoke improved from **0/4 to 4/4 cited responses**, with valid retrieved IDs, but strict release remains **REVIEW**. Tokens increased from 848 to 1,080. Final-schema controls still exposed a failed abstention and a numeric-format mismatch; the same-model judge also accepted unrelated warranty evidence. These failures are retained.

Declared intent guards the known protected-warranty proposal. SourceROI still ties maintained full-suite testing; independent grounding, customer validation and net human effort savings remain unproven.

[Full grounding sprint report and measured limitations](docs/RELIABILITY_GROUNDING_SPRINT.md) · [Agent integration](docs/GROUNDED_AGENT_INTEGRATION.md) · [Maintenance study handoff](docs/EVALUATION_MAINTENANCE_STUDY.md).

## Latest validation: fair baselines and response robustness

**183 tests pass.** Numeric JSON answers now normalize correctly; the repaired four-call local smoke passes its registered exact-answer/reference checks. All four outputs lack citations, so independent semantic/citation reliability remains **REVIEW**.

With identical approved labels and evidence updates, SourceROI **ties a maintained full-suite baseline** on 13 exposed authored scenarios: eight blocking cases, three legitimate updates and two review cases. No safe cost advantage or total human maintenance saving is established. A separate-process, Codex-authored record RAG demo accepted the intended update, blocked a protected failure and rejected an unknown corpus version. Independent customer validation remains unfinished.

[Validation sprint results, reproduction commands and external review handoff](docs/VALIDATION_DIFFERENTIATION_SPRINT.md).

## Knowledge change release workflow — November 13, 2026

Before changing an agent's knowledge, inspect a hashed source/fact diff, review proposed evaluation revisions, protect unchanged behaviors, run paired checks, and receive **ACCEPT / BLOCK / REVIEW / INCONCLUSIVE**. Existing ablations, source value studies and optional optimization remain available.

The local callback demo runs end to end with no model or network:

```bash
python examples/knowledge_change/demo.py --output workspace/my-knowledge-demo
```

Thirteen authored deterministic scenarios exercised the workflow; independent final validation and review-time savings remain unproven. A genuine four-call local-model smoke **blocked** a required-answer format failure. Reference coverage matched consequential detection; no unique detection or safe test-reduction advantage is claimed.

[Implementation, all eight feature statuses, measured comparisons and integration commands](docs/KNOWLEDGE_CHANGE_ASSURANCE.md) · [Repository audit](docs/KNOWLEDGE_ASSURANCE_AUDIT.md) · [Competitive documentation audit](docs/KNOWLEDGE_ASSURANCE_COMPETITIVE.md).

## Latest reliability-first validation — November 13, 2026

Added evidence-aware selection, conservative fallback, frozen-source Data CI, missing-information diagnostics, and bounded local evaluation through the CLI/API/dashboard. **123 tests pass.**

A fresh, document-group-separated 24-task benchmark (12 development, 12 held out) used the approved local model. The complete validation session made **283 generation calls in 354.75 seconds, with $0 external API spend**. On held-out questions, the original and guarded selector both scored **5/12**, using **9,969 total tokens**. Fallback activated on every question, preserving results but saving no tokens. A qualified simple task-aware baseline scored **5/12 with 5,893 tokens**, with no newly incorrect answers. The unguarded evidence selector introduced one regression despite the same aggregate score. No optimizer superiority is established.

In a separate controlled source-removal test, Data CI detected lost annotated evidence while answers stayed correct. A simple reference-coverage check caught the same loss; SourceROI additionally localized the version change and verified a temporary rollback. Groundedness review remains pending.

[Complete reliability report, measurements, limitations and artifacts](docs/RELIABILITY_VALIDATION.md) · [Prior failure analysis](docs/SOURCE_FAILURE_ANALYSIS.md).

## Earlier genuine local-model result — November 13, 2026

SourceROI was evaluated with **Qwen2.5-1.5B-Instruct Q4_K_M running locally**, using 96 published SQuAD/HotpotQA tasks (48 development, 48 held out). The run completed 1,920 real inference calls with **$0 external API spend**.

SourceROI used **33.22% fewer total tokens** than the original but scored **21/48 versus 22/48**, introducing four failures and recovering three. Its recommendation was **rejected**. Tuned top-k preserved the original results. No quality-preserving optimization advantage was demonstrated; semantic grounding remains pending human review.

[Full local-model setup, measurements, limitations and reproducible artifacts](docs/LOCAL_LLM_VALIDATION.md). Regression suite at that earlier phase: **98 passed**. The older synthetic and retrieval-only results below are separate historical evidence, not substitutes for this result.

## Quickest setup (Mac / Linux / VS Code)

Open this folder in VS Code and enter:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m sourceroi serve
```

Open **http://127.0.0.1:8765**. The default workspace is empty on purpose. The dashboard shows how to add real data.

### Put your real documents into SourceROI

**Option A — easiest:** Put some `.pdf`, `.docx`, `.md`, `.txt`, `.csv`, `.json`, or `.html` files into `workspace/sources/your_documents/`.

**Option B — import whole datasets:** Group your folders by source and run:

```bash
python -m sourceroi init --documents ~/Documents/my-agent-data --output myworkspace
```

For example, the input folder may contain `SEC_Filings/`, `Earnings/`, and `Industry_Research/`. Each first-level subfolder becomes its own SourceROI dataset. Top-level files go under `General documents`. The importer **copies** source files; it does not change your originals. Files are kept locally.

Then add benchmark tasks to `myworkspace/benchmark.jsonl` (or `workspace/benchmark.jsonl` for the default workspace). Each line must be a complete JSON object:

```jsonl
{"id":"f01","category":"Financial facts","question":"What was ExampleCorp's FY2025 reported revenue? Give only the number in millions.","expected":"920","scoring":"numeric","tolerance":0}
{"id":"f02","category":"Earnings","question":"What year did the company announce the product?","expected":"2025","scoring":"exact"}
```

**Replace these illustrative examples with independently verified questions and true answers from your own documents.** Do not paste unverified model-generated answers into the benchmark; that would invalidate the quality results. The `benchmark.example.jsonl` file is a template, **not automatically evaluated**.

### Connect an actual model

For a hosted OpenAI-compatible chat API:

```bash
export OPENAI_API_KEY='your-api-key'
python -m sourceroi --project myworkspace doctor
python -m sourceroi --project myworkspace serve
```

The `model` section in `myworkspace/project.json` contains the model name, endpoint, secret **environment-variable name**, and optional token pricing. The API key is never kept in SourceROI's config or returned to the UI.

For a local OpenAI-compatible server (for example Ollama), edit `model.base_url` and `model.name` to your installed model. Localhost endpoints do not require an API key. Availability and compatibility depend on your chosen model server.

**Cost note:** Token counts are read from the provider's actual `usage` response. When rates are configured, SourceROI calculates an *estimate* from those token counts; it is not your final provider invoice. If usage or rates are missing, USD cost shows **Not priced**, not a made-up value. For static local files there is no upstream pay-per-query data charge; an existing external agent can report its actual data API charges separately.

## What you can measure now

### Optimization engine

The optimizer executes source subsets on development tasks, freezes its selection, and compares original, reduced top-k, fixed source-drop, and SourceROI configurations on held-out tasks. It enforces an accuracy floor and rejects newly incorrect tasks by default. Missing cost or token usage cannot win the corresponding objective.

```bash
python -m sourceroi --project myworkspace optimize --quality-floor 0.9 --objective cost_per_success --min-citation-rate 0.75 --max-candidates 8 --repeats 2 --allow-model-calls --json
```

Give every benchmark task an explicit `"split":"development"` or `"split":"heldout"`. Without explicit splits, at least four tasks are partitioned using a stable task-ID hash; smaller benchmarks remain development-only and cannot support a deployment recommendation. Both partitions are capped separately by `--max-tasks` and `settings.max_tasks_per_run`.

Reports include input/output/total tokens, mean/median/p95 latency, cost per task/success, citation validity, source coverage, task/category changes, uncertainty, configuration/corpus hashes, and deployment status. The original optimizer leaves semantic groundedness and unsupported claims null unless actual adjudications are supplied. The new standalone study supports explicit human claim review; citation validity remains a separate metric. The legacy `--min-groundedness` spelling is an alias for citation validity only.

The CLI persists reports in local SQLite. The API uses `POST /api/v2/optimize` with `{"acknowledge_model_calls":true}`; GET performs no model calls. Optimization shares the evaluation concurrency guard. Nothing changes live retrieval settings.

For a repeatable **synthetic integration check**, with no model credentials or network:

```bash
python tools/validate_local.py --output docs/artifacts/local-validation.json
```

This explicitly labeled local test adapter simulates answers, tokens, pricing and source charges. Local wall time is real, but **these results establish no real-provider savings**. See [the audit and limitations](docs/STARTUP_VALIDATION.md).

| Capability | What is measured | What is NOT yet promised |
|---|---|---|
| **Live question accuracy** | Actual model response graded against user-supplied independent expected answers | General accuracy outside benchmark |
| **End-to-end task latency** | Real measured wall-clock milliseconds per task | Network latency or throughput under enterprise scale |
| **Model token usage** | Provider-reported input and output tokens, when available | Provider billing if usage is not reported |
| **Source ablation** | Re-evaluate same questions without an entire data source | Universal or unbiased causal contribution |
| **Document ablation** | Remove selected documents one at a time and compare outcomes | Intrinsic per-sentence information value |
| **Data CI** | Compare two saved evaluations and hashed source documents | Deterministic LLM results or coverage of untested behavior |
| **Experiment history** | SQLite records for reports and task-level evidence | Encrypted, multi-user hosted storage |
| **Bring your own agent** | HTTP adapter for an existing agent with enforced source filters | Automatic integration with any arbitrary RAG framework |

### Run baseline and ablations from the command line

```bash
# Confirm intended model/API usage with --allow-model-calls
python -m sourceroi --project myworkspace run --allow-model-calls --max-tasks 10

# Remove a named dataset and measure the changed outcomes
python -m sourceroi --project myworkspace run --without industry --allow-model-calls

# Run baseline plus each dataset removed (number of model calls grows!)
python -m sourceroi --project myworkspace run --ablate --max-tasks 10 --allow-model-calls

# Find the impact of specific documents; IDs look like filings::report.md
python -m sourceroi --project myworkspace run --ablate-documents 'filings::report.md' --max-tasks 10 --allow-model-calls

# View persisted run IDs and compare two experiments
python -m sourceroi --project myworkspace runs
python -m sourceroi --project myworkspace compare --before RUN_ID_1 --after RUN_ID_2 --fail-on-regression

# Run automated tests (no paid calls)
python -m pytest -q
```

You can perform the same experiments in the **Experiments** tab and compare runs in **Run history**.

### Use your existing AI agent instead of SourceROI's basic RAG

The included `rag_chat` runner chunks your files, retrieves passages with lexical BM25, and invokes your configured OpenAI-compatible model. This is a transparent baseline, **not** state-of-the-art retrieval.

To evaluate *your own deployed RAG/agent*, set `runner` to `http_agent` and configure an endpoint. See **[docs/AGENT_ADAPTER.md](docs/AGENT_ADAPTER.md)** for the request/response contract. It can report provider latency, tokens, and real paid-data charges. It must actively enforce the requested source/document exclusions; SourceROI rejects results unless the integration acknowledges that filtering occurred.

## Standalone task-aware policy studies

SourceROI is a standalone project. The new `study` workflow tunes top-k, context-budget, relevance-threshold, cheapest-source, and simple task-aware baselines on development tasks. It fits question-only routing among measured qualifying policies and bounded source subsets, then freezes all decisions before grouped held-out evaluation.

Semantic groundedness is scored from completed human claim adjudications tied to exact answer/context hashes. Citation validity alone is not semantic support. Missing reviews remain unknown and block grounding qualification by default.

```bash
# Free synthetic mechanics test; no APIs, downloads or other-project imports.
python tools/validate_study.py --output docs/artifacts/standalone-study.json

# Already configured free localhost generation model only.
python -m sourceroi --project myworkspace study --objective token_budget --repeats 2 --allow-model-calls --output workspace/study.json
```

The synthetic study preserved accuracy and used 290 simulated tokens versus 316 for the strongest tuned baseline. **This is not real-model evidence.** No money was spent. Quality-preserving real-model gains and independently reviewed grounding remain unproven; the later local-model experiment measured token reduction but failed the quality gate. See [the standalone setup, methods and limitations](docs/STANDALONE_STUDY.md).

Experiments now includes a free-localhost study form; saved studies support JSON, CSV, Markdown and claim-review downloads. The earlier out-of-scope cross-project bridge has been removed. SourceROI does not import or depend on another application.

## Public-document MVP validation

A small, frozen SQuAD/HotpotQA workspace is included at `workspace/public-validation`: **8 published questions, 44 source documents**, original answer/evidence annotations, attribution and CC BY-SA 4.0 data licensing. It is independent of other applications.

```bash
# No model calls: check retrieval against the published supporting evidence.
python -m sourceroi --project workspace/public-validation audit-retrieval --output workspace/retrieval-report.json

# No paid APIs: complete HTTP/persistence/gating test with an explicitly local mock.
python tools/validate_public_protocol.py --project workspace/public-validation --output workspace/protocol-report.json

# Reproduce the import in a fresh directory (free public downloads).
python -m sourceroi public-benchmark --download --per-dataset 4 --output my-public-workspace
```

**Observed result:** all selected policies fully included annotated quotes for 3/4 held-out tasks; threshold filtering used less context than SourceROI's retrieval proxy. No SourceROI advantage, measured model savings, or model answer quality was established. The model protocol test uses an abstaining stub with unknown usage; it is not LLM validation.

Studies now evaluate every frozen policy once on held-out tasks, preserve completed evidence on failure, and export actionable offline verdicts. A generic v2 reference agent demonstrates exact restriction/control acknowledgments without invented usage. See [MVP results and complete developer instructions](docs/MVP_VALIDATION.md) and [the adapter contract](docs/AGENT_ADAPTER.md).

## Project structure

```text
SourceROI_Production_Beta/
├── sourceroi/
│   ├── live/
│   │   ├── api.py          # local FastAPI service + background jobs
│   │   ├── cli.py          # init, doctor, run, compare, serve
│   │   ├── config.py       # config and path validation
│   │   ├── ingest.py       # real PDF/DOCX/CSV/JSON/text ingestion
│   │   ├── retrieve.py     # lexical RAG baseline
│   │   ├── provider.py     # live model & external agent adapters
│   │   ├── grade.py        # independent task grading, confidence intervals
│   │   ├── engine.py       # dataset/document experiments and Data CI
│   │   ├── db.py           # SQLite persistence
│   │   └── web/            # live dashboard
│   └── demo_cli.py         # preserved offline prototype
├── workspace/              # deliberately empty real-data workspace
├── examples/finance/       # separately labeled SYNTHETIC legacy demo
├── tests/                  # integration tests, no paid API calls
├── docs/                   # methodology, agent adapter, security checklist
└── .github/workflows/ci.yml
```

To launch the preserved v0.1 **fictional demo**, use `python -m sourceroi demo serve --port 8766`.

## Experimental guardrails

- Maximum tasks/calls are bounded by `settings.max_tasks_per_run` and `settings.max_model_calls_per_run` (defaults: **50 tasks** and **100 calls per run**). Excluding five datasets across 20 questions costs **120 actual model calls**; the system rejects that unless you deliberately raise the cap.
- You must acknowledge possible charges before a run from either CLI or UI.
- If `max_estimated_model_cost_usd` is provided with valid token rates, each completed call triggers an estimated spend guard. The last in-flight call may already exceed the limit. It is **not** a provider-side hard spending cap.
- Remote model/agent URLs must use HTTPS; local HTTP is allowed for localhost.
- Data and reports are kept inside the workspace, but **hosted-model requests send selected document excerpts to that provider**. Use data only when allowed by your licenses and confidentiality rules.
- Exact/numeric/contains/regex grading uses independent expected answers. A citation ID shows which chunk was referenced; citation format alone does **not** prove the answer is supported.
- Results include Wilson accuracy intervals and paired bootstrap intervals for ablations. Small or biased benchmarks are **not** evidence of general business impact.

## Security and deployment status

This beta deliberately binds to **127.0.0.1** and has no multitenant user authentication. It is **not safe to expose publicly** or to deploy to a shared production server as-is. The SQLite history includes questions, answers and excerpts; it is not encrypted at rest. Protect the workspace and your source files accordingly.

See **[docs/PRODUCTION_CHECKLIST.md](docs/PRODUCTION_CHECKLIST.md)** for what must be added before a production customer rollout. For claims and experimental design, see **[docs/METHODOLOGY.md](docs/METHODOLOGY.md)**.

**The actual startup hypothesis:** Engineering teams will pay for a source-isolated agent evaluation and regression gate that catches consequential data changes their existing eval/observability tools miss. We have built the software beta, **not validated that commercial hypothesis**.
