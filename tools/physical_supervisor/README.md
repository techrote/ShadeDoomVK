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

An explicitly recorded conditional allowance may use the separate v2 approval
and durable attempt ledger described in
[the conditional grant contract](../../docs/shadedoomvk/SDVK-009-CONDITIONAL-GRANT-DRAFT.md).
It preserves zero automatic retries; a later reviewed successor consumes the
same finite budget and cannot reset historical claims or STOP records.

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
The `native_device` map must contain exactly these four uint32 integers, with
device type 1 or 2. Nulls, booleans, metadata keys and nonphysical device types
fail validation and the approval boundary. Keep unavailable/readback provenance
outside this map. PCI/NVML values cannot replace native Vulkan properties.
An incomplete inventory remains private evidence, not a successfully prepared
packet. Obtaining missing properties requires separate explicit authorization;
the tooling never obtains them by creating a Vulkan instance.

Validation re-derives every stage's complete command from the frozen oracle,
including input/output paths and observer flags. Changing a command while
leaving capture metadata intact must fail before any execution workflow.

Native64 registered driver/layer JSON files must be in `files`, together with
every referenced library. Libraries must also appear in the module policy, and
manifest `enable_environment`/`disable_environment` names must be explicitly
captured (including absent values) through `environment_extra_keys`. Static
inspection reads registry snapshots, JSON and file bytes only; it never loads
the loader, ICD or layer. Bare DLL search names require separately resolved
evidence and fail this static path. A DWORD 0 legacy registration is enabled for
discovery; nonzero is disabled. Device `VulkanDriverName`/`VulkanImplicitLayers`
values are separate discovery sources even if legacy Drivers keys are absent.
The current x64 validator does not interpret WoW registrations as x64 inputs.
Actual loader selection and native device readback remain separate evidence.

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

Before each collector/target creation and each native resume, a distinct one-use request binds a nonce,
source-preflight pin and the exact known owner. Its audit must start after the
request and finish within ten seconds of it; the target audit independently
rehashes every generated input while the collector's immutable locks are held.
Each native call requires its own generation to have completed less than 0.5
seconds earlier. Registration validates the creation proof at its recorded native
call attempt; it authenticates and retains the target handle before later admission
checks, so a failed proof cannot strand a suspended orphan. Durable identity and
acknowledgement work precedes the separate resume request. A target resume proof
also pins the exact target registration. An expired native-boundary proof still
stops without a retry. The packet explicitly declares this separate-resume policy;
old packets cannot silently gain it. A suspended target must request resume within
two seconds; its audit remains bounded by ten seconds, and actual renderer execution
retains its independent deadline from the recorded resume call. Heartbeats retain their 0.5-second schedule and strict
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
Only transient control-loop heartbeats omit the disk-cache `fsync`: their buffered
write is flushed and closed before the same atomic no-overwrite publication.
An `fsync` can otherwise delay visibility until the timestamp is already stale.
Integrity generations, source proofs, journals, STOP records, native-call receipts
and attempt ledgers retain their existing disk flushes. Heartbeats still come
only from the live control loop; missing, partial or two-second-old publication
cannot renew protection, and no background timer hides a blocked control loop.
On Windows, transient JSON and hash readers request only `GENERIC_READ` and share
read, write and delete access. This lets them coexist with a publication metadata
handle holding `DELETE` access; a deterministic native control covers that sharing
case. It does not establish the exact interleaving of any earlier intermittent
failure. Malformed/partial JSON and genuine sharing or access denial fail on the
first read. Immutable `FileLock` handles retain their original write/delete denial.
Lifecycle records retain monotonic timestamps captured immediately before native
creation/resume calls, after their final checks. These are call-attempt times;
kernel creation FILETIME remains the separate process identity. The live mutable
config stays locked through resume preparation and is verified/released in the
last native callback. Its checked release requires successful `CloseHandle`;
failure withholds native resume and the actual-release receipt. Release-ready
and actual-release records are distinct.

The supervisor creates a suspended collector in an inventory-only Windows job.
The collector creates a suspended target, retains its process and primary-thread
handles, registers exact PID/creation ticks/path/SHA-256 and the collector's own
creation identity, and waits for the supervisor's authenticated acknowledgement.
A shared gate checks durable STOP before creation and resume. The supervisor
independently opens and verifies the target. Native termination always uses an
owned handle after rechecking target and retained-parent identity; it never uses
`taskkill`, image-name killing or a job kill-on-close shortcut. Unowned matching
renderer candidates cause STOP and are never terminated.

After an exact full identity attestation, a resumed owned object can enter a
native image-teardown interval: `QueryFullProcessImageNameW` may fail with access
denied while its retained handle has not yet signaled exit. Only that structured
native operation/error pair permits one requested 50ms exit observation per
failed authentication call, with at least that much remaining caller budget.
A positive exit signal must retain the same held PID/creation identity; there is
no second image query and no termination through incomplete live identity.
Initial registration and resume authentication stay strict. A known path, hash
or parent mismatch, another native error, insufficient budget or a live timeout
fails closed. Observations retain the original failure, requested and actual
wait times, deadline and native results; elapsed scheduling time still counts
against every caller deadline. Cleanup after STOP may make the same bounded
observation without renewing a healthy heartbeat. The prospective packet policy
includes the 50ms limit and exact reviewed operation/error pair.

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

When an IWAD selects a support WAD, the prospective seed can declare
`iwad_support = {"iwad": <oracle pin>, "packages": [<oracle pin>, ...]}`.
Oracle pins have `path`, `sha256` and `bytes`; packet custody pins use `size`.
The original IWAD pin must match exactly, and each support WAD must be a regular
file directly beside the executable and present with identical bytes in packet
custody. The oracle adds only these declared resources, retaining exact loaded-set
equality. Every capture/request/profile must preserve the declaration, and the
supervisor independently compares it with the packet. Unknown, missing, duplicate,
changed, unbound or path-aliased packages remain failures.

To update only the oracle, declare both `renderer_source_root` and `oracle_source`
(`commit`/`tree`); `source` continues to identify the renderer, while
`oracle_source_root` names the corrected oracle checkout. Both checkouts are
verified clean against their own pins. A fresh accepted tooling source, packet and
prospective review are required; sealed historical renderer/oracle inputs and
failed run statuses cannot be rewritten.

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

Run native CPU qualification invocations serially on a host: separate suites
use the same benign target basename and deliberately reject one another as
unowned candidates. Optional `SDVK_CPU_FAILURE_EVIDENCE_ROOT` retains unexpected
failing integration fixtures before temporary cleanup. Candidate STOP receipts
retain PID, parent PID and name as observations, never executable attribution.

Module enumeration can race DLL teardown. A prospective packet may additionally
declare the exact `EnumProcessModulesEx`/`ERROR_PARTIAL_COPY` 299 exit discriminator.
It requires an earlier successful sample covering every nonempty required module
set, the same fully attested retained native object, and positive exit confirmation
within the existing 50 ms bound. It never retries enumeration or forgives a live,
unidentified, incompletely observed or hash-mismatched process. Raw native error,
PID/creation identity, wait result and exit code remain in the exit observation;
the collector still requires exit code zero. Historical failed packets stay failed.
Microsoft documents [module-list changes during enumeration](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-enumprocessmodulesex)
as a possible failure cause; that alone cannot establish normal exit.

The stock VKDoom comparison also encountered a module-path read failure at
normal exit. Its historical observer discarded the native return/error code,
so that attempt remains failed. Prospective source now retains the exact
`GetModuleFileNameExW` zero return, error code, module handle, PID, buffer size
and observation time, clearing stale thread error state before the native call.
Only that precise zero-read operation with error6 or299 can use the same
previous complete coverage, full retained-object attestation and bounded
positive-exit discriminator. A truncated path, changed identity, live/unknown
object, zero/unknown error code, missing prior coverage or exhausted caller budget still stops. No path
read is retried and no running target termination authority changes.

### Registered partial capture schedules

`prepare-registered --seed SEED --registration REGISTRATION --packet PACKET`
adds the separate `registered-workload` kind. Ordinary `prepare` retains the
three fixed diagnostic stages and their 120/1 frame, 640x480, 180-second contract.
`kind: campaign` remains rejected; no full 41-process campaign is enabled.

The immutable registration uses schema
`physical-supervisor/registered-workload-v1`, profile `REGISTERED_WORKLOAD` and
scope `PARTIAL_COLLECTION_ONLY`. Its purpose is `sdvk011-viewmodel`,
`sdvk014-lifecycle`, `sdvk009-fault-discriminator`, `sdvk008-partial-reference` or
`sdvk008-partial-reference-and-cost`. It binds renderer/oracle commit and tree,
build receipt, renderer/IWAD/prepared-manifest pins and one fresh output root.
Each ordered capture declares only `name`, `scene`, `recipe_sha256`, `mode`,
`frames`, `warmup`, `extent` (two integers), `deadline_seconds`, and
`compare_with` (an earlier state stage name or null). Recipe hashes use the
frozen oracle's canonical JSON representation. All commands, copied-input pins,
observer flags, required outputs and comparison paths are derived again from
the verified prepared recipes; registration cannot supply arbitrary argv.
Viewmodel/lifecycle captures are state-only. Per-stage limits retain the oracle
bounds of 4096 retained frames, 100000 warmup frames and 1920x1080, with an
explicit 1–600 second native deadline. Existing generator-specific frame and
material assertions still execute before target creation in `run.capture`.
Fault discriminators are also state-only and permit exactly one stage per
packet, preserving a fresh unique campaign-wide CFX trace file for each creation.
That purpose alone permits optional boolean `collision_snapshot`; when true it
derives the existing `-sdvkcollisionsnapshot` option and requires
`collision-1.bin`. This records production CPU collision state and makes no
claim to capture submitted GPU bytes. Recipe-declared probe-owner, sampler-reset,
lightmap-transition and special-surface driver flags retain the exact order used
by the frozen capture adapter.

Initialize a fresh conditional ledger whose grant additionally contains
`registered_workload = {"profile": "REGISTERED_WORKLOAD", "registration":
<packet-style pin>}`. Its `tests` must equal the registration's ordered names,
`max_renderer_launches` must equal their count, and `max_retries_per_test` must
be zero. The grant, registration and inputs must be in packet custody. This is
the sole profile permitting a dynamic stage list or a 26-creation partial POM
budget. The original conditional diagnostic limits remain unchanged. Every
creation attempt is charged durably, failed creates are never refunded, and
each earlier stage must complete its independent validation and late-event
fence before the next charge. The existing v2 review binds exact packet and
grant bytes, truthful earlier owner authority and the reviewed supervisor source.

POM registrations additionally pin `pom_plan`, the existing prospective
`sdvk008-current-source-plan/v1`. Its genuine `vulkaninfo --summary`, owner
instruction, generation, legal-content license and missing full gates stay
mandatory and pinned. The admitted schedules are exactly the driver's 16
reference captures or 26 reference-and-partial-cost captures. Before the first
timing target is created, the owned collector reuses the oracle's repeat,
continuity, controlled OFF/ON image and projected-direction gates. Every gate
must PASS; inconclusive direction/image evidence cannot admit timing. The gate
receipt is retained as `registered-reference-gate.json`. Collector and independent
supervisor validations also retain the POM native backend/device, prepared OFF/ON
package continuity, emitted relief-work witness, raw timing integrity and
host/loader/environment continuity checks. The same 30-second
collector preparation bound, native job/handle ownership, module observation,
telemetry, System events, heartbeat, RootGuard, deadlines and durable STOP apply.
Partial collection remains pending issue acceptance; it cannot accept POM
quality modes, missing full gates, hardware stability or any milestone by itself.
