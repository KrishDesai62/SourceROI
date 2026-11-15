# Authenticated single-tenant engineering target

Status: **PRELIMINARY controlled beta boundary, not single-tenant production readiness**. Authentication, authorization and review binding are implemented and tested. Authenticated model-executing HTTP routes are deliberately unavailable until durable execution and parser isolation are verified. The ordinary trusted local CLI remains available; this document grants no inference permission.

The deployment is one trusted OS account, one workspace, direct loopback HTTP and one service process. All users belong to the same tenant and may read that tenant's registered data. There is no user-private data partition, tenant switching, public ingress, reverse proxy, TLS termination or remote operator access in this supported target. Both the Host/Origin browser boundary and actual loopback peer are checked. Forwarded headers are not trusted by the CLI server.

| Identity | Authority |
|---|---|
| OS administrator | Owns files, installs code, provisions/disables identities, changes roles, handles incident response. Can bypass the application through filesystem/CLI access; this is the root of trust. |
| Service process | Runs under that OS account, limited to its selected workspace by configuration. No separate cryptographic workload identity or OS sandbox is claimed. |
| Viewer | Reads the selected workspace's inventory, tasks, histories and reports. Cannot freeze, plan or review. |
| Operator | Viewer access plus source snapshot/change planning through current APIs. Cannot submit reviews. |
| Reviewer | Viewer access plus review decisions for exact server-registered plans. Cannot freeze or plan. |
| Admin | All HTTP roles. User provisioning remains an explicit offline OS-admin action, not a self-service HTTP endpoint. |
| Source owner | Must delegate authority to the provisioned reviewer/operator out of band. A supplied `declared_by` string does not prove source ownership. No per-source owner directory or automatic owner consent is implemented. |
| Model/RAG application | Existing adapters and native accounting gates remain in place. Authenticated HTTP generation is disabled. Source documents/model outputs are untrusted evidence, not instructions or approvals. |

Use only reviewed, bounded, authorized documents until parser isolation is implemented. A password login does not make malicious PDFs safe. Do not forward this port, run behind a proxy, expose a shared machine account, or use hostile uploads.

## Provision and start

From the repository using its existing verified Python environment (substitute an existing authorized workspace):

```sh
workspace/design-partner/venv/bin/python -m sourceroi --project /absolute/workspace auth-init
workspace/design-partner/venv/bin/python -m sourceroi --project /absolute/workspace auth-add-user --user operator --role operator
workspace/design-partner/venv/bin/python -m sourceroi --project /absolute/workspace auth-add-user --user reviewer --role reviewer
workspace/design-partner/venv/bin/python -m sourceroi --project /absolute/workspace serve --require-auth --host 127.0.0.1 --port 8765
```

Passwords are entered in a private interactive terminal with echo disabled, confirmed twice, never passed in arguments or environment variables, and must contain 16–1024 characters. The identity store is `.sourceroi/security/identity.sqlite3`, schema version 1. Owner-only directory/file permissions, no symlinks/hardlinks, and an exact resolved workspace binding are required. It must not be copied to another workspace as a working identity store.

Once the security directory exists, the current server detects provisioning automatically and fails closed if it is incomplete. `--require-auth` also fails if no identity store exists. Explicit unauthenticated startup of a provisioned workspace is rejected. Existing unprovisioned workspaces retain their legacy local mode; it is not authenticated and must remain OS-trusted loopback only.

Open the dashboard on that exact loopback origin and sign in. The backend enforces roles regardless of UI controls. Sessions use HttpOnly, SameSite=Strict cookies with a one-hour absolute expiry. Cookies intentionally lack Secure on literal loopback HTTP; this is not a supported HTTPS/public deployment. Every cookie-authenticated write requires a same-origin Origin header and the login response's CSRF value in `X-CSRF-Token`. The dashboard holds CSRF only in memory; refreshing asks for login again. Sign out revokes the session server-side. API clients may use the same opaque session token as a Bearer credential; there is no unauthenticated API-key issuance endpoint. Do not use both transports together.

Passwords use salted scrypt (`n=16384,r=8,p=1`). Session and CSRF values are SHA-256 hashed at rest. Login failures are serialized/throttled in SQLite: five per attempted username and twenty globally per fifteen minutes. This is a small-service abuse control, not distributed denial-of-service protection. Identity storage failures do not grant access. Credential transport, cryptographic parameters and implementation have not received an independent security review.

## Review workflow and limits

1. The operator freezes sources through the existing snapshot API/dashboard, edits authorized source files through the trusted OS workflow and submits a change plan.
2. The service records the exact plan and snapshot in its identity store.
3. A separate reviewer session submits a review of that exact plan. Omit `reviewer` in the decisions JSON or supply the authenticated username. Impersonating another username is rejected.
4. The backend rechecks source/task/configuration versions and canonical proposals. It attaches authenticated identity metadata, recomputes the approval ID, and records an expiring server receipt. Existing strict semantic reviews remain distinct from maintenance approval.
5. The receipt validator supports atomic single-use consumption, rejects forged/stale/expired/revoked approvals and rechecks canonical inputs. This is tested offline. **It is not yet connected to a durable authenticated execution worker.** All six generation endpoints, including release, return 403 before handler execution. Client-supplied semantic reviews or `acknowledge_model_calls=true` cannot unlock them.

Do not route around this restriction with the legacy HTTP mode. Authenticated generation acceptance is a later phase requiring execution authorization, durable jobs, parser controls and verified semantic-review storage. Native certificates/authorizations remain separate and the historical authorization remains consumed.

## Revocation and operations

```sh
workspace/design-partner/venv/bin/python -m sourceroi --project /absolute/workspace auth-set-role --user operator --role viewer
workspace/design-partner/venv/bin/python -m sourceroi --project /absolute/workspace auth-reset-password --user reviewer
workspace/design-partner/venv/bin/python -m sourceroi --project /absolute/workspace auth-disable-user --user reviewer
```

Role changes/password resets revoke that user's existing sessions and outstanding approvals. Disabling additionally blocks new logins. Revocation applies to subsequent authorization checks, not data already returned or requests already authorized. There is no cross-user logout or HTTP identity administration.

The private audit table records fixed event names, actor UUIDs, outcome status and request IDs, never credential values, request bodies or query strings. CLI Uvicorn access logs and proxy-header trust are disabled. Host administrators can alter the store; it is not a tamper-proof external audit log. Do not enable body/header/query logging in a supervisor. No automated audit retention is supplied yet.

Readiness checks storage and reports `production_ready=false` and `execution_enabled=false` for the provisioned target. Health is minimal and public only to loopback peers. The old readiness native-accounting field remains PENDING for current-process compatibility; a separate scope explains the historical bounded run.

Stop the foreground process with Ctrl-C. No service supervisor, automatic job recovery or production rollout was installed. Startup no longer marks every running row interrupted. Legacy orphaned jobs remain visible; do not assume automatic recovery or reissue model jobs without reconciliation.

Upgrade: stop the service, preserve the original code and all workspace files, and run the regression suite against the new version. Schema v1 accepts only its workspace/version; incompatible stores fail startup. **Coordinated backup/restore and safe production rollback are not implemented.** Never roll back to an old unauthenticated server against a provisioned workspace. Do not copy a live SQLite file or delete evidence to “repair” state. Incident handling is to stop the service, preserve artifacts, and revoke identities using the offline commands; full recovery is the next engineering phase.
