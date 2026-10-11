# SDVK-009 physical campaign — 11 October 2026

**FAILED / stopped; architecture INCONCLUSIVE; #9 remains OPEN.** This is retained
physical evidence, not acceptance or a completed benchmark. The independently
built clean renderer is `0a2fbad203549d18ac6e5a61bb4747709637bfde`, tree
`b4824f4498f0f5ac64bc61d9dc60d334f30c4840`, executable SHA-256
`10e61cf536b0b67b5396121606a6b3be8cb943a7d70d5fb2d93604b361e53fb0`.
The separately pinned Windows harness is `b075b9e32ad734a2450a89b1b8eeec3cbfe7650f`.

The actual Vulkan device was NVIDIA GeForce GTX 1650 SUPER, discrete type 2,
vendor/device `10de:2187`, PCI `00000000:07:00.0`, Windows driver 616.92. Host:
Ryzen 5 2600X, ASUS TUF B450M-PRO GAMING, 32 GiB, Windows 11 Pro build 26200,
1920×1080 desktop. MSVC 19.44.35228 / VS 2022, x64 RelWithDebInfo; Vulkan loader
1.4.341, device API 1.4.351. Freedoom2 0.13.0 was the lawful compatible IWAD.
The existing 90 W power limit was preserved; no clock, voltage, driver or BIOS
settings changed. Maximum observed temperature was 52°C, below the 80°C stop.

## Retained results

| Stage | Planned | Completed | Outcome |
|---|---:|---:|---|
| 640×480 reference captures | 20 | 12 | Six independent pairs passed exact RGB and protected state |
| Next reference process | 1 | 0 | First `shadow-boundary` process faulted and hung |
| 1904×1001 correctness captures | 6 | 0 | Not reached |
| Timing processes | 15 | 0 | Not reached |

The six passing pairs are compositing, lights-zero, lights-one, lights-many,
lights-dense-overlap and lights-dense-dispersed. Their actual state-mode light
counts/uploads and comparison hashes are in
[correctness-work-counts.json](evidence/sdvk009-physical-20261011/correctness-work-counts.json).
They do not establish full PF fixture coverage or high-resolution scaling.

The thirteenth renderer emitted Vulkan `[fault] type=4` address records and became
unresponsive. Windows recorded nvlddmkm event 153 at `2026-10-11T00:45:41.9748864Z`.
The operator verified its executable path and terminated only that renderer;
the retained native exit code therefore records forced termination. The driver
stopped with no retry. Raw stdout, event XML, configuration, process receipts,
supervisor telemetry, images, state and hashes remain retained.

Fault type 4 means an unknown instruction pointer; it does not identify a unique
shader, invalid read/write, causal resource or driver defect. Root cause remains
**UNDETERMINED**. Further physical launches on this host are stopped pending
offline diagnosis and an independently qualified repair/new experiment. SDVK-008
and SDVK-010 hardware work was not launched after this failure.

CPU/GPU scaling, thresholds and quality/performance decisions are **UNMEASURED**.
No architecture trigger can be evaluated. The inherited truncated tile path and
PF-017 rejected reuse candidate remain rejected.

Offline CPU graph tests separately reproduced a single-instance TLAS root
export defect. Its bounded repair and the outstanding sparse-geometry audit
observations are recorded in [the collision audit](SDVK-009-COLLISION-ROOT-AUDIT.md).
The failed packet does not establish that it exercised this edge case. The
repair is a new source candidate, not proof that the device fault is resolved;
the hardware stop remains active.

## Tooling correction and future measurement identity

The Windows CRT emits CRLF in `--version`; identity parsing now accepts logical
lines while preserving the original bytes. The harness pins executable, IWAD and
renderer packages before launch and enforces campaign-wide identity continuity.

Source audit also found no light-sensitive ordinary-scene timestamp group in the
frozen renderer. Postprocess/lightmapper groups cannot establish many-light GPU
scaling. The separately identified opt-in `scene.immediate` candidate is described
in [the instrumentation contract](SDVK-009-SCENE-GPU-INSTRUMENTATION.md).
It has **not** been physically measured. A future campaign must preregister its
exact new renderer/source/tree/package identity and rerun required gates; it must
not relabel this frozen packet or resume it as a successful experiment.

## Evidence and acceptance boundary

[Machine-readable receipt](evidence/sdvk009-physical-20261011/receipt.json) and
[build manifest](evidence/sdvk009-physical-20261011/build-manifest.json) publish
bounded summaries. The full 263-file packet is stored locally at
`C:\ShadeDoomVK\physical-evidence\20261011\SDVK009\gtx1650super\frozen-v1`.
Its sealed archive `C:\ShadeDoomVK\physical-evidence\20261011\sdvk009-frozen-v1-raw.zip`
is 219,768,756 bytes, SHA-256
`0ec83ad4026b870f00ae753703eb2a7fba0be257ca65ff2df74f931c040fe10b`.
The raw manifest SHA-256 is
`3bdcc96ad00a3f2a6672c0fa71acbc316cb233e74094810b9d0147df82944418`.
Additional host/build preflight logs are retained in the adjacent `preflight`
directory. Durable remote raw storage is unavailable; no remote retention claim
is made. IWAD bytes and the large archive are outside Git.

#8, #9 and #10 remain open. #11/#14 require accepted #9/#10; #12 requires accepted
#8/#9. No downstream gate is unblocked by partial captures or tooling CI.

## Separate post-restart diagnostic: failed, stop reinstated

After an explicit user restart/resume request, a new experiment was preregistered
in [issue #9](https://github.com/techrote/ShadeDoomVK/issues/9#issuecomment-6108365501).
The original frozen experiment above remains sealed and unchanged. New clean
source `a7c5df6f7a3c529cb2d8f659dade79f45e2dfdaa`, tree
`377665a654ca0d491a4671ce1eb7df7b5ff52aa4`, was independently built with the same
MSVC x64 RelWithDebInfo toolchain. Exact-master source run `38112316172` and full
CI `38112316182` passed; full CI was 9/9. The executable SHA-256 is
`4a10cf525a5e65e60c035f4f7270a708bf659e64bf5faad9fb920fd0a1475531`.

This source includes the two CPU-proven collision repairs, accepted height/TBN
changes, implemented opt-in POM and actor probes, and opt-in scene timestamps.
It is not a same-build comparison with the original baseline. CPU fixture checks
preserve original compositing, shadow-boundary and all five performance PK3s;
three updated compatibility fixtures and sprite-mirror settings are explicitly
enumerated in the preregistration. The reboot reset the previous 90 W limit to
100 W. Restoring it was denied to the agent by Windows permissions; the user
restored 90 W from Administrator PowerShell, and actual readback was verified
before any scene launch. No clock, voltage, BIOS or driver changes were made.

The bounded diagnostic planned one compositing capture followed by two
shadow-boundary captures, each 640x480, 120 warmup frames and one retained frame.
Compositing completed and validated the expected source and actual Vulkan GPU.
The first shadow-boundary capture again emitted type-4 fault records during
warmup. The strict monitor stopped the experiment and verified executable path,
SHA-256 and collector parent before terminating only renderer PID 13676. The
collector finalized failed process/diagnostic receipts. No renderer remained.
Maximum observed temperature was 50 C at 90 W; NVIDIA event 153, System record
7671, occurred at `2026-10-11T11:08:48.1048128Z`.

The second shadow capture, full 41-process campaign, all timing, SDVK-008 and
SDVK-010 launches were not reached. There was no retry or relaxed workload.
The independently reviewed monitor rejects malformed/missing event evidence,
nonfinite/80 C temperatures, power changes, device/driver changes and new driver
events. A stop latch blocks every subsequent capture and executable spawn;
driver-event baseline continuity crosses diagnostic/campaign stage boundaries.
Nine CPU guard tests and a deliberate changed-baseline negative passed before
launch. An initial failed guard test and failed PowerShell event-module probe
are retained alongside their verified replacements. Monitoring uses bounded
polling, not instantaneous detection.

**FAILED_DEVICE_FAULT; hardware STOP reinstated.** Restart and the two source
repairs did not prevent this separate physical failure. They do not establish
fault causality or resolution. Root cause remains undetermined; scaling is
unmeasured and architecture inconclusive. Known null-BLAS source hazards remain
separate offline investigation inputs, not proven conditions of this capture.

[Machine-readable report](evidence/sdvk009-reboot-v2-20261011.json) pins the new
132-file local packet, runtime/debug symbols, raw diagnostics, preflight and
operator tools. Archive `C:/ShadeDoomVK/physical-evidence/20261011/post-reboot-v2-raw.zip`
is 107,689,274 bytes, SHA-256
`4369b0d3e35b445df1434d249325a830bf3c109555d676222946c487442f0b55`;
manifest SHA-256
`cc4a2795287b2b25c77b649063074de3e0a37c394d49c3ad91c75357e0f50d6e`.
Durable external raw storage remains unavailable. No acceptance or dependent
gate changes follow, and no further physical launch is authorized by this report.
