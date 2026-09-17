# ShadeDoomVK autonomous development rules

This file is authoritative for autonomous issue execution unless a later accepted issue or decision record explicitly supersedes a rule.

## 1. Source of truth

For every issue, read the issue body, current `master`, this file, and the planning documents under `docs/shadedoomvk/` before changing code. Later accepted repository documentation outranks stale chat context. Do not invent requirements from memory when the repository contains a more precise contract.

## 2. Branch → PR → checks → merge discipline

For implementation/research issues:

1. inspect current `master` and the complete relevant open/closed issue/PR history;
2. confirm dependencies are genuinely satisfied;
3. work on a dedicated branch;
4. add implementation, tests, diagnostics and documentation required by the issue;
5. open a PR with evidence and acceptance-criteria mapping;
6. repair every required automated check failure attributable to the change;
7. merge only after all required automated checks pass;
8. verify the merge commit/change is present on `master`;
9. close the issue only when its acceptance criteria are genuinely satisfied.

If blocked, record the exact blocker, evidence and safe next action. Do not weaken acceptance criteria merely to close an issue.

## 3. Renderer truthfulness

ShadeDoomVK may use approximations, but the engine and documentation must identify what they represent. Do not describe normal mapping as geometry, height/parallax as true displacement, projected sprite shadows as ray-traced sprite geometry, or baked/probe lighting as fully dynamic GI.

Fallbacks must be explicit and inspectable.

## 4. Compatibility preservation

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

## 5. Simulation versus rendering

Gameplay remains governed by Doom-family simulation/tic semantics unless an issue explicitly changes gameplay. High-frame-rate rendering, interpolation, temporal filters and shader animation must not silently alter deterministic simulation state.

## 6. Performance evidence

Do not claim an optimization from code shape alone. Measure before/after using deterministic scenes and the repository benchmark/diagnostic harness once established. Record CPU frame, GPU frame where available, draw/light/shadow counts, memory/descriptor usage and relevant effect-specific costs.

A fast but materially wrong lighting/shadow/material result is a regression, not an optimization.

## 7. Donor and upstream provenance

Before copying or adapting code from VKDoom/GZDoom/UZDoom or a fork:

- identify exact repository and commit;
- establish whether the change is already ancestral to current `master`;
- preserve license/copyright requirements;
- document whether code was cherry-picked, adapted, reimplemented from concept, or rejected;
- prefer the smallest understandable transplant over importing unrelated fork history.

`docs/shadedoomvk/04-DONOR-PROVENANCE.md` is the starting donor register and must be updated when material donor work is added.

## 8. Vulkan/resource safety

Descriptor indices, bindless slots, lightmap/probe indices and acceleration-structure references are renderer identities, not durable semantic identities. Reuse must not permit stale references. Generation/lifetime validation is preferred when indices can be recycled.

No emergency cache flush may leave LevelMesh/material structures pointing at stale slots.

## 9. Materials

Treat material channels semantically. Albedo, normal, height, roughness, metallic, AO and emissive data may require different color spaces, sampling, mip and filtering behavior. Do not force all layers through the albedo sampler policy for convenience.

Mirrored/rotated sprites must preserve tangent-space correctness.

## 10. Testing and negative evidence

Every renderer feature needs at least one positive fixture and one deliberate edge/negative fixture. Keep minimized reproducers for visual corruption, crashes, descriptor exhaustion, portal errors, shadow acne/light leaks and materially incorrect light selection.

Where image comparisons are used, pair them with machine-readable state/diagnostic assertions so CI does not depend only on subjective screenshots.

## 11. Scope control

Do not turn an issue into a general engine rewrite. Record adjacent defects as separate evidence/issues when they are materially independent. Conversely, do not split one atomic architectural change into artificial micro-issues merely to inflate progress.

## 12. Completion report

Every merged issue should leave enough repository evidence for another autonomous agent to understand:

- what changed;
- why;
- donor/upstream provenance where relevant;
- tests/benchmarks run;
- known limitations/fallbacks;
- follow-on dependencies unblocked.
