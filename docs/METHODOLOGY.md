# How SourceROI measures source value

## What we actually test

For a fixed set of independently labeled tasks, evaluate the **same** runner, model configuration, retriever settings, and task definition under different permitted source configurations. The benchmark answer key is never given to the model.

- Baseline: all available sources.
- Dataset ablation: remove one source completely and rerun.
- Document ablation: remove selected files one at a time and rerun.
- Source update: compare a saved run to a new run after documents changed.

For every task SourceROI records model answer, independent correctness under the selected scoring rule, retrieved chunk IDs, citations returned by the agent, actual elapsed wall-clock time, and provider-reported usage when available.

## What scores mean

- **Task accuracy**: exact, contains, numeric-with-tolerance, or regular-expression scoring against the user-supplied expected answer. Real open-ended reasoning needs more sophisticated, human-validated scoring; this version does not claim to measure it.
- **Mean/P95 latency**: measured full-task time, not synthetic source latency. Retrieval timing is broken out when using the built-in RAG runner. Concurrency/throughput are not benchmarked here.
- **Token count**: from the model provider's actual usage object, or from your existing agent's reported telemetry. Null means unreported.
- **Model USD**: priced using your configured per-million-token rates and observed token counts. Null means rates/usage are missing. It is a rate-based estimate, not an invoice.
- **Data USD**: zero for local file retrieval; when using an external agent, a separately agent-reported figure is accepted. Without instrumentation, costs should be omitted.
- **Single-source loss**: number of previously correct benchmark answers now wrong when a source is removed. Redundancy and interactions can hide contributions; the finding is conditional on the other sources and the benchmark.
- **Confidence intervals**: Wilson interval for a run's fraction correct and deterministic paired bootstrap over task-level correctness deltas for a source comparison. They do not correct nonrepresentative tasks, confounding, leaked answer keys, or stochastic model effects.

## Important limitations

1. A pass/fail task benchmark is **not** a universal intrinsic data-value score. The most economically important questions may be rare.
2. One run per configuration does not robustly characterize nondeterministic models. Repeat runs and examine variation before claiming a regression or deploying a gate.
3. Document-removal experiments are interventions *in the local test environment*; they do not prove a causal effect in the live world under different tasks, users, or downstream systems.
4. Two sources that substitute for each other may both appear unimportant when removed separately. A production optimization system should test combinations and interactions, not simply rank independent drops.
5. Model prompt injection, private cached memory, and data leakage can break exclusion isolation. Agent adapters need explicit controls and independent audits.
6. A missing document can change retrieval ranking even when that document was never used. That is part of the configuration-level effect but not proof that the missing document itself contained unique information.
7. Dataset rights and information value are different questions. This system does not infer legal permission to transmit copyrighted/licensed information to a model.

## Recommended pre-customer benchmark

- At least 50–100 independently checked tasks representative of production workflows.
- Include easy/hard tasks, document revisions, amendments, numerical values, multi-document joins, deliberate insufficient-evidence cases, and important negative cases.
- Split into development and **held-out** tasks; do not tune to held-out results.
- Track source-dependent failure categories and actual monetary loss when a sound mapping is available; don't invent an “error cost” multiplier.
- Compare to a fixed regression suite and a standard RAG observability platform; only claim differentiation if SourceROI catches material regressions those baselines miss.
