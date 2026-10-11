# ShadeDoomVK autonomous issue graph

Status: canonical execution/dependency graph  
Date: 2026-09-17

## Execution rule

Stable programme IDs are authoritative even when GitHub issue numbers change. Every issue body follows `AGENTS.md` and links to shared canonical material rather than duplicating it.

**SDVK-001 is blocked until PF-020 is accepted, merged and verified on `master`.**

Current gate (2026-10-10): SDVK-001 through SDVK-006 are accepted, merged and verified. SDVK-005 substantive PR #132 merged as `aceca0d4bf7a7ca0df58b9dccfc34e6b402f21d1` with exact tested/merged tree equality and passing exact-head plus post-merge source evidence/9-job CI. Acceptance reconciliation is PR #134. SDVK-007 / #7 is dependency-ready after that reconciliation; SDVK-008 and SDVK-010 retain their declared dependency on accepted SDVK-007. SDVK-009 / #9 remains open for its physical confirmation campaign.

PF freeze gate (2026-10-05): all PF-001–019 and the explicit CFX #75 synthesis prerequisite are accepted; pre-freeze accepted renderer master was `7d29c7e4d64d61dba05524d9e7f5711ffd915d90`. PF-017 is satisfied by its accepted measured no-go/restoration, not by mandatory deduplication or hashing. Independent parser/material/probe repairs #114/#110/#112/#113 are accepted. PF-020 / #37 is accepted, merged and verified on master at `e185e60b04fe37ec84a18c5a85eec6722b541b71`, with final local/source/review gates and all eight actual final-head plus all eight exact post-merge jobs. [Release acceptance](PF-020-RELEASE-ACCEPTANCE.json) preserves bounded evidence and limitations. SDVK-001 is UNBLOCKED; no SDVK feature is implemented by this freeze. [Evidence matrix](PF-FREEZE-EVIDENCE-MATRIX.md).

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
| PF-012 | probe/lightmap correctness + spatial selection repair | PF-003, PF-004, PF-010, PF-011 |
| PF-013 | texture/material correctness repair pack | PF-003, PF-008 |
| PF-014 | sprite/portal state correctness repair pack | PF-009, PF-010 |
| PF-015 | shadow/visibility-cache correctness repair pack | PF-004, PF-010, PF-011 |
| PF-016 | unified dynamic-light query + exact-equivalence actor fast path | PF-009, PF-011, PF-015 |
| PF-017 | measured light/material reuse + lookup disposition; accepted no-go/restoration | PF-003, PF-008, PF-013, PF-016 |
| PF-018 | LevelMesh/AABB allocator/update performance | PF-004, PF-015 |
| PF-019 | pipeline/resource micro-performance + dormant-path cleanup | PF-005, PF-006, PF-007, PF-017, PF-018 |
| PF-020 | pre-foundation synthesis and SDVK-001 release gate | PF-001 through PF-019 |

## PF concurrency lanes

After PF-001, these root lanes may proceed concurrently when implementation branches do not collide materially:

```text
resource identity:  PF-002 → PF-003 → PF-005
                         ├──────→ PF-008 → PF-013 ─────┐
                         └──────────────────────→ PF-012│
LevelMesh:          PF-002 → PF-004 ─┬→ PF-012         │
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

PF-003 + PF-004 + PF-010 + PF-011 → PF-012
PF-003 + PF-008 + PF-013 + PF-016 → PF-017
PF-004 + PF-015 ──────────────────→ PF-018
PF-005 + PF-006 + PF-007 + PF-017 + PF-018 → PF-019
PF-001..PF-019 → PF-020 → SDVK-001
```

### Unsafe PF concurrency

Do not intentionally run these implementation combinations concurrently without explicit branch sequencing/rebase evidence:

- PF-002 with PF-003 on the same descriptor/identity files;
- PF-003 with PF-008 when both change material descriptor layout/binding;
- PF-003 with PF-012 when descriptor reservation/lifetime behavior is still moving;
- PF-004 with PF-018;
- PF-007 with PF-010 if capability-query interfaces are still moving;
- PF-009 with PF-014;
- PF-011 with PF-016 if shared light structs/functions are being moved;
- PF-013 with PF-017 because optimization must consume corrected material behavior;
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

With SDVK-002, SDVK-003 and SDVK-004 accepted:

- **SDVK-005, SDVK-006 and SDVK-009 are dependency-ready and may proceed concurrently** when their implementation files do not materially collide;
- SDVK-005 now consumes the accepted SDVK-004 pressure/lifetime budget; SDVK-005 → SDVK-007 → SDVK-008 remains serialized material/orientation/relief work;
- SDVK-009 is independent of SDVK-005/007 because PF-016 already established baseline actor-light query correctness/fast paths;
- SDVK-010 still requires SDVK-007 so actor IBL is evaluated against the accepted sprite orientation/material path;
- SDVK-014 may perform exploratory work earlier, but cannot accept until SDVK-005, SDVK-009 and SDVK-010 are accepted;
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


### SDVK-005 accepted gate — 2026-10-10

SDVK-005's optional height semantic is accepted on the verified implementation tree. Historical material/custom bindings remain stable, per-layer sampling is explicit, PF descriptor lifetime ownership is unchanged and software-Vulkan state/image qualification passes. **SDVK-007 is now the next serialized material/orientation task; SDVK-008 and SDVK-010 remain blocked by SDVK-007.**

### Current gate reconciliation — 2026-10-11

The historical SDVK-005 note above is superseded by SDVK-007 acceptance and the
merged SDVK-008/010 implementations. #8 still needs full physical relief/cost
acceptance; #10 still needs world-sun occlusion and linked-portal actor transition
qualification. #9's first frozen GTX 1650 SUPER campaign stopped on a retained
device fault after six passing image/state pairs, before timing. See
[physical failure report](SDVK-009-PHYSICAL-20261011.md). None of these three issues
is accepted. #11/#14 remain blocked by #9/#10; #12 remains blocked by #8/#9.
