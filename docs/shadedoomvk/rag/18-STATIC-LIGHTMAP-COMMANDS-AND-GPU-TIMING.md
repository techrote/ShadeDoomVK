# Static lightmap commands and GPU-timing diagnostics (merged increments)

**Authority:** [PR #194](https://github.com/techrote/ShadeDoomVK/pull/194), merged 13 November 2026 as `d4f34dfdc5a7701ff47d8ea6dbdb14e45c824ffb`; [PR #202](https://github.com/techrote/ShadeDoomVK/pull/202), merged 14 November 2026 as `f787f7199fc7560588bb9440b3dd0aa663cb53de`. Both are **bounded improvements**, not final [SDVK-014/#14](https://github.com/techrote/ShadeDoomVK/issues/14) approval.

**Retrieval queries:** vktool lightmap build, stuck bake, dirty tiles, no progress, wrong map write, MAPINFO redirect, tile batches, GPU timestamp lightmap probe, -sdvkobservegpu, lightmap.total, nested PushGroup, gpuStatActive.

## #194: do not save incomplete or wrong-target bakes

The static commandlet now validates the **requested loaded map** rather than merely assuming an earlier deferred load succeeded. It checks map data, finishes pending startup within bounded ticks, rejects unresolved/redirected map identity and missing LevelMesh; for build it also rejects a non-Vulkan renderer or disabled lightmapping.

After each update batch, it **recounts live dirty tiles**. If dirty count does not decrease, or no live tile exists despite dirty work, it errors before persisting `LIGHTMAP`. The existing **1,001-tile batch cap** survives; an intentionally empty atlas avoids division by zero and can complete validly.

Deletion uses the same canonical loaded-map identity guard but intentionally works even if lighting is currently disabled, so it can remove a pre-existing stored lump. Save and delete must address the **actual selected loader entry**, not a higher/lower priority map sharing the same displayed name.

Primary source: `src/commandlets/lightmapcmd.cpp` (`LoadLightmapCommandMap`, `LightmapBuildCmdlet::OnCommand`, `LightmapDeleteCmdlet::OnCommand`); real commandlet fixture `tools/pf_oracle/tests/sdvk014_lightmap_commandlet_fixture.cpp` and Python harness `test_sdvk014_lightmap_commandlet.py`.

Test scope includes a 1,002-tile bake, no-progress/interrupted bakes, empty atlas, wrong/missing/unfinished maps, redirected output target and backend rejection. **It does not certify** a native full bake/save/reopen/delete round trip or whole-program GPU stability.

## #202: opt-in Vulkan GPU intervals, not a benchmark verdict

Command: `vktool lightmap build ... -sdvkobservegpu`. On the actual tool path, timestamp-capable Vulkan provides named intervals for lightmap tile work (raytrace/resolve/blur/copy) and probe reconstruction (cubemap rendering, convolution, per-probe copies). `lightmap.total` and probe intervals use **bottom-of-pipe** timestamp boundaries on the appropriate command-buffer work; probe publication after the interval is separate.

- `src/common/rendering/vulkan/commands/vk_commandbuffer.cpp/.h` — activates tool GPU timing only when the commandlet flag is supplied; resets timestamp pools on the first *submitted transfer* buffer; parameterizes timestamp stage for `PushGroup/PopGroup`.
- **Critical capacity invariant:** reserve an end timestamp for a proposed group *and each already-open parent*. Never pop a group whose push failed; avoid unsound nested ranges near query-pool exhaustion.
- Unsupported timestamp capability produces a bounded, one-time `SDVK_TOOL_GPU unavailable=...` diagnostic instead of floods of misleading empty timing records.
- `src/common/rendering/vulkan/vk_lightmapper.cpp` and `vk_renderdevice.cpp` — issue measured groups around current lightmap/probe execution, without silently converting all renderer paths into profiling mode.

### Historical physical numbers: descriptive, not qualification

PR #202 reports an earlier GTX 1650 SUPER **100 W** controlled fixture: 12-tile bake median **1.188 ms**; two six-tile invalidations **2.01 / 3.59 ms**; same-map reload **0.90 ms**; 60 probe intervals median **26.81 ms** (range 22.71–32.96). Raw local hardware logs are **not reviewer-accessible as GitHub artifacts** and these runs used an earlier runtime SHA, not the final correction. Do **not** recast these values as independently reproduced, full-frame GPU cost or broad representative measurements.

[SDVK-014-GPU-TIMING-BOUNDARY.md](../SDVK-014-GPU-TIMING-BOUNDARY.md) explicitly records the owner's authorisation for the bounded measurement-enablement merge only. That statement describes **the historical approval scope of PR #202**, not today's blanket GPU operating policy. The owner subsequently directed normal local use of available GPUs without per-run permission on 15 November; see [current workflow](../LOCAL-GPU-WORKFLOW-20261115.md). Those earlier numbers still do not establish physical acceptance, hardware fault resolution or closure of #14.

## Safety and follow-ons

Both PRs are integrated source, but the full static-bake physical validation, LevelMesh/portal correctness matrix, probe stability and representative cost campaign remain separately gated. A nested interval must not be summed with its parent to manufacture whole-frame GPU time. A timeout/no-progress error is correct fail-closed behaviour, not an inconvenient diagnostic to suppress.

Cross-references: [lightmap/probe pipeline](06-LIGHTMAP-PROBE-PIPELINE.md), [controlled flat ownership](17-CONTROLLED-3DFLOOR-LIGHTMAP-OWNERSHIP.md), [GPU observability](11-RENDERER-OBSERVABILITY.md).
