# Hosted software-Vulkan CI latency prepass — 2026-11-07

## Purpose and immutable qualification boundary

Reduce and attribute long GitHub Actions CI runs without silently weakening the SDVK-009 native process-count, source/IWAD identity, witness, state/RGB, negative-control, physical-stop or fail-stop constraints. This PR **does not** divide the three publication captures across machines, reduce 120 warmup frames, modify benchmarks, admit physical GPU performance, or permit self-hosted publication qualification.

Current baseline: accepted `master` at `9cf86b92dac3ae784eea0554d24ca18a43a3120c`. Active renderer integration PRs #162, #172 and #186 also modify `.github/workflows/continuous_integration.yml`. Reconcile workflow edits with the subsequently accepted head before merging; do not overwrite their integration safeguards.

## Observed critical path

GitHub Actions step timestamps (not independent benchmark fixtures):

| Run | Source/run date | Full CI | Software-Vulkan job | Initial Vulkan corpus | Extended acceptance | Lossless archive |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| [#532](https://github.com/techrote/ShadeDoomVK/actions/runs/41162818984) | 2026-10-31 | 105.4 min | 102.3 min | 13.6 min | 75.6 min | 5.8 min |
| [#545](https://github.com/techrote/ShadeDoomVK/actions/runs/41541895122) | 2026-11-02 | 174.5 min | 171.3 min | 19.5 min | 133.2 min | 10.0 min |
| [#558](https://github.com/techrote/ShadeDoomVK/actions/runs/42217798651) | 2026-11-06 | 175.8 min | 172.8 min | 19.4 min | 136.4 min | 8.5 min |

On #558 the last phase included these timestamped publication processes: `compositing-control` approximately 0.15 min; `shadow-control` approximately 41.0 min; `shadow-witness-1` approximately 41.25 min; `shadow-witness-2` approximately 43.43 min. The three long captures therefore dominate CI. Do **not** describe the difference from #532 as a software regression until matched source, Mesa version, allowed cores, CPU quota, runner image and actual workload are controlled.

## Changes introduced by this prepass

1. Split the existing **single serial acceptance shell step** into named serial Actions steps for SDVK-010, SDVK-150, SDVK-153, SDVK-158 and SDVK-009. All unchanged command arguments, ordering, software ICD selection, unique fresh output directories and default fail-fast dependencies remain required. Export `VK_DRIVER_FILES`, `VK_ICD_FILENAMES` and `SDL_VIDEODRIVER` between steps through `GITHUB_ENV`. Earlier failure still prevents subsequent captures.
2. Add `tools/ci/renderer_ci_timings.py` to read the original SDVK-009 `steps/*.json` attempt receipts; publish accurate per-process seconds and a platform/CPU-affinity/cgroup snapshot in `renderer-ci-timings/report.json` and the Actions job summary. It is *read-only* and its results never grant an acceptance waiver. Run focused Python unit tests as part of `pf_oracle`.
3. Retain `renderer-software-vulkan.tar.xz` **and the existing artifact name** but replace CPU-heavy serial `XZ_OPT=-6 --lzma2=dict=64MiB` with lossless multi-threaded `XZ_OPT=-1 -T0`. Check the XZ stream, its tar member listing and a SHA-256 archive manifest before upload. Both original evidence and new timing JSON are included in the tar. The archive may grow; compare upload duration and artifact size with the baseline before claiming a net win.

No parallelisation, host migration, warmup reduction, reduced sample counts, test skipping, or benchmark result reclassification is included.

## Acceptance and follow-up

- Focused report unit tests pass; standard CPU oracle, Windows/Linux/macOS and native Vulkan workflows complete at the exact submitted PR head.
- Confirm publication outputs and witness comparisons are unchanged in count, required names, IDs, same-process/different-process constraints, hashes, licence and negative-control coverage. Retain all failures and terminate exactly as before.
- Measure both XZ packaging+upload wall time and final artifact size. If the faster preset is net worse or causes memory pressure, restore the original options, then consider a separately reviewed Zstandard format migration with documented consumers.
- Require at least three source-matched successful full runs before claiming stable improvement; record variance. Profile llvmpipe per-frame CPU/wall-time, CPU quota and driver versions before deciding whether the 31 Oct vs 6 Nov difference is a genuine engine regression.
- Consider sharding only in a later independent protocol review, since the current publication gate intentionally stops after the first failed native capture.

## Future large-core Xeon benchmarking (NOT part of qualification)

A 128 GB quad-channel Xeon v3 machine could provide strong CPU-lane parallel throughput, particularly if llvmpipe scales on its available physical cores. It is **not automatically faster**: an older Haswell core is slower than many modern runner cores, high thread counts can contend for cache/bandwidth, and these llvmpipe state-capture workloads can have serial and synchronization phases. Run a controlled sweep of `LP_NUM_THREADS` and simultaneous process count after thermal and memory stability are established, using exactly the same source/runner image/Mesa/IWAD and canonical process plans where possible. Do not change process contents or compare physical GPU acceptance against CPU software evidence.

The existing `hosted_software_guard()` explicitly requires `RUNNER_ENVIRONMENT=github-hosted`; the separate SDVK-010 guard and source/driver predicates also apply. **Do not weaken this guard or register the personal machine as a runner for untrusted public PR workflows.** GitHub warns that public-repository self-hosted runners can be persistently compromised. A potential future trusted, explicitly labelled and isolated **non-acceptance performance research** workflow should run only approved code after manual authorization, with no GitHub write token or local network/credential exposure, and must not claim to replace the existing publication gate without an independently reviewed new acceptance policy.
