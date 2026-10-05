# PF-020 final-source ordinary Dense comparison

Status: bounded preparation revision2, 2026-10-05; fresh
[FinalDense05](PF-020-FINAL-DENSE-MEASUREMENT.json) passes the complete ordinary
comparison. [Aggregate disposition](PF-020-AGGREGATE-DISPOSITION.md) satisfies B4
within declared limits; final release verification remains separate.
[Earlier native attempts](PF-020-FINAL-DENSE-CHECKPOINT.json) remain
failed historical evidence. Attempts03/04 also stop at prelaunch quiet gates;
their completed partial runs do not supply a complete five-pair packet. This
finite packet supplements the retained [ordinary Dense investigation](PF-020-ORDINARY-DENSE-PROTOCOL.md),
[targeted rechecks](PF-020-DENSE-TARGETED-RECHECK.json) and
[CPU profile](PF-020-CPU-PROFILE.json). It does not replace samples, prove a CPU
cause, supply GPU timestamps or preaccept the freeze.

## Source and package qualification

The accepted-master native baseline is unchanged qualified PF113 candidate
`a113e2bc1644fe5e7e9079b49ef67308f83eecff`; its complete native input tree must
equal accepted master `7d29c7e4d64d61dba05524d9e7f5711ffd915d90`.
Final current-seams native source `569bdb118c709dac00dc6543570d6840c88dad12`
uses qualified build07/source export07 and must equal the clean committed tool
head's complete native input tree. An original-seams binary cannot be timed as
final-current. The older Dense qualification/receipts remain unchanged.

The exact accepted-master-to-current runtime diff has15 paths,85,910 bytes and
SHA256 `d061eaf9a1b7a5915643691680e2dff2f6fc9eee36737dd3cd14f5b2c0b2db16`.
It includes observer additions and the early camera fraction guard, disabled
in these ordinary runs. Authenticate all native source, libraries, static package
inputs, CMake/attribute/vcpkg metadata and build-tool inputs. Retain complete Git
blob/mode/path identities, live raw bytes, frozen export, build/configure logs,
recipes and all eight staged/build counterparts.

The native builds have differently encoded static text packages. Verify all
five complete package/source tables, unique safe member names, paths, modes,
Git blobs, committed text attributes and authenticated index classifications.
Final members must equal frozen Git source exactly. Baseline members must equal
source or, only for authenticated text, its exact LF-to-CRLF expansion. Explicit
`text` permits actual source NUL/non-UTF8 bytes; `text=auto` additionally requires
Git `i/lf` classification and no NUL. Binary, unset, unknown, mixed/partial
projections, semantic edits, missing/extra/duplicate/aliased members and local
attribute overrides fail. Raw archives, every raw member hash/length and relation
are retained. No archive is rewritten or arbitrary binary data normalized.
This authenticated source text projection is **not a strict one-variable
byte-identical comparison**; timing cannot be attributed uniquely to callbacks.

## Fixed execution and retention

Existing pinned Dense fixture, isolated stock Doom2 IWAD and historical seed
remain fixed. Use normal startup `gl_ubershaders=true`, `gl_light_shadows=1` and
`gl_levelmesh=false`, ordinary adaptive clock,1904x1001,832 sprites and216 lights.
Retain inherited settings/camera/count/device/STOP and independently decoded
healthy PNG gates, actual queries and normal-exit configuration behavior.
Correctness observers, diagnostic cache flags, single-tic fixture clock and
Vulkan validation are disabled. Ordinary application/driver caches remain
untouched; no cold-cache claim or quality/gameplay/setting waiver is allowed.

Run exactly12 serial actual unelevated children:

```text
01 accepted-master warmup; 02 final-current warmup
03 pair1 accepted-master; 04 pair1 final-current
05 pair2 final-current;   06 pair2 accepted-master
07 pair3 accepted-master; 08 pair3 final-current
09 pair4 final-current;   10 pair4 accepted-master
11 pair5 accepted-master; 12 pair5 final-current
```

Each process supplies five raw bench blocks. Exclude its first as preregistered
warmup; retain indices1,2,3,4 for every scored child:60 raw blocks and40 scores.
No outlier removal, replacement, automatic retry or additional pair is allowed.
Record actual coordinator/child medium tokens, PID/exit and before/after Windows
events. A90-second watchdog and bounded logs/output kill and wait only for the
own child. Preserve failed packets; revisions require new paths and recorded
reasons. Before each child record at least30 and at most120 one-second
GetSystemTimes intervals. Starting after interval30, launch preparation may
finish only when the last10 maximum is strictly below15% total CPU. Retain every
observed interval, the total count and zero-based accepted-window indices.
Retain raw idle/total deltas too. Invalid intervals and sample/wait API errors
preserve all earlier readings, the offending deltas when available, and the
error stage in the failed receipt before any process creation.
Sustained load, exactly15%, fewer than ten consecutive quiet intervals, an
invalid interval or failure to reach readiness within120 intervals rejects the
child before launch. This **prelaunch** quiet check does not
guarantee in-run load. Revalidate source and the pending child's exact generated
command/config/output inventory after quiet preparation, immediately before
launch. No tests/compiler/analyzer/agent workload may compete with measurement.
Retain every score even if an in-run disturbance is suspected.

### Decision: bounded settling observation, 5 October2026

Four earlier packets preserve their fixed30-interval failures, including
attempt03 at15.5963% before pair3 and attempt04 at25.0656% before pair2's
baseline. Independent raw review confirms the completed partial observations;
none is promoted to a full packet. Later readiness and background observations
do not establish the cause of the failed windows.

Revision2 allows the existing strict ten-interval readiness condition to be
reached during one continuous observation capped at120 intervals, consistent
with the bounded preparation used for the retained targeted rechecks. It does
not change15%, shorten the required quiet window, ignore preparation readings,
retry a scored process, exclude a score, combine incomplete packets or relaunch
a failed receipt. The first eligible window after the30-interval minimum is
used. This is an explicit preparation-policy change requiring tested/reviewed
committed tools and a fresh packet, not retroactive acceptance of the old runs.
The receipt schema is version2; version1 packets cannot launch with this tool.
Source/build/input revalidation still follows preparation immediately before
process creation. No security/driver/machine setting or background process is
changed by this policy, and in-run quiet is still unproved.

## Two phases and acceptance boundary

Preparation creates fresh commands/configuration/identities without launching.
`--launch` runs only the two unscored warmups and returns
`WARMUPS_READY_FOR_AGENT_PICTURE_REVIEW`. Root inspects both actual PNGs for a
healthy fixture with query messages and benchmark overlays absent. Record
`warmup-image-review.json`, bound to the actual file/decoded pixel hashes and
same tool head. This is agent inspection evidence; no human approval is claimed.
Missing/altered review, changed images/source/input or output aliases fail before
scoring. `--launch-scored` runs only the fixed ten remaining children. No
source/tool change is allowed between phases.

Require all five paired camera/count/settings/device states and main RGB images
exactly equal at zero component tolerance. Retain all raw scores, per-run CPU
medians and signed paired/aggregate differences. Bench clocks are CPU snapshots;
All includes Finish/wait. Printed precision and preemption limit interpretation.
Report descriptive findings without invented win thresholds, causal/significance,
zero-overhead or GPU-performance claims. A valid packet returns
`PASS_EXACT_EQUIVALENCE_WITH_CPU_SNAPSHOTS`; `performanceAccepted` and
`freezeAccepted` remain false pending independent aggregate disposition and all
other [freeze gates](PF-FREEZE-MANIFEST.md).

`tools/pf_oracle/run_freeze_final_dense.py` is the adapter;
`tools/pf_oracle/tests/test_freeze_final_dense.py` supplies CPU-only controls.
Supply exact current candidate, source derivation/device files and fresh `--out`
for preparation. Launch each phase only from that preregistered output. Unit
controls never launch a renderer and are not native timing/image evidence.
