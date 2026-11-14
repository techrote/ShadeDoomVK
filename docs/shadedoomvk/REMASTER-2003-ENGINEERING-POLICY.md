# R-001 — Pragmatic renderer verification and development policy

**Decision:** Owner-approved direction, 14 November 2026. **Adoption:** pending review and integration of this planning branch and R-001's separate workflow implementation. This file does not itself change GitHub Actions or waive currently required CI while unmerged.

**Product North Star:** [The Lost 2003 Remaster](REMASTER-2003-CAMPAIGN.md). Visual plausibility, faithful classic Doom artwork, responsive gameplay and practical performance are the outcome. Exact per-frame/per-counter reproducibility is a tool for specific contracts, not a universal release goal.

## 1. Scope and governing authority

Upon accepted integration, this policy supersedes incompatible **future-work acceptance guidance** in `AGENTS.md`, `05-AUTONOMOUS-ISSUE-GRAPH.md`, `06-VALIDATION-PERFORMANCE-CONTRACT.md`, and founding #8/#9/#11–#17 **only where explicitly stated below**. Historical results, accepted PF/SDVK resource-safety contracts, prior incident STOPs, and existing CI-required checks remain factual and effective until independently and deliberately changed.

Owner approval of a strategic reset does **not** retroactively award passing status to failed campaigns, excuse unresolved proven faults or complete legacy issue acceptance criteria. Historical issues remain open until transfer is verified and the owner separately approves closure.

## 2. Severity and decision rule

Classify a finding by **observable impact, credible failure mechanism, likelihood and affected scope**, not by whether two internal records differ.

| Class | Treatment | Examples |
| --- | --- | --- |
| **P0 — Critical** | Immediate stop on affected path; preserve targeted evidence and isolate promptly. | New device loss, crash, memory corruption, invalid Vulkan synchronization that could corrupt resources, uncontrolled GPU failure, wrong-gameplay state. |
| **P1 — Material** | Block the affected change or supported mode until fixed, explicitly disabled or safely contained. | Persistent missing geometry, broken materials/lighting, demonstrably stale descriptors, severe shadow leakage, broken compatibility fallback, major performance collapse. |
| **P2 — Limited visual/quality issue** | Timebox analysis; accept only with scope, bounds, owner-visible risk and fallback. | Isolated small pixel differences, limited edge shimmer, occasional benign shadow popping without wider corruption. |
| **P3 — Incidental/diagnostic** | Record and proceed unless evidence links it to functional failure. | Irrelevant frame timing, legitimate startup texture epochs, harmless counters with unchanged supported behavior. |

**Unexplained ≠ safe, and unexplained ≠ automatically blocking.** A P2/P3 classification needs a reasoned consequence assessment, not a blanket waiver. Evidence of an invalid resource or unsafe GPU operation remains blocking even if the final RGB image matches.

**SDVK-161 example:** Original frame-37 80/84 vertex and 22/23 empty-upload mismatch remains a real unexplained source-side observation. Its identical final RGB and subsequent non-reproductions support bounded triage, **not** an assertion that the missing submission was correct or its cause fixed. Preserve the original failed receipt; retire the universal exact-repeatability veto only after a reviewed risk disposition, without falsifying the result.

## 3. Visual fidelity and comparison strategy

- **Visible source sprite artwork, alpha silhouette, palette/translation and animation:** preserve literally unless a separate explicit content-change feature is approved. Source-asset hashing and exact byte comparisons remain appropriate where applicable.
- **Raster effects, lighting, shadows and PBR:** evaluate against authored visual expectations, crispness, correct pose/receiver, absence of visible regressions, temporal stability and representative camera/play interactions. Per-scene tolerances must be declared; no universal `RGB == baseline` requirement.
- **Exactness remains appropriate where intrinsic to the contract:** serialization and archive identity, deterministic CPU transforms, exact source/payload hashes, game simulation/demo behavior, resource ownership transitions when a feature relies on them, and negative controls for known material defects.
- **Do not substitute images for safety correctness:** preserve explicit OOB/descriptor/resource-lifetime and Vulkan-validity tests independent of pixel appearance.
- For a changed effect, include OFF/ON comparisons, a representative positive, at least one adversarial/edge case and one playable/temporal check where applicable. Owner visual inspection can be an explicit acceptance step.

A visual comparison algorithm may use bounded area/colour/edge tolerances, perceptual metrics or structural/semantic checks. Document its failure class and demonstrate that an intentionally wrong case fails. Do not tune a threshold merely until a previously failed run turns green.

## 4. CI: three lanes, not a 3-hour tax on every PR

**Lane A — Routine (required):** relevant C++/shader/tool compilation, focused CPU/source checks, quick renderer smoke on a safe hosted software-Vulkan backend if affected, source-asset/branch identity and minimal OFF/ON snapshots. Start with existing stable check names and verify branch rules before changing them. **10–20 minutes is an aspirational target** and must be measured.

**Lane B — Targeted (change/risk-triggered):** resource lifetimes, portal/mirror recursion, lightmap/LevelMesh, stress, cross-build, visual regressions and compatible shadow verification only when files or identified failure modes justify them. Trigger reasons visible in CI. A known failing but unrelated historical research gate must not silently reclassify every new visual PR as broken.

**Lane C — Deep/release (separate, not routinely blocking):** broad native corpus, longer rendering workloads, representative hardware performance and legacy scientific publication experiments when warranted. These tests remain runnable; their historical contracts are not rewritten. They become release blockers only for clearly declared release promises or a newly identified material safety issue.

R-001 must implement a robust workflow selector, mandatory lightweight status/check identity, and risk escalation policy. **Do not make a required check disappear and interpret its absence as PASS.** Do not use labels or path-based skipping to silently bypass tests directly affected by the change. Validate both positive routing and deliberate negative conditions.

## 5. Evidence and operational budget

For routine work, report: source SHA, changed functionality, builds/tests, the meaningful result, one before/after image set where useful, measured cost if available and remaining limitations. No automatic multi-gigabyte publication archives for simple visual patches.

- Prefer bounded debug captures, compact JSON summaries and source-linked reproducers.
- Treat **50 MiB per routine PR** as an initial evidence-budget target, not a hard correctness threshold; document justified exceptions.
- Prefer **7-day retention** for transient routine artifacts, **30 days or intentional archival** for release/failure evidence; changing current workflow retention belongs to R-001, not this document's publication alone.
- One hypothesis-driven bounded investigation per minor anomaly, then classify, document and stop or seek explicit escalation. Unresolved P0/P1 failures are not automatically excused by a timebox.
- Distinguish native GPU elapsed time, runner occupancy, queue, archive compression and end-to-end CI; never claim a speedup from incomplete failed runs.

## 6. Physical GPU and security boundary

**The historical physical STOP remains ACTIVE.** No previous hardware-fault diagnostic permissions, GPU testing protocol, kernel dump handling, device/driver changes or security reviews are relaxed here. Hosted software Vulkan is for software correctness, not physical safety or benchmark acceptance. The owner must separately define any safe resumption policy.

Do not promote a potential device/driver fault to a confirmed vendor security defect without evidence. Keep the original CFX/PSIRT history intact.

## 7. Render philosophy and dependency governance

Raster-first, no **required** ray/path tracing, physically evocative rather than obligatorily physically exact, precise visible source pixels and deliberately processed *shadow* masks. See [SHADOW-001](SHADOW-001-SPRITE-SHADOW-PROJECTION.md).

Founding #8/#9/#11–#17 are **historical programme records**. Their rigid dependency chain does not automatically bind new R-001/SHADOW-001/MAT-001/LIGHT-001/PERF-001/WORLD-001/PLAY-001 work. Only actual code, hardware safety, data/resource contracts and demonstrated dependencies block new work. Preserve useful findings and provenance per [transfer ledger](REMASTER-2003-HISTORICAL-TRANSFER.md).

## 8. Adoption and verification

1. Owner-approved design scope is published on a planning branch; retain the original source master and unchanged runtime/physical safeguards.
2. Open R-001 implementation with workflow and rule changes as a distinct reviewable PR; validate changed CI topology on *a bounded, source-matched cohort* and audit required-check compatibility.
3. After successful required checks and independent review, guarded merge the supersession and workflow changes. Verify master commit/tree and record accepted policy version.
4. Only then mark R-001 policy authoritative; no draft-branch document or nonqualifying diagnostic claims a completed migration.
5. Historical findings and issues are transferred with links before any separate owner-approved closures.

**Hard stop:** policy cannot be used to conceal confirmed unsafe GPU/resource behavior, break gameplay, or suppress applicable failing checks.
