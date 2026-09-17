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

Until the baseline/rebranding issue is completed, some executable names, documentation and source identifiers still say `VKDoom`. This is expected and must not be silently mass-renamed without compatibility review.

## Current implementation gate

**SDVK-001 must not begin until the pre-foundation hardening programme PF-001 through PF-020 is accepted.**

The deeper VKDoom baseline audit found several source-level correctness defects, partially wired probe/tiled-light systems, raw renderer-resource identity risks and high-value output-equivalent refactors/optimizations. PF-001..PF-020 resolves that ground before the original feature roadmap diverges further.

PF-020 is the hard release gate into SDVK-001.

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
- bindless slot reuse already exists, but lifetime/capacity/reservation hardening is still required;
- per-lightmap probe selection is incomplete/stubbed in the audited baseline;
- tiled-light infrastructure exists as dormant scaffolding rather than an active clustered-light path;
- HDR/postprocess/depth/normal infrastructure is stronger than the founding plan initially assumed.

## Building

The inherited VKDoom build remains the PF execution substrate until SDVK-001 formally reconciles ShadeDoomVK identity/build documentation. PF work must keep applicable inherited CI/build paths working; it must not smuggle rebranding/build-policy scope out of SDVK-001.

## License

GPL-3.0, with inherited third-party licensing and contributor notices retained. Donor code must preserve its provenance and compatible license obligations.
