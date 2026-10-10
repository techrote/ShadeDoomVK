# SDVK-008 — preregistered **future** physical-GPU packet (draft v1)

**Status: design only; not executed, not an acceptance receipt.** Source pin is prepass `master@cbff1d10b802e60a56d239338f810f7e1e52920d`. Execution requires accepted SDVK-007 and a separately qualified production SDVK-008 candidate. This document fixes the measurement *procedure*; future accepted #8 code/build identities and fixture hashes must be filled before the first launch and cannot be substituted mid-packet.

## Synchronization with #9 without evidence contamination

Reuse SDVK-009's `tools/renderer_oracle/run.py` preparation, capture/compare, benchmark, process isolation, device checks, and its physical driver **as written for #9**. Both sessions may share a physical workstation, display state, operator, thermals/caches logging and GPU. They must retain separate process directories, manifests, correctness gates, measured outcomes and issue decisions. **The current #9 protocol pins its own exact accepted source/build.** A later #8 build is NOT automatically the same source and must not be treated as an identical-build #9 packet. Either run #9 on its own frozen accepted build and #8 on its distinct post-#7 frozen build during the same session, or formally preregister a revised #9 source pin *before* execution; never merge or relabel datasets after the fact.

Do not execute `native_ci.py` for physical timing: it is the llvmpipe lane. The existing `sdvk009_physical.py` is a #9-only driver; **a dedicated #8 wrapper does not yet exist**. Assemble this packet by reusing documented `run.py capture`, `run.py compare`, `run.py benchmark` semantics in a future #8-owned driver and verify the command line against its final commit. No code in this prepass launches GPU runs.

## Frozen environment and resource locks

Required minimum: one verified physical Turing-class Vulkan GPU, preferably GTX 1650 SUPER for continuity with PF-016/017 and #9. Quadro RTX 4000 or TITAN RTX are optional *separate device strata*. Record PCI/device ID and `VkPhysicalDeviceType` (1/2 only), vendor, VRAM, driver/Vulkan loader versions, Windows/Linux build, display dimensions/refresh/foreground status, power limit/clocks, thermal throttling, validation-layer status and any OS events. Do **not** pool devices, mixed driver versions or differing builds. No concurrent render workload or competing game process.

Pin accepted SDVK-007 commit/tree and SDVK-008 test candidate commit/tree; executable SHA-256, `--version`, compiler/flags, runtime/PACKAGE/IWAD files and hashes, shader binary/source hashes, PF-009 orientation source, material/height/normal/PBR asset hashes, `prepared.json`, effective CVars, observer mode, exact fixed camera(s) and build clean status. Require identical build, package, source and content between matched OFF/ON captures, other than the single declared relief-work setting; any material change invalidates comparison.

## Authored finite workload matrix

Extend the accepted `sprite-mirror` corpus for 640×480 state/image qualification with rotated frames, actor X/Y flips, line mirror, portal mirror where directly reproducible, face/Y, face/XY, face-camera, wall/flat, roll/pitch, asymmetric PBR/normal+height, heightless controls, alpha holes, thin features and nearest albedo/filtered height. Reuse its accepted maps/scripts rather than invent an unpinned separate scene family. The inherited PF linked-portal fixture retains its own fixed-fraction/IWAD contract; do not relabel it as native #8 evidence. All added generated package bytes and test identities must be pinned.

**Correctness:** two fresh independent native `state` + RGB8 image captures at canonical **640×480**, at minimum for: no-height baseline, height-present/OFF, height-present/zero-scale, low/medium/high single-card, alpha holes/edge escape, pixel-crisp mixed sampling, normal+PBR+height, mirrored/rotated controls, and unsupported/grazing fallback. Compare paired state and same-device exact-image outputs; inspect direction-aware image witnesses as well as the proposed machine invariants. Pair an additional 1904×1001 state/image capture twice for each distinct *timing scene* below, establishing identical draw counts/UV/source and shader selection before timing. If pixel variability on valid hardware requires the accepted SDVK-002 tolerant image policy, preregister that variant *before* running; do not weaken an exact failed comparison post hoc.

**Timing variants** (capital letters are independent scene/work identities):

| Variant | Coverage | Work |
| --- | --- | --- |
| S0 / SL / SM / SH | one projected-large sprite, same fixed camera | OFF / 8+1 / 12+2 / 20+2 |
| M0 / MM / MH | multiple overlapping qualified sprite cards, same camera | OFF / 12+2 / 20+2 |
| G0 / GH | oblique/grazing distribution (including declared fallback angles) | OFF / 20+2 |
| P0 / PM | PBR + directional normal + filtered height with nearest albedo | OFF / 12+2 |

Pixel-art alias/alpha-edge and frame/line/portal-mirror tests are **required correctness cases**, not inferred from these timing variants. The named step levels are research budgets, not SDVK-016 quality-tier promises. Light counts remain constant within each matched pair; do not blend in SDVK-009 many-light architectural changes as a performance variable.

## Measured process procedure (identical to #9 where applicable)

- Capture extent **1904×1001**, camera fixed, same shader/material/height assets; record physical extent/readback.
- For each timing variant: **three independent fresh serial processes**, each with isolated writable config/saves, output and application pipeline/shader caches. Archive before/after cache hashes. Do not clear or pretend to control the OS/driver shader cache.
- Warm up **120 rendered frames** in each process; retain the following **120 consecutive timing frames**, with raw samples (no outlier removal or automatic retry). `state` runs remain independently collected and must not be counted as timing samples.
- Preregister this 11-variant counterbalanced order:
  - repetition 1: `S0,SL,SM,SH,M0,MM,MH,G0,GH,P0,PM`;
  - repetition 2: `PM,P0,GH,G0,MH,MM,M0,SH,SM,SL,S0`;
  - repetition 3: `MM,G0,SL,P0,MH,S0,PM,SM,GH,M0,SH`.
- No overlapping processes, no automatic retries. Timeout or device loss is a retained FAILED packet; any replacement is a new explicitly identified run, not an invisible replacement.

## Metrics, analysis and decision rules

Retain **all** 120 raw samples per process: CPU `cpu_render_view_ms`, separate preexisting CPU groups, each independently resolved *non-nested* GPU timestamp group (never sum nested groups), draw/coverage/overdraw evidence, sprite count, affected screen pixels where instrumentable, height/normal/PBR descriptor state, actual algorithm/work bounds, fallback/grazing counts and cache/clock/temperature state. Default timing must not include per-fragment atomic counters; if debugging requires exact samples it is a distinct instrumented correctness stratum, never the timing variant. A work upper bound is not an observed GPU shader invocation count.

Primary comparison: within each process repetition, subtract the matched OFF median (`SL/SM/SH - S0`, `MM/MH - M0`, `GH - G0`, `PM - P0`) separately for CPU and each available named GPU group. Report differences **in milliseconds** and ON/OFF ratios, per repetition and median across three, with p50/p90/p95/p99 calculated from each original 120-frame series using SDVK-002's `(n-1)*p/100` interpolation. Preserve raw data and median absolute deviation (MAD) across the three process medians. The measurement is **inconclusive** for an affected group if its OFF per-process medians vary by more than **5% of their median** (max deviation), or an observed OS/device anomaly affects it. This is a variability gate, not permission to delete outliers. A directional effect is provisionally detectable only if ON–OFF has the same sign in ≥2/3 matched repetitions and its absolute three-repetition median exceeds `max(0.05 ms, 2 × OFF-process-median MAD)`. Otherwise label the difference below the preregistered detection limit; do not claim zero cost.

Inspect sample/work scaling by screen coverage, angle, 8/12/20 traversal caps, optional fixed 1/2 refinements, normal/PBR path and overlap, not CPU-reported mean FPS alone. A candidate is **not accepted** solely for meeting a speed threshold; correctness, boundedness, old-content equivalence, visibly useful relief, diagnostics and source acceptance still govern #8. If an effect is unacceptable, record measured trade-offs before choosing any final setting; #16 owns final user tiers/defaults. GPU groups absent from a device are reported unavailable with reason; do not fabricate them or re-label CPU timings as GPU.

## Abort conditions and final record

Fail closed for output/state mismatch, nonfinite/UV/alpha escape, silhouette/gameplay delta, unexpected material/basis/mirror divergence, >23 sampled-height evaluations in diagnostic evidence, altered no-height path, lost physical-GPU identity, invalid cache/build hashes, correlated failure, validation error, resource exhaustion or driver/device reset. Do not continue a failed correctness packet to performance acceptance. Record failed packet hashes/reasons. End with separate `sdvk008-physical-campaign.json` and the #9 receipt (if run) plus raw manifest; `physical_gpu_evidence_collected=true` is **not** equivalent to acceptance.


## Post-implementation qualification source pin — 10 October 2026

The research starting SHA earlier in this document remains **historical prepass provenance**, not the physical-test build. The actual default-OFF production POM candidate is merged from PR #138 at **`master@9536324ce33ea418af5a8efe733b4659f6b4ad9b`**. Its SHA-256-verifiable source-evidence archive, ABI and shader code were qualified at head `6c0d418e82f34de89084b4175d8aafe0bc024e71`. Both revisions have **identical tree `3123bc7fd3dd9074487cbe3487f9336ef3589003`**. The integrated tree includes accepted SDVK-010 probe semantics and the SDVK-008 relief implementation together.

For the first hardware campaign, choose this immutable **merged source tree** as the implementation authority; if `master` advances or a hotfix changes shaders, declare a **new packet identity before measurement**, rather than silently treating a newer executable as the same build. Pin target physical device, Vulkan loader/driver, executable/source/package hashes, authored map/texture assets, all console readbacks, and the 11 variant manifest as stipulated above. The original 120+120 frame timing procedure and abort criteria remain unchanged.

A working **SDVK-008-specific physical campaign driver has not yet been accepted**. The archived `sdvk009_physical.py` is for SDVK-009 only and must not be misrepresented as an executed or compatible #8 measurement. The physical operator must first prepare or explicitly qualify a dedicated wrapper using documented `run.py` capture/compare/benchmark APIs. Until its frozen build/content manifests and finite-run correctness/ON–OFF timings are successfully retained, `physical_gpu_evidence_collected=false` and issue #8 remains open. No production quality-tier or physical-GPU cost assertions are established by hosted llvmpipe CI.
