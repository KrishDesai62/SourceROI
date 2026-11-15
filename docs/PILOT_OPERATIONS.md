# Local pilot operations and deployment path

Supported deployment model: one trusted operator, one process, one workspace on a private local disk; loopback only. No public server, shared hosting, tenant isolation, identity provider, SLA or certification has been verified. Trusted callbacks/configuration execute with the operator's local permissions. A hostile user sharing that account is outside the enforced boundary.

## Installation and startup

Use PILOT_ONBOARDING.md. The project ranges are compatible constraints, not a reproducible lock. requirements-pilot-observed.txt records observed installed packages, with a declared missing DOCX dependency. Clean installation and vulnerability/supply-chain scanning remain PENDING. Existing CI runs the suite on Python 3.10/3.12; this sprint only ran Python 3.13 locally. No container or framework was added because it would not establish isolation or solve native correlation.

Start via the existing CLI with an absolute workspace path and loopback binding. Do not use `uvicorn` directly to expose the factory publicly; no server-side user authorization exists. Do not put a reverse proxy, tunnel or shared remote desktop in front of this pilot without a separate security design. Ignore forwarded identity/host headers; the new guard validates the actual Host and exact Origin. Browser mutations require application/json; each routed response gets a generated X-Request-ID. This is HTTP request correlation only, **not native model accounting**.

Liveness: GET /api/v2/health. Readiness: GET /api/v2/ready returns 503 for invalid configuration/storage and 200 only for local config/SQLite checks. It does not contact a model, certify evidence, or establish production readiness. SourceROI uses no telemetry collector and sends no new logs off-device. API run failures store exception class only, avoiding raw exception text in new asynchronous job records; raw evaluation artifacts intentionally contain source/answer evidence and must be protected as sensitive.

## Capacity and isolation

API body: 1 MiB measured before JSON parsing, total receive deadline 15 seconds; configurable server-level connection limits are still required for hostile clients. Documents: 12 MiB each; 2500 supported documents; 400000 extracted characters/document and 12 million total indexed characters. Benchmark: 12 MiB and 10000 tasks. DOCX ZIP preflight: 2000 entries and 48 MiB declared expanded size, required document parts. PDF header checked. These bounds are not parser CPU/memory isolation; decompression, PDF content streams, deeply nested JSON, regex scoring and filesystem race resistance require further review. Large document extraction can still precede text truncation. Use only reviewed pilot inputs until parsers run with verified process resource limits.

Run concurrency uses an in-process semaphore, not a cross-process workspace scheduler. Use exactly one server/CLI writer; a second app startup can mark another process's running rows interrupted. This is a known unresolved reliability limitation. Do not use multiple Uvicorn workers. Daemon background run threads are not a durable queue; shutdown may interrupt them. Stop starting jobs, wait for active work to finish, then Ctrl+C. On restart, orphaned running rows become failed; retained checkpoints are evidence, not automatic resume. Request retries can start new work: mutating API requests have no durable idempotency keys. Acknowledge fields are consent UX, not per-user authorization or a native generation budget.

## Backup and recovery

SQLite uses WAL, parameterized queries, busy timeout and transaction rollback. This sprint tests rollback, bounded pagination and a consistent SQLite backup restored into a separate empty directory. It does not establish crash/power-loss fault tolerance, retention compliance or authenticated tamper-proof audit storage.

Quiesce application writers and source edits. Store backups outside the active workspace in a private operator-managed directory. Never overwrite an earlier backup:

```bash
python tools/backup_history.py --project PATH_TO_WORKSPACE --output PATH_OUTSIDE_WORKSPACE/history-unique.sqlite3
```

The command uses SQLite's online backup API, mode 0600, exclusive creation, integrity_check, run count and SHA-256. It does not back up sources, project.json, benchmarks, snapshots, review files or model artifacts. Separately preserve the complete source/config/snapshot/review tree with relative paths and hashes while writes are stopped; disk backups contain private documents. Backup metadata/hash output should be retained alongside the archive in access-controlled storage. No backups are uploaded.

To recover: stop all writers; verify the backup hash and SQLite integrity; create a **new** private workspace; restore matching source/config/task/snapshot/review files and the database to .sourceroi/runs.sqlite3; do not copy old -wal/-shm files; run doctor and readiness, inspect run/version identities, and verify strict release behavior before use. Never restore over production or a running original. The automated test exercises a database-only restore and confirms the original is unchanged; full-workspace disaster recovery remains PENDING.

No automatic retention, deletion or vacuum is enabled. Monitor disk use; stop jobs before exhaustion. Determine customer retention/export/deletion requirements before deployment. Preserve this repository's historical reports and manifests. Hash chains and fingerprints detect accidental drift when their root is trusted; an account owner can rewrite files and hashes. Off-host immutable audit storage/signatures are not implemented.

## Troubleshooting and rollback

403 Host/Origin: open exactly the bound origin (including port/hostname); do not bypass the check with a proxy. 413: reduce the request, not evidence requirements. 408: send a complete bounded JSON body. 415: use application/json. 422: fix schema/pagination. 409: wait for the active job; do not blindly retry mutations. 503 readiness: inspect configuration/path permissions and SQLite integrity locally. Unknown usage stays null. Strict REVIEW/BLOCK/INCONCLUSIVE are policy outcomes, not transport errors; do not convert them to ACCEPT.

Rollback application changes only with a matching frozen code/dependency/config copy in a new workspace. Never reuse source/config/task-bound approvals after incompatible changes. Schema remains the original runs table; no destructive migration was added. No automatic schema upgrade/downgrade contract has been validated.

## Production requirements

Before internet/multi-user deployment: authenticated identities and roles, workspace authorization/isolation, secured approvals, transport/access controls, parser process limits, application/provider egress policy, complete dependency lock/security review, durable job ownership/cancellation/idempotency, reliable backup/restore/retention, verified native or external provider accounting, infrastructure/load/failure testing, operational monitoring and independent security review. Add tenancy only when needed and tested. Do not advertise SOC 2, compliance, uptime or security certifications from this checklist.
