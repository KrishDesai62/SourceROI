# SourceROI: real-world end-to-end validation

Executed 2026-11-13. Historical annual IRS mileage notices; local inference only.

**Verified:** SourceROI executed a real PDF → retrieval → local model → reviewed change → strict release workflow and blocked a protected-answer regression. **Verified:** an equally maintained conventional checker also blocked it. **Failed:** this experiment did not demonstrate quality-preserving token optimization. **Unverified:** independent semantic quality, customer value, and startup differentiation.

Classification throughout: **Verified** means observed mechanics or artifact-backed counts; **Preliminary** means small-sample results against Codex-authored source-derived labels; **Unverified** means required independent evidence is absent; **Failed** means an attempted quality or optimization objective was not met. Mechanical verification does not confer independent ground truth.

## A. Environment

**Verified — real authoritative documents.** Full original PDFs were downloaded from IRS after checking access restrictions, not manufactured policies or selected snippets:

| Edition | Source | PDF SHA-256 |
|---|---|---|
| 2024, Notice 2024-08 | [IRS original](https://www.irs.gov/pub/irs-drop/n-24-08.pdf) | `94545e0c068d2bcb09768975008bdfcc06b4903dbae67236d45439379eefc35d` |
| 2025, Notice 2025-5 | [IRS original](https://www.irs.gov/pub/irs-drop/n-25-05.pdf) | `aac49246870a5b943893f9407c7f20094ed887c834341de7ec69ad7a71e67773` |

Both have five pages; combined size 184,859 bytes. HTTP responses were 200. [Provenance](workspace/irs-e2e/raw/provenance.json) preserves URLs, retrieval timestamps, server dates, file/text hashes, and robots decision; [raw files](workspace/irs-e2e/raw/) preserve PDFs and unchanged extracted text. These are historical 2024/2025 rate questions, not 2026 tax guidance.

**Verified — actual existing agent.** The existing RAG engine was exercised through SourceROI's callback adapter: PDF ingestion, BM25 retrieval, generation, normalized structured answers, and cited chunk IDs. It used the already approved Qwen2.5-1.5B-Instruct Q4_K_M and llama.cpp b12345 on macOS arm64, localhost port 8788. Configuration: context 4096, one slot, four threads, seed 1729, temperature 0, maximum output 384, prompt cache disabled, top-k 3, 1,100-character chunks with 150-character overlap. Exact runtime/model URLs, revisions, hashes, Python/library versions, and pre-inference code hashes are in [environment freeze](docs/artifacts/irs-e2e/environment-and-code-freeze.json). Exact prompts and responses are preserved in [calls](docs/artifacts/irs-e2e/calls/); expected answers were not supplied to generation.

This is an actual built-in RAG workflow behind a callback, **not independently operated customer infrastructure**. The active collection contains one complete annual notice per snapshot under the same canonical document ID. Both historical files are retained; coexistence of stale and current notices is a separate retrieval control. Source authority, US jurisdiction, annual effective dates, and policy scope are explicit metadata. Annual source dates are coarse: historical facts embedded inside a notice are not individually dated.

**Verified — implementation audit and minimal repairs.** Existing ingestion/indexing and evaluator feed run storage, source/document ablations, Data CI, change-impact mapping, explicit intent review, strict release checks, and reference-based diagnosis. The existing optimizer evaluates bounded candidate policies against task scores. Deterministic test coverage establishes mechanics, not production answer quality or unique economic value.

Actual PDF execution exposed missing `pypdf` in the interpreter. The already declared dependency was installed into ignored `workspace/.deps` (pypdf 6.21.4, approximately 410 KB wheel); no major runtime was simulated. Original preflight incorrectly treated PDF page/section numbers and cross-references as conflicting facts, abstaining on all twelve task-version cases. A narrow fact-predicate filter removed standalone navigation markers and pure cross-references while retaining substantive conflicting statements. Corrected preflight abstained only on the two out-of-jurisdiction cases. Original and corrected artifacts remain preserved.

Approved expected-value revisions also forced exact scoring regardless of the task's declared numeric scorer; this was corrected to preserve declared scoring semantics. Numeric contracts still reject `70 days`. Four focused regression tests cover navigation, real numerical conflict, numeric revision semantics, and substantive text following a cross-reference prefix. **Verified:** the complete final suite passed, **234 tests**, including all four new tests (6.76 seconds for the final full-suite rerun). Initial suite contained 230 tests. A sandboxed rerun could not bind localhost fixture ports (222 passed, one failure, eleven setup errors); rerunning with localhost permission passed all 234. No Equity Research code or production infrastructure was changed.

The pre-inference implementation is preserved in [as-run code](docs/artifacts/irs-e2e/as-run-code.tar.gz). The cross-reference filter was subsequently narrowed using deterministic tests; real-document preflight/impact outcomes were checked unchanged, without new model inference. Final code is archived separately; no claim is made that final-code inference was rerun.

## B. Experiment design

**Verified — frozen development labels, not independent review.** [Annotations](docs/artifacts/irs-e2e/frozen-annotations.json), [intent](docs/artifacts/irs-e2e/intent.json), source snapshots, benchmark hashes, and [execution plan](docs/artifacts/irs-e2e/plan.json) were frozen before model outputs. All answers and quotes are Codex-authored source-derived development annotations. Before inference, the candidate business evidence quote was refined from a bare number to the source phrase `2025 is 70`; [the refinement](docs/artifacts/irs-e2e/pre-inference-evidence-refinement.json) records this. No expected answer was altered after observing outputs.

The six tasks include direct lookup, paraphrase, multi-passage subtraction, unchanged facts, and unavailable jurisdictional information. The main question wording says CURRENT notice: this means the annual edition registered in the snapshot, not today's calendar year. Date mismatches and contradictory editions are exercised separately. Numeric answer contracts and necessary subject aliases were declared; positive alias/quote matches never establish semantic entailment.

The accepted baseline is a **frozen source baseline**, not a quality-certified agent baseline. Its subsequent observed quality was poor. DRAFT intent approval was rejected. The study then used an explicitly identified **Codex technical development review**, with source quotes, solely to exercise the review boundary. This is neither source-owner authorization nor independent human approval. Strict release retained mandatory missing-semantic-review states; no strict ACCEPT or production authorization was issued.

The model budget was at most 12 actual generation requests and 120 seconds. The observer reserved each call before invoking the provider, counted failed attempts too, and preserved raw requests/responses. Tokenization requests are separate from generation. No retries or additional inference were used to improve the recorded answers.

## C. Results

**Preliminary — source-derived answer evaluation.** Values below are cents per mile except the abstention task. `IE` means `INSUFFICIENT_EVIDENCE`.

| Task | Expected 2024 → 2025 | Actual 2024 → 2025 | Interpretation |
|---|---|---|---|
| Business | 67 → 70 | 30 → 70 | Candidate correct |
| Medical | 21 → 21 | 21 → IE | Protected regression; model false abstention |
| Charity | 14 → 14 | 21 → 21 | Wrong in both versions |
| Business paraphrase | 67 → 70 | 27 → 70 | Candidate correct |
| Business minus charity | 53 → 56 | 27 → 14 | Wrong in both versions |
| Canadian rate unavailable here | IE → IE | IE → IE | Software scope guard; no model call |

| Metric | Baseline | Candidate | Classification |
|---|---:|---:|---|
| Supported numeric answers correct | 1/5 | 2/5 | Preliminary |
| Supported false abstentions | 0/5 | 1/5 | Preliminary |
| Correct including scope-guard abstention | 2/6 | 3/6 | Preliminary |
| Full annotated support retrieved | 4/5 | 5/5 | Verified literal coverage |
| Full annotated support cited | 4/5 | 4/5 | Verified literal coverage |
| Invalid cited IDs | 0 | 0 | Verified identity checks |
| Independent semantic reviews | 0 | 0 | Unverified quality |

There were 27 cited-ID occurrences across nine factual responses, all from actually retrieved applicable current-document chunks. **Failed:** valid citation IDs and even literal reference coverage did not guarantee correct answers: charity remained 21 despite the 14-cent reference being present. Independent claim entailment remains **Unverified**. The two unavailable-information answers were software abstentions, so the model's unsupported-question hallucination rate was **not measured**. Wrong supported-task answers must not be hidden by reporting zero hallucinations on these guarded negatives.

**Verified — release execution.** [Actual release](docs/artifacts/irs-e2e/release.json) and [rendered release](docs/artifacts/irs-e2e/release.md) record **BLOCK**. Execution, review-boundary mechanics, provenance, answer format, and conflict checks passed; answer and citation checks blocked; reference coverage, applicability, evidence relevance, and absent independent semantics required review. Medical was newly lost; charity already failed; the Canadian software abstention stayed correct. This one negative release does not establish specificity on legitimate updates.

**Verified — actual usage.** [Execution ledger](docs/artifacts/irs-e2e/execution-log.json): **11 generation requests, 11 response files, 15,777 provider-reported total tokens, 22.370 seconds elapsed**, within the 12-call/120-second cap. Ten calls were main before/after supported questions; one was the top-k control. Recorded generation request wall time summed to 20.323 seconds, including HTTP/logging overhead. External paid API spend was **$0**; local hardware/energy/operational cost is unpriced, not a demonstrated zero economic cost.

**Preliminary — impact and diagnosis.** One changed PDF was detected. Impact mapping selected 6/6 questions; compared with the development dependency oracle of five US questions, recall was 5/5 and precision 5/6, with the Canadian task a false positive. This is document-level coverage on one update, not independently validated fact-level impact precision. Diagnosis identified missing selected support for the baseline multi-passage question and generation/scoring hypotheses when annotated support was present. Those are useful inspectable hypotheses, not proven causal explanations. See [analysis](docs/artifacts/irs-e2e/analysis.json).

**Verified — Data CI replay.** The existing Data CI entry point was executed against recorded real outputs with generation disabled, not a new inference run. It blocked and identified the lost medical answer. Its unchanged old business references also warned on intentional 67→70 changes, exposing reference-maintenance requirements. [Replay artifact](docs/artifacts/irs-e2e/legacy-data-ci-replay.json) is explicitly labeled; its inherited token/latency fields are not new usage.

**Failed — quality-preserving optimization.** Actual source removal caused the previously correct candidate business answer to become software IE, with zero generation. This measures policy-mediated output sensitivity, not causal/economic source value. Top-k=1 used 786 tokens (761 prompt + 25 completion) versus 1,542 (1,513 + 29) for the main business response: approximately 49% fewer tokens, but the answer deteriorated from correct 70 to IE because the rate paragraph was missing. No policy was promoted. The existing optimizer's preflight required up to eight calls against its remaining one-call allocation, so it declined execution with zero additional requests. **Unverified:** optimizer savings preserving independently measured quality; this budget does not establish optimizer failure across all configurations. [Actual ablation/control](docs/artifacts/irs-e2e/actual-ablation-and-topk.json).

## D. SourceROI vs. maintained conventional baseline

**Verified — tie on release detection.** A conventional combined checker received the same documents, frozen version-specific labels, outputs, maintained references, schemas, citation/scope/version checks, and absent-independent-review requirements. It reused deterministic primitives for equivalent conditions; this is not independent implementation validation. A SourceROI no-inference replay used those same recorded outputs.

| Observation | SourceROI | Maintained conventional checker |
|---|---|---|
| Release verdict | BLOCK | BLOCK |
| Protected medical regression | Detected | Detected |
| Wrong charity answer with valid IDs | Rejected by answer expectation | Rejected by answer expectation |
| Missing independent semantic review | Unresolved | Unresolved |
| Exploratory single replay wall time | 1,516 ms | 202 ms |
| Observed human maintenance time | Not measured | Not measured |

The timing includes unequal bookkeeping/reporting and PDF rescans; it is an exploratory overhead observation, not a normalized performance comparison. No paired human effort study, independent diagnostic usefulness assessment, or legitimate-update false-positive rate was measured. Mechanical maintenance counters (three answer-entry fields, three ambiguous items, three protected expectations preserved) are not human edits or time saved. **Unverified:** unique detection, reduced maintenance effort, or net customer benefit beyond maintained ordinary evaluations. Stale-reference warnings from legacy Data CI are not evidence that the maintained comparator loses.

## E. Failure analysis and stress controls

**Failed — supported-answer reliability.** The earlier authored-document run abstained on all four supported questions. This fresh real-PDF run produced factual answers on 9/10 supported task-version cases, but only 3/10 were correct under frozen development labels. Different corpora prevent attributing that difference to a prompt fix. Medical still falsely abstained despite complete retrieved support. The prior negative run remains unchanged.

**Preliminary — likely failure locations.** Baseline 30/27 answers resemble unrelated depreciation numbers inside the notices, but confusion is only a hypothesis. The baseline arithmetic task lacked one selected reference; candidate arithmetic had both references and still answered 14. Broad chunks containing multiple facts and source-level annual dates do not resolve predicate/date applicability within a passage. The page/section false-conflict bug was an observed preflight defect, not a successful safety rejection; its narrow repair is not a general semantic conflict resolver.

**Verified — replay/control outcomes, not additional model experiments.** The following controls use real retrieved context and observed outputs or explicitly marked controlled mutations. They do not create new empirical generation success rates:

| Scenario | Outcome | Evidence limit |
|---|---|---|
| Observed incorrect charity 21 with valid retrieved citations | BLOCK | Known answer rejects it; IDs/quote presence alone do not |
| Correct value formatted `70 days` under numeric contract | BLOCK | Controlled mutation |
| Existing citation absent from supplied retrieval | BLOCK | Controlled mutation |
| Altered source manifest attestation | INCONCLUSIVE | Integrity escalation, not acceptance |
| 2025 source requested for 2024 date | BLOCK | Explicit metadata condition |
| US source for Canadian scope | BLOCK | Explicit jurisdiction condition |
| Partial context omits required business quote | BLOCK | Controlled retrieval truncation |
| Convincing extra claim under text contract | REVIEW | No automatic claim-truth determination |
| Full real 2024 and 2025 editions coexist | Potential numeric conflict; abstention | Actual retrieval, no generation; 2025 date screen excludes old edition |
| Legitimate answer with overly narrow alias contract | Abstention | Controlled misconfiguration; false-rejection risk |

All detailed inputs and outcomes are in [stress controls within analysis](docs/artifacts/irs-e2e/analysis.json). **Unverified:** general contradiction resolution, adversarial robustness, and semantic recall/precision. The alias false rejection shows that necessary-condition screening can reject valid evidence. Human/source-owner contract calibration remains necessary. Strict review escalation prevents claiming success where semantic assurance is absent; it does not itself prove useful selectivity or production readiness.

## F. Product and startup assessment

1. **Preliminary:** the problem is real in this run: a document update lost a previously correct answer, despite the correct source being available. **Verified:** SourceROI exposed and blocked it with a traceable record.
2. **Unverified:** measurable value beyond well-maintained ordinary tests. The fair comparator tied, and no human maintenance savings were observed.
3. **Preliminary:** integrated change intent, protected behavior, source manifests, and staged diagnosis provide inspectable workflow evidence. **Unverified:** differentiated customer or economic value; these mechanisms are not unique detection proof.
4. **Failed:** this local model/retrieval configuration is not reliable enough for unattended factual service. **Unverified:** independent labels, semantic judgments, source-owner approval, representative held-out quality, legitimate-update specificity, and customer-stack validation needed before a customer pilot.
5. **Preliminary:** ready for a controlled technical demonstration showing real documents, negative outputs, and BLOCK/REVIEW behavior. **Unverified:** readiness for production deployment, sales claims of autonomous optimization, or broad startup differentiation.
6. Highest-value next steps: **Unverified objectives**, not completed results: (a) obtain independently reviewed labels and semantic judgments from a genuine source owner on a fresh frozen held-out set; (b) calibrate retrieval/predicate/date handling and model reliability on separate development tasks, then evaluate once without changing held-out labels; (c) run a paired source-update maintenance study against the equally maintained baseline in an independently operated agent, measuring review time, false rejections, diagnostic usefulness, and quality-preserving usage.

### Evidence and reproducibility

**Verified:** reusable scripts are [prepare/run](tools/validate_real_world_e2e.py), [analysis/replay](tools/analyze_real_world_e2e.py), and [Data CI replay](tools/replay_irs_data_ci.py). The `prepare`/`run` commands create immutable experiment destinations and perform real generation; do not rerun over this evidence. Analysis and Data CI replay need no inference. Use `PYTHONPATH=workspace/.deps` for the locally installed PDF dependency. Full regression command: `PYTHONPATH=workspace/.deps python -m pytest -q`.

Raw source PDFs, frozen source snapshots, the pre-inference code archive, exact provider requests/responses, original failed preflight, revised preflight, explicit technical-review identity, strict release, and analysis remain preserved. [Final integrity manifest](docs/artifacts/irs-e2e/final-integrity.json) separates final code from as-run code and checks source/call counts. **Unverified** items remain explicitly unknown; no human approvals, customer results, production mutations, or paid API savings were manufactured.
