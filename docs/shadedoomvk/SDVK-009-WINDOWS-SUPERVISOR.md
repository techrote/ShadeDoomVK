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

The packet also pins the current OS version and boot identity. A bounded native
read checks these before release/claim and before every collector. The reviewed
native boot layout must be qualified against a fresh CIM timestamp; unsupported
or ambiguous native reads fail closed.

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

The parent verifies Git source identity and commit existence before creating a
collector, then locks a fresh stage-specific proof. Inside the collector, only
the frozen oracle's exact commit-existence query uses that explicitly labelled
parent proof; all recipe, regeneration and content checks still run. This keeps
read-only Git helpers outside the strict collector job without admitting unknown
children. Frozen PF generators and the dynamically loaded PNG decoder are also
part of the closed, pinned Python input set.

Only an accepted diagnostic can support a distinct full-campaign packet: 20
reference captures, six high-resolution correctness captures, then 15 timing
processes. The [existing protocol](SDVK-009-GPU-QUALIFICATION-PROTOCOL.md) governs
workloads, 120+120 timing frames, exact comparisons, `scene.immediate` coverage,
work normalization, >1.20 in two of three repetitions and the 16.67 ms trigger.
No threshold, workload or quality reduction follows from supervisor qualification.

## Responsive integrity control

A large closed-file inventory must not prevent the main supervisor from checking
observers or publishing its control heartbeat. One bounded worker performs deep
inventory, generated-input and append-only log audits. The main loop publishes
heartbeats only while observer, process ownership, deadline, root guards and the
latest integrity generation remain healthy. A separate timer cannot publish
healthy heartbeats on behalf of a stalled control loop.

The packet must explicitly declare the new integrity policy. Deep audits have a
ten-second bound and generations may be at most ten seconds old from their start.
Creation and resume additionally consume a newly requested, one-use generation:
its finish must be less than half a second old, and the request/start deadlines
must remain unexpired at the native call attempt. The recorded monotonic attempt
is an observation immediately before the native call, not a kernel start time or
an external execution attestation. Existing packets cannot silently acquire the
new policy.

The request binds the packet, stage, supervisor creation identity, source proof,
role and nonce; target requests additionally bind the actual registered collector.
The worker independently hashes generated target inputs. Retained byte locks and
terminal native namespace notifications on local fixed NTFS protect generations;
root and ancestor handles also retain directory identity. Unsupported filesystems,
signals, path ambiguity or changed membership fail closed. A notification is
never reset to reuse a generation.

Both supervisor and collector check health during bounded gate waits. The exact
live configuration remains locked through preparation and receipt writes, then
is released in the final resume callback, followed by renewed safety and proof
checks. Native create/resume code rechecks the returned minimum deadline at its
recorded call attempt. Complete receipts are published without overwriting an
existing destination. Final deep and native checks follow the last event and
telemetry fences before collection can be reported complete.

CPU controls include a realistic large inventory, deliberately slow audits,
stalled workers and gates, changed membership and junctions, replayed or expired
proofs, delayed configuration publication/handle release and process exit during
identity verification. A positive exit exception requires the same retained
handle, PID and creation time; it never authorizes termination of an ambiguous
live process. A failed experiment remains failed and consumed. Any repaired
successor requires separately qualified bytes, a new packet and a fresh decision.

## CPU qualification and privacy

The suite uses synthetic feeds and benign CPU children. It exercises native
suspended handles and file locks on Windows; portable policy tests run in the
ordinary CPU gate. These tests launch no renderer and create no Vulkan device.
The normal GitHub-hosted CI policy remains in force.

Host inventories, private operator source, signed driver bytes, crash dumps and
personal telemetry stay outside the public repository. Public evidence must be
reviewed and limited to general tooling, synthetic controls and consented results.
