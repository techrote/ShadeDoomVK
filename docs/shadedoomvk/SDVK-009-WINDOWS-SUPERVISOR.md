# SDVK-009 Windows resumption supervisor

This tooling prepares and supervises a separately registered experiment. It does
not qualify physical GPU stability, attribute either historical fault, or award
the SDVK-009 performance decision. Issue #9 remains open until actual accepted
correctness, timing and architecture evidence exists.

The original operator programs and sealed failed incident packets remain private,
historical evidence. `tools/physical_supervisor` is an independent implementation
of the reviewed containment requirements. It does not execute the historical
launcher or the old physical driver's `--execute` entry point.

## Source and approval

The renderer and the supervisor have separate source identities. A renderer
checkout is frozen to a selected accepted commit/tree and independently built
without executing either application. A build receipt pins its clean source,
compiler/configuration, executable and source-file inventory. Engine packages,
shader sources, dependencies, official IWAD and generated fixtures are pinned
separately. Installing newer tooling must not silently advance the renderer.

`prepare` and `validate` are no-launch operations. A packet includes a fresh
experiment ID, expiry, complete file inventories, exact stage commands, current
read-only hardware policy and a native System event bookmark/epoch. `run` requires
an approval record bound to that packet's canonical SHA-256 and exact scope.
Approval provenance must accurately record the actual human decision; a generated
scope phrase must never be presented as text the human typed. Publication and
green CI alone confer no physical launch permission.

The initial HELD record is retained. A packet-specific release and one-use claim
cannot clear a permanent fault STOP. The shared gate serializes STOP, process
creation, registration and resume. Missing, partial, expired or changed inputs
fail closed. A failed experiment is never retried or relabelled.

## Ownership and observation

Collectors and renderer children are created suspended and authenticated before
resume. Owned native handles bind PID, creation time, executable path/hash and
the parent creation identity. The supervisor independently acknowledges each
child. Termination rechecks the same identity and uses that handle; ambiguous
ownership withholds termination and records STOP. No image-name kill is used.
Collectors also watch their supervisor's identity, liveness and heartbeat.

Telemetry is read every second and the whole Windows System channel every five
seconds, with a ten-second reader timeout. These are polling bounds, not
instantaneous intervention. Native bookmark/anchor and log epoch checks enumerate
all new records, including batches larger than 64. Log clearing, gaps, rotation,
read errors and relevant NVIDIA/Display events stop the experiment. Stage
completion includes a late-event grace and a completed event-read fence.

The loader/ICD and registered layer manifests/libraries have prospective pins.
Registry registrations and layer enable/disable environment controls are read
and rechecked without changing them. Owned-target module snapshots distinguish
actual loaded files from static resolution candidates. Changed known bytes,
missing required modules, ambiguous reads and unexpected non-system modules
block acceptance; additional system modules retain their observed identities.

Identity/power/clock-policy drift, nonfinite data, temperature at or above the
reviewed limit (never above 80 C), reader/queue failure, device/validation/fault
output, process failure, deadline or incomplete evidence also stop subsequent
launches. Hardware configuration is never changed by this tool.

Raw output, native event XML/bookmarks, telemetry, process registration/resume/
exit/termination, independent stage validation, all cache files and incomplete
results are retained. Exclusive hash-chained records and independent SHA/size
manifests expose missing or changed evidence. Receipt-write failure must not
skip an otherwise authenticated termination attempt.

The engine normally saves its live `fixture.ini` at exit. Its original bytes are
verified before resume, while the separate input copy stays locked. Only that
declared live configuration becomes writable for normal persistence. Actual
console/observer settings and the final saved file remain separate evidence.

## Diagnostic and later campaign

The diagnostic remains compositing, shadow-boundary/1, shadow-boundary/2, serially:
640x480, 120 warmup frames, one retained state/RGB frame, 180 seconds per renderer,
zero retries. The frozen oracle validates native settings/build/device and state;
the supervisor independently repeats validation before another stage. The shadow
pair requires exact semantic state and RGB equality.

No extra `--version` application process is launched. Expected version bytes are
explicitly labelled `DECLARED_NOT_EXECUTED`; the real native observer must prove
the actual build identity. Packaged shader-source hashes and retained cache
modules do not establish the identity of an executed GPU instruction.

Only an accepted diagnostic can support a distinct full-campaign packet: 20
reference captures, six high-resolution correctness captures, then 15 timing
processes. The [existing protocol](SDVK-009-GPU-QUALIFICATION-PROTOCOL.md) governs
workloads, 120+120 timing frames, exact comparisons, `scene.immediate` coverage,
work normalization, >1.20 in two of three repetitions and the 16.67 ms trigger.
No threshold, workload or quality reduction follows from supervisor qualification.

## CPU qualification and privacy

The suite uses synthetic feeds and benign CPU children. It exercises native
suspended handles and file locks on Windows; portable policy tests run in the
ordinary CPU gate. These tests launch no renderer and create no Vulkan device.
The normal GitHub-hosted CI policy remains in force.

Host inventories, private operator source, signed driver bytes, crash dumps and
personal telemetry stay outside the public repository. Public evidence must be
reviewed and limited to general tooling, synthetic controls and consented results.
