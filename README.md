# ShadeDoomVK

ShadeDoomVK is a Vulkan-first experimental Doom-engine renderer fork based on VKDoom. Its purpose is to push the classic sprite-and-sector presentation toward materially rich, dynamically lit 2.5D rendering while preserving Doom-family gameplay, content semantics and mod compatibility wherever the renderer can do so honestly.

The project is focused on:

- dynamic world and actor lighting;
- normal-mapped and PBR sprite materials;
- explicit sprite-local tangent-space handling;
- height/parallax relief for sprites without requiring full 3D replacement models;
- light probes, baked/static lighting and dynamic lightmaps;
- ray-query world occlusion combined with sprite-aware projected/contact shadows;
- modern Vulkan descriptor/material infrastructure and measurable performance tiers.

Until the baseline/rebranding issue is completed, some executable names, documentation and source identifiers still say `VKDoom`. This is expected and must not be silently mass-renamed without compatibility review.

## Founding plan

The autonomous development programme is defined in:

- `AGENTS.md` — execution rules for autonomous implementation agents;
- `docs/shadedoomvk/00-FOUNDING-BRIEF.md` — goals, non-goals and invariants;
- `docs/shadedoomvk/01-INITIAL-IMPLEMENTATION-PLAN.md` — first-pass plan preserved for history;
- `docs/shadedoomvk/02-PLAN-REVIEW.md` — critique of the first-pass plan;
- `docs/shadedoomvk/03-REVISED-ROADMAP.md` — reviewed dependency-ordered roadmap;
- `docs/shadedoomvk/04-DONOR-PROVENANCE.md` — VKDoom-fork donor audit and exact commit provenance;
- `docs/shadedoomvk/05-AUTONOMOUS-ISSUE-GRAPH.md` — issue graph and execution order;
- `docs/shadedoomvk/06-VALIDATION-PERFORMANCE-CONTRACT.md` — evidence, compatibility and performance rules.

## Baseline

The founding ShadeDoomVK repository starts from VKDoom commit `09634479ab5bf9adf691074fffe85a006a398cd0`.

Do not assume a donor patch is missing merely because it exists in another VKDoom fork. Several apparently separate forks are ancestral to this baseline. Check Git history and `04-DONOR-PROVENANCE.md` before importing code.

## Building

The inherited VKDoom build remains authoritative until SDVK-001 updates it. On Windows the conventional baseline is Visual Studio + Windows SDK + CMake; Linux uses SDL2/OpenAL/VPX plus CMake/Ninja or Make. Every implementation issue must keep required CI green and document any deliberate platform support change.

## License

GPL-3.0, with inherited third-party licensing and contributor notices retained. Donor code must preserve its provenance and compatible license obligations.
