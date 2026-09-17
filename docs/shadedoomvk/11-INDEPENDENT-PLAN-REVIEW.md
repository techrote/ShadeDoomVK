# ShadeDoomVK independent programme review

Status: completed second-pass review of the fully emitted/reconciled plan  
Date: 2026-09-17

## Review method

This review was performed after the PF-001..PF-020 issue set had been emitted and SDVK-001..017 had been reconciled. It deliberately did not assume the first planning pass was correct.

The review checked:

- requested refactor/bug/performance coverage;
- stable-ID/live-issue/canonical-file consistency;
- dependency cycles and hidden prerequisites;
- unsafe concurrency/shared-file sequencing;
- duplicate scope between PF and SDVK;
- oversized or artificially undersized issues;
- missing acceptance/verification/stopping paths;
- hidden assumptions converted incorrectly into requirements;
- RAG/document findability for future autonomous agents;
- whether performance work can accidentally trade quality for speed;
- whether late synthesis gates genuinely fail closed.

## Coverage review

### Refactors

All ten high-value renderer refactors identified by the deep baseline audit have explicit owners:

1. generation-safe resource lifetime — PF-002;
2. LevelMesh ownership/mutation contract — PF-004;
3. semantic material representation — PF-008;
4. explicit sprite render-surface/orientation state — PF-009;
5. unified light-query semantics — PF-016;
6. lighting units/compatibility bridge — PF-011;
7. typed shader/pipeline keys — PF-006;
8. Vulkan capability/quirk registry — PF-007;
9. generation-safe async jobs/staging arena — PF-005;
10. render-view/pass context — PF-010.

No additional broad refactor was found that should precede PF-020 without turning the tranche into a general engine rewrite.

### Confirmed/source-assigned correctness work

The identified probe-map stub, probe midpoint, indexed RedIsAlpha, PBR roughness-zero edge, shadow-cap order, sprite clip sentinel, sprite precache variant, sky-info equality, visibility-cache world-generation and descriptor reservation-boundary work all have explicit PF owners and reproducer/supersession rules.

No confirmed audit defect was left only in prose.

### No-image-quality performance work

The requested opportunities are covered across PF-005 and PF-016..PF-019:

- O(1)-style dynamic-light duplicate marking;
- exact-equivalence section-local actor candidate sourcing;
- dynamic-light upload deduplication;
- material descriptor-variant hash lookup;
- typed/hash pipeline lookup;
- LevelMesh allocator/growth improvements;
- moving-AABB parent-path caching;
- reusable staging upload memory;
- equivalent default/placeholder descriptor sharing where safe;
- SPIR-V-qualified shader micro-optimization;
- avoiding allocations belonging solely to proven dormant paths.

The validation contract explicitly prohibits gaining speed by dropping otherwise eligible lights, reducing quality/precision/resolution, changing filters or silently disabling an active path.

## Dependency review

### Corrections found by this independent pass

Two hidden prerequisites were found and repaired:

1. **PF-012 now hard-depends on PF-003.** Probe/lightmap correctness validates descriptor page/range bounds and resource generations, so it cannot safely execute before descriptor reservation/lifetime hardening.
2. **PF-017 now hard-depends on PF-013.** Material descriptor lookup/default-resource optimization must consume the corrected material behavior rather than optimize and freeze pre-fix RedIsAlpha/precache/numerical edge behavior.

The canonical graph, hardening programme, canonical issue bodies and live GitHub issues were updated consistently.

### Cycle check

After those corrections, the PF graph remains acyclic. A valid coarse topological order is:

```text
L0: PF-001
L1: PF-002, PF-006, PF-007, PF-009, PF-011
L2: PF-003, PF-004, PF-010
L3: PF-005, PF-008, PF-014, PF-015
L4: PF-012, PF-013, PF-016, PF-018
L5: PF-017
L6: PF-019
L7: PF-020
L8: SDVK-001
```

Some nodes within a level have no dependency on each other but may still have shared-file concurrency restrictions recorded in `05-AUTONOMOUS-ISSUE-GRAPH.md`.

The SDVK graph remains acyclic and is hard-gated by PF-020.

## Concurrency review

Unsafe parallelism is explicitly recorded for the shared ownership boundaries most likely to cause merge-semantic errors:

- PF-002/PF-003 descriptor identities;
- PF-003/PF-008 material binding;
- PF-003/PF-012 descriptor-bound probe work;
- PF-004/PF-018 LevelMesh allocator;
- PF-007/PF-010 capability/view interface;
- PF-009/PF-014 sprite-state code;
- PF-011/PF-016 shared light structures/math;
- PF-013/PF-017 corrected material/cache behavior;
- PF-015/PF-016 visibility/query semantics;
- PF-016/PF-017 light query/upload representation.

Issue-level concurrency guidance can further serialize branches when current `master` evolves; the graph is a minimum hard-dependency graph, not permission to ignore merge conflicts.

## Issue-size review

### PF-012

Large but cohesive. Probe-map shader selection, AABB lifecycle, probe-0 fallback, placement and atlas/descriptor identity are one coupled probe-plumbing boundary. Splitting them before defining the selected spatial-probe mechanism would create circular handoffs and duplicate fixtures. Retained as one issue.

### PF-015

Contains shadow-cap selection and actor-light visibility-cache validity. Both govern **which world light/shadow visibility result is considered current** and share the LevelMesh/view-generation evidence. Retained as one correctness pack; PF-016 consumes the accepted semantics.

### PF-019

Broad by title but intentionally a late bounded micro-performance sweep. Each candidate is optional and requires measurement/equivalence; no downstream issue depends on an individual micro-optimization. Splitting speculative candidates into mandatory issues would create artificial work/issue inflation. Retained.

### SDVK-015 / SDVK-017 / PF-020

These are intentionally large synthesis/qualification gates rather than implementation monoliths. Their purpose is to consume already-implemented work, rerun evidence, reconcile contradictions and fail closed. Splitting them would weaken the single point at which composition is assessed.

No implementation issue was found so large that it must be decomposed before work can start, provided agents obey scope/stopping conditions and file independent adjacent defects separately.

## Duplicate-scope review

The earlier overlap was successfully removed:

- PF-002/PF-003 own descriptor identity/capacity/reuse hardening; SDVK-004 is now rich-workload stress/integration.
- PF-008 owns semantic representation of **existing** layers; SDVK-005 adds first-class height authoring/policy.
- PF-016 owns exact-equivalence CPU actor-light query optimization; SDVK-009 now evaluates higher-order scalable many-light architecture.
- PF-012 owns basic probe plumbing correctness; SDVK-010 owns actor environment response; SDVK-014 owns integrated robustness/stress.
- PF-015 owns inherited world shadow/cache correctness; SDVK-012/013 own new sprite-caster research/integration.

No remaining duplicate implementation issue was found.

## Hidden-assumption review

Assumptions are localized and fail closed rather than silently accepted:

- exact Vulkan limits/capabilities — PF-003/PF-007;
- whether section-local light gathering is exactly equivalent — PF-016 comparison mode;
- whether light upload dedup can preserve ordering/lifetime — PF-017;
- whether dormant tiled-light resources are truly unused — PF-019;
- intended per-texel probe-selection semantics — PF-012 stopping condition;
- whether any shadow-overflow relevance metric requires a visible product decision — PF-015 stopping condition;
- whether a higher-order many-light architecture is warranted at all — SDVK-009 may conclude no change.

No unresolved assumption currently invalidates starting PF-001.

## Verification-path review

Every live PF/SDVK issue includes or references:

- objective;
- scope;
- non-goals;
- dependencies;
- concurrency guidance;
- required context;
- autonomous implementation prompt;
- acceptance criteria;
- verification;
- expected artifacts;
- blocking/stopping conditions.

`AGENTS.md` and `docs/shadedoomvk/issues/ISSUE-CONTRACT.md` make these mandatory for future issues as well.

PF refactors/performance use `06-VALIDATION-PERFORMANCE-CONTRACT.md` state/image equivalence. Correctness issues preserve pre-fix negative fixtures. Comparative research may validly conclude no candidate qualifies.

## Documentation-findability review

A future agent can start from:

1. `README.md` — current gate and canonical index;
2. `AGENTS.md` — execution rules;
3. `03-REVISED-ROADMAP.md` — macro roadmap;
4. `05-AUTONOMOUS-ISSUE-GRAPH.md` — exact dependencies/concurrency;
5. `08-PREFOUNDATION-HARDENING-PROGRAMME.md` — PF intent;
6. `09-PLANNING-RECONCILIATION.md` — requirements/findings/decisions/assumptions;
7. `rag/README.md` — subsystem truth references;
8. canonical/live issue body — task-specific execution contract.

The initial implementation plan remains historical rather than executable.

## Review result

After correcting PF-012 and PF-017 dependencies, the plan is ready for implementation decomposition and autonomous execution beginning at PF-001.

No planning-level blocker remains. Implementation-level uncertainty is intentionally localized to issue stopping conditions and does not require a user decision before PF-001.
