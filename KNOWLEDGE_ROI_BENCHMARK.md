# Knowledge ROI benchmark — offline development evidence

**Outcome: INCONCLUSIVE for differentiated technical/customer value.** The new decision workflow functions internally; the equally maintained conventional workflow selects the same alternative and detects the same evidence failures. No real model, independently held-out questions, semantic reviewers or customer workload was used.

## Protocol and reproduction

```sh
workspace/design-partner/venv/bin/python tools/benchmark_knowledge_decision.py --output /private/tmp/NEW-knowledge-benchmark
```

Final executed evidence: `docs/artifacts/knowledge-decision/benchmark-v3/summary.json`, the four `*-report.json` files, original/candidate documents, frozen snapshots and per-case `development-protocol.json`. Output directories must not exist. Each protocol records exact task/source/configuration identities, candidate byte hashes, alternatives and development expectations before invoking the decision engine. Labels are Codex-authored exposed development labels; hashes do not turn them into independent ground truth. No published policy changes or real customer documents are invented.

Four fictional development workspaces use returns/warranty statements: consistent duplicate, consistent version replacement (30 to 14 days), contradictory added statement (99 days), and a fourth unsupported task with no evidence labels. The unchanged warranty behavior is protected. Three registered tasks include a two-document joint question. Each case evaluates the original plus six explicit alternatives: remove duplicate, remove policy, remove warranty, remove policy and warranty jointly, current candidate version, and fixed top-one context. Source/document/passage variants are also exercised in regression tests.

Both workflows receive identical versions, task IDs, labels, protected questions, retrieved passages, source/version identities, applicability/conflict observations and quality requirements. No answers or labels are supplied to retrieval selection. Ordinary conventional evaluation uses exact reference coverage and version/scope/conflict checks, and an exhaustive search over the **same alternatives and budget**, with the same deterministic minimum-context selection rule. It is not a deliberately weak top-one-only baseline. The two workflows share one set of measured retrieval observations; no duplicated model calls exist. Missing semantic authority prevents ACCEPT in either workflow.

## Final observed results

| Case | Current-candidate evidence decision, both workflows | Impact prediction vs authored affected-task labels | Reference/uncertainty observations |
|---|---|---|---|
| Duplicate unchanged | REVIEW | No positive labels/predictions; precision/recall undefined | All registered quotes retained |
| Consistent replacement | BLOCK | Precision 1.0, recall 1.0 on two development affected tasks | Frozen return references lost; unchanged warranty retained |
| Contradictory addition | REVIEW | Precision 1.0, recall 1.0 on two development affected tasks | Quotes still present, but potential same-predicate conflict flagged |
| Missing unsupported-task labels | INCONCLUSIVE | One false alarm: unsupported task; precision 0.0, recall undefined | Unsupported answer rejection cannot be measured without generation/labels |

The ordinary evaluator and SourceROI tie on all **28 experiment-level verdicts** (seven configurations in four workspaces). They select `without_duplicate` for the first three workspaces and no evidence-qualified alternative for the missing-label workspace. The overall report is a review proposal, not approval of the current candidate: e.g. a safe baseline removal can remain reviewable while the actual replacement experiment is BLOCK.

For the unchanged three-task case:

| Alternative | Mean literal reference coverage | Estimated retrieved-context tokens | Decision |
|---|---:|---:|---|
| Original | 1.0 | 44 | REVIEW |
| Remove duplicate | 1.0 | 30 | REVIEW, potential redundancy only |
| Remove policy | 0.5 | 30 | BLOCK |
| Remove warranty | 0.5 | 28 | BLOCK |
| Remove both | 0.0 | 14 | BLOCK |
| Top one | 0.5 | 23 | BLOCK |

Estimation is `sum(ceil(passage characters / 4))` for selected passage bodies. It excludes prompt scaffolding and completions, and is **not a tokenizer measurement or acceptable-answer-quality saving**. Both workflows find the same 44-to-30 estimate. Provider prompt/completion/total tokens, model cost, quality-qualified savings, semantic citation correctness and answer accuracy are all UNKNOWN. External spending was $0; actual generations were zero.

Joint removals are executed, never inferred by adding individual losses: removing policy loses two task references, removing warranty loses two, while the joint removal loses three distinct tasks, not four. The joint task depends on both documents. This establishes internal nonadditive task accounting, not a model-level causal interaction or a demonstration that individually harmless sources become jointly harmful.

All 16 source-action outputs match the predeclared development expectations (four per case); no REMOVE contradicts those authored expectations. This small policy-conformance result is not independent recommendation accuracy. The tests deliberately require REVIEW for insufficient/conflicting evidence and preserve protected evidence; unseen semantic errors remain possible. A version change is not proof that the new version is authoritative or correct.

## Overhead and failures

Final end-to-end local wall times were 347.90, 485.74, 459.22 and 362.01 ms respectively, on the same macOS ARM64/Python 3.13.9 environment. Retrieval evaluations were 21, 21, 21 and 28 respectively: **91 total** including ablations and repeated original/candidate comparisons. These timings include SourceROI preparation/persistence and may benefit from local immutable caches. They are not isolated CPU benchmarks, model latency, sustained throughput or independently measured developer effort. Conventional-only wall overhead was not separately timed; source planning adds work rather than a proven speed advantage.

Initial test evidence (`focused-first.txt`) includes a failed UPDATE expectation when the fixture retained an old conflicting duplicate. The engine correctly returned REVIEW. The development fixtures were separated into consistent replacement versus contradiction; conflict gating was not weakened. Earlier benchmark invocations and failures remain preserved. Missing-label impact prediction overselects the unsupported task: this is an observed false alarm, not silently omitted from precision.

## What would establish or falsify the product claim

Demonstrated: traceable source/task/version links, explicit combined interventions, conservative evidence constraints, saved review proposals and an inspectable recommendation policy. **Not demonstrated:** better detection than conventional checks, lower human maintenance/diagnosis time, acceptable-quality real token savings, model accuracy, semantic grounding or customer ROI. The historical exploratory 52.6% reduction is unchanged and is not a new qualifying optimization result.

A future independently prepared corpus/question split, reviewed semantic labels and separately authorized model run must compare both workflows with equal search/compute/evaluation authority, including all ablation overhead. Failure to outperform a strong maintained baseline, excess unsupported recommendations, missed protected regressions or evaluation cost exceeding savings would falsify the claimed benefit. The present detection/selection tie is evidence against claiming superiority now.
