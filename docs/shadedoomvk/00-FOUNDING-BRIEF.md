# ShadeDoomVK founding brief

Status: founding contract with pre-foundation implementation-gate amendment  
Date: 2026-09-17

## Purpose

ShadeDoomVK is a Vulkan-first Doom-family renderer experiment built from VKDoom. The target is not to convert Doom into a conventional fully polygonal modern engine. The target is to make the existing 2.5D language—sprites, sectors, flats, walls, portals and classic mod content—participate in a much richer lighting/material system.

The visual reference is the class of effects explored in Steelmoth-style rendering: strong local dynamic lighting, materially responsive sprites, convincing contact/projected shadows, pseudo-volume, soft grounding and high-frame-rate visual motion. ShadeDoomVK must implement those ideas natively for Doom-family content rather than depend on private Steelmoth code/assets.

## Founding baseline

Repository baseline: VKDoom commit `09634479ab5bf9adf691074fffe85a006a398cd0`.

The inherited baseline already contains substantial modern infrastructure:

- Vulkan rendering;
- LevelMesh representation;
- bindless texture/material plumbing;
- normal/specular/PBR material paths;
- dynamic lights and sprite-lighting machinery;
- baked lightmaps, AO/bounce/sunlight infrastructure;
- light probes/environment lighting work;
- Vulkan ray-query/acceleration-structure world occlusion;
- dynamic/shadow-map/ray-query lighting paths.

The programme therefore concentrates on the missing or weak seams rather than rebuilding those systems from scratch.

Important deep-audit qualification: "already contains" does not mean every inherited subsystem is complete. In particular, per-lightmap probe selection and parts of probe-AABB integration are incomplete at the founding baseline; tiled-light infrastructure is dormant rather than an active clustered-light path. Conversely, per-layer material sampling and bindless slot reuse are already inherited and should be hardened/generalized rather than reimplemented as missing features. The canonical source-truth references live under `docs/shadedoomvk/rag/`.

## Primary goals

1. Make sprite materials respond correctly and predictably to world-space lighting.
2. Support explicit normal, height, roughness, metallic, AO and emissive semantics for sprite materials.
3. Add shallow pseudo-depth/relief that preserves Doom's sprite character rather than turning sprites into embossed plastic.
4. Make sprite lighting, probes, sunlight and viewmodels visually coherent.
5. Add scalable sprite-cast shadows and contact grounding without requiring every sprite to become full 3D geometry.
6. Retain VKDoom's efficient ray-query world occlusion and combine it with sprite-aware shadow techniques.
7. Modernize descriptor/light bookkeeping where richer materials and more dynamic lights expose architectural limits.
8. Keep the renderer measurable, diagnosable and compatibility-aware.

## Non-goals for the founding programme

- full path tracing;
- replacing all Doom sprites with meshes;
- making gameplay simulation frame-rate dependent;
- a mandatory high-resolution texture pack;
- automatic AI-generated replacement assets;
- wholesale UZDoom/GZDoom rebases without a measured migration case;
- Zandronum multiplayer/network-port work;
- claiming physically exact geometry from height/parallax effects.

## Rendering model

The target sprite material concept is:

```text
albedo ────────────────┐
normal ────────────────┤
height ────────────────┤
roughness ─────────────┤
metallic ──────────────┤──► sprite material / PBR lighting
AO ────────────────────┤
emissive/brightmap ────┘
                         │
                         ├── probes / sunlight / local dynamic lights
                         ├── world occlusion / ray query
                         ├── shallow parallax/relief
                         └── sprite-aware projected/contact shadowing
```

A normal map changes apparent surface orientation. A height map may change UV/depth interpretation. Neither changes the actor's authoritative gameplay collision or automatically creates real 3D silhouette geometry.

## Shadow architecture hypothesis

World geometry should continue to use LevelMesh/ray-query acceleration where it is effective. Actor shadows should be hybrid and quality-scalable:

- `OFF` — no extra actor shadow;
- `BLOB` — cheap existing/contact approximation;
- `PROXY` — coarse actor proxy when useful;
- `CARD` — alpha-shaped projected sprite shadow;
- `DEPTH_CARD` — alpha + height/depth-influenced projected shadow.

The programme must measure whether rasterized sprite-card shadows are preferable to adding alpha-tested billboard geometry to ray-query acceleration structures. No choice is frozen until the relevant issue produces evidence.

## Material character rule

Default effects should be shallow enough that original Doom art remains legible and recognizable. A physically plausible shader that destroys pixel-art intent is not automatically a success.

## Compatibility rule

New material/shadow behavior should fail safely to inherited VKDoom rendering when required data or hardware capability is absent. Vulkan ray-query features must retain non-RT fallbacks.

## Upstream rule

VKDoom is the renderer baseline. UZDoom/GZDoom are active related lineages and may be better sources for compatibility, safety, build and engine-maintenance changes. ShadeDoomVK will use an explicit differential/upstream policy rather than uncontrolled periodic mega-merges.

## Pre-foundation implementation gate

Before the founding SDVK feature programme begins, PF-001 through PF-020 perform a long renderer-internal hardening/refactor/correctness/performance tranche. This gate exists because the deep source audit found raw renderer-identity risks, partially wired probe/tiled-light systems, confirmed correctness defects and high-value output-equivalent refactors/optimizations that should be resolved before adding more graphical complexity.

Rules:

- SDVK-001 must not begin until PF-020 is accepted, merged, verified on `master`, and explicitly records `SDVK-001: UNBLOCKED`.
- PF refactors preserve accepted output/state unless the owning issue explicitly repairs a confirmed defect.
- PF performance work may not trade image quality or lighting semantics for speed.
- Stable SDVK-001..017 IDs remain intact; PF work must not silently consume later headline feature scope.
- `08-PREFOUNDATION-HARDENING-PROGRAMME.md`, `09-PLANNING-RECONCILIATION.md`, `05-AUTONOMOUS-ISSUE-GRAPH.md` and `AGENTS.md` are authoritative for the execution gate.

## Success condition

The founding programme is successful when the repository can demonstrate, on deterministic reference scenes and real Doom-family content:

- correct tangent-space sprite normal mapping across rotations/mirroring;
- materially distinct PBR sprite regions under moving lights;
- bounded height/parallax relief with documented fallback;
- coherent probe/sun/local-light response for actors and first-person viewmodels;
- convincing scalable sprite-cast/contact shadows integrated with world occlusion;
- no descriptor/resource-lifetime corruption under rich material loads;
- compatibility and performance tiers with measured budgets;
- automated regression evidence sufficient for continued autonomous development.

The PF gate is a prerequisite to this success condition, not a replacement for it.
