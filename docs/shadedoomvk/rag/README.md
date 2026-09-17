# ShadeDoomVK renderer RAG/reference index

Baseline source reference unless a document says otherwise: `nashmuhandes/VkDoom@09634479ab5bf9adf691074fffe85a006a398cd0`.

These references are compact retrieval aids for autonomous agents. They describe architecture, ownership, invariants, active versus dormant paths and known traps. They do **not** replace current source inspection. If source and a RAG document conflict after an accepted change, update the RAG document in the same PR.

## Documents

1. `01-RENDERER-EXECUTION-MAP.md` — frame/view/pass flow.
2. `02-RENDERER-IDENTITY-LIFETIME.md` — renderer resource identity and ownership.
3. `03-LEVELMESH-MUTATION-MATRIX.md` — LevelMesh state and invalidation responsibilities.
4. `04-MATERIAL-SHADER-CONTRACT.md` — current material/layer/shader meaning.
5. `05-LIGHTING-SHADOW-TRUTH-TABLE.md` — lighting/shadow modes and fallbacks.
6. `06-LIGHTMAP-PROBE-PIPELINE.md` — baked/dynamic lightmaps and environment probes.
7. `07-PORTAL-COORDINATE-SPACES.md` — portal/mirror/view and axis-space rules.
8. `08-VULKAN-PIPELINE-CAPABILITIES.md` — Vulkan descriptors/pipelines/capability seams.
9. `09-POSTPROCESS-HDR-FUTURE-SEAMS.md` — current postprocess/HDR substrate and temporal seams.
10. `10-KNOWN-TRAPS-DORMANT-PATHS.md` — explicit incomplete, dormant and dangerous assumptions.

## Status vocabulary

- **active** — used in ordinary current renderer execution.
- **partial** — real code/data exists but the path is incomplete or limited.
- **dormant** — infrastructure exists but current production execution does not use it.
- **experimental** — functional intent exists but correctness/stability is not sufficiently established for an architectural assumption.
- **fallback** — compatibility path used when an optional feature is absent/disabled.

## Change rule

PF-001 establishes fixtures that can falsify these documents. PF-020 must reconcile every document against the resulting source before SDVK-001 begins. Later issues must update affected RAG documents in the same accepted PR.
