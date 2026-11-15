# Controlled 3D-floor lightmap source/facing ownership (merged)

**Source authority:** [PR #192](https://github.com/techrote/ShadeDoomVK/pull/192), merged 13 November 2026 as `f4546ee1d21a37473f0a3bc405949bc81253a811`, PR head `0c1bc00893fc14dc4b7b34717e8809c7fd300d8c`. Parent [SDVK-014/#14](https://github.com/techrote/ShadeDoomVK/issues/14) remains open. Follow-on [#194](https://github.com/techrote/ShadeDoomVK/pull/194) and [#202](https://github.com/techrote/ShadeDoomVK/pull/202) cover command and instrumentation, not this geometry ownership.

**Retrieval queries:** FF_BOTHPLANES, 3D-floor inverted planes, lightmap tile alias, ControlPlane, vindex[2], per-facing UV, retained v5 atlas, SDVK-161, tile retirement, flat vertex streams.

## Reproduced defect and corrected invariant

The same controlled 3D-floor can emit **both model source planes** with the same output facing. Earlier `(type, subsector, control sector)` tile keys could alias two geometrically different heights. The original one-stream/one-tile-per-rover assumption also failed when opposite facings needed independent UV pages. The preexisting SDVK-161 check correctly detected contradictory ownership; simply relaxing that guard would introduce wrong bakes.

The merged correction explicitly distinguishes:

- **Source axis:** `LightmapTileBinding::ControlPlane` becomes a runtime component of controlled flat tile identity; normal flat/wall keys retain their sentinel.
- **Emitted facing:** Upward/floor vs downward/ceiling choose independent slots and, when lightmapped, independent index/vertex streams `planeref::vindex[2]`. Without lightmaps, existing shared stream behavior stays available.
- **Per-subsector slot layout:** slot 0 sector tile; then slot `1 + 2 * rover + facing` per source-axis table. All allocation, visible-tile publication and vertex ownership must use the same mapping.
- **Retirement:** `FreeFlat` detaches all source/facing slots **before** tile pool recycle; reconstructed or disappearing faces cannot retain numeric references into unrelated new allocations.
- **Receiver:** Actual oriented plane and source axis must match the bake receiver. Face orientation changes do not justify mixing incompatible bake data.

This is renderer-only geometry, tile and persistence logic: no Doom actor simulation, pipeline ABI, GPU descriptor format or atlas allocator redesign.

## Retained format compatibility

The retained **v5** lightmap format has no source-axis field. The loader can derive the historical axis for supported legacy faces without changing file layout, checksums, duplicate/span checks or version. **New `FF_BOTHPLANES` runtime-only tiles are excluded from v5 serialization in all count/entry/pixel passes**: they need a fresh bake rather than blindly reusing ambiguous historical RGB. Quarantined alternative-plane cases remain quarantined.

## Source map

| Source | Contract |
| --- | --- |
| `src/common/rendering/hwrenderer/data/hw_lightmaptile.h` | `ControlPlane` tile binding key and comparison. |
| `src/gamedata/r_defs.h`; `src/playsim/p_3dfloors.*`; `src/maploader/maploader.cpp` | Sector/source-facing ownership representation. |
| `src/rendering/hwrenderer/hw_vertexbuilder.*` | Separate emitted index streams, selected tile-to-UV mapping and source-range height propagation. |
| `src/rendering/hwrenderer/scene/hw_flats.cpp` | Source/facing selection, live tile visibility and actual draw diagnostic scope. |
| `src/rendering/hwrenderer/doom_levelmesh.cpp` | Bake tile ownership, lifetime and persisted receiver compatibility. |
| `src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp` and renderer oracle `sdvk014_controlled_planes.py` | Joined submitted index ranges/vertex UV/page and live tile-owner evidence. |

## Evidence, boundaries, traps

The PR includes retained **pre-fix failing fixtures**, focused compiled/source checks and a native authored controlled-face qualification route. The independent record is in [SDVK-014-CONTROLLED-PLANES.md](../SDVK-014-CONTROLLED-PLANES.md) and [CPU evidence](../evidence/SDVK-014-CONTROLLED-PLANES-CPU.json); source/PR integration is merged. The note distinguishes CPU adapters from genuine submitted GPU geometry, and says the historical #161 repeatability failures, general slopes/inversions, dynamic copied-plane cases and SDVK-014 physical bake/update acceptance remain open.

**Do not infer:** all slope/portal/mirror 3D-floor combinations are correct, a v5 format migration occurred, all tiles can be serialized, or a resource key is durable across atlas incarnation/reallocation.

Cross-references: [lightmap pipeline](06-LIGHTMAP-PROBE-PIPELINE.md), [mutation matrix](03-LEVELMESH-MUTATION-MATRIX.md), [identity](13-DURABLE-IDENTITY-AUDIT.md), [portal spaces](07-PORTAL-COORDINATE-SPACES.md).
