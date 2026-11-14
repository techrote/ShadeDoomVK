# ShadeDoomVK — The Lost 2003 Remaster

**Campaign charter and visual/engineering guidebook — owner-approved, 14 November 2026**  
**Status:** OWNER-APPROVED CAMPAIGN DIRECTION. Engineering acceptance/CI changes are implemented separately under R-001 and become authoritative only when reviewed and merged. No physical GPU testing is authorised by this charter.  
**Historical repository reference:** `techrote/ShadeDoomVK`, `master@f787f7199fc7560588bb9440b3dd0aa663cb53de` at the approved planning checkpoint. Reconfirm `master` at implementation time.

> **North Star:** Make Doom II look the way a PC gamer in 2003 might have dreamed the ultimate Doom II remaster would look: unmistakably original art, physically evocative materials, powerful dramatic lighting and theatrical shadows, all produced by controlled real-time illusion rather than a demand for photorealism.

## Contents

1. [Mission and experience](#1-mission-and-experience) — What the player should see and feel.
2. [Art-direction laws](#2-art-direction-laws) — Preserve original pixels while selectively enriching surface response and shadows.
3. [Rendering doctrine](#3-rendering-doctrine) — Raster-first, light- and artist-directed, scalable to older Vulkan GPUs.
4. [Design reference interpretation](#4-design-reference-interpretation) — What to take from Doom 3 and early Splinter Cell, and what not to copy.
5. [Programme slate and sequencing](#5-programme-slate-and-sequencing) — The refreshed issues, their concrete outputs, and real dependencies.
6. [Verification and evidence policy](#6-verification-and-evidence-policy) — Proportionate, risk-based tests and finite investigation budgets.
7. [Hardware and user-facing quality](#7-hardware-and-user-facing-quality) — Explicit modes, fallbacks and provisional performance targets.
8. [Preview acceptance guide](#8-preview-acceptance-guide) — A repeatable visual playtest that produces useful decisions.
9. [Historical transfer and migration](#9-historical-transfer-and-migration) — Preserve the founding programme's gains without perpetuating its blockages.
10. [Immediate owner decisions](#10-immediate-owner-decisions) — What approval of this charter would and would not authorise.

## 1. Mission and experience

The product is **not** “the most advanced Doom renderer available regardless of cost.” It is a **faithful, knowingly artificial, millennial-era graphical reimagining**. The emotional target is the first encounter with convincing real-time 3D: metals gleam; a torch suddenly makes a zombieman's rifle look tangible; an imp's shadow stretches across a tiled floor; doors and equipment feel substantial; the original sprite still reads as the original sprite.

The highest-value effect is not necessarily the most computationally advanced. Prefer a convincing, understandable illusion that can be tuned by the artist and exercised in ordinary gameplay over a comprehensive physical model that erases the intended character of the image.

**The central quality question:** “Does this make classic Doom artwork more evocative, more spatially present and more playable while remaining unmistakably Doom?”

The era is an **aesthetic reference, not a hardware restriction**: modern Vulkan and offline generation are welcome where they deliver the right result efficiently. Do not introduce retro limitations for their own sake.

## 2. Art-direction laws

1. **Original artwork is the foundation.** Do not automatically replace or blur visible albedo pixels, animation, sprite silhouettes, scale, palette translation or poses. Any visible-art replacement needs separate deliberate opt-in.
2. **Material richness is layered on.** Procedural normal, metallic, roughness, specular and AO interpretations may add convincing response to existing art. A metallic switch housing can shine while the button, paint, rust, wood or moss remains dielectric.
3. **The shadow is a separate artwork.** The *shadow caster mask* may be upscaled, antialiased, contour-smoothed, cleaned and hand-modified; the displayed sprite should not be. No implied change to the underlying collision or visual sprite geometry.
4. **Light should be theatrical.** Strong local sources, sharply defined illuminated areas, purposeful darkness and readable shadow patterns are first-class. Avoid uniformly flattening contrast through compulsory global illumination.
5. **Preserve visual authorship.** Offer simple global controls and bounded per-actor/material overrides. A plausible physical response is a starting point, not a compulsory result.
6. **Keep gameplay semantics.** Rendering must not change collision, Doom tics, AI, line-of-sight gameplay logic, demos, damage, animation timing or content load order.
7. **Truthful nomenclature.** A raster-projected cutout is a projected sprite shadow, not fully volumetric geometry or ray tracing. A sprite relief shader is not mesh displacement. A light probe is not full dynamic GI.
8. **No gratuitous cinematic processing.** No obligatory TAA, aggressive blur, ghosting, chromatic aberration, film grain or supersampling of the *visible original sprites*. Apply smoothing selectively to shadows and other secondary effects only when it improves the presentation.

## 3. Rendering doctrine

**Default: raster-first.** The refreshed campaign does not require hardware ray tracing or path tracing for any flagship effect. The renderer may retain its existing optional ray-query world-visibility capabilities for compatibility/experimentation; the proposed sprite-shadow feature must work independently of those capabilities, with the ray path disabled.

Preferred toolkit:

- Forward/forward-like rasterised dynamic lighting with selected artist-friendly falloff.
- Raster PBR material response with localized metallic/dielectric masks, not mandatory photorealistic environment lighting.
- Opaque geometry depth, receiver masks, bounded shadow projection, conventional shadow maps where already useful, and contact grounding.
- Compact preprocessed alpha or signed-distance shadow proxy atlases.
- Hard-edged shadow silhouettes with modest screen-space antialiasing; optional *small* adjustable penumbra, not a global soft-shadow mandate.
- Graceful, explicit per-effect budgets and fallbacks rather than requiring a newly invented universal many-light system.

**Stencil terminology:** Doom 3 used polygonal stencil shadow volumes; ShadeDoomVK already has an inherited `STYLE_Stencil` black sprite-shadow *render style*. These are different technologies. `STYLE_Stencil` is not evidence that the engine already constructs volumetric stencil-buffer shadows. The initial sprite-shadow production design should use **receiver-space projected masks**, potentially stencil/depth-clipped, rather than assume extruded closed volume meshes. A literal shadow-volume branch is a bounded optional experiment only if it earns its complexity.

## 4. Design reference interpretation

**Doom 3 (2004):** Massive forms emerging from deep darkness; brilliant, deliberately concentrated highlights; aggressive local-light contrast; crisp hard shadows. Learn from its feeling of impossible technical advancement and heavy presence, not its models, assets, palette or horror content. Doom 3's stencil volumes are a useful historical touchstone, not an implementation mandate.

**Splinter Cell (2002):** Venetian-blind, grille, doorway and equipment shadows that articulate the geometry of rooms. The player can read the light source, the intervening shape and the receiver immediately. The “Splinter Cell effect” means *designed shadow readability*, including authored cutouts or simplified caster masks where appropriate, not necessarily a physically exact source-to-surface simulation.

**Doom II (1994):** Exact sprite personality, readable monsters, harsh contrasts, iconic weapons, palette and texture composition. Never let the 2003-inspired effects overwhelm these foundations.

The three reference images supplied in the planning conversation are **art-direction references only**; this charter does not redistribute them or purport to license their publication in the repository.

## 5. Programme slate and sequencing

The following labels are **provisional issue identifiers**, not actual GitHub issue numbers. Separate workstreams may proceed concurrently if they do not conflict in source ownership. No issue should depend on formal acceptance of the entire founding #8/#9/#12/#13 chain.

| Proposed issue | Priority | Output / acceptance in one sentence |
| --- | --- | --- |
| **R-001 — Development policy and CI reset** | Immediate enabling | Establish a risk-based short CI gate, optional deeper coverage and bounded evidence, with prior physical-test authorisations unchanged until separately reviewed. |
| **SHADOW-001 — Stylised raster sprite shadow projection** | Flagship #1 | Demonstrate light-relative shadows from improved sprite silhouette proxies with safe floors, expressive hard edges and a cheap contact fallback. |
| **MAT-001 — Material Forge** | Flagship #2 | Evolve PR #190's Doom II/DBP50 local material-generation showcase into configurable, per-material editable PBR interpretations without replacing source sprites. |
| **LIGHT-001 — Expressive lighting and viewmodels** | Flagship #3 | Refine flashlight, local-light response, sector/probe and first-person weapon coherence in real scenes. |
| **PERF-001 — Older-GPU performance and quality profiles** | Continuous | Measure real representative workloads, select explicit quality budgets and optimise proved hot paths rather than assuming a costly architecture rewrite is needed. |
| **WORLD-001 — Practical lightmap/probe workflows** | Selective | Make bake/rebake/load/update operations and ordinary world lighting dependable, with accepted lifecycle fixes preserved. |
| **PLAY-001 — Doom II 2003 preview** | Early milestone | Produce a playable opt-in showcase and small compatible build with defaults, instructions, known limitations and owner visual acceptance. |

**Sequencing:** R-001 policy must be agreed before *changing acceptance rules*; it is not permission to stall visual prototyping. SHADOW-001, MAT-001 and LIGHT-001 form the first visible wave. PERF-001 establishes cost measurements alongside them. WORLD-001 advances only on user-value or substantive defects. PLAY-001 starts early using the existing #190 gallery and can ship without future optional shadow subfeatures.

### Already delivered foundations worth reusing

- **PR #190:** local Doom II/DBP50 material packs, flashlight, optional gallery; generator currently covers 427 wall textures, 150 flats and 1,167 sprite lumps per supported pack.
- **PR #191:** corrected sprite POM albedo derivative sampling; preserve source pixel and alpha behavior.
- **PR #186:** explicit legacy, sector and enhanced viewmodel lighting, with ordinary-input gameplay smoke.
- **PR #192:** controlled 3D-floor lightmap ownership/receiver correctness.
- **PRs #193/#195:** shadow-off many-light measurements and a meaningful bounded spotlight shader optimisation.
- **PR #194:** static bake commandlet stall/wrong-target protections.
- **PR #202:** opt-in lightmap/probe GPU instrumentation, merged 14 November 2026 at `master@f787f7199fc7560588bb9440b3dd0aa663cb53de`; retained acceptance remains bounded, with physical STOP active.

Do not mislabel these bounded deliveries as complete acceptance of their founding parent issues.

## 6. Verification and evidence policy

**Owner-approved policy direction; implementation pending R-001.** Existing repository rules (including `AGENTS.md` and `06-VALIDATION-PERFORMANCE-CONTRACT.md`) remain binding until a reviewed repository policy change explicitly supersedes them.

### What should block

- A credible new crash, device loss, invalid GPU resource lifetime, OOB access, unsafe descriptor reuse or materially wrong rendering with an identified mechanism.
- Material gameplay or demo determinism changes introduced by renderer work.
- Obvious persistent missing geometry, broken silhouettes, uncontained shadow bleeding, egregious portal duplication or regressions to supported fallback paths.
- Required builds failing, or a demonstrably affected focused functional test failing for a substantive reason.

### What should not automatically block

- Tiny isolated pixel differences within an *explicitly defined visual tolerance*.
- A legitimate change in incidental resource epochs, CPU work counters or execution timing that does not change a supported functional invariant.
- An old unexplained statistical discrepancy with no credible consequence after a bounded, documented investigation.
- The absence of unrelated long-horizon provenance experiments or exhaustive research-grade repeatability campaigns.

A visually equal frame **does not** excuse a proven use-after-free, stale resource ownership or invalid Vulkan submission. Conversely, an unexplained variation is not *by itself* proof of one of these defects.

### Proposed tiered CI

- **Every PR:** compilation of affected targets, focused unit/source checks, representative renderer smoke (including option OFF), limited visual snapshots where relevant, source/asset identity. Target roughly 10–20 minutes when practical; measure actual feasibility.
- **Risk-triggered:** special-surface, renderer-resource, portal/mirror, stress, or hardware-correctness suites only if the changed code implicates them.
- **Release/nightly:** wider compatibility and performance sweeps, not a default mandatory dependency of every tiny PR.
- **Forensic investigation:** one bounded hypothesis, decision criterion and evidence budget; stop if no discriminating mechanism emerges. Preserve compact failed evidence, not redundant archives.

Historical failures and earlier exact comparisons remain historically true; this policy changes *future decision criteria*, not past data.

### Physical GPU testing

The repository records a physical GPU STOP associated with historical driver/device-loss incidents. **This proposal does not lift that STOP or authorise experiments.** A separate, explicit owner decision should distinguish ordinary gameplay evaluation on normal settings from deliberate hazardous reproduction and establish practical safe operating limits. Neither CPU llvmpipe success nor the existence of hardware samples automatically grants new physical acceptance.

## 7. Hardware and user-facing quality

The initial target is **older, broadly accessible Vulkan graphics hardware**, not RT-core hardware. A GTX 1650 SUPER-class card is a useful quality-target reference because previous repository work recorded results there; much weaker hardware should retain a functional low-cost profile. Do not promise P400 parity for every advanced effect without measurement.

Suggested user-facing modes (subject to owner preference and code inspection):

| Mode | Shadow treatment | Intended role |
| --- | --- | --- |
| Off / Legacy | Inherited render behavior only | Compatibility and reference baseline |
| Contact | Inexpensive actor grounding | Weak GPUs and crowded scenes |
| Projected | Single dominant light, clean hard-edged silhouette | Primary “2003 remaster” aesthetic |
| Enhanced | Projected plus optional authored cutouts, bounded wall receivers, small penumbra | Quality preset where performance permits |

Hardware eligibility is capability-based; the feature must have **no Vulkan ray-query requirement**. Budgets and LOD must be inspectable and reversible. The initial SHADOW-001 document carries **provisional, testable** numerical budgets, not historical benchmarks or promises.

## 8. Preview acceptance guide

Use a small playable showcase, not an exhaustive academic matrix. Inspect the same simple scenes with the effect OFF, Contact and Projected, holding game content, visible artwork, camera path and light setup fixed where possible:

1. **Zombieman under a sharp side light:** read head, shoulders, rifle and feet; shadow convincingly separates from actor as the light angle changes.
2. **Imp against concrete and metal:** observe claw/arm cutouts, shadow length, specular metal and dielectric dirt/moss staying distinct.
3. **Barred doorway or industrial grating:** combine environmental stripe shadows with actor projection; confirm a deliberate early-Splinter-Cell visual style rather than overlapping noise.
4. **Moving actor and circling camera:** actor-shadow orientation follows actor/light, not the camera-facing billboard frame. Animation changes must not create obvious shadow jumps.
5. **Uneven floor, stair/step and one wall receiver:** identify what is supported; unsupported geometry must fall back cleanly rather than draw a shadow through a wall.
6. **Busy firefight:** multiple actors, changing dominant lights and muzzle flashes; check stable cost, bounded actor selection and absence of persistent ghost shadows.
7. **Compatibility toggles:** Doom II and a compatible user-owned PWAD; verify original visible sprite texels and gameplay remain unchanged with SHADOW-001 disabled or enabled.

**Owner acceptance:** user reports that the enhancement looks unmistakably more atmospheric, honours the original art, exhibits no glaring unstable projection and does not compromise ordinary gameplay. Automated tests support this decision; they do not replace it.

## 9. Historical transfer and migration

Retain a slim, provenance-linked historical index before closing or superseding old issues. Transfer useful implementation, known limitations, root-cause reproducers and actionable research, **not** entire CI logs into Markdown.

| Founding issue | Proposed destination |
| --- | --- |
| #8 POM | SHADOW-001 only for tangent/height context; selective MAT-001 relief polish |
| #9 many lights | PERF-001; keep original collision/crash evidence and unresolved physical caveats |
| #11 viewmodels | LIGHT-001; preserve accepted #186 implementation |
| #12 prototype sprite casters | SHADOW-001 supersession, with raster-first owner decision replacing RT-neutral comparative obligation |
| #13 hybrid sprite/world shadows | SHADOW-001 later optional receiver/composition stage, not a blocking milestone |
| #14 lightmapper | WORLD-001 and focused consequential bug reports |
| #15 compatibility | PLAY-001 continuous representative smoke |
| #16 performance tiers | PERF-001, moved earlier |
| #17 final freeze | PLAY-001 playable preview; no all-predecessors gate |

Open CI PRs #187/#196/#197/#198/#201 should be independently disposed after reviewing reusable improvements against R-001; do not blindly merge their existing qualification burden. Open CFX/physical risk records need separate faithful disposition. Existing issue closures require **separate owner approval** and exact historical transfer comments; the new plan does not falsely satisfy original acceptance criteria.

## 10. Immediate owner decisions

The owner **approved this direction and authorised GitHub kickoff on 14 November 2026**, endorsing (a) the 2003-remaster artistic target; (b) raster-first sprite shadows with independently processed masks and optional authored cutouts; (c) a refreshed, non-serial issue slate; and (d) drafting an explicit risk-based acceptance policy.

That approval does **not** authorise: mass closure of founding issues, physical GPU experiments, publisher/content redistribution, modifications to gameplay, relaxation of proven Vulkan/resource safety rules, or merging outstanding CI PRs. Publishing this plan and creating new tracking issues is authorised. Policy changes require reviewed GitHub integration.

**Suggested first concrete work:** Implement the smallest working SHADOW-001 vertical slice on the existing sprite code. One zombieman, one light, one floor, one shadow proxy, clear OFF/ON comparison and bounded CPU/hosted software-Vulkan testing. Then assess whether the look is worth extending.

---

### Sources and starting references

- Repo: https://github.com/techrote/ShadeDoomVK
- Source baseline: `src/rendering/hwrenderer/scene/hw_sprites.cpp`, `hw_sprite_surface.h`, `hw_sprite_tangent.h` and `docs/shadedoomvk/rag/05-LIGHTING-SHADOW-TRUTH-TABLE.md`.
- Founding issues: https://github.com/techrote/ShadeDoomVK/issues/12 and https://github.com/techrote/ShadeDoomVK/issues/13
- Material showcase: https://github.com/techrote/ShadeDoomVK/pull/190 and `docs/shadedoomvk/DOOM2-SHOWCASE.md`
- Earlier Doom 3 renderer source, illustrative not a transplant requirement: https://github.com/id-Software/DOOM-3/blob/master/neo/renderer/tr_stencilshadow.cpp
- Stencil shadow-volume conceptual reference: https://www.opengl.org/archives/resources/code/samples/sig99/advanced99/notes/node194.html
- Optional SDF technique (published 2007; modern technique, not a claim about 2003 implementation): https://cdn.fastly.steamstatic.com/apps/valve/2007/SIGGRAPH2007_AlphaTestedMagnification.pdf