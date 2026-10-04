# PF-113 missing environment contribution decision

Status: **implementation decision adopted; repair and release acceptance pending**

Authority: [#113](https://github.com/techrote/ShadeDoomVK/issues/113), which
delegates resolving and recording the contribution decision before implementation.
This decision does not accept #113, PF-020 or SDVK-001. Date: 2026-10-04.

## Requirement and finding

Preserve valid allocator-backed probe pairs, their existing interpolation and
operation order, PBR calibration, material bindings and gameplay. Accepted
[PF-012](issues/PF-012.md) defines runtime token zero as default/no-probe;
authored probe ordinal zero resolves a real nonzero dynamic cube pair.

The [source-established counterexample](PF-020-PBR-PROBE-BLOCKER.md) shows that
the inherited consumer attempts cube samples through fixed 2D slots zero/one
for an unavailable uniform probe and zero lightmap taps. It supplies no valid
radiometric baseline for those accesses. No original mismatch was launched on
GPU, and no native failure or driver causation is inferred.

## Decision

Runtime pair token zero contributes exactly zero to both irradiance and
prefiltered environment radiance. Check the pair base before any cube access
or adjacent prefilter index is used. Resolve every nonzero base through the
existing allocator-backed producer and sample the same pair as before.

For mixed lightmap taps, retain the original four coefficients and ordered
sums. A missing tap contributes zero at its original weight. Do not renormalize
the remaining weights or substitute authored probe zero or another environment.
The all-zero case therefore has zero IBL. Ambient sector compatibility lighting,
direct and sunlight contributions through `Lo`, the BRDF LUT, Fresnel, AO,
roughness LOD and material sampling retain their current operations. Zero IBL
does not imply a black final surface.

This is a new explicit missing-IBL policy for the correctness repair. It is not
a retroactive claim that PF-012 already adopted zero radiometry. Renormalization
would alter live-tap coefficients; environment substitution would introduce a
new selection and availability policy. Neither is needed for this bounded fix.

## Implementation and verification boundary

Keep the lightmap/uniform branch and sample order: four irradiance reads, then
four prefilter reads, followed by the original weighted sums. A guarded helper
may replace each existing expression while preserving its nonzero body.
Do not change descriptor allocation, fixed 2D users, probe publication/reset,
selector omissions, transforms, channel interpretation or gameplay.

Before affected GPU execution, retain exact accepted production negatives and
source-extracted current guards with strict CPU fixtures. Protect initial
two-probe publication ordering, authored zero, missing-to-available lookup,
reset and nonordinal live slots. All-zero, mixed and all-live controls must
verify sample types, order, retained coefficients and output. For example,
`t=(0.25,0.6)` gives weights `0.30,0.10,0.45,0.15` in existing tap order.

Native acceptance requires a fresh tiny authored two-probe/PBR scene without
prebaked lumps, an actual unavailable-to-published observation, legal output
readbacks and separate core/synchronization validation. Exact source/build/input
identities, independent review, required CI, merge/master and post-merge checks
remain mandatory. Historical CFX/PF-017 STOP scopes stay sealed; repaired P400
behavior and GPU performance remain untested by this decision.
