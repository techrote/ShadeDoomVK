# ShadeDoomVK final planning consistency check

Status: planning workflow complete; implementation ready at PF-001  
Date: 2026-09-17  
Verification snapshot master: `9e3d016fff290dfbe3b78490cbc5a1d7f60af2e6`

## Repository/tracker checks performed

- Live issue tracker inspected after all issue reconciliation.
- Programme issues occupy #1 through #37 with stable mappings recorded in `07-ISSUE-EMISSION-STATUS.md`:
  - SDVK-001..017 → #1..#17;
  - PF-001..020 → #18..#37.
- Canonical issue-body directory inspected and contains the issue contract plus PF and SDVK body sets.
- Renderer RAG directory inspected and contains its index plus ten subsystem/reference documents.
- Exact planning-placeholder phrase search returned no repository result.
- `TEMP` issue search returned no result.
- Open-pull-request listing returned empty; no abandoned planning PR remains.
- `master` branch state was fetched after document/issue reconciliation.

## Dependency consistency

The independent review identified and repaired two hidden dependencies before this final pass:

- PF-012 now depends on PF-003 in addition to PF-004/PF-010/PF-011;
- PF-017 now depends on PF-013 in addition to PF-003/PF-008/PF-016.

After repair:

- PF dependency graph is acyclic;
- SDVK dependency graph is acyclic;
- PF-020 is the only release gate into SDVK-001;
- PF correctness work precedes optimizations that could otherwise freeze incorrect behavior;
- unsafe concurrency is explicitly documented separately from hard dependency order.

See `11-INDEPENDENT-PLAN-REVIEW.md` for the topological review and issue-size analysis.

## Scope consistency

The principal PF/SDVK overlaps were deliberately removed:

- descriptor allocator/lifetime hardening is PF; rich-workload descriptor qualification is SDVK-004;
- existing material semantic representation is PF-008; first-class height authoring/policy is SDVK-005;
- exact-equivalence CPU actor-light optimization is PF-016; higher-order scalable many-light architecture is SDVK-009;
- basic probe plumbing correctness is PF-012; actor IBL is SDVK-010; integrated lightmapper/probe stress is SDVK-014;
- inherited world shadow/cache correctness is PF-015; new sprite-shadow representation/integration is SDVK-012/013.

No remaining duplicate implementation issue was found.

## Requested-work coverage

The planning set accounts for:

- all ten high-value refactors from the baseline audit;
- all confirmed/source-assigned bugfix classes, with reproducer or supersession proof requirements;
- the identified no-image-quality performance opportunities, under explicit output/state-equivalence rules;
- RAG/reference material for execution, identity/lifetime, LevelMesh, materials, lighting/shadows, probes/lightmaps, portals/spaces, Vulkan capabilities, HDR/future seams and known traps;
- milestone hierarchy, dependency order and safe/unsafe concurrency;
- late PF and SDVK synthesis/freeze gates.

## Issue-contract consistency

The live/canonical programme issues use the required autonomous structure:

- objective;
- scope / required work;
- non-goals;
- dependencies;
- concurrency guidance;
- required canonical context;
- autonomous implementation prompt;
- acceptance criteria;
- verification;
- expected artifacts;
- blocking/stopping conditions.

`AGENTS.md` and `docs/shadedoomvk/issues/ISSUE-CONTRACT.md` make this structure mandatory for future work.

## Documentation authority consistency

Execution authority is discoverable in this order:

1. `README.md` — project/gate/index;
2. `AGENTS.md` — mandatory workflow rules;
3. `03-REVISED-ROADMAP.md` — executable macro roadmap;
4. `05-AUTONOMOUS-ISSUE-GRAPH.md` — exact dependencies/concurrency;
5. `08-PREFOUNDATION-HARDENING-PROGRAMME.md` — PF scope/reasoning;
6. `09-PLANNING-RECONCILIATION.md` — requirements/findings/decisions/assumptions;
7. `rag/README.md` — source-truth retrieval index;
8. canonical/live issue body — issue-specific execution contract.

`01-INITIAL-IMPLEMENTATION-PLAN.md` is explicitly historical/non-executable.

## Governance observation

At the verification snapshot, GitHub reports `master` is not branch-protected and has no repository-enforced required status-check contexts. No administration change was made during this planning pass. `AGENTS.md` therefore explicitly requires branch → PR → required automated checks → merge → verify `master` discipline even when GitHub does not enforce it mechanically.

This does not block PF-001. If repository-admin branch protection is desired later, it is an optional governance hardening action rather than an unresolved renderer design dependency.

## Unresolved blockers

None at planning level.

Implementation uncertainties are intentionally localized to issue stopping conditions. In particular, PF-012 may fail closed on unresolved per-texel probe-selection semantics, PF-015 may fail closed if shadow overflow prioritization requires a product decision, SDVK-009 may conclude no higher-order many-light architecture is warranted, and SDVK-012 may conclude no new sprite-caster candidate qualifies. Those are valid evidence outcomes, not missing planning.

## Ready state

The repository is ready to begin **PF-001 / GitHub issue #18**.

SDVK-001 / #1 remains blocked until PF-020 / #37 accepts the complete pre-foundation tranche and explicitly records `SDVK-001: UNBLOCKED`.
