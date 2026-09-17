# ShadeDoomVK revised roadmap

Status: founding implementation roadmap  
Date: 2026-09-17

## Programme structure

The implementation is dependency-gated but deliberately not fully serial. After the small shared foundation, independent tracks may proceed in parallel where they do not destabilize the same renderer contracts.

## Gate 0 — project authority and reproducibility

**SDVK-001 — Foundation, identity, reproducible build and provenance**

Establish ShadeDoomVK naming/ownership boundaries, exact baseline provenance, supported build commands, CI expectations and donor register. Avoid risky mass renames that break config/WAD compatibility.

Exit gate:

- deterministic documented build path;
- CI status understood and repaired where baseline is broken;
- project/version identity exposed without destroying inherited compatibility identifiers;
- donor/upstream policy documents validated.

## Gate 1 — measurement and upstream strategy

These can proceed in parallel after SDVK-001.

**SDVK-002 — Renderer observability, deterministic reference scenes and benchmark harness**

Create machine-readable diagnostics and a compact visual/material/light/shadow corpus. This becomes the oracle for all later performance and correctness work.

**SDVK-003 — VKDoom/UZDoom/GZDoom differential and upstream maintenance policy**

Pin current related upstreams, classify changes worth importing, prove a maintainable selective-sync procedure and record ownership boundaries. No automatic rebase assumption.

Exit gate:

- renderer changes can be measured rather than judged only by screenshots;
- future upstream imports have an explicit policy.

## Gate 2 — renderer substrate

After SDVK-002 and SDVK-003:

**SDVK-004 — Bindless descriptor capacity, reuse and stale-reference hardening**

Start from the jalovisko device-limit-aware idea, then design safe slot reuse/generation/lifetime behavior. Treat MAD's flush-and-stale-index result as a negative fixture.

**SDVK-005 — Semantic material layers and per-layer sampler/mip policy**

Generalize GriddleVK's per-layer sampling concept. Make albedo, normal, height, roughness, metallic, AO and emissive first-class semantics with correct sampling/color-space defaults.

**SDVK-006 — Render-frame time and opt-in visual interpolation substrate**

Adapt the useful MAD delta-time and alpha/scale interpolation concepts without changing gameplay determinism.

SDVK-004 should merge before SDVK-005 if the material implementation changes bindless lifetime semantics. SDVK-006 is largely parallel.

## Gate 3 — correct advanced sprite materials

**SDVK-007 — Explicit sprite-space tangent basis and normal-map conformance**

Define sprite-right/up/forward, mirror handedness and billboard/rotation behavior. Validate front/back/rotated/flipped frames before richer effects.

**SDVK-008 — Height/POM sprite relief and advanced PBR response**

Add shallow height/parallax occlusion mapping, tunable relief, sensible mip/filter rules and bounded self-occlusion approximation where useful. Preserve non-height fallback and original sprite character.

Gate rule: no advanced height default until SDVK-007 fixtures prove orientation correctness.

## Gate 4 — scalable lighting

**SDVK-009 — Dynamic-light gathering and data-structure qualification**

Benchmark stock collection against small-actor/section-list and compact-index alternatives inspired by MAD-VKDoom. Preserve exact selected-light behavior including portals/groups. Implement only evidence-backed changes.

**SDVK-010 — Probe/environment lighting qualification for actors**

Validate inherited light probes/probe maps, nearest-probe selection, sunlight/specular response and transitions for sprites/models under the new material contract. Repair light leaks/probe selection defects uncovered by deterministic fixtures.

**SDVK-011 — First-person viewmodel lighting/material parity**

Bring weapon sprites/models into the same explicit world-light/probe/PBR semantics with compatibility modes, rather than a single ad-hoc brightness toggle.

SDVK-009 and SDVK-010 may overlap after SDVK-007; SDVK-011 depends on their accepted contracts.

## Gate 5 — sprite shadow architecture

**SDVK-012 — Sprite shadow-caster comparative prototype**

Compare blob/proxy, alpha-card, depth-card and any tractable acceleration-structure approach on the same fixtures. Measure silhouette correctness, mirror/rotation behavior, softness, portals and cost.

**SDVK-013 — Hybrid world + sprite shadow integration and contact grounding**

Adopt the qualified sprite-caster path and integrate it with LevelMesh ray-query/world shadows, light softness, contact bias and distance/quality LOD. Do not mislabel raster sprite shadows as full RT sprite geometry.

## Gate 6 — inherited lighting-system hardening

**SDVK-014 — Lightmapper, dynamic-lightmap and probe robustness campaign**

Stress atlas lifetime, moving/dynamic sectors, dynamic lights, sunlight, bounce/AO, decals, reflective/warped surfaces and probe transitions under the richer material/shadow stack.

This may begin earlier as research after SDVK-002, but acceptance should occur after the material/lighting contracts are known.

## Gate 7 — compatibility and performance qualification

**SDVK-015 — Doom-family compatibility and renderer regression campaign**

Run representative IWADs/maps/mod patterns plus targeted portal/3D-floor/decal/canvas/translucency/model/voxel/particle fixtures. Document fallback behavior and minimize regressions.

**SDVK-016 — Performance tiers, budgets and adaptive quality policy**

Measure CPU/GPU/memory/descriptor costs, establish conservative/balanced/high quality tiers and explicit hardware/fallback rules. Use real algorithm switches rather than cosmetic labels.

## Gate 8 — synthesis and first renderer freeze

**SDVK-017 — Integrated renderer synthesis, defaults and first ShadeDoomVK freeze**

Consume SDVK-001 through SDVK-016 evidence, run end-to-end scenes, reconcile contradictions, set defaults/fallbacks, update user/developer documentation and only then declare the first renderer tranche foundation-qualified.

## Parallelism summary

```text
SDVK-001
   ├── SDVK-002 ─┬── SDVK-004 ── SDVK-005 ── SDVK-007 ── SDVK-008 ─┬── SDVK-012 ── SDVK-013 ─┐
   │             │                                                   │                        │
   │             ├──────────────────── SDVK-009 ──────────────────────┤                        │
   │             └──────────────────── SDVK-010 ── SDVK-011 ─────────┘                        │
   ├── SDVK-003 ────────────────────────┘                                                     │
   └── SDVK-006 ───────────────────────────────────────────────────────────────────────────────┤
                                                                                               ├── SDVK-015 ── SDVK-016 ── SDVK-017
SDVK-002 ─────────────────────────────── SDVK-014 ──────────────────────────────────────────────┘
```

Exact dependency declarations live in `05-AUTONOMOUS-ISSUE-GRAPH.md` and the issue bodies.

## Programme-wide acceptance rules

Every issue must:

- preserve or explicitly revise the founding invariants;
- include deterministic automated validation where practical;
- record donor/upstream provenance;
- measure performance claims;
- preserve negative/counterexample fixtures;
- open a PR and merge only after required checks pass;
- verify the merge on `master` before closing.

The programme may narrow a feature or retain a fallback when evidence rejects an ambitious implementation. It may not silently lower correctness or compatibility criteria to claim completion.
