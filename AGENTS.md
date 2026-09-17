# ShadeDoomVK autonomous development rules

This file is authoritative for autonomous issue execution unless a later accepted issue or decision record explicitly supersedes a rule.

## 1. Source of truth

For every issue, read the issue body, current `master`, this file, and the relevant canonical documents under `docs/shadedoomvk/` before changing code. Later accepted repository documentation outranks stale chat context. Do not invent requirements from memory when the repository contains a more precise contract.

The renderer RAG/reference corpus under `docs/shadedoomvk/rag/` is mandatory reading when an issue touches its subsystem. RAG material describes architecture/invariants and does not replace inspection of current source.

## 2. Programme gate

The pre-foundation tranche PF-001 through PF-020 executes before the founding SDVK feature programme.

- **Do not begin SDVK-001 until PF-020 is accepted, merged and verified on `master`.**
- PF-020 must fail closed while a PF blocker can corrupt renderer identity, produce materially wrong light/probe/shadow state, break a declared compatibility path, or invalidate a shared PF contract.
- Existing SDVK-001..017 IDs remain stable; PF work is not permission to silently consume later feature scope.

Canonical programme documents include:

- `08-PREFOUNDATION-HARDENING-PROGRAMME.md`;
- `09-PLANNING-RECONCILIATION.md`;
- `10-EXECUTION-LEDGER.md`;
- `05-AUTONOMOUS-ISSUE-GRAPH.md`;
- `06-VALIDATION-PERFORMANCE-CONTRACT.md`;
- `rag/README.md` and relevant subsystem references.

## 3. Branch → PR → checks → merge discipline

For implementation/research issues:

1. inspect current `master` and the complete relevant open/closed issue/PR history;
2. confirm dependencies are genuinely satisfied;
3. restate the issue objective and relevant invariants before implementation;
4. work on a dedicated branch;
5. add implementation, tests, diagnostics and documentation required by the issue;
6. open a PR with evidence and acceptance-criteria mapping;
7. repair every required automated check failure attributable to the change;
8. merge only after all required automated checks pass;
9. verify the merge commit/change is present on `master`;
10. close the issue only when its acceptance criteria are genuinely satisfied.

If blocked, record the exact blocker, evidence, affected dependents and safe next action. Continue independent work where possible. Do not weaken acceptance criteria merely to close an issue.

Repository branch protection is not a substitute for this rule; follow it even when GitHub does not technically enforce the checks.

## 4. Required issue contract

Every implementation/research issue must contain or link unambiguously to:

- objective;
- scope / required work;
- non-goals;
- hard dependencies;
- concurrency guidance;
- required canonical context/RAG references;
- autonomous implementation prompt;
- acceptance criteria;
- verification instructions/evidence;
- expected repository artifacts;
- blockers and stopping conditions.

Shared architecture belongs in canonical documents rather than being duplicated across issue bodies.

## 5. Renderer truthfulness

ShadeDoomVK may use approximations, but the engine and documentation must identify what they represent. Do not describe normal mapping as geometry, height/parallax as true displacement, projected sprite shadows as ray-traced sprite geometry, or baked/probe lighting as fully dynamic GI.

Fallbacks must be explicit and inspectable.

## 6. Compatibility preservation

Preserve Doom/GZDoom/VKDoom content behavior by default. New rendering behavior should normally be opt-in per material/actor/map or controlled by clearly documented quality/compatibility settings until evidence supports changing defaults.

Do not break:

- palette/translation semantics;
- sprite rotation/mirroring conventions;
- portals and portal groups;
- decals and warped materials;
- translucent/canvas textures;
- models/voxels/particles;
- classic lighting modes;
- demo/gameplay determinism for render-only features.

When compatibility and a new effect conflict, prefer an explicit capability/fallback rule over silent visual corruption.

## 7. Simulation versus rendering

Gameplay remains governed by Doom-family simulation/tic semantics unless an issue explicitly changes gameplay. High-frame-rate rendering, interpolation, temporal filters and shader animation must not silently alter deterministic simulation state.

## 8. Performance evidence and PF equivalence rule

Do not claim an optimization from code shape alone. Measure before/after using deterministic scenes and the repository benchmark/diagnostic harness once established. Record CPU frame, GPU frame where available, draw/light/shadow counts, memory/descriptor usage and relevant effect-specific costs.

For PF-005 and PF-016..PF-019, performance changes are **output/state-equivalent optimizations** unless the issue explicitly owns a correctness fix. They may not gain speed by:

- selecting fewer otherwise eligible lights;
- changing filtering/mip/color-space behavior;
- lowering resolution/precision;
- changing accepted shadow/probe selection;
- silently disabling an active feature;
- changing gameplay or renderer-visible quality policy.

A fast but materially wrong lighting/shadow/material result is a regression, not an optimization.

## 9. Donor and upstream provenance

Before copying or adapting code from VKDoom/GZDoom/UZDoom or a fork:

- identify exact repository and commit;
- establish whether the change is already ancestral to current `master`;
- preserve license/copyright requirements;
- document whether code was cherry-picked, adapted, reimplemented from concept, or rejected;
- prefer the smallest understandable transplant over importing unrelated fork history.

`docs/shadedoomvk/04-DONOR-PROVENANCE.md` is the donor register and must be updated when material donor work is added.

Do not assume GriddleVK per-layer sampling is missing: the audited VKDoom baseline already contains materially equivalent per-layer sampling support. Treat donor history as provenance unless a concrete delta is proven.

## 10. Vulkan/resource safety

Descriptor indices, bindless slots, lightmap/probe indices, LevelMesh offsets and acceleration-structure references are renderer identities, not durable semantic identities. Reuse must not permit stale references. PF-002 defines the generation/lifetime contract used by later PF work.

No emergency cache flush may leave LevelMesh/material structures pointing at stale slots.

All fixed/reserved descriptor-range arithmetic must be bounds-checked against actual runtime/device capacity.

## 11. Materials

Treat material channels semantically. Albedo, normal, height, roughness, metallic, AO and emissive data may require different color spaces, sampling, mip and filtering behavior. Do not force all layers through the albedo sampler policy for convenience.

The inherited baseline already supports per-layer sampling for relevant custom layers. PF-008 preserves/exposes existing channel semantics; SDVK-005 later adds first-class height authoring/policy.

Mirrored/rotated sprites must preserve tangent-space correctness.

## 12. Views, portals and temporal state

Main view, portal/mirror recursion, camera textures and probe cubemap renders are distinct renderer contexts. Persistent view caches/history may not be shared between them unless the cache key proves equivalence.

PF-010 extracts render-view/pass identity. Future temporal effects must build on that contract rather than one global history buffer.

## 13. Testing and negative evidence

Every renderer feature/refactor needs at least one positive fixture and one deliberate edge/negative fixture. Keep minimized reproducers for visual corruption, crashes, descriptor exhaustion, portal errors, stale identities, probe selection, shadow acne/light leaks and materially incorrect light selection.

Where image comparisons are used, pair them with machine-readable state/diagnostic assertions so CI does not depend only on subjective screenshots.

Refactors must preserve baseline output/state within a declared tolerance. Bugfix issues must preserve a failing pre-fix fixture and demonstrate the corrected expected state.

## 14. Scope control

Do not turn an issue into a general engine rewrite. Record adjacent defects as separate evidence/issues when materially independent. Conversely, do not split one atomic architectural change into artificial micro-issues merely to inflate progress.

If a refactor supersedes a later assigned bugfix, preserve the bug reproducer and prove the refactor made the bad state impossible; do not close the bug silently as "no longer relevant" without evidence.

## 15. Canonical reference maintenance

When an accepted implementation changes architecture described under `docs/shadedoomvk/rag/`, update the affected RAG file in the same PR with:

- new invariant/state;
- source symbols/paths;
- fallback/limitation;
- issue/PR provenance where material.

PF-020 performs a complete reconciliation before SDVK-001.

## 16. Completion report

Every merged issue should leave enough repository evidence for another autonomous agent to understand:

- what changed;
- why;
- donor/upstream provenance where relevant;
- tests/benchmarks run;
- output/state equivalence or deliberate bugfix delta;
- known limitations/fallbacks;
- follow-on dependencies unblocked.

Append programme-level gate transitions to `docs/shadedoomvk/10-EXECUTION-LEDGER.md`.
