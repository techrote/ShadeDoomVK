# SDVK-009 software dependency authority and physical acceptance hold

Decision ID: **SDVK-009-GATE-SPLIT-20261014**
Date: **14 October 2026**
Owner approval: explicit programme-owner instruction to separate these gates.
Effect: governing repository authority when this documentation change is merged.

## Decision

Separate two acceptance dimensions within the existing SDVK-009 / issue #9.
Do not renumber or close #9, and do not create an alternative lighting architecture.

| Gate | Disposition | Meaning |
| --- | --- | --- |
| **SDVK-009-SW** | **QUALIFIED FOR DOWNSTREAM SOFTWARE WORK** | The existing PF lighting architecture, with the merged correctness fixes and bounded software evidence, is the dependency baseline for SDVK-011 and SDVK-014. |
| **SDVK-009-PHYSICAL** | **HELD / NOT ACCEPTED** | Physical GPU performance, representative scaling, hardware stability and final physical architecture suitability remain unqualified. |

**State C / provisional no-change remains the overall many-light decision.**
The software gate is permission to build on the current implementation, not a
finding that this architecture is the fastest, sufficiently scalable on physical
hardware, or free of every possible defect. The historical physical fault root
cause remains **UNDETERMINED**. **Physical STOP remains ACTIVE.**

This explicitly supersedes older statements that #11/#14 must wait for *all* of
#9's physical acceptance before beginning or merging software work. It supersedes
only those dependency edges. Original physical protocols, failed receipts,
workloads, thresholds and the full #9 completion criteria are not rewritten.

## Evidence and baseline

The reconciled starting baseline is merged master
`6aadd8458773014e4333cf93cf4b4269ce5733b3`, tree
`c520fd111c8da5c6714c60a5bc256247e4569577` (PR #148).

- [SDVK-009 software disposition](https://github.com/techrote/ShadeDoomVK/issues/9#issuecomment-6134452869)
  records #146's publication/SPIR-V/resource/fence/readback software qualification
  and State-C no-change decision. Physical acceptance remains held.
- [SDVK-010 final acceptance](https://github.com/techrote/ShadeDoomVK/issues/10#issuecomment-6167916940)
  records #148's integrated sunlight/world-occlusion and linked-portal actor
  correctness acceptance, review, guarded merge and exact-master tree equality.
- [Required CI 38493635327](https://github.com/techrote/ShadeDoomVK/actions/runs/38493635327)
  passed all nine jobs on authored head
  `a98a6144e65c6edac5ced478c8269a77255fe65e`; source evidence
  [38493635271](https://github.com/techrote/ShadeDoomVK/actions/runs/38493635271)
  also passed. Its tested merge checkout
  `43b87add782f5b050219523593434e4318433123` has the same tree as merged master.
  The existing Avrea16 software job includes both actor pairs, 16 real-record
  falsifications, the inherited corpus and the unchanged SDVK-009 publication gate.

This decision consumes those bounded results; it makes no new measurement or
claim about private physical incident bytes. Later descendants must preserve the
same contracts and pass their own required checks; the baseline hash is evidence,
not a demand that downstream branches remain forever on one commit.

## Exact dependency edges

| Consumer | Software entry gate | Scope now permitted | Still held |
| --- | --- | --- | --- |
| **SDVK-011 / #11** | SDVK-009-SW + accepted SDVK-010 | Implement explicit legacy/sector/enhanced viewmodel lighting modes, projection-aware fallbacks, material parity, diagnostics and deterministic CPU/hosted-software correctness fixtures. | Physical launches, physical GPU cost/stability claims, automatic parity for unsupported HUD projection effects. |
| **SDVK-014 / #14** | Accepted SDVK-002 and SDVK-005 + SDVK-009-SW + accepted SDVK-010 | Implement the software robustness campaign: bake/load/delete and update logic, atlas/probe lifetime/reset/rebuild stress, supported surface/portal cases, diagnostics and bounded software-Vulkan CI smoke. | Physical bake/update GPU cost, representative hardware scaling/stability or full campaign acceptance where physical evidence is still required. |

The existing #2/#5 prerequisites are retained, not bypassed. #10 is accepted
through PR #148. **#11 and #14 are dependency-ready for their software scopes,
not implemented or accepted by this decision.** They may proceed in parallel
on separate branches when shared observer/probe/material files are coordinated.
Each real implementation gets its normal review and required CI; do not add
parallel comparator runners or repeat CI solely to benchmark runner sizes.

SDVK-012's #8/#9 dependency and SDVK-015/016/017 compatibility, performance,
default and freeze gates are **not** released by this decision. A GitHub issue's
closed flag is not evidence that all its technical/physical requirements passed.
No SDVK-008 relief mode or missing acceptance case is newly accepted here.

## Contract inherited by both consumers

Preserve PF-011 lighting/compatibility math, PF-015 visibility and shadow policy,
PF-016 eligibility/order/portal-relative query semantics and PF-017's restored
contiguous light path. PF-019's dormant tiled producer stays disabled; neither
its truncated tile payload nor the rejected temporal-reuse candidate is revived.
Do not obtain a pass or speedup by dropping eligible lights, changing quality,
loosening state/image thresholds or extending a failed timeout.

Preserve PF-002/003/004 lifetime/generation rules and PF-012/PF-113 probe authority:
authored ordinal zero is valid; absent/unpublished selection uses the explicit
runtime-zero fallback; valid irradiance and adjacent prefilter descriptors share
the proven lifetime/epoch. Consume SDVK-010's conservative portal-sector selection,
source-versus-presentation ownership, accepted sprite orientation and traced-sun
parity. These are not new viewmodel projection rules or universal bake guarantees.

Source symbols remain those in the [lighting RAG](rag/05-LIGHTING-SHADOW-TRUTH-TABLE.md)
and [probe RAG](rag/06-LIGHTMAP-PROBE-PIPELINE.md), particularly
`HWDrawInfo::GetDynSpriteLightList`, `HWActorProbeSelection::Resolve`,
`VkRenderState::ApplySurfaceUniforms` and the existing PBR `traceSun`/PF-113
sampling routes. No renderer, shader, fixture, settings or workflow change is
part of this decision.

## Execution, acceptance and reporting

Authorized software work is source inspection/implementation, CPU/static/compiled
fixtures and explicitly isolated hosted software-Vulkan correctness qualification.
Do not launch a renderer or create a Vulkan device in the ordinary coding
environment. Physical GPU execution, driver/firmware/BIOS/settings changes and
retries of either sealed physical failure remain forbidden under Physical STOP.

Downstream PRs must name the consumed gate **SDVK-009-SW**, map their own acceptance
criteria to evidence, preserve existing negative controls, retain failures and
record exact source/build/runtime identities. Green CI is not proof of untested
hardware behavior. Hosted CPU/llvmpipe timings may be reported descriptively for
that host; they are not physical-GPU speedups, budgets or performance acceptance.

Software-qualified increments of #11/#14 may be reviewed, merged and exact-master
verified without waiting for SDVK-009-PHYSICAL. Overall issue closure still requires
the consumer's own declared criteria. Where a required physical result is missing,
record **software complete / physical held** and leave the issue or an explicitly
approved tracked physical acceptance scope open. In particular #14's requested
physical cost/scaling evidence is not silently deleted or marked passed. Nothing
here automatically closes #11/#14 or qualifies later defaults/release gates.

## Reblocking and physical resumption

A reproducible foundational error in eligibility, visibility, probe/descriptor
identity, portal ownership or accepted fallback reblocks the *affected* software
consumer; record the upstream regression and preserve its failing fixture rather
than compensating locally or citing this decision as a waiver. A new many-light
architecture or changed selection/quality policy requires its own explicit
qualification and programme decision.

#9 remains the visible owner of the held physical campaign. Resumption requires a
separate, explicit owner authorization after a defensible discriminator/repair or
new experiment has been reviewed, with prospective exact source/content/host
identity, stop conditions and retained failure evidence. Existing fixed workloads,
thresholds and no-automatic-retry rules remain binding unless a separately approved
prospective protocol explicitly changes them. This decision is **not** that
resumption authorization, and no post-failure evidence is relabelled as a pass.

Machine-readable counterpart:
[SDVK-009-DEPENDENCY-DISPOSITION.json](evidence/SDVK-009-DEPENDENCY-DISPOSITION.json).
