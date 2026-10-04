# Known traps, incomplete systems and dormant paths


Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: canonical audit warnings; update as PF work resolves them  
Primary issues: PF-001, PF-003, PF-006, PF-012..PF-019, PF-020/#110/#112

This is a warning index, not a defect count. Items may be fixed, removed or reclassified only with issue/PR evidence.

## 1. Per-lightmap probe selection is stubbed

Historical baseline defect owned by PF-012. PF-012 replaced the probe-0 stub with bounded live per-texel nearest-probe selection and explicit fallback semantics. See the PF-012 canonical record for acceptance evidence.

Owner: PF-012.

## 2. Probe AABB integration is partial

`LightProbeAABBTree` has build/query implementation, but baseline `Update()` and `Upload()` were empty. PF-012 bounded this path explicitly rather than silently reviving unfinished GPU traversal; live probe selection does not depend on it.

Owner: PF-012.

## 3. Automatic probe Z formula is wrong for non-zero floors

Resolved by PF-012: automatic probes use the true `(floor + ceiling) * 0.5` midpoint with non-zero-floor coverage.

Owner: PF-012.

## 4. Tiled-light path is dormant

The LevelMesh fragment path disables `uLightIndex` and draw-info dispatch remains disabled/commented. PF-019 gates the corresponding producer resources behind `VkLightTilePolicy::Enabled`, which defaults false: no Z-min/max pyramid, dedicated tile/Z-min-max descriptor sets, dedicated shaders/pipelines or per-frame descriptor rewrites are created while dormant. One `LightTileBlock` storage buffer remains bound at the unchanged LevelMesh binding 4 so descriptor ABI stays valid.

The producer implementation is retained rather than deleted. Enabling the single policy seam restores full tile-grid sizing and all gated resource creation; SDVK-009 owns reactivation of the consumer and must validate that path before enabling it. Do not claim clustered/tiled lighting is active.

## 5. Bindless reuse exists but raw indices remain dangerous

`AllocBindlessSlot`/`FreeBindlessSlot` recycle blocks by size. The issue is not absence of reuse; it is capacity, reserved ranges, stale long-lived consumers and generation validation.

Owners: PF-002/PF-003.

## 6. Fixed descriptor limits/reservations

Baseline uses hard-coded bindless/lightmap reservations. Lightmap pages also associate probe textures. Test maximum page/reservation arithmetic explicitly.

Owner: PF-003.

## 7. Pipeline/shader keys use whole-object `memcmp`

Resolved by PF-006: shader/pipeline/render-pass keys use explicit semantic identity; object padding and `FRenderStyle` packed representation no longer define cache identity.

Owner: PF-006.

## 8. Large vendor/driver policy is embedded in sampler code

Resolved structurally by PF-007: vendor/driver capability and quirk classification is centralized in the Vulkan capability snapshot while inherited policy boundaries remain unchanged.

Owner: PF-007.

## 9. Sprite normal mapping has no explicit stable sprite-local tangent contract

Generic derivative TBN is active. Mirrored/rotated Doom sprite correctness is not guaranteed by front-facing success.

PF-009 extracts orientation metadata; SDVK-007 owns new explicit tangent behavior.

## 10. Sprite clipping sentinel inconsistency

Resolved by PF-014 / PR #63, merged as `42aae69ec97b124970b88b8ddba314a486ac5a55`. `HWSprite::PerformSpriteClipAdjustment` now uses the same `-NO_VAL` ceiling sentinel from initialization through ordinary-sector fallback. The floor sentinel, matched 3D-floor/height-sector values and inherited displacement policy remain unchanged. Adversarial coverage includes no candidate, floor-only, ceiling-only, paired 3D-floor and height-sector cases.

Owner: PF-014.

## 11. Sky-info equality uses raw memory comparison

Resolved by PF-014 / PR #63, merged as `42aae69ec97b124970b88b8ddba314a486ac5a55`. `HWSkyInfo` identity now compares all authored/resolved semantic fields explicitly; object padding and representation noise do not participate in deduplication. Mirror/double-sky/sky2 state, both resolved textures, texture id, offsets and fade color remain identity.

Owner: PF-014.

## 12. Sprite precache variant flag bug

Resolved by PF-013: sprite material precache passes the computed scale flags so expand/upscale variants retain normal material lookup identity.

Owner: PF-013.

## 13. Indexed RedIsAlpha Vulkan material path is explicitly incomplete

Resolved by PF-013: Vulkan `CTF_IndexedRedIsAlpha` has separate luminance-as-alpha resident image/descriptor identity and no longer aliases ordinary indexed/palette translation semantics.

That bounded accepted repair does not prove the separate public `DTA_Indexed` material provisioning path. The unaccepted #110 defect/candidate is recorded in item 26 below.

Owner: PF-013.

## 14. PBR roughness-zero numerical edge

Resolved by PF-013: GGX roughness-zero handling is finite at the sampled zero-width boundary while ordinary roughness calibration is unchanged.

Owner: PF-013.

## 15. Shadow-map 1024-light selection is traversal-order dependent

Resolved by PF-015 / PR #65, merged as `1a60a3cbb9360e8b1d74a2764c8472ffd65d044d`. Eligible sets at or below 1024 retain the inherited selected set and row order exactly. On overflow, selection is ordered by squared distance to the interpolated central main view plus deterministic spatial/light semantic tie fields instead of first-1024 linked-list traversal. `stat shadowmap` exposes processed, candidate, selected and dropped counts. Exact implementation-head CI run 106 and post-merge `master` run 107 both passed the required PF oracle and Windows/macOS/Linux matrix.

Owner: PF-015.

## 16. Static actor-light visibility caching needs world-generation validity

Resolved by PF-015 / PR #65, merged as `1a60a3cbb9360e8b1d74a2764c8472ffd65d044d`. Actor/static-light and sun visibility cache reuse now rejects PF-004 `LevelMeshMutationEpochs::Query` changes while retaining actor-position, stable portal-group and per-light invalidation. Moving world occluders therefore invalidate stationary actor/light visibility without globally disabling caching. Transient PF-010 pass serials remain deliberately excluded because the current LevelMesh trace does not consume them. `stat actorlightcache` exposes cache hits, misses and invalidation reasons. Exact implementation-head CI run 106 and post-merge run 107 passed.

Owner: PF-015.

## 17. Dynamic-light collection uses costly duplicate maintenance

Resolved by PF-016 / PR #67, merge `6091d6739c4b7dc96ef7913c911bf4eba89d7715`. The shared candidate pipeline uses generation membership for BSP/qualification and omits redundant membership only on a proven unique, qualified single-section list. Baseline/local identity/order/class/group equivalence is checked before enabling; changes to actor position/radius/section/group invalidate qualification. Runtime portal/visibility/model/invalidation fixtures and exact images pass, with a 9.09% representative production setup median improvement and a separate 4.45% warm-frame improvement. Submitted-head and post-merge CI passed. Unsupported fallback remains correct but repeated qualification still allocates temporary selection vectors; that cost is not claimed fixed. See `PF-016-RUNTIME-EVIDENCE.md`.

Owner: PF-016.

## 18. GPU light buffer notes lack of deduplication

LightBufferSSO retains contiguous per-consumer light arrays. PF-017 profiling on accepted master 66b09a872b9d45b496a27c1bf1406d8a74606cd2 found 49,473 references to 217 packed records in a dense frame, but exact whole-range/subrange reuse saved only 2.40%. A frame-local per-record hash plus shader indirection cut mapped writes 94.24% yet increased representative S: Setup median 133.25% across five alternating pairs. The prototype was restored. Source identity is absent from accepted FDynLightData; future sharing must prove logical order/class/lifetime and measured benefit. The second source-owned revision/temporal-write prototype avoids those hashes/fetches and improves setup 6.83%, but is not intra-frame physical compaction and has incomplete identity/lifetime acceptance. It was restored. See PF-017-PROFILING-NOTES.md and [PF-017-REUSE-RESEARCH.md](../PF-017-REUSE-RESEARCH.md).

Owner: PF-017.

## 19. Material descriptor variants use linear search

VkMaterial::GetDescriptorEntry still scans cached variants. PF-017 physical profiling found at most one variant per material in the dense light scene and three in DBP37 MAP04; 38,572 of 42,285 DBP37 lookups scanned a one-entry cache. A second Champions workload reaches 15-17 variants, but node/flat hash lookups are 94.8%/36.8% slower than the same executable's accepted scan despite zero observed oracle mismatches. Both were restored; the accepted linear path remains. See [PF-017-REUSE-RESEARCH.md](../PF-017-REUSE-RESEARCH.md). A later Sunlust/Champions arena sustains median 1,201 large-cache calls/frame, but only about 47.13 microseconds/frame of estimated large-search cost; a separate arena driver failure stopped production confirmation and no candidate was retained. See [PF-017-MATERIAL-QUALIFICATION.md](../PF-017-MATERIAL-QUALIFICATION.md). Any future key must preserve PF-013 palette/RedIsAlpha, translation, clamp and global-shader distinctions and PF-003 retirement. See PF-017-PROFILING-NOTES.md.

Owner: PF-017.

## 20. LevelMesh allocator is intentionally simple

Historical baseline concern resolved by accepted PF-018 / PR #68, merge `8ad883ada35b80dbf750462dbb4c36b5edf38893`. Current production uses a deterministic eight-range small-list scan, a `{size,address}` best-fit index for larger free lists and bounded geometric growth without moving live ranges. PF-004 address/generation/span ownership and dirty uploads remain authoritative. Four complete DBP37 MAP04 diagnostic pairs report main-array logical bytes11,702,876→8,635,124(−26.21%), plus10,244nominalcacheB; this is not GPU heap residency/FPS and the map has negligible steady allocation/moving-AABB work. [Runtime evidence](../PF-018-RUNTIME-EVIDENCE.md).

Owner: completed PF-018; PF-020 verifies the retained contract.

## 21. Moving AABB lines rediscover parent paths

Historical baseline concern resolved by accepted PF-018 / PR #68, merge `8ad883ada35b80dbf750462dbb4c36b5edf38893`. Current moving-line update caches immutable line→leaf and node→parent topology while retaining leaf→root order. A targeted light-bearing moving-polyobject fixture matches1,630fixed-tic RayTest records and paused world/geometry; five pairs measure310.378→159.175CPU ns/movedline(−48.72%). Full BeginFrame20.129→20.082ms is mixed/essentially flat, so no material whole-path speedup is claimed. Dirty upload merging is unchanged. [Runtime evidence](../PF-018-RUNTIME-EVIDENCE.md).

Owner: completed PF-018; PF-020 verifies topology/reset/lifetime invariants.

## 22. Texture uploads allocate staging buffers per image

Historical PF-005 concern. Qualified ordinary texture uploads now use the bounded persistent staging arena; unrelated lightmap/probe/readback staging remains under its owning paths.

## 23. Model translucency lacks true depth sorting

`hw_models.cpp` explicitly notes that culling is used to mitigate lack of proper depth sorting. This is real technical debt but not a PF blocker unless a PF refactor regresses it. Track for post-PF renderer work if still relevant.

## 24. Experimental whole-scene raytrace view is distinct from normal ray-query shadowing

`gl_raytrace` can replace normal scene processing in `RenderViewpoint`. Do not conflate this viewer experiment with production world ray-query visibility.

## 25. Temporal rendering infrastructure is not a coherent baseline subsystem

HDR/depth/normal buffers exist, but motion vectors/history ownership/per-view invalidation are not established. Do not bolt temporal effects onto one global history buffer.

Owner for preparatory context: PF-010. Actual temporal effects are later work.

## 26. Public indexed 2D material lacks its palette resource

Accepted starting master `4df7dea1338f063c6417e024f967bfa4aa23edd4` constructs one authored albedo layer for public `DTA_Indexed` / `DTA_TranslationIndex`, but the Vulkan consumer allocates three descriptors and attempts missing material layers. `material_paletted.glsl` needs a real second palette resource. This supported path is a PF-020 blocker; it is not a native crash claim and is independent of PF-013's accepted RedIsAlpha boundary. [Blocker and ancestry](../PF-020-INDEXED-MATERIAL-BLOCKER.md).

The focused #110 candidate supplies two real resources: a canonical-remap-specific, one-mip R8 image plus an entry-owned opaque base-palette row. Moving translation to the palette row is rejected because inverse/colour operations run before palette lookup. Public indexed upload is scoped synchronous, so numerical ID replacement cannot overwrite an earlier canonical variant via deferred production. Index/row lookup is nearest; `XY_NOMIP` must normalize to `NOFILTER_XY`, not `CAMTEX`. Non-mip create and update must explicitly finish in shader-readable layout. Palette rows and all resident variants retire through existing owner reset, PF-003 invalidation and draw fences. Ordinary authored layer order, asynchronous true-colour loading, state-driven palette/RedIsAlpha and SWCanvas must remain independently protected.

Status: **candidate / unaccepted**. Production-linked negative/positive fixtures and a scoped native command are prepared; native execution, validation activation, restart/SWCanvas controls, exact-head CI, review, merge and verified-master gates are still pending. Do not remove this trap or unblock PF-020/SDVK-001 from source inspection or a successful build. [Implementation notes and acceptance limits](../PF-110-IMPLEMENTATION-NOTES.md).

Owner: [#110](https://github.com/techrote/ShadeDoomVK/issues/110), required by PF-020.

## 27. Mapped software framebuffer declares an uploaded-image layout

Accepted starting master `4df7dea1338f063c6417e024f967bfa4aa23edd4` creates the sampled linear mapped software framebuffer with tracked layout `GENERAL`. `SWSceneDrawer::RenderView` writes it through `MapBuffer`; `CreateTexture(nullptr, ...)` records no upload/transition and `GetImage` returns that owner. The inherited bindless writer unconditionally declares `SHADER_READ_ONLY_OPTIMAL`. This source-established supported-route mismatch is independent of #110's public indexed palette provisioning; it is not a claimed observed GPU crash.

The focused #112 candidate publishes each selected material image's actual tracked layout, retains READ as the default for audited uploaded-image callers, and guards the writer to READ/GENERAL. It leaves pixels, palette/translation, filtering, mapped producer, upload policy, cache identity and normal fence retirement unchanged. The existing software-paletted SWCanvas R8 plus palette pair must stay intact; no substitute producer, blanket flush, extra per-frame upload or forced layout transition is acceptance.

Status: **TESTED BUT UNACCEPTED**. Extracted original/current MSVC fixtures pass, but allocation-only native offset/pitch observations and #110 raw paletted output do not prove a real software frame. Actual warm SWCanvas state, repeated use/retirement, presentation, scoped core-plus-sync validation, clean build, eight exact-head CI jobs, review and verified merge/master gates remain pending. Keep PF-020/SDVK-001 blocked. [Implementation notes and exact evidence limits](../PF-112-IMPLEMENTATION-NOTES.md).

Owner: [#112](https://github.com/techrote/ShadeDoomVK/issues/112), required by PF-020.

## 28. Missing PBR probe token reaches fixed 2D views as cubes

Accepted starting master `4df7dea1338f063c6417e024f967bfa4aa23edd4` initially provides one sampled cube pair. A fresh multi-probe scene without prebaked maps can render a PBR surface assigned unavailable authored target `1` before completed-pass publication grows the collection. `GetLightProbeTextureIndex()` then returns `0`; the consumer samples fixed null/BRDF descriptors `0`/`1` through `samplerCube`. Zero lightmap gather taps reach the same mismatch when that branch executes. Ordinary authored target `0` resolves a separate real nonzero pair and must not be conflated with this token.

Status: **OPEN — source-established blocker; contribution decision unresolved**. PF-012's default/no-probe identity does not adopt black IBL, authored-target substitution, another environment or mixed-tap weight renormalization. Record the contribution/blending decision before repair, preserve exact production-extracted original negatives off GPU, and retain valid-pair/material behavior. No original invalid GPU launch, native failure, driver cause or passing freeze is claimed. [Source hashes, reachability and acceptance limits](../PF-020-PBR-PROBE-BLOCKER.md).

Owner: [#113](https://github.com/techrote/ShadeDoomVK/issues/113), required by PF-020; serialize with the existing coordinator rather than opening a competing probe worker.

## Maintenance rule

When a PF issue resolves an item, replace the warning with:

- resolved issue/PR/merge commit;
- resulting invariant/contract;
- remaining limitation if any.

Do not simply delete historical traps; their provenance is useful when reviewing regressions or donor patches.
## PF-017 integrated physical no-go — 2026-10-03

Accepted PR #74, merge `844462c3a4ed5f7037ade1b49d1a28f578077213`, completes PF-017 as a measured no-go and restores the original light path after five integrated-source GTX 1650 SUPER pairs regress CPU setup (+10.79%) and CPU whole-frame (+2.42%). Five exact images do not override performance failure. Candidate counter/state diagnostics stopped on an added baseline metadata-hook defect; no candidate physical correctness acceptance is claimed. No reuse, hash/indirection, material index or default-resource sharing is retained. Entries18/19 describe historical research, not outstanding mandatory optimization or retained savings. Accepted repaired master semantics and CFX lifetimes are unchanged. See [final report](../PF-017-FINAL-ACCEPTANCE.md).

## CFX descriptor-retirement trap — resolved current-source state

Historical CFX-009 evidence showed that atlas shrink could leave previously published reserved light/probe descriptor slots naming views whose old atlas owner was then retired. PR #104 resolves that current-source state by publishing persistent initialized correctly typed neutral views into removed reserved slots before submission while preserving ordinary fence-controlled atlas retirement.

The matched retention experiment is not the production behavior: normal repaired runs use retention OFF. Three exact formerly failing DBP37 processes succeed on the repair, followed by 3/3 qualification for each selected original DBP50, v1.2 and Sunlust/Champions route. Live reconciliation after PF-019 / PR #107 confirms the publication path remains present on `master@44864d9d27495d3992d3a7314f4cb7de6c029b7b`.

The executing shader/SASS, illegal dynamic access, shared historical cause and repaired P400 behavior remain unknown and must not be inferred from the successful qualification.

Owner: completed CFX-009/#102 repair and CFX-000/#75 synthesis; PF-020 must preserve the invariant in the final freeze.


## GLDEFS custom texture sampling slot isolation

The inherited material/map/class and legacy HardwareShader texture properties
initialized a new slot's default through the initial index zero. A later texture
could overwrite the first texture's explicit filter. The PF-020 partial repair
selects the actual free slot first. The exact original producer retains both
counterexamples in the strict compiled regression; the current producer checks
defaults, overrides, ordering, sparse slots and errors. See [repair](../PF-GLDEFS-SAMPLING-REPAIR.md).
This parser repair does not accept the renderer freeze or close its independent
material/probe/compatibility gates.

## 26. Public indexed 2D material lacks its palette resource

The inherited public `DTA_Indexed` / `DTA_TranslationIndex` path constructs one authored albedo layer but its Vulkan consumer allocates three descriptors and attempts missing layers. `material_paletted.glsl` requires a real palette at binding1. This is a source-established supported-path defect, not a native crash claim.

The #110 candidate supplies a canonical-remap-specific one-mip R8 image and an entry-owned unchanged base-palette row as two real PF-003 resources. Moving translation to the row fails inverse/additive/object ordering. Public indexed production is synchronous; index/row lookup is nearest, including the explicit `XY_NOMIP` to `NOFILTER_XY` normalization. Both non-mip upload paths finish READ. Rows/variants retain owner reset, PF invalidation and draw-fence retirement; ordinary authored layers, async truecolour, palette/RedIsAlpha and SWCanvas remain protected.

Status: **native verified repair; integration tracked in the source issues**. Candidate4 normal evidence is retained history; the newer candidate5 native qualification is verified below and release integration is tracked in the source issues. [Implementation notes and historical evidence](../PF-110-IMPLEMENTATION-NOTES.md). Owner: [#110](https://github.com/techrote/ShadeDoomVK/issues/110).

## 27. Mapped software framebuffer declares an uploaded-image layout

The existing sampled linear software framebuffer is tracked GENERAL. `SWSceneDrawer::RenderView` writes that owner; nullable `CreateTexture` records no upload/transition and `GetImage` returns it unchanged. The inherited bindless writer declares READ. This supported producer/declaration mismatch is separate from #110 and is not evidence of a native crash.

The #112 candidate publishes each selected material image's actual tracked layout, retains READ as the default for audited uploaded callers and guards READ/GENERAL. Pixels, palette/translation, filters, producers, cache identity and normal fence retirement are unchanged. Real paletted SWCanvas retains its mapped R8 plus original palette; no replacement resource or forced transition is acceptance.

Status: **native verified repair; integration tracked in the source issues**. Candidate4 mode0 core/sync evidence is historical. Mode1 BGRA frame execution and direct post-retirement SWCanvas token measurement remain unclaimed; candidate5 native qualification is verified below and release integration is tracked in the source issues. [Implementation notes and precise limits](../PF-112-IMPLEMENTATION-NOTES.md). Owner: [#112](https://github.com/techrote/ShadeDoomVK/issues/112).

Neither focused repair accepts PF-020 or unblocks SDVK-001.


## Verified candidate5 native qualification

The final clean candidate passes all twelve normal mode/filter cases and both
genuine one-process core/sync restarts, with zero requested-validation errors or
warnings, unchanged pins and all294 presentation ROIs. Strict PF393/393, four
standalone contracts, CFX8/8 and deterministic source oracles pass.
See [source and acceptance scope](../PF-110-IMPLEMENTATION-NOTES.md) and
[compact independently reviewed qualification](../PF-110-FINAL-NATIVE-VERIFICATION.json) for hashes, methods,
retained failures and unmeasured mode1/SW-retirement/performance limits.
Focused release integration is tracked in #110/#112; PF-020 and SDVK-001 remain
separate blocked gates.
