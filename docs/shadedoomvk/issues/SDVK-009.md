# SDVK-009 — Scalable many-light architecture qualification

## Objective
Determine, from the PF-optimized baseline and SDVK-002 measurements, whether ShadeDoomVK needs a higher-order scalable many-light architecture, and select/implement only an evidence-backed next step without changing lighting semantics.

## Scope / required work
- Profile PF-016/PF-017 actor/scene light collection, upload and shader cost under increasingly dense lights/materials/scenes.
- Audit the inherited dormant Z-min/max/light-tile compute/buffer/pipeline scaffold in current source: establish exactly what is usable, obsolete, incomplete or already gated by PF-019.
- Compare feasible strategies such as repairing the inherited tiled path, modern forward+/clustered culling, improved per-object/section lists, or retaining PF architecture if it meets measured goals.
- Require selected-light/portal/occlusion semantic equivalence for any architecture intended as an equivalent path; isolate quality-tier culling decisions for SDVK-016.
- Prototype/implement the smallest winning architecture only when evidence supports it; otherwise commit a no-change decision with thresholds that would reopen research.
- Instrument CPU/GPU light-culling/upload/shader work and overflow/fallback behavior.

## Non-goals
No arbitrary light caps/quality reduction; no shadow-caster architecture; no reimplementation of PF-016 small-actor fast path; no assumption the dormant tiled scaffold is correct merely because it exists.

## Dependencies
SDVK-002, SDVK-003. PF-016/PF-017/PF-019 are inherited via PF-020.

## Concurrency guidance
May proceed in parallel with SDVK-004/005/006/007/008 as dependencies allow, but SDVK-011/012/014 consume accepted lighting architecture and wait where required.

## Required context
Read `AGENTS.md`, PF freeze/PF-016/017/019 evidence, lighting/Vulkan/trap RAG, SDVK-002/003 evidence and canonical body.

## Autonomous implementation prompt
Complete SDVK-009 autonomously as comparative performance/architecture research. Measure current hardened baseline, audit dormant scaffold, prototype only promising candidates, preserve semantic lighting or clearly label future quality policy, commit evidence and implementation/no-change decision, branch→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
Current bottlenecks quantified; dormant tiled infrastructure truthfully classified; candidates compared on same workloads; any adopted path preserves declared light/portal/occlusion semantics and has deterministic overflow/fallback; measured improvement justifies complexity, or evidence-backed no-change decision recorded; PR merged/verified.

## Verification
Sparse→dense light scales, many sprites/models/world surfaces, portals/occlusion, CPU/GPU timings, selected-light comparison, overflow tests and PF/SDVK image/state oracle.

## Expected artifacts
Many-light research report, prototypes/results, selected architecture implementation or no-change ADR, diagnostics/benchmarks, lighting/Vulkan/trap RAG and ledger updates.

## Blocking / stopping conditions
Do not adopt an architecture that only wins by silently dropping eligible lights or changing quality. If candidates do not beat the PF baseline enough to justify complexity, record that result and retain the simpler system.

## Non-physical qualification candidate — 2026-10-09

Dedicated branch: `sdvk-009-many-light-qualification`. Starting live authority:
`master@cafbad5c45977327ba507bcf5f2dea9c3661f3d3`.

The complete off-GPU audit is recorded in
[SDVK-009-NON-GPU-QUALIFICATION.md](../SDVK-009-NON-GPU-QUALIFICATION.md), with
the later physical protocol in
[SDVK-009-GPU-QUALIFICATION-PROTOCOL.md](../SDVK-009-GPU-QUALIFICATION-PROTOCOL.md).

Current disposition is **State C / provisional no-change**. The inherited tile
path is not a qualified candidate: it hard-caps each 64x64 tile at 16 copied
light records, its dormant LevelMesh producer still has unresolved portal-group
packing, and the existing LevelMesh light-index lists have lightmapper-specific
eligibility plus a four-portal-copy cache boundary. PF-017's temporal packed-light
reuse/indirection remains an accepted physical no-go and is not resurrected.

This phase adds bounded state-only many-light diagnostics, two deterministic
256-light overlap/dispersed workloads, hosted software-Vulkan qualification for
them, and a correctness repair for a one-past immediate-light range index. No
quality cap, shadow policy or lighting semantic is changed. A host-only indexed
tile model is retained as representation research only; it is not a runtime
candidate or performance claim.

**#9 remains open.** Final acceptance still requires the finite representative
physical-GPU campaign defined in the protocol unless later repository authority
changes that requirement.
