# ShadeDoomVK

ShadeDoomVK is a Vulkan-first experimental Doom-engine renderer fork based on VKDoom. Its purpose is to push the classic sprite-and-sector presentation toward materially rich, dynamically lit 2.5D rendering while preserving Doom-family gameplay, content semantics and mod compatibility wherever the renderer can do so honestly.

The project is focused on:

- dynamic world and actor lighting;
- normal-mapped and PBR sprite materials;
- explicit sprite-local tangent-space handling;
- height/parallax relief for sprites without requiring full 3D replacement models;
- light probes, baked/static lighting and dynamic lightmaps;
- ray-query world occlusion combined with sprite-aware projected/contact shadows;
- modern Vulkan descriptor/material infrastructure and measurable performance tiers;
- long-term renderer foundations suitable for HDR, bloom, richer volumetrics and later temporal work without sacrificing Doom semantics.

ShadeDoomVK's project version is `0.1.0-dev`. Build and startup diagnostics identify the project, source commit, working-tree state, founding VKDoom lineage and PF-020 freeze. Executables remain `vkdoom` / `vktool`; resource, configuration, save and protocol identifiers retain their inherited values. See [identity and compatibility policy](docs/shadedoomvk/SDVK-001-FOUNDATION.md).

## Current implementation gate

**PF-001 through PF-020 are accepted.** PF-020 was merged and verified on `master` at `e185e60b04fe37ec84a18c5a85eec6722b541b71` on 5 October 2026; [the release receipt](docs/shadedoomvk/PF-020-RELEASE-ACCEPTANCE.json) records its evidence and limits. SDVK-001 establishes the project/build foundation on that freeze. SDVK-002 and SDVK-003 require SDVK-001's verified merge; [the execution ledger](docs/shadedoomvk/10-EXECUTION-LEDGER.md) records programme transitions.

The advanced material, sprite relief and shadow goals above are the founding feature programme. PF acceptance establishes the hardened baseline and does not imply those later features are implemented.

## Canonical programme

The autonomous development programme is defined in:

- `AGENTS.md` — mandatory autonomous execution rules and issue contract;
- `docs/shadedoomvk/00-FOUNDING-BRIEF.md` — goals, non-goals and invariants;
- `docs/shadedoomvk/01-INITIAL-IMPLEMENTATION-PLAN.md` — first-pass plan preserved for history;
- `docs/shadedoomvk/02-PLAN-REVIEW.md` — founding review plus source-audit amendment;
- `docs/shadedoomvk/03-REVISED-ROADMAP.md` — dependency-ordered PF + SDVK roadmap;
- `docs/shadedoomvk/04-DONOR-PROVENANCE.md` — donor/upstream audit and corrected provenance;
- `docs/shadedoomvk/05-AUTONOMOUS-ISSUE-GRAPH.md` — complete PF/SDVK dependency graph and concurrency rules;
- `docs/shadedoomvk/06-VALIDATION-PERFORMANCE-CONTRACT.md` — correctness/equivalence/performance evidence rules;
- `docs/shadedoomvk/07-ISSUE-EMISSION-STATUS.md` — stable ID ↔ GitHub issue mapping;
- `docs/shadedoomvk/08-PREFOUNDATION-HARDENING-PROGRAMME.md` — long pre-SDVK refactor/correctness/performance tranche;
- `docs/shadedoomvk/09-PLANNING-RECONCILIATION.md` — requirements/preferences/research/decisions/assumptions classification;
- `docs/shadedoomvk/10-EXECUTION-LEDGER.md` — programme-level execution ledger;
- `docs/shadedoomvk/rag/` — source-linked renderer architecture/invariant references for autonomous agents.

## Baseline

The founding ShadeDoomVK repository starts from VKDoom commit `09634479ab5bf9adf691074fffe85a006a398cd0`.

Do not assume a donor patch is missing merely because it exists in another VKDoom fork. Several apparently separate forks are ancestral to this baseline. Check Git history, current source and `04-DONOR-PROVENANCE.md` before importing code.

Important source-audit corrections include:

- per-layer material sampling is already inherited;
- bindless slot reuse is inherited; PF-002/003 hardened lifetime, capacity and reservation boundaries;
- PF-012 replaced the founding per-lightmap probe-selection stub with bounded selection and explicit fallback;
- tiled-light infrastructure exists as dormant scaffolding rather than an active clustered-light path;
- HDR/postprocess/depth/normal infrastructure is stronger than the founding plan initially assumed.

## Building

Follow [Building and running ShadeDoomVK](docs/BUILDING.md) for Windows/Linux commands, dependencies, CPU checks and executable provenance verification. Use a fresh build directory under `build/`; keep historical qualification builds intact.

From a configured C++ developer environment:

```text
python tools/check.py
```

Both executables support `--version` without an IWAD or renderer initialization. Ordinary play requires your own supported game IWAD and the resources built from this checkout.

## License

GPL-3.0, with inherited third-party licensing and contributor notices retained. Donor code must preserve its provenance and compatible license obligations.
