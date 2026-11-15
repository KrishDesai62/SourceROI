# Phase 4 implementation plan (audit-backed)

Existing: `engine.py` and `validation.py` already implement generated source/document/passage ablations and quality-constrained policy studies; `recommendation.py` qualifies held-out study results. `assurance.py` supplies frozen version comparisons, impact predictions, pending evaluation maintenance, release reviews and limited source-value recommendations. `data_ci.py` supplies literal reference coverage, change checks and rollback comparisons. The fixed analytical worker, shared admission, authenticated role boundary, durable fixture jobs and strict semantic gate must remain intact.

Missing vertical slice: an offline, persisted decision record joining version changes, explicit individual/combined alternatives, conservative source/document/passage recommendations and a fair identical-output conventional comparison. Existing source-value output has KEEP/REVIEW only and cannot justify combined removals. No new generation is authorized.

1. Add strict typed request/alternative/quality structures. Compare a verified frozen snapshot and current workspace using the same frozen tasks. Use existing inventory/plan/policy/evidence primitives in the same bounded worker. Test individual and combined exclusions directly; never sum independent effects.
2. Record exact retrieved evidence/version identities, literal reference/applicability/conflict signals, quality constraints, estimated context tokens separately from unavailable provider usage and unknown model cost. Produce KEEP/REMOVE/UPDATE/REVIEW review proposals, never release approval or mutation.
3. Persist immutable content-bound decisions idempotently in the existing run-history schema; expose an authenticated operator POST and existing read/history/dashboard paths. Keep security state in the parent and all model routes disabled.
4. Build an offline authored development benchmark with redundant, interacting, changed, protected, conflicting and unsupported cases. Give the conventional comparator identical observations, labels, evidence requirements and authority. Report ties and failures; independently held-out/semantic/human effort claims remain pending.
5. Run focused tests and full regression suite. Preserve earlier reports/artifacts byte-for-byte and produce the three requested Phase 4 reports with exact scope and evidence.

No schema rewrite, new framework, customer deletion/deployment, independent-review fabrication or change to historical labels/results. Phase 3 hard-memory, encryption/off-host and independent security blockers remain pending.
