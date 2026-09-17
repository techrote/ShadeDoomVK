# ShadeDoomVK autonomous issue graph

Status: founding execution graph  
Date: 2026-09-17

## Execution rule

Issue IDs are stable programme identifiers even if GitHub issue numbers differ. Every issue body contains an autonomous prompt and references this document, `AGENTS.md`, the founding brief, revised roadmap, donor register and validation/performance contract.

## Issues and dependencies

| ID | GitHub | Title | Hard dependencies |
|---|---:|---|---|
| SDVK-001 | #1 | Foundation, identity, reproducible build and provenance | none |
| SDVK-002 | #2 | Renderer observability, reference scenes and benchmark harness | SDVK-001 |
| SDVK-003 | #3 | Upstream differential and maintenance strategy | SDVK-001 |
| SDVK-004 | #4 | Bindless descriptor capacity/reuse/stale-reference hardening | SDVK-002, SDVK-003 |
| SDVK-005 | #5 | Semantic material layers and per-layer sampling | SDVK-004 |
| SDVK-006 | #6 | Render-frame time and visual interpolation substrate | SDVK-001, SDVK-002 |
| SDVK-007 | #7 | Sprite tangent basis and normal-map conformance | SDVK-005 |
| SDVK-008 | #8 | Height/POM sprite relief and advanced PBR | SDVK-007 |
| SDVK-009 | #9 | Dynamic-light gathering/data-layout qualification | SDVK-002, SDVK-003 |
| SDVK-010 | #10 | Probe/environment lighting qualification for actors | SDVK-002, SDVK-007 |
| SDVK-011 | #11 | First-person viewmodel lighting/material parity | SDVK-009, SDVK-010 |
| SDVK-012 | #12 | Sprite shadow-caster comparative prototype | SDVK-008, SDVK-009 |
| SDVK-013 | #13 | Hybrid world+sprite shadows and contact grounding | SDVK-012 |
| SDVK-014 | #14 | Lightmapper/dynamic-lightmap/probe robustness | SDVK-002, SDVK-005, SDVK-009, SDVK-010 |
| SDVK-015 | #15 | Doom-family compatibility/regression qualification | SDVK-008, SDVK-011, SDVK-013, SDVK-014 |
| SDVK-016 | #16 | Performance tiers, budgets and adaptive quality | SDVK-015 |
| SDVK-017 | #17 | Integrated synthesis, defaults and first renderer freeze | SDVK-001 through SDVK-016 |

## Dependency-ready concurrency

After SDVK-001:

- SDVK-002 and SDVK-003 can proceed together;
- SDVK-006 can begin once diagnostics are available;
- descriptor/material work and dynamic-light research can proceed on separate branches after the upstream policy is frozen;
- probe qualification can begin once the material/TBN contract is stable;
- shadow prototypes should not block unrelated lightmapper hardening;
- compatibility/performance qualification waits for the feature stack to compose.

## Autonomous issue completion protocol

Every issue must:

1. inspect `master` and dependency evidence;
2. restate hypothesis/objective and measurable acceptance criteria in the working branch/PR;
3. preserve baseline/failure fixtures;
4. implement the smallest coherent solution;
5. add or extend automated tests/diagnostics;
6. document donor/upstream provenance;
7. open a PR;
8. repair required CI;
9. merge only after checks pass;
10. verify the merge on `master`;
11. close only after acceptance criteria are satisfied.

## Final freeze gate

SDVK-017 must fail closed if any unresolved defect can cause:

- stale/corrupt renderer resource identity;
- materially wrong light selection or tangent-space response;
- silent compatibility breakage in the declared supported path;
- shadow/probe/lightmap state that is visually plausible but semantically mismatched to the scene;
- unsupported hardware to crash instead of using a documented fallback;
- unbounded performance collapse in a declared quality tier.

Visual polish, optional high-end effects and later content tooling do not block the first freeze when safe explicit fallbacks exist.
