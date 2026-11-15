# Complete workspace backup and restore — Phase 2

**VERIFIED on bounded internal workspaces under explicit quiescence.** This is not a malicious-writer filesystem snapshot, encrypted backup service or production disaster-recovery certification.

Stop the service, foreground workers, external editors and direct Python writers. Current CLI invocations, HTTP requests, legacy background jobs and the offline worker cooperate through a POSIX workspace lock. `serve` holds a shared lock for its lifetime; backup requires an exclusive nonblocking lock. Busy work fails rather than racing a copy. Direct library/filesystem writers outside this contract must be stopped by the trusted OS administrator; `--quiesced` attests that condition. Before/after inventory, source identities and identity history are compared to detect ordinary uncooperative changes, not adversarial change-and-revert attacks.

```sh
workspace/design-partner/venv/bin/python -m sourceroi --project /absolute/workspace workspace-backup --output /private/backup-new.zip --quiesced
workspace/design-partner/venv/bin/python -m sourceroi workspace-restore --archive /private/backup-new.zip --destination /private/restore-new --sha256 TRUSTED_SHA256_FROM_BACKUP_OUTPUT
```

The restore creates `/private/restore-new/workspace`. The container must not exist. Trust the digest through an independent protected channel; a digest stored next to an attacker-modified archive does not establish authenticity. No live workspace is overwritten.

Backup schema v1 inventories relative paths, sizes and SHA-256 values; captures all ordinary workspace files within 10,000-file / 512-MiB bounds; includes sources, task/config files, snapshots, reports, evidence, old manifests and run histories. Registered frozen snapshots are verified. Standalone SQLite files are captured through the SQLite online backup API and integrity checked. Known SQLite sidecars and the cooperative lock are runtime state, not separately copied. Symlinks, hardlinks, special files and unexpected identity-store files reject the backup rather than silently disappearing.

The private identity DB is deliberately **not** copied. A protected historical export retains user IDs/names/roles, plans, audit, approval provenance, job schema/history/events and original workspace metadata, without password hashes/salts, session/CSRF secrets or live authority. Sources/reports may themselves contain sensitive information. Backup archives are owner-only plaintext; encryption/key management/off-host storage remain PENDING. No sensitive customer data was used in acceptance tests.

A backup writes a new `.partial-...` file, checks consistency, flushes it and atomically publishes via exclusive link. Existing outputs cannot be overwritten. Interrupted files are distinguishable and never accepted as the requested final archive. Keep them for investigation; this tool does not delete historical data.

Restore verifies the trusted archive digest **before extraction**, validates member paths/types/duplicates/size bounds and exact manifest membership, verifies all file hashes, SQLite integrity, active source/config/task identities and frozen snapshots. Extraction is into a private new container with `RESTORE_INCOMPLETE`; failures/kills preserve that marker and never publish `workspace`. Successful verified content is flushed and renamed within the reserved container. The marker is removed only on completion.

Identity recovery is intentionally asymmetric: create an empty private identity store bound to the final new root; restore no users/passwords, sessions, usable approval receipts or queued jobs. Re-provision authorized identities with `auth-add-user`. Historic reviews retain original IDs/versions in JSON/run history but grant no new authority. Historic active/uncertain jobs require explicit reconciliation; no worker auto-resumes them. Native authorizations/certificates are not renewed by restoring artifacts.

Retention preview only:

```sh
workspace/design-partner/venv/bin/python -m sourceroi --project /absolute/workspace retention-preview evidence/example.json
```

It returns inventory and `would_delete=false`; no deletion is implemented. Paths are confined; identity and registered historical-development paths are excluded. Customer retention categories must separately cover sources, generated answers, logs, evaluation reports, credentials and backups. Secure erasure, WAL/backup propagation, timed deletion, retention policy and legal deletion guarantees remain PENDING. No historical experiment evidence was deleted.
