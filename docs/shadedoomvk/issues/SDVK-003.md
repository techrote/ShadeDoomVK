# SDVK-003 — VKDoom/UZDoom/GZDoom differential and upstream maintenance strategy

## Purpose
Define how ShadeDoomVK remains maintainable while preserving VKDoom-specific renderer capability.

## Autonomous execution prompt
Complete SDVK-003 after SDVK-001. Read `AGENTS.md`, all founding docs, especially `04-DONOR-PROVENANCE.md`, and current source history. At execution time identify and pin the current suitable UZDoom/GZDoom/VKDoom references rather than relying on stale names or unpinned branches. Work on a dedicated branch; document evidence; PR; repair CI; merge after required checks; verify `master`; close only if policy is actionable.

## Required research
- Diff current ShadeDoomVK baseline against pinned current UZDoom/GZDoom lineage for engine compatibility, Vulkan backend, resource system, scripting, platform/build and security/robustness changes.
- Identify VKDoom-specific lightmapper/probe/ray-query features that would be lost or materially changed by wholesale rebase.
- Trial at least one small representative selective upstream import or dry-run merge to expose conflict topology.
- Define owned ShadeDoomVK renderer surfaces versus periodically syncable upstream surfaces.
- Define provenance/merge procedure and conflict tests.
- Do not perform a wholesale rebase unless evidence makes that a separately reviewed necessity.

## Acceptance criteria
- Exact upstream versions/commits and meaningful deltas are recorded.
- A repeatable selective-sync policy exists.
- Renderer-specific ownership boundaries are explicit.
- At least one representative sync path is practically exercised or a precise blocker is recorded.
- No accidental loss of inherited VKDoom features.
- PR merged and verified on `master`.

## Dependencies
SDVK-001.