# SDVK-002 — Renderer observability and reference corpus

Status: implementation and qualification in progress; issue #2 is not accepted
until its PR/check/merge/master-verification gates are recorded.

## Dependency and evidence boundary

This work starts from accepted SDVK-001 master
`a2d2d293d680895bb8daae86466596b05aaef483`. PF-020's accepted merge is
`e185e60b04fe37ec84a18c5a85eec6722b541b71`; the foundation implementation merge is
`7f34f15827f3cc98685d1af303d212ed5edc2b47`. Their release receipts retain the
owning qualifications, unsuccessful attempts and limitations. New observations
do not re-award those historical native or performance results.

The entry point for later renderer work is
[`tools/renderer_oracle/README.md`](../../tools/renderer_oracle/README.md).
[`corpus.json`](../../tools/renderer_oracle/corpus.json) connects eleven scene
recipes, eight reference classes and nineteen executable retained CPU
contracts. The accepted PF fixture generators and native validators remain
independent. Newly authored assets contain generated pixels and map geometry;
IWAD content must be supplied separately and its actual bytes are pinned.

## What is observed

`-sdvkobserve PREFIX` enables a bounded, default-off observer. Its JSON envelope
is `sdvk-renderer-observation/v1`; the
[shape schema](../../tools/renderer_oracle/observation.schema.json) and
[cross-record validator](../../tools/renderer_oracle/validate.py) describe the
machine contract. Unavailable fields carry reasons. Collection success means a
completed observation interval, not correctness or performance acceptance.

| Channel | Actual source and meaning | Limit |
| --- | --- | --- |
| Frame/view | Hardware `RenderView`, actual camera/map/settings, PF-010 context epochs, identities, parent/depth and eligibility | View metadata is descriptive; it does not change transforms or simulation |
| Material/sampler | Existing descriptor entry selected by the emitted immediate draw; PF semantic layer order and successful Vulkan sampler creation arguments | No descriptor/image is allocated to produce a diagnostic; indexed auxiliary palette binding is identified separately |
| Lights | The actual actor per-pixel or CPU aggregate query predicates, selected/rejected candidates and per-pixel summary | Frame-local census ordinal plus semantic fields is not a durable gameplay ID; LevelMesh per-surface light decisions are outside this observer |
| Probe/sun | Actual immediate-draw uniform index/fallback, descriptor identity, published resources and current authored sun state | Per-texel lightmap probe selection and native fragment readbacks retain their PF drivers; a uniform does not prove every shader consumes it |
| Shadow | Actual candidate selection/row and immediate-draw shadow policy | Casters are world geometry; no sprite silhouette or physical-lighting claim |
| Resources | Existing descriptor capacity/current/high-water/reuse/failure counters, generation/epoch tokens, texture/probe/lightmap/upload and LevelMesh owners | Distinct epoch domains are never inferred equal; cumulative counters are not a GPU memory measurement |
| Pipeline | Explicit canonical shader/pipeline field state at draw emission | The observer does not claim executed SPIR-V or whole-pipeline coverage |
| CPU | Steady-clock elapsed `RenderView`, with its camera/probe/scene work | Excludes simulation and later finish/presentation; state instrumentation affects state-mode cost |
| GPU | Resolved named Vulkan timestamp groups, only when requested and available | Groups can nest; never sum them or label them whole-frame GPU duration |

The collector preserves event order, coalescing only adjacent identical
observations. Limits are 4,096 measured frames, 65,536 records, 16,384 bytes per
record and 16 MiB retained record text. Invalid numerics, malformed UTF-8,
unbalanced contexts, premature dumps, output collisions and exhausted bounds
fail explicitly. Ordinary rendering uses the existing code paths with the
observer disabled.

## Reproduction and comparison

Preparation is pure and deterministic. A preparation receipt pins source files,
recipes, archive members and generated configuration/script bytes. Before a
capture, the harness checks the current source inventory and regenerates the
expected assets; rehashing an edited archive cannot authorize a different scene.

Each capture starts one process with a fresh configuration, save directory,
application shader/pipeline cache and output directory. The driver cache remains
external and uncontrolled. The request is written before launch and records the
executable/source identity, selected workload, seed, settings, frame/warmup
budget, image policy, content hashes, selected loader/thread environment and
host identity. Actual console readbacks, loaded-package inventory, map/camera,
extent and workload counters must agree. No automatic retry is allowed.

The engine completes the requested observed frames, disables tracing, uses the
ordinary PNG screenshot writer after presentation in state mode, writes the
native receipt and exits normally. An unsuccessful attempt retains all output;
the harness does not kill a successful run to manufacture a completion event.
An explicit timeout is a failed attempt and its partial output remains failed.

State and timing are separate runs. State scenes declare static content after
initialization and retain the observed simulation tic and interpolation
fraction. Their comparator removes declared static clock labels, renderer-local tokens; view position/angle/FOV representation is canonicalized
only to 1e-9. The human-readable derived context label is excluded from equality;
its actual producer is now an explicit validated field and the numeric context
state is compared directly. Full normalized parent state is hashed into each child. Ordered draw/query records, semantic material decisions,
resource generations/epochs/aliasing, failure/rejection diagnostics, light and
shadow selections, and pipeline fields remain compared. Raw resource-owner
counters are always retained, but only process-cumulative/lazy allocation,
upload-volume and staging-volume counts are excluded from correctness equality.
Resets, cancellations, staging wrap/dedicated state and all failure/rejection
counters remain correctness-visible.

Image comparison decodes bounded RGB8 PNGs with the accepted PF decoder. Exact
mode compares RGB bytes, independently of PNG compression/metadata. Tolerant
mode is selected before capture and requires all three declared limits:
maximum channel error 2/255, mean channel error 0.25/255 and changed-pixel
fraction 0.01. These limits are a corpus policy, not a portable GPU guarantee.
Both image and state comparisons must pass. The comparison command requires
the same actual device/driver/workload profile; a build change is explicit.
Cross-device qualification needs an owning issue's state assertions and
justified policy, rather than reusing a same-device exact golden claim.

## Benchmark interpretation

Ordinary timing runs skip per-draw state enumeration and use ordinary engine
time. Resource-owner snapshots are recorded after the measured CPU interval;
their overhead and optional GPU timestamp instrumentation still belong to the
documented workload. CPU summaries require at least thirty raw samples by
default and report min/max/mean/p50/p90/p95/p99 using linear interpolation at
`(n - 1) * percentile / 100` (Hyndman–Fan type 7).

Baselines retain each process and its raw samples separately, including workload
counters and each GPU group. Three distinct captures establish the presence of
repetition evidence; they do not establish a confidence interval, no-regression
claim or speedup. Duplicate/copied runs and different executable, package,
device, workload, host or loader/layer/thread environments cannot be pooled.
No outliers are removed. Virtualized software-renderer measurements are useful
for exercising collection and repeatability, with their host scheduling and
driver limitations retained explicitly.

## Verification and remaining qualification

`python3 tools/check.py --output build/checks-new` runs the retained PF/CFX
checks, compiled contracts, new observer/harness negative controls, deterministic
PF source oracle and two independently generated corpus preparations. The
software Vulkan CI lane runs real captures and produces complete artifacts;
preparation or CPU checks alone do not qualify native rendering. The shadow-capacity correctness scene is the smallest true overflow witness:
1,025 authored candidates, 1,024 selected and one dropped, using one warmup frame
and the minimum valid 128 shadow-map resolution. This preserves the capacity
invariant while making CPU Vulkan execution tractable; it is not an image-quality
or timing claim.

The local native Linux build uses GCC 13.3, authenticated ZMusic dependencies
and ordinary Vulkan/SDL sources. A private Mesa 25.2.8 llvmpipe capability probe
finds Vulkan 1.4 and required descriptor-indexing features. This execution
container rejects `AF_UNIX` socket creation with `EPERM` before bind/listen, so
Xvfb cannot create a display here. That limitation is retained as an environment
finding; it is not a successful renderer run. Hosted captures, their failures
and completed outcomes are recorded separately.

Retained PF recipes continue to require their declared original IWAD and
dedicated state/native-control protocols. In particular, the interpolated
sprite/view recipe uses PF's fixed-tic/fixed-fraction driver and is not an
ordinary timing workload. No physical-GPU baseline, new full bake, exhaustive
compatibility campaign, LevelMesh shader execution proof or later feature
acceptance follows from this implementation.

The final issue receipt must identify the publication and merge commits, all
required CI jobs, the two-run state/image comparisons, raw timing/counter
baseline, retained failures and verified master. Until then, SDVK-002 and its
dependent feature gates remain pending.

## Recovery qualification hardening

The source checkpoint was recovered through the exact GitHub CI source-bundle
artifact, not reconstructed from chat. PR #121 owns continued qualification.
The `sprite-mirror` scene adds freely reproducible rotation/mirror coverage while
leaving all three original PF generators unchanged. Material stress requires all
64 named panels and their declared authored semantic prefix. The renderer may
append only its canonical one-pixel lump-0 brightmap/detail/glow placeholders;
those placeholders are distinguished by actual source identity and arbitrary
extra semantics still fail. Sun/probe state requires actual published pairs, a
live draw binding and the authored sunlight intensity.
A comparison rejects one capture reused under the same path or copied paths.
These are fail-closed workload/evidence checks, not new renderer features.
