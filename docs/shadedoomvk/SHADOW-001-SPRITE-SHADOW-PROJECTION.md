# SHADOW-001 — Stylised Raster Sprite Shadow Projection

**Proposed GitHub issue and implementation specification**  
**Programme:** ShadeDoomVK — *The Lost 2003 Remaster*  
**Status:** OWNER-APPROVED DESIGN. Implementation still requires a scoped branch/PR, normal review, and the applicable acceptance policy.  
**Priority:** First flagship visual feature.  
**Proposed branch:** `feature/shadow-001-raster-proxy` (illustrative, not created).  
**Relation:** Supersedes the proposed future scope of legacy SDVK-012/#12 and selectively absorbs SDVK-013/#13. Does not claim to complete their historical acceptance contracts.

## Issue summary / product promise

> A Doom II sprite should cast a beautiful, legible, light-relative shadow that feels at home in Doom 3 and early Splinter Cell **without ceasing to be the original Doom II sprite**.

Deliver an opt-in, entirely rasterised **sprite-shadow proxy** system: generate a separate medium/high-resolution smoothable alpha silhouette from existing sprite artwork, allow optional artist cutouts, and project the silhouette onto eligible world receivers from an appropriate light. The visible sprite's source pixels, animations and gameplay remain unchanged.

**Acceptance image:** a zombieman beside a strong side light casts a readable, rifle-bearing silhouette across a corridor floor, with crisp edges and recognizable arm/leg gaps. Walking the camera around him must not cause the shadow to spin merely because the billboard rotates. The effect must work with Vulkan ray-query support disabled.

## Existing source and technical distinction

Inspect current `master` before implementation, especially:

- `src/rendering/hwrenderer/scene/hw_sprites.cpp`: `HWSprite::Process` already supports an inexpensive `isSpriteShadow` path. It snaps to `thing->floorz`, scales sprite height by `0.15`, applies black translucent `STYLE_Stencil`, optionally height-fades with `r_actorspriteshadowalpha`/`r_actorspriteshadowfadeheight`, and uses current viewport-relative frame selection. It is an **inherited ground-shadow rendering style**, not a full world-projected silhouette or stencil-buffer shadow volume.
- `src/rendering/hwrenderer/scene/hw_sprite_surface.h`: existing presentation decisions for face/wall/flat/model sprites, billboard modes and mirroring. Reuse the existing semantics rather than introducing a second inconsistent sprite-rotation implementation.
- `src/rendering/hwrenderer/scene/hw_sprite_tangent.h`: accepted sprite basis and mirror conventions. Reuse where physically meaningful; shadow proxy basis is light-relative, not identical to visible-camera basis.
- `src/rendering/hwrenderer/scene/hw_drawinfo.cpp`, `hw_spritelight.cpp`, and `docs/shadedoomvk/rag/05-LIGHTING-SHADOW-TRUTH-TABLE.md`: actor lighting, existing shadow-map and world-occlusion modes, PF-015 actor/portal cache contracts. None automatically provides alpha-tested sprite shadow geometry.
- `docs/shadedoomvk/rag/07-PORTAL-COORDINATE-SPACES.md`, `08-VULKAN-PIPELINE-CAPABILITIES.md`, `04-MATERIAL-SHADER-CONTRACT.md` and the relevant `AGENTS.md` rules.

**Avoid terminological confusion:** a literal Doom 3 stencil shadow volume extrudes watertight silhouette geometry and updates the stencil buffer for shadowed receivers. The proposed first production path is a **receiver-projected alpha/distance-mask technique**; it may use ordinary depth/stencil receiver clipping, but it is *not* a volumetric shadow algorithm. A true extruded stencil volume may be studied later only if clearly superior for a concrete receiver problem.

## Non-negotiable visual constraints

1. **Never upscale/smooth the displayed sprite as part of this work.** Source albedo, pixel edges, animation frames, alpha cutout and pose stay unchanged.
2. **Separate shadow proxy from sprite material.** A smoothed shadow mask does not modify diffuse, PBR, normal, height or collision data.
3. **Shadow is light-relative, not camera-relative.** Camera movement alone cannot change the selected shadow-facing pose or make its orientation pivot around the actor.
4. **Exaggeration is allowed.** Controlled contour rounding, hole cleanup, arm/leg/weapon cutouts, silhouette stretching and artist-authored masks are valid aesthetic choices, provided they remain recognisable and do not introduce distracting motion.
5. **Prefer hard and near-hard edges.** The default should evoke early-2000s theatrical shadowing. Antialias the projected edge enough to prevent crawling; optional softness must remain selective.
6. **No hardware ray tracing or ray queries are required.** The ordinary Vulkan raster backend remains sufficient; existing ray-query capability may be disabled.
7. **No gameplay coupling.** Shadows do not alter gameplay visibility, actor state, demo ticks, collision or content rules.
8. **Honest fallback.** Unsupported actors, materials, portals and receiver conditions get Contact/Legacy/Off, not speculative shadow geometry.

## Proposed v1 architecture

### 1. Shadow-proxy asset pipeline

At offline authoring time, or cached at content load when needed, create an independent shadow proxy from the sprite's alpha channel:

1. Acquire the **actual sprite frame and rotation** with source content identity, native dimensions, offsets, scale/mirror policy and logical pivot. Do not assume every sprite uses the same rotation layout.
2. Threshold or preserve alpha coverage using a defined rule. Differentiate exterior background from intentional gaps and translucent content.
3. Upsample the *mask only*, initially testing **4×** contour resolution against **8×** for high-value silhouettes. Use a bounded edge-aware or contour-first cleanup; smoothing should not turn hands, rifles, horns and leg gaps into unrecognisable blobs.
4. Remove tiny disconnected noise and close obvious one-pixel pinholes **only where configured**; preserve significant holes and interior negative space. Expose controlled erosion/dilation instead of always expanding the shape.
5. Apply optional authored **subtractive cutouts**, optional additive silhouette strokes, or a complete per-frame override mask; place edits in source-image coordinates with explicit pivot/scale alignment.
6. Export/cache either an **R8 filtered alpha mask** or a **signed-distance field (SDF)** derived from the cleaned contour. Evaluate both on visual quality and actual cost. SDF is a compact *modern implementation convenience*, not a claim that Doom 3 used it.
7. Deduplicate shared frames, cache by content identity + sprite frame/rotation + generation settings + override revision, and invalidate stale entries safely on map/content/resource changes. Bound atlas memory.

Start with an R8 alpha implementation for minimal integration cost; use SDF if the fixed screen-space edge threshold/penumbra is materially better. Do not make a full-blown texture authoring editor a prerequisite.

**Artist control:** normal sprite remains pristine; its separate caster mask can be more graceful than its pixel silhouette, including hand-authored gaps that produce distinctive “Splinter Cell” shadow language.

### 2. Pose, orientation and light selection

At runtime, derive caster pose from the actor's **logical facing + current animation frame**, with the **light-to-actor direction** selecting the closest appropriate source rotation/override. Reuse existing rotation, flip and sprite offset conventions; **do not reuse the currently camera-selected frame as the caster without independent selection**.

- Support opaque standard face sprites first; special sprite types, translucent/fuzz actors and model renderers use explicit fallback until supported.
- Prefer one **dominant eligible local light per caster** in v1. Candidate relevance should account for source intensity, distance, cone eligibility and actor/receiver context. Make changes stable (hysteresis or a bounded explicit owner policy); do not snap rapidly between equivalent lights.
- The flashlight can act as a useful primary scenario, but do not hard-wire it or assume every light is attached to the player.
- Use the actor's render-interpolated pose only; never drive gameplay state from the shadow.
- Correctly transform actor/light/receiver coordinates for supported portal groups. If a receiver cannot be represented consistently, omit projection and keep cheap contact grounding.
- If an actor is airborne, the shadow may lengthen and soften/fade with height, but it must remain planted on the actual eligible receiver rather than an arbitrary global Z=0 plane.
- Falling back to a stable canonical proxy is preferable to adopting the current player's camera-facing art and causing obvious rotational discontinuities.

### 3. Raster projection onto receivers

**v1 target: one light, one standard floor receiver, one actor**, with depth-tested clipping and sane bounds. Later support the nearest eligible wall/step/controlled 3D-floor receiver if a first-stage visual prototype proves valuable.

One viable method: define a virtual 2D silhouette card located on the actor and oriented relative to the casting light, then project it into a floor receiver using the light ray through each mask point. For a point light at `L`, a point `P` on the caster proxy and a receiver plane containing `Q` with normal `n`, the projected point is:

`X = L + t(P-L)`, where `t = dot(n, Q-L) / dot(n, P-L)`.

Only use valid forward intersections (receiver behind the proxy relative to the light), reject nearly parallel rays, bound shadow length and clip to legitimate receiver geometry. The expression describes a projection candidate, **not** a demand to implement arbitrary 3D stencil-volume extrusions.

Implementation alternatives to scout before coding:

- **A — Raster receiver projection/decal:** project a bounded mask polygon to the floor/receiver, clip using depth/sector/portal identity, and modulate the receiver's local illumination or apply a deliberate darkening layer.
- **B — Receiver-shader sampled projector:** compute shadow-mask UV from receiver position and projector state in an existing shading path. May avoid separate decal geometry but increases integration/overlap complexity.
- **C — Actual contour-extruded stencil volume (research only):** polygonise the cleaned contour into closed geometry, extrude from light, handle caps/z-fail, and rasterise stencil occupancy. This is **not v1**, especially not if it creates excessive silhouette tessellation or fill-rate cost on older GPUs.

**Default implementation recommendation:** A, unless a short source spike proves B integrates more cleanly. Verify that the chosen ordering respects opaque depth and translucent sprites, and does not produce shadow-through-wall or double-darkening when existing world shadows are enabled. Renderer architecture must be surveyed before selecting the exact render pass.

### 4. Shading and style

Ideally the projected mask attenuates only the **selected casting light** on its receiver; it should not erase unrelated local lights or all sector ambience. If the initial implementation uses a cheaper bounded **dark decal approximation**, label it honestly, limit opacity and test interactions with multiple light sources. Do not allow black decal accumulation to create implausible double shadows.

The effect's visual controls should be few and meaningful:

| User control | Suggested baseline | Notes |
| --- | --- | --- |
| Mode | Legacy / Contact / Projected | Default to existing behaviour until user acceptance; no hidden enablement |
| Hardness | Hard with small edge AA | Optional slight smoothing for selected masks |
| Strength | Medium–high | Aesthetic, not fixed physical occlusion |
| Length | Bounded by light/receiver | Prevent unlimited stretch/screen fill |
| Caster budget | Explicit quality-tier setting | Avoid surprise N-lights × N-actors behavior |

Expert overrides may include per-actor bias, contour correction, cutout path, fade and light-selector hysteresis. Expose active mode, selected light, proxy frame and fallback reason in an opt-in debug view, not an always-on intrusive diagnostic overlay.

### 5. Fallback and quality tiers

Provisional design knobs for measurement, **not validated performance claims**:

| Tier | Visible result | Initial bounded implementation target |
| --- | --- | --- |
| Legacy | Exact inherited sprite-shadow behaviour | No new projection work |
| Contact | Cheap flattened/elliptical grounding with height fade | No per-light projection |
| Projected | One dominant light, cleaned mask, eligible floor receiver | Start with **8 simultaneous projected actors**, adjustable after measurement |
| Enhanced | Higher proxy quality, authored cutouts and optionally wall receiver | Start with **16 simultaneous projected actors** on capable hardware |

Use distance/importance selection and an explicit fallback when the budget is exhausted; never silently evict source sprites, material layers or the actor itself. A starting **16 MiB proxy-atlas cap** and **512×512 maximum cached single-mask dimensions** are provisional candidates to test; atlases may need other policies after profiling. A 4×/8× *processing* upscale does not require shipping a 4×/8× uncompressed GPU texture for every animation frame.

Aspirational target: no more than approximately **1.5 ms incremental GPU frame cost** at 1080p for an eight-caster Projected scene on GTX 1650 SUPER-class hardware, with a separate clear baseline and distribution. **This is an engineering hypothesis, not a pass/fail gate or a measured result.** Adopt actual budgets after representative measurement under a separately authorised hardware policy. No requirement to achieve projected shadows on a P400-class GPU; Contact/Legacy must remain available and practical.

## Editable proxy data contract (proposal)

Avoid content-specific hard-coded renderer edits. Associate a shadow proxy with a stable *logical source sprite/frame/rotation/flip* and content identity. The following is illustrative JSON; schema and engine integration need a brief source-owned spike:

```json
{
  "schema": "shadedoomvk.shadow-proxy.v1",
  "source": {
    "sprite": "TROO",
    "frame": "A",
    "rotation": 3,
    "flipped": false,
    "alpha_sha256": "SHA256_OF_INPUT_ALPHA"
  },
  "pivot_uv": [0.5, 0.94],
  "override_mask": "shadowproxies/troo_a3_alpha.png",
  "subtract_cutout_mask": "shadowproxies/troo_a3_cutouts.png",
  "contour": {
    "working_upscale": 4,
    "cleanup_radius_source_px": 0.6,
    "expansion_source_px": 0.0
  },
  "style": {
    "strength": 0.72,
    "edge_softness_screen_px": 0.8,
    "length_cap_world_units": 192.0
  }
}
```

Paths are illustrative, *not* an established PK3 namespace or a published schema. Define final packaging, precedence, source-identity and fallback semantics only after confirming existing texture/archive conventions. Cache keys must distinguish differently replaced texture lumps and live game content. Do not distribute third-party game assets or derived masks in the public repository without licensing clearance; keep generated assets local and use original/copyright-free fixtures in CI.

## Staged implementation — small vertical slices

### M0 — source inventory and visual fixture (no Vulkan algorithm work)

- Confirm current shadow draw path, render pass ordering, actor rotation/flip translation and available receiver/depth/stencil interfaces.
- Create a copyright-free minimal opaque humanoid sprite/receiver fixture, plus locally generated Doom II demonstrations from legally owned content.
- Define a reproducible **visual acceptance composition**: one zombieman/imp, one side light, one floor, mask OFF/ON. Document what is currently unsupported.
- Choose renderer integration A or B and explain why it is the smallest viable implementation.

**Exit:** explicit implementation seam and a useful before image; no new large shadow infrastructure.

### M1 — first recognisable floor projection

- Generate one smoothed alpha proxy; render from one stable light onto one ordinary floor; project a hard shadow with appropriate depth clip.
- Test stationary, moving and rotating actor; circling camera must not rotate the proxy.
- Preserve legacy/contact fallback, game tic semantics, current sprite/palette and normal/PBR material output.

**Exit:** owner can actually see a dramatic, stable shadow in a minimal test, with OFF/ON comparison.

### M2 — robust mask authoring and projection

- Add per-frame/rotation auto-generation and cache, mirrors/actor animation, stable light selection, bounded mask smoothing and optional hand-authored cutout overrides.
- Compare R8 and SDF only if beneficial; prefer the simpler method if quality differences are marginal.
- Add actor unload/replacement cache invalidation and explicit shader/receiver fallback diagnostics.

**Exit:** several ordinary enemies/pickups cast recognisable shadows; no obvious pop/crawl in common views.

### M3 — optional world receivers and artistic polish

- Add a narrow wall/step receiver prototype or explicit non-support disposition. Test portals and 3D floors in an isolated capability-aware fixture rather than make them a mandatory universal requirement.
- Test interaction with the existing dynamic world shadow map and PBR lighting, without accidental double-darkening.
- Expose one-page quality controls, performance tiers and troubleshooting.

**Exit:** practical configurable feature suitable for preview, with known receiver limitations documented.

Each milestone should be a reviewable, owner-visible PR/draft or checkpoint **under the revised CI policy once it is adopted**. No giant all-or-nothing shadow rewrite. Do not add M3 scope just because M1 looks compelling; reassess the value/cost after each stage.

## Acceptance and test policy

### Must pass before claiming M1 as delivered

- **Visible impact:** projected shadow is immediately recognizable and meaningfully more expressive than inherited Contact; compare OFF/ON in the same composition. M2 adds an authored cutout demonstration.
- **Source fidelity:** source albedo pixels, sprite rotation/flip handling, animation timing, alpha and gameplay/collision are unchanged.
- **Camera independence:** a camera orbit with unchanged actor and light does not swivel the cast shadow because the visible billboard frame changes.
- **Correct placement:** shadow is anchored to the actor/light and appears only on one eligible floor receiver; no projection across an intervening wall or above floor height.
- **Stability:** walk/turn/animation and light movement do not cause persistent floating, visible shadow trails, unbounded stretch or pathological switching.
- **Fallback:** OFF/Legacy and Contact work, and running with Vulkan ray queries disabled works.
- **Safety/build:** affected builds pass, no new resource-lifetime failures, no visible shader artefacts from invalid data or texture/generation reuse, no crash.
- **Performance:** report baseline vs effect and work counts under the available authorised environment. No performance claim based solely on code shape or hosted llvmpipe timings.

### Focused automatic tests

- CPU: proxy bounds/pivot, mirrored source orientation, offset transforms, mask interpolation, cutout alignment, bad source/override rejection, cache invalidation, near-parallel projection, behind-light/receiver rejection, length clamp, actor removal.
- Shader/offline: mask extraction output and SDF coverage if used, finite UVs and no NaN, no texture read outside valid atlas, preview with no ray query extension.
- Hosted software Vulkan: one positive bounded projection, one light-relative camera-orbit counterexample, one wrong-receiver prevention case and effect-off equivalence in the same test configuration.
- Human visual: Doom II/DBP50 legally owned content, sharp specular scene, industrial slat light and fast moving actor, documenting image quality *subjectively but explicitly*.

Use compact source identity and targeted failed attachments. **Do not require pixel-perfect equality across unrelated frames, exact CPU submission-count matching across valid runs, a large negative-control forest or multi-hour publication qualification for routine M1/M2 iteration.** New safety/correctness defects still block their own affected scope. Existing repository CI rules remain authoritative until amended by owner-approved policy changes.

### Open risks, not blockers for M1 unless reproduced

- Multilight blending/selection of several simultaneous casters.
- Wall, stair, sloped floor and controlled 3D-floor geometry beyond the first supported floor case.
- Sprite types with fuzzy, translucent, additive or sprite-replacement rendering.
- Portal recursion/mirrors where placement or shadow energy is ambiguous.
- FOV extremes, tall bosses, arbitrary custom shader sprites and model shadow parity.
- Dense scenes on the oldest Vulkan GPUs.

Known unsupported paths must **fail safely and visibly fall back**. Do not misrepresent limited v1 scope as universal.

## Hard stops and scope limits

- No changes to Doom actor simulation, movement, collision, tick timing or content semantics.
- No mandatory ray tracing, path tracing, ray-query / acceleration-structure sprite shadow dependency.
- No automatic visual-sprite smoothing, source replacement, PBR channel mutation or global TAA pass.
- No new universal world-shadow architecture or mandatory clustered-light work as a prerequisite.
- No blind GPU fault reproduction, physical hardware setting changes or physical test execution without a separate owner authorisation; **repository's recorded physical STOP remains active**.
- Do not copy Doom 3 production shadow-volume code merely to imitate the period. Historical source is a reference, not a donor approval.
- Do not merge or close #12/#13 solely because this issue has been created. Preserve their useful concepts and record explicit transfer on owner-approved supersession.

## Required outputs

- Small runnable SHADOW-001 scene and OFF/Contact/Projected comparison captures.
- Clean versioned proxy-generator source, minimal editable metadata sample and synthetic fixture assets.
- Raster projector integrated on one bounded path, with debug fallback reasons and opt-out.
- Focused CPU/hosted software-Vulkan tests and concise owner playtest instructions.
- Performance report with exact scene/settings/mode, but without overclaiming physical stability.
- Short architecture note: chosen method, why actual stencil volumes were deferred, known receiver/actor limitations and the result of the owner visual review.

**Definition of done for the first preview:** one actor + one light + one floor looks compelling in live play; common actors remain stable; every supported case has bounded, maintainable behavior; unsupported cases fall back; original sprite presentation survives untouched. A complete stencil-volume research programme is expressly **not** required.

---

## Proposed Codex implementation brief (copy/paste)

Implement SHADOW-001 only after reading current `master`, `AGENTS.md`, relevant RAG/source and the owner-approved refreshed campaign policy. Preserve all existing physical-test restrictions. Start with M0→M1: inspect the inherited sprite-shadow path, make one source-grounded raster floor projector from a separately smoothed alpha proxy, select the light-relative sprite frame independent of the camera, and retain Legacy/Contact/Off fallback. Use a minimal copyright-free fixture and focused tests. Produce one owner-playable OFF/ON demonstration before expanding to masks for all sprite types, additional lights, portals or wall receivers. No ray queries, gameplay changes, image smoothing of visible sprites or literal Doom 3-style stencil volumes. If an integration decision is uncertain, document the smallest alternatives and choose the least invasive approach, with a clear reversal path. Do not launch unauthorized physical GPU tests, override current CI rules without a superseding approved decision, merge or close founding issues.

## References

- Campaign charter: `SHADEDOOMVK-2003-REMASTER-CAMPAIGN.md` (companion proposed file).
- Current base: https://github.com/techrote/ShadeDoomVK
- Legacy sprite shadow proposal: https://github.com/techrote/ShadeDoomVK/issues/12
- Legacy hybrid shadow plan: https://github.com/techrote/ShadeDoomVK/issues/13
- Material showcase: https://github.com/techrote/ShadeDoomVK/pull/190
- Doom 3 stencil volumes (historical example): https://github.com/id-Software/DOOM-3/blob/master/neo/renderer/tr_stencilshadow.cpp
- Shadow volume primer: https://www.opengl.org/archives/resources/code/samples/sig99/advanced99/notes/node194.html
- Alpha/SDF edge reconstruction, 2007 Valve research (optional technique, not historical Doom 3 claim): https://cdn.fastly.steamstatic.com/apps/valve/2007/SIGGRAPH2007_AlphaTestedMagnification.pdf