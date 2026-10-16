# SDVK-014 — Lightmapper, dynamic-lightmap and probe robustness campaign

## Current audit status — 16 October 2026

**Implementation in progress; software campaign NOT ACCEPTED.** PR #151's
bounded atlas/tile/load repairs and PR #152's #150 semantic probe-owner repair
are merged. Verified master is `ca254b6ea08228c8408562ebba26bbc1060a0311`.
The #150 blocker is resolved; older candidate/reblocked notes below are historical.

The [durable identity audit](../SDVK-014-DURABLE-IDENTITY-AUDIT.md) now reblocks
**retained probe-map/live descriptor-reset acceptance on #153**. Exact production
CPU replay shows a filter reset can recycle a raw retained probe texel as another
valid probe pair. A separate copied-atlas-receipt ABA control exposes a missing
durable incarnation without claiming a reachable stale native surface.
See the [audit receipt](../evidence/SDVK-014-DURABLE-IDENTITY-AUDIT.json) and
[RAG addendum](../rag/13-DURABLE-IDENTITY-AUDIT.md). No production workaround is
included in the audit; evidence reproduction is not clean lifetime acceptance.

Accepted SDVK-002 / SDVK-005 / SDVK-009-SW / SDVK-010 remain authority for their
bounded scope. #153, durable allocation identity, repeated/multi-page native
transitions and supported special-surface/material lifecycle coverage remain
outstanding. Older [increment](../SDVK-014-CPU-INCREMENT.md) and
[production audit](../SDVK-014-PRODUCTION-AUDIT.md) evidence is retained unchanged.

**Not software-complete. Issue #14 remains OPEN. Physical STOP remains ACTIVE.**
Required physical GPU bake/update cost, scaling and stability remain HELD / NOT
ACCEPTED. Historical physical root cause remains UNDETERMINED. See the
[governing gate decision](../SDVK-009-SOFTWARE-DEPENDENCY-AUTHORITY.md).

## Objective
Stress and harden the integrated lightmapper/dynamic-lightmap/probe system after PF-012 establishes correct/basic probe plumbing and SDVK material/many-light/actor-environment semantics are in place.

## Scope / required work
- Stress static bake/load/delete round trips, AO/bounce/sun combinations and dynamic-lightmap updates.
- Cover moving/changing sectors/lights/polyobjects where supported, atlas create/repack/rebuild across multiple pages and repeated level/resource transitions.
- Stress probe-map/index lifetime, environment cubemap reset/rebake and transitions using PF-012/SDVK-010 semantics.
- Cover decals, warped/reflective/translucent surfaces, portals/Line_Horizon/3D-floor interactions where supported.
- Verify semantic material/height additions do not corrupt baked/dynamic lightmap state.
- Collect bake/update CPU, memory and upload evidence plus descriptive hosted-software timings and tractable CI smoke. Keep the required physical-GPU cost/scaling part explicitly held; do not substitute llvmpipe timings or delete that requirement.
- Classify all discovered failures as fix, explicit fallback/limitation, baseline incompatibility or blocker.

## Non-goals
No reinvention of PF probe-map selection; no actor IBL policy redesign; no speculative global illumination claim; no hidden quality reduction to make dynamic updates cheap.

## Dependencies
Accepted SDVK-002 and SDVK-005, SDVK-009-SW (qualified software dependency), and accepted SDVK-010.

The [SDVK-009 gate split](../SDVK-009-SOFTWARE-DEPENDENCY-AUTHORITY.md) is authoritative.
SDVK-009-PHYSICAL is held but is not a prerequisite to this issue's software implementation,
correctness qualification or reviewed software PR merge. All other dependencies remain.

## Concurrency guidance
May overlap late SDVK-012/013 work on separate paths with coordination. SDVK-015 waits for acceptance.

## Required context
Read `AGENTS.md`, PF-004/PF-012 evidence, SDVK dependency evidence, LevelMesh/probe/material/lighting RAG, validation contract and canonical body.

## Autonomous implementation prompt
Complete SDVK-014 autonomously. Build an integrated stress matrix, reproduce/fix lifetime/update/light-leak failures or establish explicit fallback, measure bake/update costs, keep CI smoke coverage, branch→PR→checks→merge→verify `master`→RAG/ledger→close.

## Acceptance criteria
No stale atlas/probe/descriptor identity in stress; dynamic geometry/light updates produce current state; known light bleeding/update issues fixed or bounded/fallbacked; semantic material/height paths compatible; bake/update diagnostics and CI smoke exist; PR merged/verified.

## Verification
Bake/load/delete; AO/bounce/sun matrix; dynamic sector/light/polyobject changes; multi-page atlases; probe reset/rebake; decals/warps/translucency/portals/3D floors; repeated level transitions; timing/memory/upload counters.

## Expected artifacts
Stress corpus/results, fixes/fallbacks, bake/update diagnostics/benchmarks, lightmap/probe/LevelMesh RAG/docs and ledger updates.

## Blocking / stopping conditions
If a PF foundational lifetime/selection invariant regresses, classify/block upstream rather than adding local compensating hacks. Do not close with an unexplained visually plausible stale result.

## Software execution and remaining physical boundary

Use source/CPU/static tests and explicitly isolated hosted software-Vulkan correctness
fixtures. Do not execute a renderer/Vulkan device in the ordinary coding environment,
use a physical GPU, change hardware/driver settings or retry the sealed physical failures.
Preserve existing lighting/probe/fallback/portal contracts and retain negative evidence.

Software increments may merge after their own required checks, review and exact-master
verification. Report hosted timings as descriptive only. Do not mark an unmeasured
physical requirement passed or close this issue while its own mandatory criteria are
still unmet. Record any such remainder explicitly as **software complete / physical held**.
A foundational lighting/probe/lifetime regression reblocks the affected scope upstream.

#11 and #14 may proceed in parallel on coordinated separate branches. Use normal
required CI as the runner benchmark; no duplicate runner or benchmark-only repeat.


## Implementation continuation — retained lifecycle hardening

Branch `sdvk014-lightmapper-probe-robustness` now also fail-closes malformed retained
LIGHTMAP admission before tile mutation, defers dynamic-tile completion until actual
copy/publication, and zero-initializes newly expanded light/probe atlas pages before
shader-readable publication. Focused CPU/source negative controls are carried in
`test_sdvk014_retained_lifecycle.py`.

This advances unblocked software scope only. Cross-map probe reset/rebake/publication
remains reblocked by #150. Durable stale-identity review, native repeated transitions,
special-surface/material lifecycle coverage, exact-head CI/review/merge and exact-master
verification remain outstanding. The issue is not software-complete. Physical bake/update
cost, scaling and stability remain HELD / NOT ACCEPTED under active Physical STOP.


The retained-lifecycle continuation also corrects 3D-floor/control-sector
admission: serialized `ControlSector` is a sector ordinal and is now bounded
against the sector table, with a deliberate namespace-mutation negative control.


Full atlas replacement now also initializes active resources fail-closed:
`CreateLightmap` clears every new probe page to runtime no-probe zero and clears
new light pages when no retained RGB payload exists before shader-readable
publication.


Special-surface hardening now also preserves 3D-floor control-sector identity
during side lightmap baking. Same-side/same-type surfaces from different 3D-floor
control sectors can no longer enter one another's bake visibility set; producer,
tile-binding and consumer boundaries are covered by deliberate alias negatives.


## Upstream #150 repair candidate — semantic probe owner identity

The cross-map probe lifecycle blocker has a dedicated repair candidate on
`sdvk150-probe-owner-identity`, documented in
[SDVK-150-PROBE-OWNER-REPAIR.md](../SDVK-150-PROBE-OWNER-REPAIR.md).

The candidate replaces count-as-owner behavior with a process-unique authored
probe-set revision, observes empty transitions, retains exact pre-fix same-count
and partial-pass negatives, and adds a bounded state-only lifecycle witness.
A focused same-process two-map fixture is registered in the existing Avrea
16-vCPU software-Vulkan job.

This is **not yet accepted** until exact-head source evidence, normal CI, the
focused native gate, review/merge and exact-master verification pass. #14 remains
OPEN. Physical cost/scaling/stability remain HELD / NOT ACCEPTED under Physical
STOP; historical physical root cause remains UNDETERMINED.
