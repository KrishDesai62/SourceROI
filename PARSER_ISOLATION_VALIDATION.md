# Parser isolation validation — Phase 3

**VERIFIED internal tests on macOS 26.5.1 ARM64 / Python 3.13.9.** This is a scoped resource/security boundary, not a container, independent penetration test or guarantee against arbitrary parser exploitation.

## Routes and contracts

`ingest.scan_sources`, `extract_document`, legacy `_extract`, and `load_benchmark` now enter `parser_boundary`. Source enumeration takes bounded read-only byte snapshots; parsing, extraction, chunk construction, CSV/Markdown table parsing and benchmark JSON validation run in `parser_worker`. The raw extractor rejects invocation in the service process. Numerical source-bound calculation/table binding also runs in that worker. Published dataset JSON decoding, prior published-source extraction and retrieval-audit evidence verification use the boundary. Regex task grading is isolated to prevent a configured regex hanging the service.

The shared helpers cover inventory/project preflight, frozen snapshots/version checks, knowledge plans, impact/maintenance evidence, citation/source validation, evaluation/ablation/optimization preparation, Data CI, diagnosis/repair, CLI and API consumers. CLI registration copies bytes without interpreting them; its first source inspection uses this boundary. Trusted project configuration, identity/SQLite records and bounded HTTP JSON remain control-plane data, not documents. External customer callbacks/RAG services execute their own code and are outside SourceROI's parser sandbox.

The parent passes only fixed operation names and parser settings/data, never a document-supplied command, reviewer, provider or executable. Copied inputs use private temporary directories, a scrubbed environment and closed inherited descriptors. Worker output is versioned JSON. Source/document/chunk IDs, registered paths, extracted fingerprints, literal offsets, raw table hashes and allowed output fields are checked. Authority/scope remains registered configuration, never source-instruction authority. No output is unpickled or executed.

Raw file identity includes descriptor device/inode/size/mtime/ctime and SHA-256. Symlinks/hardlink aliases/traversal are rejected. Sources are re-read/rechecked before accepting parsed output, including on immutable cache hits; changed file sets reject. Workspaces inside trusted runtime/code read exceptions are unsupported and fail closed. macOS temporary-root aliases are normalized before checks.

## Actual enforced bounds

| Bound | Implementation / evidence |
|---|---|
| Wall time | Parent supervisor 15 s per parser process, plus trusted steward deadline; capacity wait separately 15 s. Hang test kills the group. |
| CPU | Worker RLIMIT_CPU soft 8/hard 9 seconds. A real busy-loop rlimit test terminates its child. |
| Memory | Parent samples total steward/worker group RSS, threshold 512 MiB. Allocation stress verifies kill at a lower test threshold. **Sampling can overshoot; this is not a hard macOS address-space bound.** |
| Output file | RLIMIT_FSIZE 48 MiB and response size checks. Actual configured oversized writer is killed/rejected. |
| File descriptors / cores | Worker RLIMIT_NOFILE 64 and RLIMIT_CORE 0. |
| Processes | macOS profile denies fork; unexpected third process in the steward group triggers rejection and group cleanup. RLIMIT_NPROC is attempted but not independently claimed as the macOS enforcement mechanism. |
| Host effects | Tested macOS profile denies network, writes outside private temp and reads of the protected original workspace/home data, with explicit trusted code/runtime read exceptions. |
| Input / corpus | 12 MiB per source file, 2,500 source files, 64 MiB copied source corpus. Published dataset input has a separate 64 MiB bound. |
| Parsed text | 400,000 characters/document, 12 million/corpus; oversized content is rejected, never silently truncated. |
| Formats / complexity | PDF >250 pages and encrypted PDFs reject; DOCX >2,000 ZIP entries or >48 MiB inflated data reject; unsafe ZIP paths/symlink members reject. CSV/JSONL >10,000 records reject. JSON depth >64 and source nodes >100,000 reject; dataset JSON nodes >1 million reject. |
| Service concurrency | Two active ingestion operations per process, including snapshot allocation; nested helper calls share the slot. Waiting callers time out before allocating source snapshots. This is not a cross-host/global fleet limit. |

The macOS profile deliberately permits necessary runtime services; it is not deny-default. An early deny-default experiment could not launch this Python runtime and was not accepted as working isolation. The constrained profile was tested against real forbidden actions. Missing macOS sandbox support and unverified operating systems fail closed without an unsandboxed production-parser fallback. Linux/Windows production ingestion is not certified by this phase.

## Termination, provenance and negative tests

Real tests cover hangs, CPU exhaustion, memory allocation, oversized output, fork/network/write/read denial, child processes, parser failure, and killing a supervisor. A separate trusted steward monitors the original parent; parent death kills its process group even when parser code is stuck. A successful worker exit without a complete terminal JSON file is rejected. Source files and approval state are never modified by parsing. Failed work cannot return a partial parsed document as complete.

TXT, Markdown, CSV multiline fields, JSON/JSONL, malformed HTML, malformed PDFs/DOCX, DOCX bombs, Unicode, traversal, symlink/hardlink substitutions, concurrent content/file-set changes and frozen-source checks are exercised. Installed-wheel smoke additionally parses TXT, PDF and DOCX with the optional dependencies. Existing table-cell/offset and numerical regression cases continue passing.

**PENDING limitations:** independent SBPL/dependency security review; absolute no-overshoot memory enforcement; global limits across manually launched service processes; robust orphan-temp retention after SIGKILL; and adversarial CPU bounds for all downstream analytics. BM25 query scoring, change diffing and some reference/diagnostic matching consume bounded parsed data in the main process; the whole analytical pipeline is not claimed to run inside the parser sandbox. This is a remaining broader Phase 3 acceptance limitation, not a reason to enable hostile public uploads or real generation.
