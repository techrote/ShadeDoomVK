# Conditional renderer grant and atomic attempt accounting

The original CPU-only `resolve_for_review` output remains a deliberately
non-executable draft. It cannot release the v1 gate. The integrated path is a
separate `physical-supervisor/conditional-approval-v2`; the existing exact-packet
human approval remains unchanged for packets without a conditional grant.

The grant retains the owner's actual instruction/addendum, identity, recorded
time, unique ledger root, finite expiry and limits. A later plan review binds
the exact packet and grant digests, accepted clean supervisor commit/tree,
source/CPU evidence, fulfilled conditions and reviewer provenance. It cannot
claim a later human `decided_utc` or invented approval phrase. Self-review must
be labelled as such. Source acceptance/CI are required before physical use.

The reviewed maximum is 24 renderer creation attempts, with at most three
retries per named test (four attempts total). The supported workload still has
only compositing, shadow-boundary-1 and shadow-boundary-2 in that order, hence
at most 12 attempts across these three tests. The maximum is not a quota and
does not authorize inventing more tests. Each packet has zero automatic retries.

Initialize a new ledger once with `initialize_ledger(grant)`, then pin its
`grant.json` as `packet.conditional_grant` and in `packet.files`. The absolute
root and grant/owner identity are part of those immutable reviewed bytes; an
execution never silently creates or resets a missing ledger. The OS byte-range
lock serializes an append-only, numbered hash chain. Complete exclusive records
are flushed before publication. Pending publications, chain gaps and unresolved
sessions block successors. Release, session claim and the existing experiment
claim remain bound to the packet and its fresh STOP root.

Budget publications additionally use Windows `MoveFileExW` with only
`MOVEFILE_WRITE_THROUGH` (no replace/copy/reboot flags), or directory `fsync`
after exclusive hard-link publication on POSIX CPU controls. The native
[publication contract](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)
is required before returning a charge; there is no ordinary-rename fallback on
failure. This requests OS durability, not a claim to survive broken storage.

The collector charges once in the final native creation callback, before
`CreateProcess`, under the shared spawn gate and budget lock. Failed creation,
expired proof after charging, collector death and later failed validation all
consume the attempt. No reservation is refunded. Resume does not charge twice.
A later stage cannot charge until independent validation and the preceding
stage's telemetry/System-event grace fence complete. Final receipts retain
failure or collected-pending-acceptance, never physical approval.

A successor requires a fresh packet, output and experiment root, retained final
result pins and explicit assessed predecessor digests plus a written retry or
repetition disposition. A crashed session without a terminal receipt remains
held for investigation; this interface supplies no automatic recovery or STOP
removal. Hardware faults are assessed before any proposed retry. Global and
per-test caps remain shared across all successors using the grant.

CPU controls cover concurrent native reservations, global/per-test exhaustion,
order/fence/replay rejection, interrupted publication, chain corruption, forged
later decisions and missing prerequisites. Native end-to-end controls use only
benign Python targets: three serial successful stages, failed creation, observer
failure and collector death after durable charge. No control creates Vulkan
objects or launches the renderer. Historical STOP/failure bytes are immutable,
Physical STOP remains active, SDVK-009-PHYSICAL held and issue #9 open.
