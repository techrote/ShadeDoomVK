# ShadeDoomVK revised roadmap

Status: canonical implementation roadmap  
Date: 2026-09-17

## Programme structure

ShadeDoomVK now has two serial macro-tranches:

1. **PF-001..PF-020 — pre-foundation hardening/refactor/correctness/performance**;
2. **SDVK-001..SDVK-017 — founding renderer feature programme**.

The PF tranche is mandatory. SDVK-001 has hard dependency PF-020.

Within each tranche, independent lanes may run concurrently only when issue bodies/`05-AUTONOMOUS-ISSUE-GRAPH.md` permit it.

# Macro-tranche A — pre-foundation hardening

Detailed scope lives in `08-PREFOUNDATION-HARDENING-PROGRAMME.md` and the renderer RAG corpus.

## PF Gate 0 — hardening oracle

**PF-001 — Pre-foundation renderer safety harness and invariant fixtures**

Establish minimal targeted fixtures/diagnostics capable of detecting state/output regressions during the large refactor pass. This intentionally does not consume SDVK-001 project-brand/build scope or SDVK-002's later full benchmark corpus.

## PF Gate 1 — identity/lifetime safety

After PF-001:

- **PF-002 — Renderer resource generations, stale-reference detection and lifetime contract**;
- **PF-003 — Bindless descriptor capacity, reservation and reuse hardening**;
- **PF-004 — LevelMesh ownership, mutation and allocator hardening**;
- **PF-005 — Asynchronous texture jobs and persistent staging-upload arena**.

PF-002 precedes PF-003/PF-004 where those issues introduce recyclable identities. PF-005 waits for the resource-lifetime contract and bindless behavior it can affect.

## PF Gate 2 — canonical renderer contracts

Largely parallel after PF-001 subject to file ownership:

- **PF-006 — Typed shader/pipeline keys and cache contract**;
- **PF-007 — Central Vulkan capability and driver-quirk registry**;
- **PF-008 — Existing material-layer semantic refactor**;
- **PF-009 — Sprite render-surface and orientation-state extraction**;
- **PF-010 — Render-view/pass context extraction**;
- **PF-011 — Lighting math, units and compatibility-bridge contract**.

These are output-preserving refactors. PF-008 does not add height/POM; PF-009 does not switch sprite normal mapping to a new TBN; PF-010 does not implement temporal history; PF-011 does not retune lighting.

## PF Gate 3 — correctness repairs

Once relevant shared contracts are accepted:

- **PF-012 — Probe/lightmap correctness and spatial-selection repair**;
- **PF-013 — Texture/material correctness repair pack**;
- **PF-014 — Sprite/portal state correctness repair pack**;
- **PF-015 — Shadow/visibility cache correctness repair pack**.

The PF issues preserve failing fixtures and either fix the assigned defect or prove a superseding refactor made the bad state impossible.

## PF Gate 4 — no-image-quality performance

- **PF-016 — Unified dynamic-light query service and exact-equivalence actor fast path**;
- **PF-017 — Light/material data deduplication and cache lookup performance**;
- **PF-018 — LevelMesh/AABB allocator and update-path performance**;
- **PF-019 — Pipeline/resource micro-performance and dormant-path cleanup**.

Performance acceptance requires equivalent selected-light/material/probe/shadow state and image evidence within the declared baseline tolerance. These issues may not trade quality for speed.

## PF Gate 5 — pre-foundation synthesis

**PF-020 — Pre-foundation hardening synthesis and SDVK-001 release gate**

Consumes PF-001..019 evidence, reruns the complete hardening corpus, reconciles RAG/reference documents against the resulting source and unlocks SDVK-001 only when the renderer ground is trustworthy.

# Macro-tranche B — founding ShadeDoomVK feature programme

## SDVK Gate 0 — project authority and reproducibility

**SDVK-001 — Foundation, identity, reproducible build and provenance**  
Hard dependency: PF-020.

Establish ShadeDoomVK naming/ownership boundaries, build/run/CI documentation and runtime provenance without compatibility-breaking mass rename.

## SDVK Gate 1 — measurement and upstream strategy

After SDVK-001, in parallel:

**SDVK-002 — Renderer observability, deterministic reference scenes and benchmark harness**

Expand PF fixtures into the durable renderer oracle: machine-readable diagnostics, image evidence, reference scenes and performance capture.

**SDVK-003 — VKDoom/UZDoom/GZDoom differential and upstream maintenance policy**

Pin current related upstreams and prove selective maintenance imports without discarding VKDoom-specific renderer capability.

## SDVK Gate 2 — renderer substrate extension

**SDVK-004 — Rich-material descriptor integration and lifetime stress qualification**

PF already establishes descriptor reuse/lifetime/capacity safety. SDVK-004 now stress-qualifies that infrastructure under the richer material/lightmap/probe workload and resolves integration gaps discovered by SDVK-002/003.

**SDVK-005 — First-class semantic material authoring including height**

Build on PF-008's semantic representation and the already inherited per-layer sampling system. Add height as a first-class semantic plus authoring/color-space/sampler/mip/fallback contract.

**SDVK-006 — Render-frame time and opt-in visual interpolation substrate**

Adapt renderer delta-time and alpha/scale interpolation concepts without changing gameplay determinism; use PF-010 render-context identity where relevant.

## SDVK Gate 3 — correct advanced sprite materials

**SDVK-007 — Explicit sprite-space tangent basis and normal-map conformance**

Consume PF-009's orientation state to define sprite right/up/forward, mirror handedness and billboard/rotation tangent behavior.

**SDVK-008 — Height/POM sprite relief and advanced PBR response**

Implement bounded shallow height relief after SDVK-005/007 establish material and orientation semantics.

## SDVK Gate 4 — scalable lighting and environment response

**SDVK-009 — Scalable many-light architecture qualification**

PF-016 already handles exact-equivalence CPU actor-light collection optimizations. SDVK-009 profiles the resulting path and evaluates higher-order scaling, including whether the inherited dormant Z-min/max/light-tile scaffold should be repaired/reused, replaced, or left disabled. No architecture is preselected.

**SDVK-010 — Probe/environment lighting qualification for actors**

Start from PF-012's corrected/bounded probe plumbing and validate actor probe assignment, IBL, sunlight and transitions under semantic sprite materials.

**SDVK-011 — First-person viewmodel lighting/material parity**

Bring weapon sprites/models into explicit world/probe/PBR semantics with compatibility modes.

## SDVK Gate 5 — sprite shadow architecture

**SDVK-012 — Sprite shadow-caster comparative prototype**

Compare inherited/simple, blob/proxy, alpha-card, depth-card and tractable AS approaches on one oracle.

**SDVK-013 — Hybrid world + sprite shadow integration and contact grounding**

Integrate the selected actor-caster architecture with world shadowmap/ray-query visibility, softness/contact bias and scalable fallback.

## SDVK Gate 6 — inherited lighting-system robustness

**SDVK-014 — Lightmapper, dynamic-lightmap and probe robustness campaign**

Assume PF-012 repaired/bounded basic probe plumbing; stress integrated lightmap/probe/atlas lifetimes and dynamic updates under the new material/shadow stack.

## SDVK Gate 7 — compatibility and performance qualification

**SDVK-015 — Doom-family compatibility and renderer regression campaign**

Run targeted synthetic fixtures plus representative content patterns and classify every regression/fallback.

**SDVK-016 — Performance tiers, budgets and adaptive quality policy**

Define measured Compatibility/Enhanced/High (or evidence-backed equivalent) feature tiers and hardware fallbacks.

## SDVK Gate 8 — first renderer freeze

**SDVK-017 — Integrated renderer synthesis, defaults and first ShadeDoomVK freeze**

Consume PF and SDVK evidence, reconcile defaults/fallbacks/documentation and fail closed while material correctness, resource identity, compatibility or declared quality-tier performance is unresolved.

## Macro dependency summary

```text
PF-001 → PF shared refactors → PF correctness → PF equivalent-performance → PF-020
                                                                     │
                                                                     ▼
                                                                  SDVK-001
                                                                  /      \
                                                             SDVK-002  SDVK-003
                                                                 │        │
                                                           feature/lighting graph
                                                                 │
                                                            SDVK-015
                                                                 │
                                                            SDVK-016
                                                                 │
                                                            SDVK-017
```

The exact dependency/concurrency graph is `05-AUTONOMOUS-ISSUE-GRAPH.md`.

## Programme-wide acceptance rules

Every implementation/research issue must:

- preserve or explicitly revise accepted invariants;
- consume relevant RAG references and update them when architecture changes;
- include deterministic validation where practical;
- preserve failing negative fixtures for bugfixes;
- record donor/upstream provenance;
- measure performance claims;
- prove output/state equivalence for PF optimization/refactor work unless the issue explicitly owns a bugfix;
- open a PR and merge only after required automated checks pass;
- verify the merge on `master` before closing.

The programme may narrow an ambitious feature when evidence rejects it. It may not silently lower correctness, compatibility or resource-safety criteria to claim completion.
