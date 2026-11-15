# Operational closure acceptance

**VERIFIED internal single-host fixture operations; production operations PRELIMINARY.** Platform: Mac16,12 / 24 GiB / macOS 26.5.1 ARM64 / Python 3.13.9. No other OS/Python combination was newly certified.

## Resource ownership and crash evidence

`runtime_resources.py` establishes two shared advisory slots under a fixed per-OS-user private runtime directory. Current service/CLI/fixture workers participate; trusted stewards inherit the slot and operation-owner descriptors until supervised children stop. Real subprocess contention and SIGKILL tests verify rejection and recovery. Nested operations share ownership rather than deadlocking. An older runtime or a trusted OS user executing arbitrary code is outside this advisory boundary.

Admission fails below 512 MiB free disk, at 128 retained operation directories or above 256 MiB retained evidence. Two bounded in-flight operations can overshoot these admission thresholds: these are not hard physical disk or total-memory quotas. Snapshot/request work is bounded independently. No automatic removal of uncertain active operations occurs.

Scratch is owner-only and records ACTIVE/INCOMPLETE state. A killed owner leaves evidence. Cleanup requires an exclusive owner lock, validated operation identity, and verified process-group termination; uncertain groups remain untouched. Before deletion it creates an exclusive private ZIP, hashes its regular files, records symlink metadata without following links, reopens/verifies the archive and records the archive digest/tombstone. Archive output must be outside the runtime tree. Historical workspace/experiment paths are never cleanup targets.

Commands from the activated environment:

```sh
sourceroi runtime-cleanup
sourceroi runtime-cleanup --confirmed --operation op-EXACT32HEX --archive-directory /private/path/forensic-archives
```

Use the actual preview operation ID. Retained archives can contain document content: keep them private and follow the operator's retention policy. General errors do not print source bodies. This sprint preserved test failure logs and new temporary forensics. An early cleanup revision removed 42 newly created fixture scratch directories with metadata-only records; the final policy was subsequently strengthened to require verified raw forensic export. No historical artifacts or real-model records were removed. Later cleanup exported 41 inactive operations with verification; see `forensic-cleanup-results.json` and `runtime-forensics/`.

## Installed upgrade and rollback

`tools/validate_closure_install.py` builds on the local wheelhouse and hash-locked dependencies in a fresh temporary Python environment. It installs the preserved Phase 3 wheel, provisions authored identities, installs the new test wheel, verifies silent migration refusal, executes `sourceroi --project PATH auth-migrate`, verifies session revocation and credential retention, rolls back to the earlier auth-aware wheel and verifies store/service refusal (including explicit unauthenticated mode), then reinstalls the new wheel and runs installed TXT/PDF/DOCX parsing. Evidence: `installed-upgrade-results.json`, including both wheel hashes and exact subprocess commands.

Schema 2 is explicit, transactionally upgraded under an exclusive stopped-writer workspace lock. Migration revokes sessions/receipts, increments identity revisions, fences unfinished jobs, marks outstanding attempts UNKNOWN and preserves terminal history. Failure rolls back the transaction. Running service processes must be stopped before migration. This is a tested supported rollback refusal, not protection against an OS administrator running arbitrary ancient pre-authentication code. The new wheel is a test artifact of beta version 0.2.0, not a newly sealed release/distribution; prior packages remain intact.

## Recovery and measured workload

`acceptance-final/measurements.json` records 22 documents / 82 chunks, cold ingestion 150.97 ms and immutable cache 11.62 ms. Four synthetic fixture attempts completed in 2.73 seconds with verdict REVIEW. Twenty in-process API reads had median 3.16 ms and maximum 4.72 ms. These are local authored measurements, not throughput guarantees, real-model latency or customer scale.

Complete backup and fresh-directory restore retained source/config/task identities; restored active users, sessions, approvals, jobs, fixture authorizations and semantic judgments were all zero. Historical records are inspection data, never live restored authority. `offline-copy-restore.json` additionally verifies the trusted digest after a copy into a separate temporary directory before restore. This is **same-host offline-media simulation**, not an actual off-host recovery test. Existing corruption, parser failure, worker death/recovery and restored-provenance tests remain in the full suite. Actual Chrome Uvicorn startup/shutdown and fixture foreground-worker completion are separately recorded.

**PENDING:** encrypted-at-rest backup and actual off-host restore/RPO/RTO. The existing verified environment lacks cryptography/gpg/age; system LibreSSL is available, but no reviewed authenticated-encryption wrapper was implemented. Ordinary ZIP restore is not encryption. A vetted encryption/key custody implementation and failure/tamper/restore tests remain required; absence of a library is not a claim that encryption is technically impossible. Independent operations/security acceptance, sustained larger workloads and deployment-specific capacity remain pending.
