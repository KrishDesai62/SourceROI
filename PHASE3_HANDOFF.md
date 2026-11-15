# Phase 3 handoff — parser isolation and execution acceptance

Phase 2 supplies a durable **offline** worker and quiesced complete recovery. It does not enable native/provider execution or certify legacy job recovery. Keep every authenticated generation route disabled. The historical model authorization is consumed.

Next required engineering:

1. Isolate every production ingestion route, including inventory/plan/preflight, in bounded subprocesses. Enforce wall deadlines, memory/CPU/process/output/file limits on the supported OS; terminate children, retain errors and fail closed. Test malformed PDF/DOCX, decompression bombs, hangs, large Unicode/text/JSON/CSV/HTML and parser regex behavior. Size checks alone are insufficient.
2. Recheck file/symlink/version identity at the parser boundary and keep exact source/cell provenance. Documents and embedded instructions must never confer authority. Verify all eight features through the isolated path.
3. Bind durable reservations to a separately recorded bounded generation authorization, existing native permits/task IDs/terminal events and immutable reconciliation. A lease expiry never permits redispatch. Test unknown outcomes, crashes after actual fixture dispatch/response, late commits, deadlines, cancellation and child/untracked calls using deterministic protocol providers. No real generation is authorized by this handoff.
4. Add authenticated semantic adjudication storage and strict release integration distinct from maintenance receipts. Preserve missing-review REVIEW, protected BLOCK and incomplete/lost-owner INCONCLUSIVE. No fixture assertion may become independent review or ACCEPT.
5. Expand API/dashboard acceptance for job polling/cancel/ownership, maintenance evidence, errors and restore operations. Current offline jobs are API/CLI operable; no new dashboard job runner or supervisor is installed.
6. Exercise larger local workloads, native process-tree shutdown fixtures, operational restart, encrypted/off-host restore and full installation/migration/rollback. Explicitly test restored provenance while never reviving sessions/receipts or uncertain old jobs.

Before enabling any generation path, pass those gates, obtain a fresh explicit execution authorization and independently review the security boundary. No paid APIs/public deployment are authorized. SourceROI remains a controlled local beta, not single-tenant production/enterprise SaaS. Real semantic/customer value and superiority over the tied conventional baseline remain unproven.
