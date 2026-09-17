# ShadeDoomVK autonomous issue graph

Status: canonical execution/dependency graph  
Date: 2026-09-17

## Execution rule

Stable programme IDs are authoritative even when GitHub issue numbers change. Every issue body follows `AGENTS.md` and links to shared canonical material rather than duplicating it.

**SDVK-001 is blocked until PF-020 is accepted, merged and verified on `master`.**

# Pre-foundation issue graph

| ID | Objective | Hard dependencies |
|---|---|---|
| PF-001 | pre-foundation safety harness + invariant fixtures | none |
| PF-002 | renderer resource generations/lifetime/stale-reference diagnostics | PF-001 |
| PF-003 | bindless capacity/reservation/reuse hardening | PF-002 |
| PF-004 | LevelMesh ownership/mutation/allocator hardening | PF-002 |
| PF-005 | async texture jobs + persistent staging arena | PF-003 |
| PF-006 | typed shader/pipeline keys + cache contract | PF-001 |
| PF-007 | central Vulkan capability/driver-quirk registry | PF-001 |
| PF-008 | existing material-layer semantic refactor | PF-003 |
| PF-009 | sprite render-surface/orientation-state extraction | PF-001 |
| PF-010 | render-view/pass context extraction | PF-007 |
| PF-011 | lighting math/units/compatibility-bridge contract | PF-001 |
| PF-012 | probe/lightmap correctness + spatial selection repair | PF-004, PF-010, PF-011 |
| PF-013 | texture/material correctness repair pack | PF-003, PF-008 |
| PF-014 | sprite/portal state correctness repair pack | PF-009, PF-010 |
| PF-015 | shadow/visibility-cache correctness repair pack | PF-004, PF-010, PF-011 |
| PF-016 | unified dynamic-light query + exact-equivalence actor fast path | PF-009, PF-011, PF-015 |
| PF-017 | light/material data dedup + cache lookup performance | PF-003, PF-008, PF-016 |
| PF-018 | LevelMesh/AABB allocator/update performance | PF-004, PF-015 |
| PF-019 | pipeline/resource micro-performance + dormant-path cleanup | PF-005, PF-006, PF-007, PF-017, PF-018 |
| PF-020 | pre-foundation synthesis and SDVK-001 release gate | PF-001 through PF-019 |

## PF concurrency lanes

After PF-001, these root lanes may proceed concurrently when implementation branches do not collide materially:

```text
resource identity:  PF-002 → PF-003 → PF-005
                         └──────→ PF-008 → PF-013
LevelMesh:          PF-002 → PF-004 ─┬→ PF-012
                                      ├→ PF-015 → PF-016 → PF-017
                                      └→ PF-018
pipeline keys:      PF-006 ───────────────────────────────→ PF-019
Vulkan capability:  PF-007 → PF-010 ─┬→ PF-012
                                      ├→ PF-014
                                      └→ PF-015
sprite state:       PF-009 ───────────┬→ PF-014
                                      └→ PF-016
lighting contract:  PF-011 ──────────┬→ PF-012
                                      ├→ PF-015
                                      └→ PF-016

PF-005 + PF-006 + PF-007 + PF-017 + PF-018 → PF-019
PF-001..PF-019 → PF-020 → SDVK-001
```

### Unsafe PF concurrency

Do not intentionally run these implementation combinations concurrently without explicit branch sequencing/rebase evidence:

- PF-002 with PF-003 on the same descriptor/identity files;
- PF-003 with PF-008 when both change material descriptor layout/binding;
- PF-004 with PF-018;
- PF-007 with PF-010 if capability-query interfaces are still moving;
- PF-009 with PF-014;
- PF-011 with PF-016 if shared light structs/functions are being moved;
- PF-015 with PF-016 because optimization must consume the accepted visibility-cache semantics;
- PF-016 with PF-017 where light-data representation changes cross the query/upload boundary.

# Founding SDVK issue graph

| ID | Title / reconciled objective | Hard dependencies |
|---|---|---|
| SDVK-001 | foundation, identity, reproducible build and provenance | PF-020 |
| SDVK-002 | renderer observability, reference scenes and benchmark harness | SDVK-001 |
| SDVK-003 | upstream differential and maintenance strategy | SDVK-001 |
| SDVK-004 | rich-material descriptor integration/lifetime stress qualification | SDVK-002, SDVK-003 |
| SDVK-005 | semantic material authoring + height semantics | SDVK-004 |
| SDVK-006 | render-frame time and visual interpolation substrate | SDVK-001, SDVK-002 |
| SDVK-007 | explicit sprite tangent basis and normal-map conformance | SDVK-005 |
| SDVK-008 | height/POM sprite relief and advanced PBR | SDVK-007 |
| SDVK-009 | scalable many-light architecture qualification | SDVK-002, SDVK-003 |
| SDVK-010 | probe/environment lighting qualification for actors | SDVK-002, SDVK-007 |
| SDVK-011 | first-person viewmodel lighting/material parity | SDVK-009, SDVK-010 |
| SDVK-012 | sprite shadow-caster comparative prototype | SDVK-008, SDVK-009 |
| SDVK-013 | hybrid world+sprite shadows/contact grounding | SDVK-012 |
| SDVK-014 | lightmapper/dynamic-lightmap/probe robustness | SDVK-002, SDVK-005, SDVK-009, SDVK-010 |
| SDVK-015 | Doom-family compatibility/regression qualification | SDVK-008, SDVK-011, SDVK-013, SDVK-014 |
| SDVK-016 | performance tiers/budgets/adaptive quality | SDVK-015 |
| SDVK-017 | integrated synthesis/defaults/first renderer freeze | SDVK-001 through SDVK-016 |

## SDVK dependency-ready concurrency

After SDVK-001:

- SDVK-002 and SDVK-003 can proceed together;
- SDVK-006 begins after SDVK-002 establishes the durable oracle;
- SDVK-004 waits for SDVK-002/003;
- SDVK-005 → SDVK-007 → SDVK-008 remains serialized material/orientation/relief work;
- SDVK-009 can proceed after SDVK-002/003 independently of SDVK-005/007, because PF-016 already established baseline actor-light query correctness/fast paths;
- SDVK-010 requires SDVK-007 so actor IBL is evaluated against the accepted sprite orientation/material path;
- SDVK-014 may perform exploratory work earlier, but cannot accept until its declared dependencies are merged;
- compatibility/performance/freeze remain late synthesis gates.

## Autonomous completion protocol

Every issue must:

1. inspect current `master`, its dependencies and relevant open/closed issue/PR evidence;
2. read `AGENTS.md` and relevant canonical/RAG docs;
3. state objective, invariants and expected evidence;
4. preserve baseline/failure fixtures;
5. implement the smallest coherent accepted scope;
6. add/extend tests/diagnostics;
7. update affected RAG/reference docs;
8. document donor/upstream provenance;
9. open a PR;
10. repair required CI;
11. merge only after required checks pass;
12. verify the merge on `master`;
13. close only after acceptance criteria are satisfied;
14. append programme-level gate changes to `10-EXECUTION-LEDGER.md` when applicable.

## PF-020 release blockers

SDVK-001 remains blocked while any unresolved PF defect can cause:

- stale/corrupt renderer resource identity;
- visible/query geometry divergence;
- materially wrong light, probe or shadow selection;
- unsafe descriptor/lightmap/probe range behavior;
- portal/view-context cache contamination;
- silent compatibility regression in a PF-touched path;
- a claimed performance win that changes accepted output/quality;
- canonical RAG/reference documentation that no longer matches the source.

## SDVK-017 freeze blockers

The first renderer tranche cannot freeze while any unresolved issue can cause:

- stale/corrupt renderer resource identity;
- materially wrong light selection or tangent-space response;
- silent compatibility breakage in the declared supported path;
- shadow/probe/lightmap state that is visually plausible but semantically mismatched;
- unsupported hardware to crash rather than use documented fallback;
- unbounded performance collapse in a declared quality tier.
