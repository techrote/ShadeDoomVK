# SDVK-014 — Bounded GPU timing evidence and authorisation boundary (PR #202)

**Status:** bounded measurement-enablement increment only. Parent [SDVK-014 (#14)](https://github.com/techrote/ShadeDoomVK/issues/14) stays open. Physical STOP remains active.

## Owner decision (14 November 2026)

The owner explicitly authorised repairing two diagnostic problems in PR #202, recording this evidence/authorisation boundary, qualifying the corrected head and merging **as a bounded measurement-enablement increment only**. This instruction does **not** authorise additional physical GPU runs, waive the physical STOP, accept representative performance/scaling/stability, close #14, or retroactively establish separate authorisation for previously reported physical activity. Future physical execution requires separate explicit approval under the existing safety gate.

## Historical physical report (no new physical run)

The PR author reports a bounded session using a GTX 1650 SUPER at its configured **100 W** limit, with shadow maps and hardware ray queries disabled. The reported hardware runtime source was commit **85585874318e79f95ccd5beba70d0c5945567f92**, parent master **0ecba708e283e33c381fae329ace7a2cedc6a3f3**. The second PR commit, **e201bb10fe0fe47fb21720dbf20c6cea3c628db2**, changed only extracted test fixtures; its runtime source matches the physical-test revision. The subsequent diagnostic fix is a *different* runtime-source revision and cannot inherit an assertion of physical retest.

| Reported Vulkan GPU interval | Milliseconds |
| --- | ---: |
| 12-tile bake (median) | 1.188 |
| Two-page atlas, first six-tile invalidation | 2.01 |
| Two-page atlas, second six-tile invalidation | 3.59 |
| Same-map reload lightmap tile work | 0.90 |
| Probe rebuild (60 intervals, median) | 26.81 |
| Probe rebuild range | 22.71–32.96 |

The PR reports nine fenced physical processes; three bakes with PWADs byte-identical to prior master; five complete probe passes per map owner; three mutually matching image captures for each runtime fixture; peak sampled temperature 36 °C; and no new GPU fault in that bounded session.

**Author-reported local raw evidence path:** physical-evidence/sdvk014-master-0ecba708/gpu-costs-06. Raw logs, machine telemetry, run commands, captures and a cryptographic evidence manifest are **not available as reviewer-accessible GitHub artifacts** for these measurements. The numbers here are historical, *author-reported descriptive fixture results*, not independently reproduced physical qualification. Do not treat this local path as a hosted artifact or assign invented hashes.

## Accepted scope of the code increment (subject to exact-head CI)

- Opt-in command-line mode: vktool lightmap build [options] -sdvkobservegpu.
- Vulkan timestamp grouping for lightmap tile work and per-probe render/convolution/per-probe-copy work. The published probe family and broader lifecycle lie outside the measured interval.
- Completed near-capacity timestamp ownership: reserve closing timestamps for active groups; never pop failed inner pushes.
- Bounded unsupported-GPU diagnostic when no timestamp query can be allocated, without generating per-idle-frame noise.
- Exact-head source/CPU and existing hosted software-Vulkan CI qualify **this code revision** separately from the earlier physical measurements.

## Not accepted / retained gates

No representative GPU benchmark, multi-configuration or scaling conclusion, long-term hardware stability claim, historical physical-fault root cause or full SDVK-014 qualification is established. Nested timings are not additive and GPU intervals omit CPU setup and subsequent lifecycle work as applicable. **Physical STOP: ACTIVE. Physical GPU cost/scaling/stability: HELD / NOT ACCEPTED. SDVK-014: OPEN.**

Sources: [PR #202](https://github.com/techrote/ShadeDoomVK/pull/202) and [issue #14](https://github.com/techrote/ShadeDoomVK/issues/14).
