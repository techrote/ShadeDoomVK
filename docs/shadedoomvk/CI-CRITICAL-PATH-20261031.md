# CI critical-path qualification — 31 October 2026

**Status:** Draft-only low-risk optimisation, not approved for merge or physical execution. Starting master: 2f7681e749f6e6a8560bb7b831857d356b99193d.

## Measured original hosted-runner baseline

Normal required GitHub-hosted runs (not synthetic runner comparisons):

| Run | Software-Vulkan job | End-to-end | Result |
| --- | ---: | ---: | --- |
| [39102861031](https://github.com/techrote/ShadeDoomVK/actions/runs/39102861031) | 170.9 min | 173.8 min | Nine CI jobs passed |
| [39094461177](https://github.com/techrote/ShadeDoomVK/actions/runs/39094461177) | 175.4 min | 179.8 min | Nine CI jobs passed |
| [39107722480](https://github.com/techrote/ShadeDoomVK/actions/runs/39107722480) | 171.8 min | 179.4 min | Nine CI jobs passed |

In run 39102861031: native compilation took 7.1 min, inherited renderer corpus/SDVK-008 qualification 19.1 min, combined actor/publication qualification 136.1 min, and lossless xz packaging 7.6 min. The largest individual publication processes were the shadow control (about 41 min), witness 1 (about 41 min), and witness 2 (about 43 min). The older 31-minute Avrea self-hosted result is NOT a comparable GitHub-hosted baseline.

## Changes deliberately limited to this draft

- Overlap OS package installation with the existing SHA-256-authenticated ZMusic fetch/extraction. The package trees are disjoint. Both child statuses are joined, both logs printed, and either failure stops the build.
- Permit up to four compile jobs **only** for the existing Ubuntu-24.04 native software-Vulkan configuration when at least four CPUs are visible. Keep parallelism 3 for the other seven configurations.
- Preserve the original single renderer-software-vulkan.tar.xz artifact, all nine included directory names, exact unfiltered raw members, 30-day retention, xz level 6 and 64 MiB dictionary, and the downstream tar -xJf interface. Use two xz compression threads. The compressed archive bytes/size can change; extracted files must not.
- Publish a **read-only** per-original-process timing summary derived from existing immutable publication step receipts. This does not generate, omit, retry or reorder a capture.
- Add nine synthetic CPU-only regression tests covering actual concurrent startup, independent failure propagation, Windows no-op, archive extraction and SHA-256 round-trip, partial-failure retention, unmodified timing receipts and malformed timestamp rejection.

There are no intended changes to renderer, authored fixture, capture settings, timeouts, evidence thresholds, process ordering, fail-stop behavior, required nine CI jobs or software/physical acceptance status. Original full hosted-CI coverage is still mandatory.

## The highest-value follow-up is publication sharding

This low-risk draft cannot eliminate the serial ~125-minute shadow capture sequence. Do not shorten or omit any of the four preregistered captures. The existing collector intentionally requires a passing control before either witness and compares exact build, device, source, workload, state and image identities.

Any future sharding PR must first prove: (1) one immutable exact-source build transferred with authenticated binary/package bytes; (2) safe control-before-witness gating with zero retries and preserved failed packets; (3) actual llvmpipe device/driver equivalence on each GitHub-hosted runner; (4) distinct real native processes and immutable separate raw artifacts; (5) the original compare_control, compare_runs, validate_witness and negative-control adjudication, with no relaxed thresholds or rewriting original packets; (6) negative tests for mismatched device, source, fixtures, omitted frames, failed control, duplicate packet and timeout; (7) preservation of the original required software-Vulkan check rather than a build-only green replacement.

Only after exact-head, complete, normal CI can the high-value sharding runtime be estimated fairly. No benchmark-only runner duplication. Physical STOP remains active; hosted software-Vulkan results do not establish physical-GPU performance, health or architecture acceptance.

## Review/merge boundary

This draft needs independent source review, exact-head nine-job qualification, and a lossless archive equivalence assessment before it could be considered acceptable. Keep as draft, retain all failures and original evidence, and do not merge without explicit owner approval.
