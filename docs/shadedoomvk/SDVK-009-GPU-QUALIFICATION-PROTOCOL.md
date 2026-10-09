# SDVK-009 — physical-GPU qualification protocol

Status: **required later evidence; not executed by the non-physical-GPU phase**.

## Decision being tested

The off-GPU phase leaves one production-correct candidate: the unchanged PF many-light architecture plus SDVK-009's correctness-only upload boundary repair and state diagnostics. Physical testing decides whether that architecture remains adequate under matched sparse→dense workloads. No tiled/clustered prototype is permitted into this campaign unless a later repository revision first passes the same off-GPU semantic gates and receives a new preregistered variant section.

## Exact source/build identity

Before the first launch, record:

- exact accepted SDVK-009 preparation merge commit and tree;
- `ShadeDoomVK --version` output, clean/modified flag and executable SHA-256;
- compiler/toolchain, configuration and optimization flags;
- Vulkan loader/runtime, physical device, driver and OS identity;
- runtime package hashes and the isolated IWAD hash;
- generated scene/config/script SHA-256 values from `prepared.json`;
- all requested/read-back renderer settings.

Do not substitute a different source revision after profiling starts. Any source change invalidates the campaign and requires a new packet.

## Required workloads and fixed settings

Use the generated renderer-oracle scenes with their exact fixed cameras and scene-authored settings:

1. `lights-zero` — fixed lower bound;
2. `lights-one` — accepted timing/control workload;
3. `lights-many` — 64-light ordinary dense control;
4. `lights-dense-dispersed` — 256 mixed static point/spot normal/additive/subtractive lights;
5. `lights-dense-overlap` — same 256-light profile concentrated for worst overlap;
6. `shadow-boundary` — correctness-only 1,025-candidate / 1,024-selected shadow boundary; do not use it as the main many-light timing comparator.

The accepted corpus reference extent remains **640x480**. First run the full ten-scene paired state/image corpus at that authored extent on the exact physical build so portals, materials, sprites, probes and shadows remain covered. PF-016 retained model evidence remains authoritative; do not add an unpinned third-party model during measurement.

The architecture timing campaign uses **1904x1001**, matching the representative PF-016/PF-017 physical extent closely enough to preserve historical continuity and avoiding a GPU-scaling decision based only on the CI-friendly 640x480 reference. `tools/renderer_oracle/run.py capture --extent 1904x1001` records the override in the reproduction profile, rewrites only the prepared `-width`/`-height` launch values and validates the actual observed extent. Before timing, collect and exact-compare two 1904x1001 state/image captures for `lights-many`, `lights-dense-dispersed` and `lights-dense-overlap`; those high-resolution state packets are the timing-workload selected/upload-count authority.

For the dense timing scenes, keep shadows disabled exactly as authored so light-list/shader scaling is not confounded by shadow-map selection. Do not lower light count, resolution, precision, material quality or effects selectively between runs.

## Cache, warmup and run order

For each independent timing process:

- use the preregistered **1904x1001** extent override for every zero/one/many/dispersed/overlap timing process;
- start from the same preregistered application pipeline/shader-cache policy;
- archive before/after cache identities;
- use a fresh process and isolated output directory;
- warm up **120 rendered frames** before retaining timing samples;
- retain **120 consecutive timing frames** per process;
- no automatic retry. A failed run stays in the packet and a replacement is an explicitly additional run.

Use three serial repetitions per timing workload with this deterministic Latin-style order to reduce monotonic host drift:

- repetition 1: zero → one → many → dispersed → overlap;
- repetition 2: overlap → dispersed → many → one → zero;
- repetition 3: many → zero → overlap → one → dispersed.

No two game instances or builds may overlap. Record foreground/display state, thermal/clock/power anomalies, device loss and OS driver events when the established PF harness supports them.

## Raw evidence to retain

For every timing process retain the complete raw per-frame distributions; do not replace them with average FPS.

Required CPU fields:

- SDVK observer `cpu_render_view_ms` per frame;
- established CheckBench/renderer CPU groups where available, especially setup and whole-frame clocks;
- process elapsed/warmup metadata.

Required GPU fields:

- every resolved named GPU timestamp group emitted by the existing observer;
- raw per-frame samples for each group;
- do **not** sum nested groups into a fabricated whole-frame GPU duration.

Required workload/state fields from paired state captures:

- authored/active/spot/additive/subtractive lights;
- actor queries/candidates/selected/filtered/duplicates/traces;
- wall/flat considered/rendered counters;
- upload range/record counts, bytes, capacity failures, peak and histogram;
- draw/sprite/wall/flat/portal counts;
- shadow candidate/selected/dropped state where applicable;
- exact semantic state comparison and same-device exact RGB image comparison.

## Correctness stop conditions

Stop the timing decision and retain the failure if any of these occur:

- state comparison failure or same-device exact-image mismatch on a static matched scene;
- any dynamic-light upload failure/capacity fallback;
- authored/candidate/selected counts change unexpectedly between matched repetitions;
- portal/group, occlusion, point/spot, additive/subtractive or shadow evidence disagrees;
- device loss/reset, validation error attributable to the build, timeout, corrupt packet or build/content identity mismatch.

Do not waive a correctness failure because timing looks favorable.

## Decision thresholds

This campaign is a **no-change confirmation**, not an optimization A/B. The current architecture is accepted for SDVK-009 only if all correctness gates pass and its dense scaling does not demonstrate a material architecture problem on the representative device.

For each repetition, derive `work_ratio` from the matched 1904x1001 state evidence as `overlap uploaded_records / many uploaded_records`; if actor-selected records are the dominant changing path, retain that ratio alongside the upload ratio rather than silently substituting it. A zero denominator is a failed/ill-formed comparison, not an infinite-performance result.

Use these preregistered triggers:

- **CPU architecture trigger:** compute `cpu_ratio = overlap median cpu_render_view_ms / many median cpu_render_view_ms`, then `cpu_normalized = cpu_ratio / work_ratio`. Trigger when `cpu_normalized > 1.20` in at least two of three repetitions. Apply the same normalized rule separately to any established light/setup CPU group; do not compare an unnormalized timing multiplier with a fourfold light-count multiplier.
- **GPU architecture trigger:** for each non-nested light-sensitive resolved GPU group, compute `gpu_ratio / work_ratio`; trigger when this normalized ratio is `>1.20` in at least two of three repetitions. Do not sum nested groups.
- **Practical dense-overlap trigger:** at the preregistered **1904x1001** extent, median observed render CPU time or a non-nested light-sensitive GPU group exceeds **16.67 ms** on `lights-dense-overlap` in at least two of three repetitions while `lights-many` is below that threshold. This is a research-reopen trigger for the representative device, not a universal 60-fps product guarantee.
- **Dispersal diagnostic:** compare `lights-dense-dispersed` against overlap using the same normalized work ratios. If their selected/upload record counts differ materially, interpret timing through those counts; do not attribute a timing delta to tile locality without evidence.

A single threshold crossing does not authorize silently enabling inherited tiles. It changes the #9 disposition from provisional no-change to **architecture research required**, with the semantic-substrate blockers in the non-GPU report remaining mandatory inputs.

If no trigger fires, all correctness checks pass, and raw repetitions are internally coherent, record final **no-change accepted for the measured representative device/workloads**. Do not generalize to untested GPUs, resolutions or arbitrary content.

## Operator campaign command

The hardware operator does not use `native_ci.py`; that driver is intentionally llvmpipe-only and rejects a discrete physical GPU. SDVK-009 provides a dedicated physical campaign driver that reuses the same prepared fixtures, capture receipts, state/image comparison and timing summarization without software-Vulkan preflight assumptions.

Run exactly:

```text
python3 tools/renderer_oracle/sdvk009_physical.py --exe <EXE> --iwad <IWAD> --out <FRESH_CAMPAIGN_OUT> --execute
```

The driver creates the preparation itself and then, with **no automatic retries**:

1. runs two 640x480 state/image captures plus exact comparison for all ten hosted scenes (20 processes);
2. runs two 1904x1001 state/image captures plus exact comparison for `lights-many`, `lights-dense-dispersed` and `lights-dense-overlap` (6 processes);
3. only after all correctness comparisons pass, runs the preregistered three-repetition Latin timing order at 1904x1001 for zero/one/many/dispersed/overlap (15 processes);
4. writes one three-process timing summary per timing scene and an overall `sdvk009-physical-campaign.json` receipt.

It requires an identified integrated or discrete Vulkan device (`VkPhysicalDeviceType` 1 or 2), exact build/device continuity across all processes, 120-frame warmup for every retained state/timing launch, 120 retained timing frames, fresh caches/output directories and explicit `--execute`. Any state/image/device/build/capture failure stops the campaign before further timing. Successful collection is recorded as `COLLECTED_PENDING_SDVK009_DECISION` with `physical_gpu_evidence_collected=true`, while `physical_gpu_qualified` and `performance_accepted` remain false until the threshold analysis and final repository gate are completed.

The individual process packets remain ordinary `run.py` receipts. If manual inspection is necessary, use `run.py compare` and `run.py benchmark` against those retained directories; do not hand-edit requests or relabel a failed process.

## Minimum hardware matrix

Minimum acceptance matrix: one representative physical Vulkan GPU that supports the current renderer and can reproduce the established PF/SDVK harness. Reusing the GTX 1650 SUPER class from PF-016/PF-017 is preferred because it gives historical continuity.

A second architecture/driver may be run as portability evidence, but is not required for the provisional no-change decision and must remain a separate stratum rather than pooling samples across GPUs.

## Final repository action after hardware

Commit the complete machine-readable packet summary, exact source/build/content identities, raw-data manifest/hashes, state/image disposition, threshold calculation and final architecture decision. Update SDVK-009/RAG/ledger, run exact-head CI, merge and verify resulting `master`. Close #9 only after that final repository gate passes.
