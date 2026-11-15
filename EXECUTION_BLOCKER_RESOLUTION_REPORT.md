# Native execution resolution and real experiment evidence — 2026-11-14

## Outcome

**VERIFIED:** the missing native request/task/response correlation was implemented and tested in an isolated local build of the approved llama.cpp source tag. The existing authorized accounting smoke executed **two actual Qwen generations**, reconciled **6,210 tokens**, and shut down normally in **13.159 seconds** of supervised process lifetime (13.234 seconds in the single-use authorization session). No legacy gate was removed or bypassed.

**FAILED development answer quality:** the model answered **21** for both business-rate questions, where the original notices support **67** (2024) and **70** (2025). Both answers had correct JSON shape and valid retrieved citation IDs. Correct business evidence was present in the retrieved context. Two supported answers, zero correct, zero false abstentions; these two observations are an accounting smoke, not a completed representative benchmark.

**PRELIMINARY:** an authentic ten-question/twenty-task-pair development benchmark and actual RAG/full comparison harness are frozen and offline-tested. **PENDING:** the separately authorized full experiment, independent semantic review and any customer/commercial claim. The larger benchmark has **not** run. The original REAL_WORLD_EXECUTION_RESULTS.md remains an immutable record of the earlier blocked attempt; this report records subsequent progress.

## 1. Root cause and route investigation

The old owned runner propagated request UUIDs only in client headers/ledger events. Native task launches recorded task numbers, but had no verified binding to those client identities. The approved upstream HTTP request logger was disabled. Enabling a logger alone would not enforce reservations, prevent child tasks or establish terminal/token correspondence. Matching request totals and timing records were insufficient, as shown by historical extra generations.

The existing callback bridge checks document manifests, passage IDs, completeness and optional application-reported usage. HTTP v2 checks source restrictions, configuration/knowledge identity acknowledgments and application traces. Neither independently controls hidden nested generations, retries or provider spend. No separately authorized external application with its own verified accounting was available; a callback/HTTP acknowledgment is not that proof. The installed CLI also starts a server internally and was not used as a gate workaround.

Primary source audit: [approved-tag HTTP implementation](https://github.com/ggml-org/llama.cpp/blob/b12345/tools/server/server-http.cpp), [native task pipeline](https://github.com/ggml-org/llama.cpp/blob/b12345/tools/server/server-context.cpp), and [CLI server lifecycle](https://github.com/ggml-org/llama.cpp/blob/b12345/tools/cli/cli-context.cpp). The actual downloaded source archive is frozen by SHA-256 `6e774abb097960ba5a233559d4035f3f91069cc5cdf33cb9c7874d873abf7b43`; that exact content, not a mutable tag name alone, identifies the local build.

## 2. Engineering change and enforcement

The original installed runtime/model were preserved. Source was fetched for the already approved b12345 tag and built under workspace/execution-resolution/ using a project-local CMake 3.31.6 wheel and existing Clang/SDK. No global dependency, new model, replacement system binary, hosted service or product framework was introduced. The tar-source build reports unavailable Git build metadata; it is identified as a local instrumented build by source/library/binary hashes, not falsely claimed byte-identical to the original release.

Changes reuse the existing Experiment class, provider `_experiment_transport`, authenticated UNIX socket and parent-death/deadline supervisor:

- **Reserved:** a durable Python attempt reservation and authorization ledger precede dispatch. Authorization IDs are single-use; the prior smoke cannot be reset/reissued by restarting a directory. Retries are disallowed and all attempts consume the ceiling.
- **Admitted:** the native HTTP handler must consume a private single-use permit whose contents exactly equal the wire request. Missing, mismatched, replayed and over-budget permits are refused before task generation. Public/reusable TCP serving is not used.
- **Bound/dispatched:** the HTTP UUID is bound to one native task ID; dispatch requires that binding. Multiple prompt tasks, n>1, best_of>1, streaming and child/replayed task dispatch cannot produce untracked generations. Untracked task hooks abort rather than proceed.
- **Completed:** native task counters record the actual prompt and generated-token counts. A separate terminal HTTP event records request UUID, status and exact body. Python independently compares reservations, wire JSON, task identity/order, captured response and native token counters.
- **Failed/cancelled/unknown:** native failure/cancel hooks and existing supervisor/client failure artifacts retain uncertainty. Missing/multiple events, body/usage/task mismatches, abnormal shutdown, lost responses and failed attempts make reconciliation INCONCLUSIVE; no missing usage is fabricated as zero.
- **Limits/isolation:** server-side admission counts/deadline, shared owner/supervisor deadline, one slot, no warmup, private authenticated UNIX transport, single-use authorization and exclusive runtime/test lease. Inherited runtime/library override environment variables are stripped. The same local account remains trusted; this is not tenant isolation or protection from an account owner rewriting local files.
- **Integrity:** certificate binds the executable, runtime libraries, approved model, instrumentation source and Python accounting/supervision files. Raw client artifacts, independent native JSONL events, shutdown record, reconciliation and seal are retained. Legacy native invocation still refuses without the explicit verified certificate and recorded authorization.

Implementation: sourceroi/live/native/accounting.h, native_accounting.py, native_gate.py, experiment.py, experiment_worker.py and tools/instrument_native.py. Build/configure logs and all before/after hook hashes are under docs/artifacts/execution-resolution/. Original approved-runtime hashes remain recorded in the native certificate.

**Verification scope:** deterministic C++ admission/task/terminal probes exercise replay, unknown task/child/duplicate completion, caps, missing permits, failure and cancellation. Existing supervisor fixtures exercise deadline, parent death, process crash, cancellation and untracked traffic. The real native smoke verifies two successful completions on this exact build/model/OS. Real model failure/cancel injection was not authorized or performed; those paths are tested deterministically, not represented as additional empirical inference or third-party certification.

## 3. Authentic documents and frozen development benchmark

The corpus uses the original public IRS PDFs, original extracted text and preserved download metadata, with hashes checked before copying. Official URLs were inspected again this sprint:

| Edition | Authoritative source | Effective start | Genuine changes / protected content |
|---|---|---|---|
| Notice 2024-08 | [2024 standard mileage notice](https://www.irs.gov/pub/irs-drop/n-24-08.pdf) | 2024-01-01 | Business 67 cents/mile; medical 21; charity 14; FAVR maximum $62,000; own-year depreciation 30 cents/mile |
| Notice 2025-5 | [2025 standard mileage notice](https://www.irs.gov/pub/irs-drop/n-25-05.pdf) | 2025-01-01 | Business changes to 70; medical remains 21; charity remains 14; FAVR maximum changes to $61,200; own-year depreciation changes to 33. It explicitly supersedes Notice 2024-08. |

PDF hashes: 2024 `94545e0c068d2bcb09768975008bdfcc06b4903dbae67236d45439379eefc35d`; 2025 `aac49246870a5b943893f9407c7f20094ed887c834341de7ec69ad7a71e67773`. No policy version or contradictory row was invented.

Frozen inputs: docs/artifacts/execution-resolution/frozen-benchmark/ (portable copy) and workspace/execution-resolution/benchmark-v1/ (execution copy). frozen-labels.json contains exact quotes, character offsets, extraction hashes, version-specific expected answers, original source URLs/metadata and explicit authorship. freeze-manifest.json binds all input files. accepted/ preserves original labels; candidate/ keeps the same benchmark bytes. Intended expectation/evidence changes are separate proposals/review inputs.

Ten questions cover five supported numeric lookups (three genuine changed values, two protected unchanged values), absent parking-rate information, Canada/US mismatch, future-2030 and past-2020 applicability mismatches, and cross-version business-rate equality. The apparent conflicting evidence is the authentic difference between annual editions, not a fabricated same-period policy contradiction. The baseline lacks the 2025 edition and cannot establish the both-years assertion; the candidate contains differing 2024/2025 rates. CURRENT means the registered experimental current edition, not the real calendar-2026 IRS rate.

Annual end-window metadata is a **declared evaluation applicability window** inferred from annual notice titles/supersession, not a claim that the source text specifies a legal expiry date. Unsupported labels include explicit absence/scope rationales. The documents were used in earlier development; this is exposed, Codex-authored development data, not a new independently held-out corpus. Labels/evidence were frozen before this sprint's model responses; they were not changed after the two wrong answers. Human/source-owner/independent semantic reviews remain absent.

## 4. Actual RAG configuration and prepared full harness

Model: existing Qwen2.5-1.5B-Instruct Q4_K_M, revision `91cad51170dc346986eccefdc2dd33a9da36ead9`, model SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`. Local instrumented llama.cpp build with Metal support, native threadpool observed at four threads; one slot, context 4096, no warmup/context shift, temperature 0, seed 1729, maximum output 192 tokens, prompt cache disabled. The complete runtime command and build/library hashes are retained in the runtime manifest/certificate.

Retrieval uses existing ingestion and BM25 with fixed 1800-character chunks, 200 overlap, top 5 and 9000-character context bound. Production routing recognizes literal CURRENT in the question and restricts that query to the current source; cross-edition queries search the registered collection. This rule uses question/source identity, not expected answers. Scope/evidence prechecks remain enabled. Provider prompt, numeric response contract and citation-enum schema are unchanged; numbered citation IDs map back to actual passages. Auxiliary tokenization is disabled in this experiment; accounting comes from actual completion response/native counters.

`tools/run_empirical_experiment.py` implements:

1. Frozen input verification, actual retrieval, provider/native generation and raw question/answer/evidence capture.
2. Supported accuracy/false abstention separately from unsupported rejection and citation-ID failures. Software precheck abstention is distinguishable from model generation.
3. Strict SourceROI assessment and diagnosis from the exact primary captured traces, reusing actual outputs without an additional generation disguised as replay.
4. Independently implemented ordinary answer/format, citation membership, source/version, scope and identical quoted-reference checks with maintained expected labels/references. Both methods get the same generated answers and absent independent reviews.
5. A separately recorded built-in Data CI paired run. It uses the original frozen labels and its own built-in retrieval, so it is **not** the maintained-label comparator or an identical-context primary rerun. This distinction is explicit in its output; intentional updates flagged by stale labels cannot count as unique detection advantage.
6. Immutable new output paths, failure/unknown artifacts and accounting reconciliation. No implicit model retries or budget increase.

Offline preparation traversed all 20 version/question tasks: 11 generation prompts were captured without dispatch; nine tasks abstained in software prechecks. Those are harness observations, not model quality measurements. Full benchmark and Data CI inference remain unexecuted. The full real-inference branch cannot be claimed empirically exercised from an accounting smoke.

## 5. Authorized accounting smoke: actual observations

The existing permission was preserved exactly: at most two generation attempts, 30 seconds, no retries, $0 external spend, accounting smoke only. No other native process was found before launch. The one-use authorization is now closed/consumed. Native PID exit was checked after normal shutdown.

| Actual observation | 2024 registered edition | 2025 registered edition |
|---|---:|---:|
| Question | Business mileage rate, cents/mile | Same question, updated edition |
| Frozen development expectation | 67 | 70 |
| Actual Qwen answer | **21** | **21** |
| Answer contract / response completion | Valid / complete | Valid / complete |
| Citation membership | All five retrieved IDs valid | All five retrieved IDs valid |
| Correct business evidence retrieved | Yes | Yes |
| Prompt tokens | 3,059 | 3,081 |
| Completion tokens | 35 | 35 |
| Measured model request latency | 4,027.90 ms | 3,929.13 ms |
| Maintained conventional observed-answer check | BLOCK | BLOCK |
| SourceROI observed exact-answer check | BLOCK | BLOCK |

**Reconciled totals:** 2 reserved/dispatched attempts, 2 native task completions, 2 terminal/captured responses, 0 failed requests, **6,140 prompt + 70 completion = 6,210 total tokens**. Supervised native process elapsed 13.158898 seconds, exit code 0, owner_shutdown. No retry, cancellation or additional real generation occurred. Local hardware/energy cost is unpriced, not claimed zero operating cost.

Raw evidence: docs/artifacts/execution-resolution/native-smoke/accepted-business.json and candidate-business.json contain full questions, raw JSON answers and retrieved source passages. runtime/requests/ contains exact request/response artifacts; native-events.jsonl independently contains admission/binding/dispatch/completion/terminal records; authorization-ledger.json, worker-exit.json, reconciliation.json and seal.json retain accounting/shutdown evidence. The original sealed smoke output is unchanged by subsequent read-only analysis.

## 6. Reliability, fair comparison and diagnosis

**FAILED observed correctness:** 0/2 supported answers. False abstentions: 0/2. Unsupported questions executed: 0; their rejection rate is undefined/null. Citation-ID failures: 0/2 factual outputs; independent semantic citation correctness remains unreviewed. These metrics must not be combined into a fabricated overall accuracy or generalized to all four/five supported question types. The previous all-abstention problem is not demonstrated fixed: this tiny smoke now gives wrong factual answers instead, and the larger question set remains pending.

Both systems detect both observed answer failures using the **same** version-specific development expectations and actual outputs. Citation membership, source version and quoted evidence coverage pass mechanically; these checks alone miss that 21 is not the requested business rate. An ordinary *retrieval-only* check could miss this, but the strong maintained answer-test baseline catches it just as SourceROI does. **Observed detection coverage ties at 2/2; no differentiated coverage is established.** There is no observed before-correct/after-wrong protected regression in this smoke—both versions are already wrong.

SourceROI's existing diagnostic classification is generation_or_scoring_failure, a hypothesis. Correct source quotes are present and model answers match a different medical-rate number in the same retrieved context. That supports an observed wrong-answer failure despite successful retrieval; it does not prove a causal mechanism or that shorter context/another prompt would fix it. No additional ablation or inference was authorized. Post-analysis records exact quotes and classifications without altering the responses or expected labels.

The existing strict assurance workflow was also fed only these actual partial traces, without inventing the other answers or approving a human review. It correctly returns **INCONCLUSIVE** for incomplete task coverage. This is a partial-trace safety check, not a completed full release decision. Its execution.calls field counts requested logical task slots; **actual native generation count is the separately reconciled two**, not that logical counter. Details: actual-smoke-final-analysis.json and actual-smoke-final-analysis-incomplete-strict-release.json.

Observed single-pass evidence inspection was about 51 ms per answer, versus about 50–52 ms for ordinary checks. These ordered local timings include source reads and lack controlled repetition; they establish neither a speed advantage nor human maintenance effort savings. Native instrumentation overhead versus an uninstrumented model run was not separately measured. Human review/edit/integration effort and economic value remain null/unmeasured.

## 7. Authorization required for the full experiment

**Technical route available for this exact verified local build; full benchmark authorization PENDING.** The previous two-call smoke allowance is exhausted and cannot be reinterpreted or reused.

A proposed, unapproved record is at workspace/execution-resolution/benchmark-authorization-PENDING.json (also copied to the artifact directory): **up to 40 generation attempts, up to 90 seconds total runtime, zero retries, $0 external spending**. This ceiling includes up to 20 primary before/after attempts and up to 20 additional built-in Data CI attempts. Software abstentions can reduce actual calls. A ceiling does not guarantee the whole run finishes; timeout must remain a failed/incomplete outcome.

Only after the actual user approves the exact larger budget should a new approval record be created with a unique authorization_id, status approved, scope benchmark and an authorization_basis quoting that real approval. Do not fabricate approval or merely turn the pending template into permission. Then execute once into a fresh destination:

```bash
workspace/design-partner/venv/bin/python tools/run_empirical_experiment.py run \
  --benchmark workspace/execution-resolution/benchmark-v1 \
  --authorization workspace/execution-resolution/benchmark-authorization-APPROVED.json \
  --output docs/artifacts/execution-resolution/full-benchmark-01
```

The pending record was explicitly tested and refused with exit 2 before a model/experiment destination was created. No additional execution is authorized by this report. Independent semantic review and a representative held-out external corpus are separate requirements for broader quality/commercial claims, not permissions silently inferred from a technical smoke.

## 8. Tests, preservation and readiness judgment

**VERIFIED regression evidence:** 387 tests pass (14.61s), including compiled native protocol probes, existing isolation/deadline/failure fixtures, unauthorized-full-run rejection, metrics/baseline checks and correct baseline/candidate identities in read-only actual-smoke replay. No model call is made by the tests. The full suite runs after the native process has shut down, under the shared lease and existing real-port isolation. Earlier test logs, failed pre-generation benchmark preparation and intermediate analyses are preserved; the final frozen benchmark/final analysis are explicitly identified above.

All eight product capabilities, CLI/FastAPI/dashboard/SQLite/legacy adapters and earlier historical artifacts are preserved. No onboarding guide, distribution or cosmetic feature was added in this sprint. Native success-path accounting is verified for the scoped build/smoke; fixture failure-path tests are not broad production validation, and independent identity/security review remains unperformed.

**Judgment:** the execution blocker was materially resolved and genuine retrieval/generation evidence obtained. The current model failed both observed business-rate questions. SourceROI caught those failures, but the equally maintained conventional evaluator caught them too. **Differentiated technical value, reliable real-world answer quality and customer/commercial benefit remain unproven.** The full prepared experiment awaits separately recorded user authorization, not another packaging milestone.

Final preservation audit: **699 pre-existing artifact/report files are unchanged**. The exact as-run smoke source, final code hashes, source/build provenance, raw sealed native records, frozen inputs, read-only analyses and pending authorization record are indexed in docs/artifacts/execution-resolution/evidence-manifest.json. No additional model generation occurred during analysis or regression testing.
