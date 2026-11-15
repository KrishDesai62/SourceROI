# Real-world execution results — blocked, not completed

**PENDING / NOT EXECUTED. No new empirical reliability result exists.**

The requested completion criterion—real document retrieval, authorized model generation, recorded answers/usage, and an equal-authority conventional comparison—was not met. No synthetic adapter, fixture result, historical replay, test count or package is substituted for that experiment.

## Exact execution blocker

The installed model is Qwen2.5-1.5B-Instruct Q4_K_M, revision `91cad51170dc346986eccefdc2dd33a9da36ead9`; the approved runtime is llama.cpp b12345 macOS arm64. Both model and server files are present. Installation availability is not the blocker.

The existing owned runner in `sourceroi/live/experiment.py:143` unconditionally rejects native execution when fixture_command is absent. Only the bundled fake-runtime command is accepted by fixture mode. Its defaults/caps are implementation limits, not operator authorization. A direct constructor check using the earlier smoke limits (2 calls, 30 seconds) produced:

> Live inference disabled: native request/response reconciliation is not yet verified; use offline replay

It failed before creating an experiment output or launching a process. Evidence: `docs/artifacts/real-world-execution-blocker/execution-status.json` records the check, current gate-code digest and installed-file presence. No gate, application code, approval boundary, existing report or regression test was changed. No additional automated suite or packaging sprint was performed.

The preserved prior audit, `docs/artifacts/native-tables/native-audit.json`, records missing verified native request-to-task-to-terminal-response correlation. Equal server task totals, timing records and a Python ledger are insufficient. That historical audit is not a fresh native accounting verification in this turn. No native build source was found in the installed runtime directory. Starting the legacy server, invoking another native executable, or disguising a native process as a fixture would bypass the still-required gate and was not attempted.

## Authorization scope

The earlier explicitly quantified native authorization was at most two generations and 30 seconds, solely for an accounting smoke **after** accounting was verified. It does not authorize the requested paired multi-category benchmark. The current request requires an explicitly authorized recorded budget and preservation of approval boundaries; it supplies no replacement numerical benchmark budget or permission to bypass the native gate. More approval alone would not solve the technical reconciliation prerequisite.

## Requested empirical measurements

| Measurement | This attempt | Status |
|---|---|---|
| New model process starts | 0 | VERIFIED internal control observation |
| New real generation calls dispatched | 0 | VERIFIED internal control observation |
| Actual provider/native token usage | Not measured; null | PENDING |
| External spending | $0 | VERIFIED |
| Real document pair selected/retrieved for this experiment | Not performed after execution prerequisite failed | PENDING |
| Source URLs, versions, effective dates and frozen evidence spans | No new experimental corpus established | PENDING |
| Frozen benchmark and version-specific development labels | Not constructed | PENDING |
| Raw questions, retrieved evidence and generated answers | No new run artifacts | PENDING |
| Supported accuracy and false-abstention rate | Undefined; no observations | PENDING |
| Unsupported rejection, citation failure and out-of-scope behavior | Undefined; no observations | PENDING |
| Impact mapping, Data CI, maintenance, release and diagnosis on new outputs | Not executed | PENDING |
| Equally maintained conventional comparison | Not executed | PENDING |
| Experimental latency/overhead or maintenance effort | Not measured | PENDING |

Zero dispatch is not an answer-quality result or a measured token-saving result. No aggregate accuracy, rejection rate, tokens or cost savings can be inferred. Whether the earlier supported-question abstention failure remains after prompt/contract changes is **unknown**. Existing historical model failures and baseline ties do not answer that fresh experimental question.

## Required prerequisites before execution

1. The approved native execution path must actually enforce and reconcile request identity, reserved attempts, generation/child-task dispatch, terminal response/failure/cancellation and observed/unknown usage, with exclusive traffic and deadline/call enforcement. Only then may the previously authorized accounting smoke run within its two-call/30-second limit. This turn did not replace the empirical request with an instrumentation project.
2. After that gate passes, record explicit benchmark authorization: maximum total generation attempts, total runtime and any retry allowance. Freeze source versions, evidence-backed development labels and equal-comparator scoring before observing outputs. The scope must cover paired supported/unsupported/changed/protected/conflicting/out-of-scope questions and preserve all failed/unknown attempts.
3. Execute the real retrieval/model path once per frozen question/version and reuse those identical outputs for SourceROI and the maintained conventional evaluator. Real source/semantic reviewers remain absent unless actually supplied; no independent approval may be invented.

## Judgment

**SourceROI has not demonstrated differentiated real-world technical value in this attempt.** The execution prerequisite failed before empirical evaluation began. Internal gate enforcement is verified; actual RAG reliability, diagnosis advantage, maintenance savings, independent semantic quality and commercial value remain pending hypotheses. This task is blocked, not successfully completed.
