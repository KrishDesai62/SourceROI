# Single-tenant security acceptance — Phase 3 closure

All VERIFIED classifications below mean internally authored executable tests on this Mac, not penetration testing or independent security approval.

| Protection | Status | Evidence / limit |
|---|---|---|
| Fixed analytical worker operations, bounded input/output/CPU/wall | VERIFIED | `test_closure_resources.py`, parser tests, analytical report |
| Source identity and traversal protection | VERIFIED | Descriptor-relative no-follow snapshots; directory-substitution regression; both original roots denied |
| macOS scoped filesystem/network/process restrictions | PRELIMINARY | Negative executable parser tests plus replacement-exec test; scoped profile retains required runtime/code exceptions |
| Hard memory isolation | PENDING | Sampled 512 MiB group RSS can overshoot; RLIMIT_AS probe failed on this Mac |
| Shared current-runtime capacity | VERIFIED | Two actual subprocesses, contention and SIGKILL; fixed per-user root, two advisory slots inherited by trusted steward |
| Aggregate memory / physical disk quotas | PENDING | Slots and admission thresholds bound overlap, not total parent/browser RSS or kernel disk use |
| Private crash evidence and controlled orphan cleanup | VERIFIED | Owner lock, process-group termination check, mandatory verified forensic export before deletion |
| Authenticated roles / CSRF / reviewer identity | VERIFIED | Existing identity suite and real Chrome negative role test; no client reviewer identity accepted |
| Delegated source-owner identity / external independence | PENDING | Local reviewer role is not source-owner delegation or independent expertise |
| Approval authority separation | VERIFIED | Explicit UNVERIFIED external authority and false generation/release permission in new maintenance receipts |
| Semantic uncertainty / strict release | VERIFIED | Missing review REVIEW, protected regression BLOCK, unknown execution INCONCLUSIVE; fixtures cannot authorize ACCEPT |
| Durable native-style attempt contract | VERIFIED | Protocol fixtures only, existing native reconciler, body-bound one-use permits, terminal/unknown handling |
| New real native/provider execution acceptance | PENDING | Generation routes remain denied; no model startup or new model calls |
| Browser dashboard | VERIFIED | 17 actual Chrome fixture checks; basic keyboard/AX only |
| Full accessibility / independent usability | PENDING | No WCAG audit or external operator study |
| Explicit migration and supported rollback refusal | VERIFIED | Fresh installed wheel; old auth-aware build refuses schema 2; no silent migration |
| Complete backup and restore | VERIFIED | Source/config/task identities retained; no live authority restored |
| Encrypted backup / actual off-host recovery | PENDING | Plaintext archive; separate-directory same-host simulation only |
| Independent security assessment | PENDING | Not performed |

## macOS audit and residual risk

The profile denies outbound networking, fork, replacement exec except the required Python interpreter, AppleEvent send, mDNSResponder lookup, original source roots and sibling runtime evidence. Only the current work directory is writable; runtime/code access exceptions remain necessary for installed Python and optional parsers. `parser_steward.py` holds inherited capacity/owner descriptors until the primary child stops; parent death and deadlines kill supervised groups. Descriptor traversal and exclusive no-follow protocol files reduce symlink/replacement races. Existing tests exercise network, filesystem, process, CPU, file output and RSS restrictions; these are not exhaustive Mach/allocator or OS exploitation tests.

Hardware: Mac16,12, 24 GiB RAM, macOS 26.5.1 ARM64, Python 3.13.9. `platform-probe.json` records the attempted address-space limit failing with `ValueError: current limit exceeds maximum limit`. No stronger supported macOS hard-RSS primitive was demonstrated. Linux address-space limits exist in the worker but Linux deployment was not tested in this sprint. Introducing a VM/container boundary is outside this incremental implementation; review an appropriate stronger deployment boundary before hostile-input production acceptance.

**P0 production blockers:** no demonstrated hard aggregate memory boundary; no independent assessment of sandbox/runtime exceptions and privileged parent contracts. **P1:** encryption and off-host recovery acceptance, sustained workload/capacity validation, external authority verification, complete accessibility/operator acceptance. Native execution has its own mandatory fresh authorization and separately reviewed gate. Verdict: **production acceptance PENDING; Phase 3 not unconditionally complete**.
