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

Keep the lightmap/uniform branch and sample order: four irradiance helper calls,
then four prefilter helper calls, followed by the original weighted sums. The
explicit sampling exception below replaces the nonzero irradiance expression;
all other nonzero operations remain unchanged.
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

## Decision amendment: defined sampling across missing/live taps

The zero guard can diverge within a fragment quad. For every nonzero pair base,
the irradiance helper therefore uses
`textureLod(cubeTextures[nonuniformEXT(base)], N, 0.0).rgb`. The prefilter helper
uses `textureLod(cubeTextures[nonuniformEXT(base + 1)], R, lod).rgb`, where the
caller supplies the unchanged `roughness * MAX_REFLECTION_LOD`. Both helpers
return exactly `vec3(0.0)` for base zero before descriptor access or evaluation
of the adjacent prefilter index. No descriptor, sampler or environment is
substituted for a missing tap.

**Research finding:** implicit texture derivatives can be undefined in
nonuniform control flow; explicit LOD supplies the level without those
derivatives. See [GLSL texture functions](https://registry.khronos.org/OpenGL/specs/gl/GLSLangSpec.4.60.html#texture-functions)
and [Vulkan sampling](https://docs.vulkan.org/spec/latest/chapters/textures.html#textures-derivative-image-operations).
Varying sampled-image descriptor indices separately require explicit nonuniform
qualification; see [Khronos descriptor indexing](https://docs.vulkan.org/samples/latest/samples/extensions/descriptor_indexing/README.html).

**Source finding:** current `VkTextureManager::CheckIrradiancemapSize` creates
one-mip sampled cubes. `ImageBuilder::Size` and `ImageViewBuilder::Image` in
`libraries/ZVulkan/src/vulkanbuilders.cpp`, with their header defaults, expose
base mip zero and exactly one level. The dedicated
`VkSamplerManager::CreateIrradiancemapSampler` retains `SamplerBuilder` defaults:
identical LINEAR min/mag filters, zero LOD bias and disabled anisotropy. Ordinary
sampler reset/delete loops do not replace this dedicated sampler. Existing
`VulkanCapabilities::SupportsRequiredBindlessContract` already requires sampled
image array nonuniform indexing; this amendment adds no new device feature.

**Decision:** LOD zero is the narrow sampling-expression exception. Under the
recorded one-level/view/sampler contract, it retains the defined live sample's
level, spatial filtering and direction. `nonuniformEXT` changes qualification,
not pair selection. Preserve N/R, four-tap invocation order, original
coefficients and ordered sums, roughness prefilter LOD, `Lo`, BRDF, Fresnel, AO
and all material operations. If the source contract changes, reconsider this
exception rather than silently applying it to a different mip/filter policy.

**Verification requirement:** extract and hash-guard original/current shader
branches, the zero guards and actual builder/view/sampler bodies. Prove that
zero causes no cube read or base-plus-one evaluation and that live calls keep
directions, order, weights and prefilter LOD. CPU sample-service goldens alone
do not establish spatial GPU parity. Native controls must include spatially
varied live sampling, adjacent zero/live and differing-live fragments across
quad boundaries, plus actual tiny two-probe initial publication. An original
live comparison may use only a legal uniform pair/control-flow path; never
launch the original fixed-2D mismatch or undeclared divergent indexing as a
GPU negative. Core/synchronization and all release gates above still apply.
