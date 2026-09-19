# PF-011 lighting compatibility contract

Status: accepted implementation contract; PR #57 merged as `1c16f7e76d8927c315c4fc57b8c9e532ca99c84b` after exact-head CI passed.  
Baseline implementation lineage: `master` at `71d969210ca44b4a5154d1ced2add09fb7774820` before PF-011.

## Purpose

PF-011 names the inherited ShadeDoomVK/VKDoom lighting calibration without retuning it. The quantities below are renderer compatibility units. They are **not** lumens, candela, watts, EV, or any other physical-lighting unit.

This contract covers dynamic-light authoring/packing, classic and PBR attenuation, spotlight shaping, sunlight proxy data, GLDEFS intensity, fake model light, and the classic-to-PBR brightness bridge. Shadow selection, probe policy, exposure/bloom calibration and physical-unit conversion remain outside PF-011.

## Ownership and units

| Quantity | Current meaning | Owner |
|---|---|---|
| GLDEFS/current light intensity | legacy authoring radius-like scalar | `FDynamicLight` / `a_dynlight.cpp` |
| render radius | `2 * m_currentRadius` while active | `FDynamicLight::GetRadius()` |
| inverse-square strength | `min(1500, render_radius^2 / 10)` | `LightCalcStrength()` |
| color channels | authoring byte channel normalized by `/255` | `AddLightToList()` via `HWLightCompat::NormalizeColorChannel` |
| GLDEFS light-def intensity | multiplicative color calibration, default `1.0` | `FLightDefaults` / `FDynamicLight` |
| uploaded linearity | compatibility blend factor clamped to `[0,1]` | `HWLightCompat::ClampLinearity` |
| soft-shadow radius | inherited source-size metadata; not changed by PF-011 | GLDEFS / light packing |
| PBR brightness scale | classic-to-PBR visual bridge `2.5` | `LIGHT_COMPAT_PBR_BRIGHTNESS_SCALE` |
| PBR ambient-sector scale | inherited approximation `2.25` | `LIGHT_COMPAT_PBR_AMBIENT_SCALE` |
| PBR metallic ambient specular scale | inherited approximation `0.40` | `LIGHT_COMPAT_PBR_METAL_SPECULAR_SCALE` |

## Distance attenuation

The GPU local-light inverse-square compatibility equation remains:

`a = dist / radius`

`b = clamp(1 - a^4, 0, 1)`

`inverse = (b^2 / (dist^2 + 1)) * strength`

`linear = clamp((radius - dist) / radius, 0, 1)`

`attenuation = mix(inverse, linear, linearity)`

When inverse-square mode is disabled, attenuation is the `linear` term. A packed light whose radius is at least `LIGHT_COMPAT_SUN_ATTENUATION_RADIUS` (`1,000,000`) bypasses inverse-square attenuation and returns `1.0`; this identifies the inherited far-away sunlight proxy class, not a physical distance threshold.

The operation ordering above is intentionally retained because changing algebraic grouping can change floating-point output or shader compilation.

## Spotlight shaping

Spotlights retain the inherited cosine-space smoothstep:

`cosDir = dot(normalize(lightPos - pixelPos), spotDir)`

`spot = smoothstep(cosOuterAngle, cosInnerAngle, cosDir)`

The numerical fixture covers below-outer, exact-outer, midpoint, exact-inner and above-inner boundaries.

## Light classes and color packing

GPU/per-pixel light lists retain three ranges: normal/modulated, subtractive and additive.

- Normal color is normalized RGB multiplied by actor-alpha when `RF2_LIGHTMULTALPHA` is active, then by GLDEFS light-def intensity.
- Additive GPU lights additionally apply the inherited `HWLightCompat::AdditiveGpuColorScale == 0.2` before entering the additive range.
- Subtractive GPU lights convert normalized RGB to `length(rgb) - rgb` and enter the subtractive range; the shader subtracts the resulting contribution.

The CPU aggregate sprite-light path is deliberately **not** collapsed into the GPU packing path. It applies subtractive sign conversion directly to the accumulated RGB and does not apply the GPU additive `0.2` pre-scale. That is inherited behavior and is protected here rather than silently normalized.

## CPU aggregate sprite compatibility path

`HWDrawInfo::GetDynSpriteLight` is an active legacy/compatibility path and remains separate where its inputs differ from fragment lighting:

- inverse-square distance is floored with `max(dist, sqrt(radius) * 2)` before the common-shaped equation;
- it consumes raw `GetLinearity()` rather than the GPU upload clamp;
- it performs its own actor trace/shadow-map eligibility;
- additive lights do not receive the GPU list's `0.2` pre-scale.

These distinctions make apparently duplicated equations semantically non-identical. PF-011 therefore documents them instead of forcing a shared helper that could alter accepted output.

## Sunlight and fake-model-light proxy

`AddSunLightToList` retains the inherited directional-light proxy:

- proxy distance: `HWLightCompat::SunProxyDistance == 100000`;
- proxy radius: `HWLightCompat::SunProxyRadius == 100000000`;
- proxy strength: `HWLightCompat::SunProxyStrength == 1500`.

Real sunlight packs `SunColor * SunIntensity`. The fake model-light path uses the same proxy representation but its inherited adjusted direction, `SunColor * SunIntensity * gl_fakemodellightintensity`, and no trace flag. PF-011 does not reinterpret either path as physical radiometry.

## Classic-to-PBR bridge

PBR direct dynamic lights and direct sunlight multiply inherited light color/attenuation by `LIGHT_COMPAT_PBR_BRIGHTNESS_SCALE == 2.5`. The purpose is historical visual correspondence with non-PBR lighting, not energy conservation or exposure calibration.

PBR sector ambient retains a separate approximation: ambient color is scaled by `2.25`, and its metallic specular approximation uses `0.40`. These values are now named because future exposure, bloom and HDR work must distinguish compatibility calibration from physical-light policy.

The Cook-Torrance BRDF constants and equations remain owned by `lightmodel_pbr.glsl`; PF-011 does not redesign them.

## Numerical tolerance and adversarial coverage

`tools/pf_oracle/tests/lighting_compat_fixture.cpp` freezes representative and boundary vectors for authoring-strength saturation, RGB normalization, linearity clamping, GLDEFS/alpha scaling, additive/subtractive packing, inverse-square/linear moving-light response and spotlight edges. The fixture uses an absolute tolerance of `1e-5` for ordinary values and `1e-4` for high-magnitude inherited attenuation samples where float rounding is expected.

`test_lighting_compat_contract.py` additionally asserts source ownership, operation ordering, named constants, intentional CPU/GPU path distinctions, sunlight proxy behavior, and numerical direct-PBR/sun/ambient/metallic bridge vectors. The ordinary PF oracle and complete platform build matrix remain mandatory.

## Acceptance evidence

- Implementation head: `6c977abec0a9f957d9bc5e0f24d46bb87990950e`.
- Exact-head Continuous Integration run 76 passed the deterministic PF renderer oracle and complete Windows/macOS/Linux build matrix before merge.
- Implementation PR #57 merged as `1c16f7e76d8927c315c4fc57b8c9e532ca99c84b`, and `master` was verified at that exact merge commit.
- The implementation is a calibration-preserving refactor: literals are named and ownership is made explicit while inherited equations, operation ordering and deliberately distinct CPU/GPU compatibility paths are retained.
- No donor renderer code, audio, art or external assets were imported.

## Compatibility invariants

1. No authoring defaults, light selection, portal-relative position, occlusion, shadow selection, probe behavior, material meaning, exposure, tonemap or bloom policy changes in PF-011.
2. The baseline inverse-square/linear equation and operation ordering remain unchanged.
3. Additive/subtractive class semantics remain unchanged, including the GPU-only additive `0.2` scale.
4. CPU aggregate sprite-light input conditioning remains distinct and explicit.
5. Sun proxy values and fake-model-light semantics remain unchanged.
6. PBR `2.5`, `2.25` and `0.40` compatibility scalars are named but numerically unchanged.
7. Future calibration work must treat these values as compatibility bridge inputs and must not infer physical units from them.

## Provenance

PF-011 only names and documents equations/constants already present in this repository lineage. It imports no donor renderer code, audio, art or external assets, and therefore does not change source/audio/provenance obligations.
