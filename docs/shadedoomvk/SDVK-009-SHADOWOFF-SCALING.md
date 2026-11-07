# SDVK-009 bounded shadow-off scaling collection

This software increment enables prospective partial architecture measurements
through the existing physical supervisor. It contains no GPU execution or
physical acceptance. The owner-authorized current-source campaign still needs
an exact source/build/content/device packet and independent review before launch.
The full [SDVK-009 protocol](SDVK-009-GPU-QUALIFICATION-PROTOCOL.md), thresholds,
historical failures and unresolved 1025-light shadow fault remain unchanged.

## Workloads and quality boundary

`lights-one-shadow-off` and `lights-many-shadow-off` are explicit variants of
the original one- and 64-light scenes. Only their identity/descriptive metadata,
shadow switch and zero-shadow assertions differ. Their generated PK3/map/light/
material/image bytes match their originals. Filtering, geometry, authored light
eligibility/counts, camera, ordinary engine clock and all other renderer settings
are preserved. The existing shadow-enabled recipes are not rewritten or relabeled.
The disabled variants keep explicit zero-shadow frame assertions and, like the
existing dense recipes, require no inactive shadow draw-record channel.

The two 256-light workloads retain their existing mixed-static overlap/dispersed
recipes. All four require `gl_light_shadows=0`, `vk_rayquery=false`, and the
immediate path (`gl_levelmesh=false`). This is a common shadow-off stratum, not
an optimization gain obtained by comparing different quality settings. It does
not measure shadow scaling, moving lights, POM, LevelMesh or general gameplay.

## Exact partial schedule

The purpose is `sdvk009-shadowoff-scaling`, with the existing registered schema,
`REGISTERED_WORKLOAD` profile and `PARTIAL_COLLECTION_ONLY` scope. It admits
exactly twenty named creations, zero retries and a matching conditional ledger.
Every capture uses 1904x1001, 120 **rendered** warmup frames and a 180-second
deadline. The first eight processes retain one state frame: two independent
captures of each one/64/dispersed/overlap workload, with exact paired state/RGB
comparison. The following twelve processes retain 120 consecutive timing frames
each, in these three serial orders:

1. one, 64, dispersed, overlap;
2. overlap, dispersed, 64, one;
3. 64, one, overlap, dispersed.

`tools.renderer_oracle.sdvk009_shadowoff.capture_specs(recipe_hashes)` derives
these declarations from four frozen recipe hashes. Use the ordinary
`prepare-registered --seed ... --registration ... --packet ...` entrypoint;
no caller-provided argv or callback is admitted. Renderer and oracle commit/tree,
build receipt, runtime/IWAD/legal content, prepared manifest and fresh output
root remain pinned by the existing registration. Historical STOPs are retained;
no old approval or failure is reused as this generation's outcome.

Before the first timing creation, all eight state packets are revalidated.
Every pair must pass exact image/state comparison and equal light census,
selected/upload counts and resource pressure. Actual authored/active light counts
must match 1/64/256/256; shadow work and upload failures must be zero. Existing
descriptor/allocation bounds, native ownership, registry/module observation,
heartbeat, event/thermal policy, deadlines and post-exit fences remain mandatory.
This increment changes none of those guards or the owner-configured GPU state.

Every timing packet must retain complete groups and exactly one resolved
`scene.immediate` GPU sample in every frame. Final validation reuses existing
three-process benchmark summaries per scene, retaining raw distributions and
source/build/engine/IWAD/device/host/environment continuity. No outlier removal,
retry, nested-group sum or automatic architecture decision is introduced.

## Interpretation and remaining gates

CPU timing is the existing RenderView steady-clock interval; it excludes CPU
tick/simulation and later presentation. GPU `scene.immediate` is the existing
main-view immediate-scene timestamp span, excluding postprocessing; it is not
whole-frame GPU time or an isolated light-evaluation timer. State captures supply
selected-light/upload work ratios without adding bookkeeping to timing mode.
Timing retains existing draw counters and resource/descriptor snapshots.

Receipts remain partial and descriptive with `physical_gpu_qualified=false` and
`performance_accepted=false`. Sparse/dense normalized thresholds can inform
later reviewed research, but this reduced matrix cannot close SDVK-009, waive
the full correctness corpus or resolve the held shadow fault. Full source review,
focused CPU checks and normal exact-head CI precede integration. Physical data
must come from a separately reviewed prospective packet, not these CPU controls.
