# Phase 3 security audit

## VERIFIED internal controls

- Shared document/benchmark/dataset decoding, source chunk/table extraction and numerical binding moved into bounded subprocesses; raw in-process extractor rejects service invocation.
- macOS profile denies network, fork, non-private writes and protected original-workspace/private-home reads, with explicit trusted runtime/code exceptions. Workspaces inside those exceptions reject even on cache hits. Unsupported sandbox platforms do not silently fall back.
- Parent and independent steward enforce deadlines/process-group cleanup, including actual supervisor death. CPU, output-file, descriptor and core limits apply; memory RSS is sampled. Per-process ingestion capacity is two, with bounded waiting before input allocation.
- Descriptor-based raw snapshots, source-set checks, hashes, literal offsets, table provenance and strict output schema prevent ordinary TOCTOU/substitution and trusted-field injection. Extracted instructions remain data; OS tests prove actual denied effects, not just prompt filtering.
- Durable fixture authorization is separate from maintenance receipt and real generation authority. Requests, state transitions, raw terminals, usage and reconciliation seals are private/version-bound. Unknown outcomes never retry or ACCEPT.
- Semantic identity is authenticated/assigned; claims and evidence are immutable/input-bound; source/result/reviewer changes invalidate records. Independence is explicitly unverified. Fixtures cannot promote ACCEPT.
- Original Host/Origin/loopback/CSRF/role protections remain. Job access is actor-scoped; assigned-reviewer packets have a separate permission boundary. Operational audit omits bodies and credentials; raw provider fixture bodies stay in private evidence storage, not ordinary logs.
- Full restore retains source/history provenance but restores zero active identities, sessions, receipts, fixture authorizations, jobs or semantic judgments. Existing historical files remain unchanged.

## FAILED intermediate checks, preserved

Initial semantic test helpers attempted to quote a fixture task with no retrieved evidence; they failed. The fixture's changed property key did not match its question and strict retrieval correctly lacked support. Tests were corrected to review the actually cited protected warranty task, without changing original labels/grading. Separate acceptance uses a correctly registered authored source and still returns REVIEW, not independent quality success.

An early eight-feature optimizer assertion assumed a nonexistent success/None contract; actual behavior correctly kept the baseline with no valid reduction. A source-race monkeypatch needed the new boundary keyword argument. An experimental deny-default macOS profile could not start this Python runtime; it was rejected, not represented as isolation. The constrained profile was then tested against actual denied actions. All intermediate logs are retained.

## PENDING / limitations

This is not a complete arbitrary-code container sandbox. Trusted interpreter/dependency read exceptions and macOS runtime services remain; independent SBPL, dependency and parser-exploit review is required. Memory enforcement samples RSS and can overshoot; it is not a hard macOS RLIMIT_AS guarantee. Multiple manually launched service processes are not globally resource-scheduled. SIGKILL can leave private temporary evidence directories; retention/cleanup policy remains manual/pending.

Downstream BM25 scoring, change diffing and some matching/diagnosis consume bounded extracted data in the main process. They are not all protected by independent hard CPU deadlines. This is an unresolved broader hostile-workload acceptance item. SourceIO copies and parses, but customer callback applications retain their own execution/ingestion trust. No full end-to-end hostile-code certification is claimed.

Browser automation, an adjudication UI, external reviewer authority, real native/provider authorization-to-job integration, real uncertain-provider reconciliation, global deployment supervision, encrypted/off-host recovery drills and independent security/customer validation remain PENDING. Existing artifact hash/dependency checks are not vulnerability certification; network advisory/publisher attestation review is still pending. No real generation/public deployment is enabled.
