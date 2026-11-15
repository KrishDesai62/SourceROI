# Evaluation maintenance study handoff

A [source-owner onboarding tool](SOURCE_OWNER_ONBOARDING.md) now prepares the existing review/release workflow without editing internals. It does not supply independent labels, human participants or time-saving evidence.

**Status: pending real participants and independent source owners.** No human session, click, edit or time saving was fabricated during this sprint. Automated unit events occur only in temporary test directories and are excluded from human summaries.

## Equal-authority comparison

Compare A: a maintained full-suite answer/evidence process with B: SourceROI proposals, explicit review and integrated release assurance. Both receive identical frozen before/after documents, approved factual updates, protected behaviors, independent labels, supporting references and applicability rules. Compare equivalent release requirements: giving only B semantic checks or change intent is unfair.

An external operator should preregister case selection, participant identities, domain expertise, outcomes, exclusions and analysis. Counterbalance workflow order using separate comparable document groups to limit learning effects. Keep final cases hidden from implementation/tuning and label them before outputs. Record independently verified correctness and errors, not just elapsed time. Annotate/exclude interruptions and validate the logger's wall-clock timing; elapsed time is not automatically active work time.

Measure discovery/editing/review/debug effort, accepted/rejected/corrected proposals, new tests, protected expectations, missed failures and total task/model executions. SourceROI's automated `maintenance` counters are field/decision counts, not observed human effort. Existing controls show fewer answer entries with declared intent, but additional ambiguous items still require judgment. They do not establish a labor advantage.

## Event logger

Use a preregistered protocol ID and exact source/test/change hash. Commands below are instructions for actual participants; they were not executed as human study evidence:

```bash
python tools/maintenance_study.py record --log study-events.jsonl \
  --protocol-id REGISTERED_PROTOCOL_HASH --session-id UNIQUE_SESSION \
  --participant-id VERIFIED_PARTICIPANT --origin human --workflow sourceroi \
  --change-id EXACT_CHANGE_HASH --event start
# Record review or edit events using the same identity; --edit-count records actual edits.
# Finish with --event complete. Workflow A uses --workflow maintained_full_suite.
python tools/maintenance_study.py summarize --log study-events.jsonl
```

Origin must be `human` or `automation`; automation cannot enter the human-time summary. Each event has a sequence, UTC timestamp and hash-chain link. macOS/Linux file locking serializes append operations. The logger rejects invalid event order, changed session identity and broken chains. The chain detects accidental/tampered edits without recalculated hashes; it is not authentication against a malicious operator.

Raw declared-human elapsed times are emitted only for completed sessions. A real operator must verify participant identity, activity, clock validity and study design; the tool does not authenticate them. `time_savings` remains null: paired/counterbalanced analysis and uncertainty must be produced from an externally validated study rather than automatic raw differences. No reported customer time saving exists.

## Independent annotation package

```bash
python tools/independent_validation.py template --output owner-annotation.json
# External source owner completes labels, approved updates, protected behaviors,
# jurisdiction/scope/effective dates, citations, reviewer declarations and provenance.
python tools/independent_validation.py freeze --input owner-annotation.json \
  --output frozen-independent-protocol.json
```

The package supports before/after document versions and separate label hashes. Approved factual changes require an authorized approver and source quotes in the correct before/after version. Both development and final sets must cover required challenges and use disjoint document families; exact/normalized and near-duplicate checks reject detected leakage. Semantic/pretraining overlap and human independence cannot be guaranteed by a hash or hidden directory. Current delivered package is unannotated and pending, not an independent final validation result.
