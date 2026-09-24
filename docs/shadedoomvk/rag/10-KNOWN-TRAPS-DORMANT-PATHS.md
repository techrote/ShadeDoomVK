# Known traps, incomplete systems and dormant paths

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: canonical audit warnings; update as PF work resolves them  
Primary issues: PF-001, PF-003, PF-006, PF-012..PF-019, PF-020

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

Z-min/max textures, light-tile buffer, descriptor/pipeline and compute shader infrastructure exist, but the LevelMesh fragment path disables `uLightIndex` and draw-info dispatch is disabled/commented.

Do not claim clustered/tiled lighting is active. PF-019 may remove unnecessary active allocations when dormant; SDVK-009 may later research revival.

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

LightBufferSSO retains contiguous per-consumer light arrays. PF-017 profiling on accepted master 66b09a872b9d45b496a27c1bf1406d8a74606cd2 found 49,473 references to 217 packed records in a dense frame, but exact whole-range/subrange reuse saved only 2.40%. A frame-local per-record hash plus shader indirection cut mapped writes 94.24% yet increased representative S: Setup median 133.25% across five alternating pairs. The prototype was restored. Source identity is absent from FDynLightData; future sharing must prove logical order/class/lifetime and measured benefit. See PF-017-PROFILING-NOTES.md.

Owner: PF-017.

## 19. Material descriptor variants use linear search

VkMaterial::GetDescriptorEntry still scans cached variants. PF-017 physical profiling found at most one variant per material in the dense light scene and three in DBP37 MAP04; 38,572 of 42,285 DBP37 lookups scanned a one-entry cache. No representative hash benefit was established, so the accepted linear path remains. Any future key must preserve PF-013 palette/RedIsAlpha, translation, clamp and global-shader distinctions and PF-003 retirement. See PF-017-PROFILING-NOTES.md.

Owner: PF-017.

## 20. LevelMesh allocator is intentionally simple

First-fit free-range scans and aggressive growth are understandable but can become inefficient under richer dynamic renderer state.

Owner: PF-018 after PF-004 freezes ownership semantics.

## 21. Moving AABB lines rediscover parent paths

Dynamic AABB update calls `FindNodePath` for changed dynamic lines. Caching parent/leaf topology can remove repeated traversal if topology invariants permit it.

Owner: PF-018.

## 22. Texture uploads allocate staging buffers per image

Historical PF-005 concern. Qualified ordinary texture uploads now use the bounded persistent staging arena; unrelated lightmap/probe/readback staging remains under its owning paths.

## 23. Model translucency lacks true depth sorting

`hw_models.cpp` explicitly notes that culling is used to mitigate lack of proper depth sorting. This is real technical debt but not a PF blocker unless a PF refactor regresses it. Track for post-PF renderer work if still relevant.

## 24. Experimental whole-scene raytrace view is distinct from normal ray-query shadowing

`gl_raytrace` can replace normal scene processing in `RenderViewpoint`. Do not conflate this viewer experiment with production world ray-query visibility.

## 25. Temporal rendering infrastructure is not a coherent baseline subsystem

HDR/depth/normal buffers exist, but motion vectors/history ownership/per-view invalidation are not established. Do not bolt temporal effects onto one global history buffer.

Owner for preparatory context: PF-010. Actual temporal effects are later work.

## Maintenance rule

When a PF issue resolves an item, replace the warning with:

- resolved issue/PR/merge commit;
- resulting invariant/contract;
- remaining limitation if any.

Do not simply delete historical traps; their provenance is useful when reviewing regressions or donor patches.