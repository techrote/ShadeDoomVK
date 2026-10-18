# Strict Windows diagnostic supervisor

This package is general tooling. It contains no historical operator source,
machine readings, renderer executable, protected dumps or driver images.
Importing it and using `prepare`, `validate`, `event-baseline` or `init-stop`
does not launch a renderer or create Vulkan objects.

The supported physical scope is exactly three serial diagnostic processes:
compositing, shadow-boundary/1, shadow-boundary/2; 640×480, 120 warmup frames,
one state/RGB frame, 180 seconds, exact comparison and zero retries.
`kind=campaign` is deliberately rejected. The separate 41-process campaign
needs its own fully implemented workload/coverage gate and review.

Closed runtime roots must be on local fixed NTFS volumes. The packet constructor
adds an exact `integrity_policy`; packets without this policy require a new
prospective review and approval. Existing packets are never upgraded at runtime.

## No-launch preparation

Use Python 3.10 or later on Windows. A private seed supplies:

- `experiment_id`, timezone-aware `created_utc` and `expires_utc`;
- a reviewed `host_identity` from the read-only native `host-identity` command:
  exact OS version/build/platform/service-pack, native pointer width and boot
  FILETIME; keep the independently surveyed CIM boot time as separate evidence;
- `source: {commit, tree}`, an independently verified `build_receipt` pin,
  `oracle_source_root` (the clean frozen checkout), and a pinned Git executable;
- absolute paths for `python`, `renderer`, `nvidia_smi`, `prepared`, `iwad`,
  `stage_output_root` and the shared `stop_root`;
- `runtime_roots`, including the isolated renderer and Python runtime directories;
- reviewed `telemetry` identity/policy, `native_device` expected native readbacks,
  `event_baseline`, and optional extra evidence `files` pins;
- the reviewed `environment_policy` map; preparation can capture it using
  `common.environment_policy(environment_extra_keys)`. It explicitly records
  absent controls as null, including manifest-derived layer enable/disable keys;
- complete native64 `registry_policy` full-value rows for HKLM/HKCU Vulkan
  Drivers/ImplicitLayers/ExplicitLayers and actual device driver keys, plus
  `registry_enumeration_policy` for display-class/ControlVideo parent keys;
- `module_policy` with `required_paths`, `optional_paths`, `sample_seconds:0.25`,
  `reader_timeout_seconds:10`, `unknown_policy:"record-system-only"`. All required
  and optional loader/ICD/layer library paths must already be pinned.

A pin is `{path, sha256, size}` with an absolute path, lowercase SHA-256 and byte
size. The build receipt contains a versioned `schema`, `source` with
`dirty:false`, `executable` pin, `configuration`, `toolchain`, `flags` and
`source_snapshot` pin. The executable may be copied into the isolated runtime;
the original and copied byte identities must agree and both remain pinned.

`telemetry` requires name, PCI bus ID, driver version, GPU UUID, PCI device ID,
actual/default power limits, measured maximum graphics/memory clocks and an
explicit allow-list of hexadecimal clock event reasons. Transient clocks must
remain finite and inside the reviewed envelope. Native observer identity uses
`vendor_id`, `device_id`, `device_type` and `driver_version_raw`.

Power draw must fit NVML's unsigned 32-bit milliwatt representation, allowing
observed centiwatt CSV rounding up to 4294967.30 watts. This checks representation;
finite readings above the configured power limit remain valid.
[NVIDIA's power-usage API](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html)
documents the unsigned milliwatt result.

```text
python -B -m tools.physical_supervisor init-stop --root <fresh shared STOP directory>
python -B -m tools.physical_supervisor host-identity --out <fresh private host identity receipt>
python -B -m tools.physical_supervisor event-baseline --out <fresh private event receipt>
python -B -m tools.physical_supervisor prepare --seed <private seed.json> --packet <fresh packet.json>
python -B -m tools.physical_supervisor validate --packet <packet.json>
```

Preparation reads the frozen oracle recipes, constructs the exact target argv
and generated-copy pins, inventories closed runtime/code/spec/input directories,
and verifies clean source HEAD/tree with read-only Git. It creates no stage
output directory. Seal the packet only after code, fixtures, runtime and review
are final. Its approval digest is SHA-256 of `common.canonical(packet)`, rather
than the original JSON whitespace. Changing any field invalidates approval.

## Exact approval and execution

The external operator workflow must record a fresh trusted decision for the
final packet. The tool does not infer permission from a seed, a broad intent,
old approvals or software CI. An approval has:

```json
{
  "schema": "physical-supervisor/approval-v1",
  "experiment_id": "THE-EXACT-EXPERIMENT-ID",
  "packet_sha256": "<canonical packet SHA-256>",
  "phrase": "AUTHORIZE THE-EXACT-EXPERIMENT-ID (three diagnostic processes only)",
  "decided_utc": "<fresh timezone-aware timestamp>",
  "expires_utc": "<reviewed timezone-aware expiry>"
}
```

Additional trusted authorization provenance can be retained in this private
record. The tool cannot authenticate a human identity or manufacture an operator
decision. The caller owns that provenance and must present the exact packet.

```text
python -B -m tools.physical_supervisor run --packet <packet.json> --approval <approval.json> --out <fresh control output>
```

The shared root retains its initial `HELD.json`, one exact-packet release and a
one-attempt claim. Every STOP is a new exclusive file; even a partial STOP file
blocks all spawn/resume gates. Never remove a failed claim/STOP to retry. A new
experiment requires a reviewed disposition and must preserve the previous root.
Before approval release/claim and every collector creation, a bounded native
read must match the packet's OS/boot identity. A reboot or OS identity change
invalidates an unused approval even when the event-log epoch remains unchanged.
There is no fallback or automatic update of the reviewed identity.

The native reader uses documented `RtlGetVersion` fields and the reviewed
48-byte `NtQuerySystemInformation(SystemTimeOfDayInformation)` native layout.
Its boot-time offset is a compatibility assumption, not a documented stable
Windows ABI: unknown size/status or implausible time fails closed. Independently
compare the prospective native boot FILETIME with fresh CIM LastBootUpTime at
CIM's reported precision before accepting a host packet. See Microsoft's
[RtlGetVersion](https://learn.microsoft.com/en-us/windows/win32/devnotes/rtlgetversion)
and the [System Informer native boot-time reader](https://github.com/winsiderss/systeminformer/blob/master/phlib/include/phnativeinl.h).

## Containment and evidence

Deep closed-directory and append-only log audits run in one bounded worker,
separate from the supervisor control loop. Canonical expected memberships are
computed once; every audit still enumerates current membership and rejects
reparse points. Each exclusive generation receipt records its packet, stage,
supervisor creation identity, sequence, start/finish times, coverage and policy.
The worker never publishes heartbeats or controls a process. A dead worker,
failure, queue overflow, ten-second audit timeout or successful generation older
than ten seconds from its start stops the experiment without a retry.

Before collector and target creation, a new one-use request binds a nonce,
source-preflight pin and the exact known owner. Its audit must start after the
request and finish within ten seconds of it; the target audit independently
rehashes every generated input while the collector's immutable locks are held.
Creation, target acknowledgement and resume require that generation
to have completed less than 0.5 seconds earlier. The same proof must remain valid
through final native creation/resume checks; an expired proof stops rather than
requesting another attempt. Heartbeats retain their 0.5-second schedule and strict
two-second parent guard. Both processes poll the shared gate without blocking
their health/deadline checks; one second of gate contention is a STOP.

Retained no-delete directory handles bind roots and ancestors by volume/file ID.
Recursive native change notifications are installed before audits, and a signal,
invalid handle, changed path binding or reparse point permanently invalidates the
generation. Signals are never reset. Existing immutable file locks protect bytes;
notifications protect namespace membership between deep checks. This policy
rejects remote and unsupported filesystems. See Microsoft's
[change-notification limitations](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-findfirstchangenotificationw).
Exact registry and process ownership readbacks remain in each serialized launch
boundary. Completed JSON is flushed and atomically published without overwriting
an existing receipt, so coordination readers cannot observe a partial writer.
Lifecycle records retain monotonic timestamps captured immediately before native
creation/resume calls, after their final checks. These are call-attempt times;
kernel creation FILETIME remains the separate process identity. The live mutable
config stays locked through resume preparation and is verified/released in the
last native callback; its release-ready and actual-release records are distinct.

The supervisor creates a suspended collector in an inventory-only Windows job.
The collector creates a suspended target, retains its process and primary-thread
handles, registers exact PID/creation ticks/path/SHA-256 and the collector's own
creation identity, and waits for the supervisor's authenticated acknowledgement.
A shared gate checks durable STOP before creation and resume. The supervisor
independently opens and verifies the target. Native termination always uses an
owned handle after rechecking target and retained-parent identity; it never uses
`taskkill`, image-name killing or a job kill-on-close shortcut. Unowned matching
renderer candidates cause STOP and are never terminated.

The collector checks a retained supervisor handle and fresh healthy heartbeat.
Supervisor death or stalled protection causes authenticated target termination.
The supervisor detects collector failure and contains its retained target,
including an orphan whose authenticated parent has exited. A suspended process
whose identity cannot be established is retained as an explicit unresolved
containment failure; the tool never guesses a PID to kill.

Pinned files are opened denying writes/deletion. Runtime directory inventories,
source HEAD/tree/clean state and loader environment are rechecked before stages.
Native64 driver/layer registry values and device-key enumeration are rechecked
before creation/resume and throughout the active guard. The seed's independent
loader inventory must pin all referenced manifests/libraries, including enabled
implicit hooks; the tooling neither disables layers nor changes registry values.
The target receives only the explicit sealed environment. The only mutable input
exception is the exact live `stage/fixture.ini`: it is checked and locked until
immediately before native resume, then may be persisted by the engine. Its
original `stage/input/fixture.ini` stays locked. Both original and final live
config bytes are inventoried; actual console/native settings remain required.

The isolated adapter imports the pinned frozen oracle without changing its
source. It substitutes explicitly labelled **DECLARED_NOT_EXECUTED** expected
version bytes for the oracle's extra `--version` process, so the diagnostic still
has exactly three targets. `run.json` and `request.json` label that provenance.
The real native observer build/working-tree/device record must independently
agree. Both collector and supervisor perform the frozen observer/state/RGB
validation before another stage.

Before collector creation the parent independently checks frozen HEAD/tree/clean
state and the candidate commit's existence with pinned read-only Git, then seals
a fresh stage receipt binding that transcript to the packet, stage and parent's
creation identity. The frozen preparation verifier's single exact
`git cat-file -e <candidate>^{commit}` request reuses that fact with explicit
`DECLARED_FROM_SEALED_PARENT_GIT_CHECK` provenance. It creates no Git child in the
collector's job. Every other preparation subprocess request is rejected. Actual
fixture source/member/hash checks and pure regeneration still execute. The full
frozen PF Python package, including the dynamically executed PNG decoder file,
belongs to the pinned closed runtime and stays locked by the parent.

An independent bounded reader enumerates the actual owned target's loaded
modules and retains native paths plus SHA/size observations without launching an
extra process. Every configured required path, including the Vulkan loader and
selected ICD, must be observed; optional registered layers stay pinned and are
verified if observed.
Any pre-pinned module must match. Previously unknown Windows-root modules are
retained as post-launch observations; unreviewed external/driver/layer modules
fail closed. Static DLL closure remains prospective until actual observation.
Samples are attempted about every 0.25 seconds with a ten-second bound; short
lived modules between samples cannot be excluded. Reader/hash work runs away
from the main heartbeat and GPU/event cadence loops.

GPU observations start at one-second cadence and System event reads at five
seconds, on separate loops. Reader timeout is at most ten seconds; missed
cadence, nonfinite values, policy drift, event/read errors and queue failure stop
the experiment. This is bounded polling, not instantaneous protection.

The native `wevtapi` reader retains raw XML, channel creation epoch, oldest ID,
exact anchor hash and bookmark. It resumes strictly at the bookmark, reads **all
System events** to the captured watermark, verifies every ID without a last-64
limit, and rejects clear/rotation/gap/security ambiguity or NVIDIA/Display events.
After each stage, monitoring continues for 15 seconds; in-flight readers then
finish and a new synchronous event/telemetry fence must pass before continuation.
An event arriving after the finite observation window cannot be ruled out.

Receipts use exclusive writes, fsync and a numbered SHA-256 chain. Every stage
retains collector/target lifecycle, raw output, telemetry/events, partial failure
data and a recursive size/SHA inventory including caches and final config. The
final control manifest independently inventories all stage roots. Evidence
storage failure cannot skip authenticated containment attempts. Power loss or OS
failure can leave incomplete records; those records cannot qualify as success.
`COLLECTED_PENDING_ACCEPTANCE` awards no physical/performance acceptance and says
nothing about a historical fault's cause.

## CPU qualification

```text
python -B -m unittest discover -s tools/physical_supervisor -t . -v
```

Portable synthetic tests cover packet/approval gates, hashes/partial receipts,
STOP races, event gaps/clears/bookmarks/>64 batches, late events, policy/nonfinite
telemetry, output faults/replacement, timeout/no-retry and failed evidence writes.
Windows tests additionally exercise actual suspended Win32 handles, retained
parent identity, wrong-identity kill withholding, asset locks and job inventory.
Integration tests use an isolated synthetic oracle and a uniquely named copied
**Python CPU executable**, including three-stage success, failed observer/output,
abrupt supervisor/collector death, orphan containment, late event fence and config
persistence. They do not launch a renderer, renderer version command or Vulkan.
The existing GitHub-hosted Windows RelWithDebInfo job runs these controls; no
physical campaign is dispatched by CI.
