# SDVK-010 resource lifetime and transition stress design

**Status:** plan only / no native run / no production changes. Authority: PF-002 `{index,generation,epoch,span}`; PF-003 allocator-owned contiguous pairs; PF-004 LevelMesh owner + `LightmapProbe` and `Query` domains; PF-012 corrected probe mapping; PF-113 typed zero; CFX-009/PR #104 neutral atlas publication; SDVK-004 128-page/64-probe pressure. No actor-specific allocator or reset scheme.

## Identity and event vocabulary

- **A**: map-authored probe ordinal, includes real ordinal 0.
- **B**: runtime irradiation base, allocator-returned; 0 = no live probe, not authored0.
- **P**: adjacent pair descriptor B/B+1, valid only when both resources are published current cube views and the PF-003 identity has the same owner/generation/epoch/span=2.
- **G**: PF-003 allocator slot generation/epoch. A retired and reused slot can have numerically identical B but different G. Never infer freshness solely from B.
- **Eprobe**: `VkTextureManager::LightProbeEpoch`; `ResetLightProbes` advances it while existing image/view objects and B may remain live.
- **Elightmap**: `VkTextureManager::LightmapEpoch`; `CreateLightmap` advances on atlas recreation.
- **Emesh/EprobeMap/Equery**: LevelMesh resource, `LightmapProbe` and `Query` epochs. Geometry-dependent sun occlusion reuses Equery, not EprobeMap.
- **Eview**: PF-010 transient render-context epoch+identity; does not substitute for any persistent owner identity.
- **Page pair**: reserved atlas descriptors `LightmapsStart+2*page` and `+1`; removed page must bind initialized typed fallback before former page owners retire.
- **F**: explicit missing-pair runtime 0. The shader returns zero environment radiance; separate sector/direct/sun radiance can be nonzero.

Every run records actor+map/sector, source/render portal groups, A, B, P/G, Eprobe, Elightmap, Emesh/EprobeMap/Equery, Eview, atlas page and actual published resource views. Unknown observations fail acceptance rather than being guessed.

## Matrix

| ID | Trigger and source seam | Expected identity/state and fail condition | Native control |
|---|---|---|---|
| L01 | Startup before first probe publication, `GetLightProbeTextureIndex` | F=0, no B+1 lookup; later both cube views arrive before B becomes live | PF-113 fresh two-probe control; preserve first-unavailable/read timing |
| L02 | Publish first authored ordinal 0 | A=0, B nonzero, P span2, both cube views; F must remain false | Explicit negative against “authored 0 equals fallback” |
| L03 | Publish second probe while first live | B values allocator-assigned, never computed from ordinal; pair identity disjoint | Change allocator pressure so token ordinal arithmetic fails |
| L04 | Change count 2→0→2, `LightProbeIncrementalBuilder::Step` / `ResetLightProbes` | Eprobe advances on each reset; cleared views may keep B/G live, but radiance and availability reflect clear/publication state | Distinguish *content reset* from actual *slot retirement* |
| L05 | Add one authored probe at runtime, `InvalidateLightmapProbeSelection` | Recalc sector/side authored targets; `ReceivedNewLight` dirty; EprobeMap advances; world texels refreshed | Exact stage order and pair identity; don't mutate via observer |
| L06 | Relocate moving actor across two sector targets | Actual sector A changes where intended, B current; no persistent stale unrelated probe | Fixed actor positions and camera; also static actor/camera movement |
| L07 | Cross per-texel nearest-probe boundary in copied tile | R16_UINT B correctly mapped; 512 inclusive and first-entry tie; shader gather retained weights | Reference `HWProbeSelection::FindClosest` CPU + emitted GPU texels |
| L08 | Atlas rebuild at constant probe set, `CreateLightmap` | Elightmap advances; current page resources and descriptor publication agree; persistent B unaffected unless separately reset | Compare page identities before/after rebake |
| L09 | Shrink lightmap 128→3 pages | Former page descriptors publish private typed zero fallback before old owner fence deletion; no stale view | Reuse SDVK-004/CFX-009 contract |
| L10 | Atlas page count above 128 / invalid CPU page | Bounds fail closed before writer; no forged page descriptor, no truncation | Host negative; do not submit invalid GPU access |
| L11 | Runtime B>65535 in candidate upload | Omit candidate; R16_UINT map fallback or another valid candidate, never truncate to unrelated pair | Offline selector negative + actual drop telemetry if available |
| L12 | B allocator slot retirement/reuse | PF-003 G changes/old token rejected; new probe may happen to reuse same numeric B without aliasing | Host stale-generation negative; GPU controls only valid current resources |
| L13 | Level change/reload 20× | Emesh changes and/or ownership changes, stale per-sector A/B/atlas refs never resolve from previous map | Actual map/actor/probe identities in both captures |
| L14 | Toggle `gl_lightprobe` and `gl_levelmesh` | Explicit availability/fallback or retained valid publication, no false stale token; do not assert toggles necessarily delete images | Compare exact settings and observed producer stages |
| L15 | Repeat actor movement across boundary 100× | Stable authoritative A/B pattern under constant world/probe owner; no cumulative descriptor leak or stale sampling | Small bounded CPU/event samples; normal no-per-fragment generation guard |
| L16 | Portal group / linked displacement change | Query context and source/render portal group remain coherent; trace visibility invalidates when stable group changes | PF-015 world Query + group, no Eview cache key invented |
| L17 | Moving floor/wall / 3D-floor occluder with stationary actor | Equery advances on LevelMesh world update; CPU `TraceSky` cache invalidation; EprobeMap only if probe-map dependency changed | Distinguish geometry from probe rebake; source expected epoch before implementation |
| L18 | Mirrored child view after main view | Eview differs and mirror parity is correct; actor persistent probe owner/G/Eprobe unchanged absent actual world mutation | PF-010 nested portal and separate shader orientation oracles |
| L19 | 64 simultaneous environment pairs + rich materials | PF-003 allocator span and generation all valid; pressure does not reassign A or eliminate legitimate samples | Reuse existing SDVK-004 host and software-Vulkan workload |
| L20 | Probes clear while atlas pages remain (zero probe state) | Existing R16_UINT probe maps transfer-clear/re-published to 0; Eprobe advanced; no sampled retired cube | PF-012 zero-count and CFX-009 publication ordering |
| L21 | Shader no-probe, mixed zero/live, all-live taps | Zero tap never samples fixed 2D slots 0/1 as cube; live samples keep original four weights/ordered sums/LOD; independent direct Lo unchanged | Reuse PF-113 source extraction/native readback comparisons |
| L22 | Portal mirror followed by camera-only movement | Authoritative actor A must not be overwritten by observer or transient view state; reflection can legitimately change | State assertions separate from RGB |
| L23 | Actor without sector / particles while authored0 is published | No assumption that default authored0 is fallback; existing observed B may be nonzero; unresolved explicit actor absence policy recorded | Negative semantic fixture, do not modify production now |

## Diagnostic ordering and rejection policy

At native draw time capture the *already selected* `mLightProbeIndex` and already published `uLightProbeIndex` (PF-113 has the precedent) plus actual image/view type and identities. Do **not** call `GetLightProbeTextureIndex` from an observer: it may allocate an adjacent pair. Snapshot existing allocator identity through PF-003 public access only. For B>0, prefilter is **only** inspected after B and pair-owner span=2 validity have been established; B+1 is not a legal fallback computation.

Distinguish 3 states: (a) allocated current pair with fully published live radiance; (b) allocated current pair whose images were content-cleared at Eprobe transition and whose publication is pending; (c) retired pair invalid by PF-003. (b) may keep B+G unchanged yet *must not* show pre-reset radiance; avoid falsely requiring `G` to change during content reset. Separate map owner and descriptor pair identity from authored ordinal; logging an old B alone proves nothing.

A failure must include the minimized actor frame/sector/group, trigger, first bad event, pair slot/generation/epoch/span, page count + atlas owner epochs, probe and world Query epochs, view context, shader/material, and capture-independent reproducer. Skip unsafe negative GPU descriptor access; use offline mock/state fixture instead. Lifetime evidence can be native semantic state and legal readbacks; never launch stale pointers to “see if it crashes.”

## Stop gates

- PF-012 selector or CFX-009 typed-neutral lifetime mismatch is foundational; block #10 and identify regression owner rather than patching an actor workaround.
- No accepted #7 normal orientation: only generic N/V/R math and offline assets qualify.
- Aesthetic probe blending not adopted: keep discrete actor target and document hard boundaries.
- Insufficient actor native instrumentation: output **unknown**, not a passing screenshot.
- Physical GPU unnecessary absent a concrete driver/hardware-specific failure.

**This table is future qualification design, not evidence of completed resets, Vulkan draws or actor IBL.**
