# SDVK-011 viewmodel lighting software increment

Status: implementation candidate; native qualification, independent review and
exact-head CI are required before acceptance. Issue #11 remains open.

`gl_viewmodel_lighting` selects an archived, render-only policy:

| Value | Behaviour |
|---|---|
| 0 (default) | Inherited weapon sector/aggregate/per-vertex lighting and gameplay presentation. |
| 1 | Inherited sector colour, fog/fullbright and weapon-light calibration; local lights and environment probes disabled. |
| 2 | Built-in true-colour weapon cards use normal/specular/PBR materials, accepted actor probe selection and per-pixel local/sun light lists at one camera-relative sample. |

Mode 2 samples eight world units along the current camera forward direction.
Candidate light eligibility, attenuation, spot/shadow calculations and BRDF view
vectors use that same point. The card keeps its original HUD vertices, projection,
alpha, translation, bob, interpolation, FOV and weapon state. This is a lighting
approximation, not world weapon geometry. World geometry can occlude light rays
from the sample; the card does not acquire geometric world shadows or depth.

The final interpolated four screen vertices are mapped onto camera right/up
vectors for the accepted sprite tangent solver. Signed UVs retain mirrored-frame
handedness. Normal-free diffuse materials use the same camera-facing normal.
Every card clears basis, relief and stale actor/probe/sun observations before
drawing, and clears viewmodel uniforms afterwards. World draws retain their
original lighting positions when the appended selector is zero. The frozen
shader-key ABI and existing surface-uniform offsets are unchanged.

HUD models have a bounded enhanced candidate using their inherited object-to-world
and inverse-transpose normal matrices; per-skin and native qualification is
required before that extension is accepted. Disabled per-pixel sprite
lighting, ambiguous linked-portal ownership, palette mode, custom/warped materials
and special render styles use explicit legacy fallback. Ordinary built-in default,
normal/specular and PBR cards are supported. POM/height displacement is disabled
for HUD cards in every mode; semantic material layers keep their accepted
ordering/samplers, and no gameplay or muzzle-light thinker/tic code changes.

`stat viewmodel` shows requested mode, the last emitted HUD draw's effective mode
and fallback reason. Bounded emitted `viewmodel` records additionally identify
the actual sample, TBN, shader, light range, authored probe, runtime pair, resource
generation and probe epoch. These observations never drive lighting decisions.

Source: `hw_weapon.cpp`, `hw_viewmodel_policy.h`, appended `SurfaceUniforms`,
`SDVK_LIGHTING_POSITION` in the built-in light models, and Vulkan emitted-draw
diagnostics. No donor source was copied; the previously registered MAD option
remains problem evidence. Policy/TBN CPU fixtures include mirrored and deliberate
fallback cases. The whole-PBR preservation test reverses exactly three owned
position substitutions before checking the retained original shader.

The 7 November owner correction authorizes fresh physical qualification in the
existing system configuration. Historical STOPs and failed packets remain
retained; neither this implementation nor hosted llvmpipe evidence supplies
physical acceptance. Required gameplay verification and any remaining unsupported
projection paths must remain visible in #11.


## Bounded HUD-model continuation (candidate)

The inherited `RenderHUDModel` already starts from inverse(view), then composes
MODELDEF scale/offset/FOV, bob, pivot and authored model rotations. Its actual
world vertex positions and inverse-transpose `NormalModelMatrix` feed the normal
shader and derivative material TBN. The continuation retains those geometry,
culling, skin, bone and interpolation paths; it does not invent a camera-space
normal transform or assign the card's constant tangent to a curved model.

Enhanced model light eligibility, attenuation, probes and traced sunlight use the
same eight-unit camera anchor as cards. Fragment lighting replaces the legacy
vertex-light selector only in mode 2; the fake model contrast light is absent in
that mode. Mode 0 keeps the old query, fake-light option, model transforms and
vertex shading unchanged. Mode 1 retains explicit sector lighting.

Each actual model skin is admitted after its production material is bound.
Built-in true-colour default, normal/specular and PBR skins participate; unsupported
warped/custom/palette skins or a nonfinite model normal matrix receive diagnosed
sector fallback 4. A later supported skin restores its own enhanced state, so one
surface cannot leak its fallback into another. Sample, probe and dynamic-light
selectors are cleared in fallback and after the HUD draw. No POM is enabled.

Emitted model records retain the actual normal matrix and final model vertex
format/pipeline, rather than claiming a single per-model TBN. The generated
original OBJ box uses ordinary MODELDEF and weapon states. Four prospective native
scenes cover legacy PBR, mirrored normal/specular, enhanced PBR and static Warp2
skin fallback. The box must submit its real 36 model vertices; an ordinary card
cannot satisfy the model cell. CPU fixtures execute the inherited production
matrix implementation for camera rotation/translation, mirrored nonuniform scale
and a deliberately wrong normal transform. Native qualification remains pending;
this bounded rigid-model corpus does not claim all skeletal/animated formats.


Local preflight: the complete Windows RelWithDebInfo executable/resource build
passes. Six compiled policy/matrix/actual-skin-method tests, nine viewmodel
recipe/observation tests and all 27 corpus tests pass. The skin-method replay
executes the extracted production `SetMaterial` across PBR → unsupported Warp2 →
normal → custom → PBR, plus invalid-matrix/palette and unchanged legacy/world
controls. These CPU services do not pretend to execute a native model draw.

To prepare the live model room without launching a renderer:

```text
python tools/renderer_oracle/prepare.py --out build/viewmodel-model --scene viewmodel-model-pbr
```

The generated `scenes/viewmodel-model-pbr/scene.pk3` can be loaded with a legal
Doom-family IWAD and current build, using `+map SDV122 +gl_viewmodel_lighting 2`.
Leave off the capture script for ordinary player movement and firing. The normal
software-Vulkan CI runs all four model scenes and their emitted-state/image
contracts; its exact-head result remains required before model acceptance.

## 7 November physical checkpoint

At source `4be6eecf7d193f9e4b273019277059acccea562d`, ten guarded physical
processes completed the legacy, enhanced normal and PBR card cells plus enhanced
normal and PBR rigid-model cells. Each independent pair retained equal normalized
static state and zero changed RGB pixels at 640x480. Native exits, module/health
checks and completion fences passed. Root image review confirmed centered cards
and visible models. The owner-configured GTX 1650 SUPER remained at 90 W; no
hardware setting was changed. The retained campaign manifest is
`524e9c999b149128d9e7a362e8a6a28fdadeb1e4480929fc9e63b1b4402eb4a5`.

The first ordinary-input gameplay process also exited 0 and retained all 128
frames, nine images and actual movement, turning, ammo use, muzzle light/reset
and three fresh map owners. Its original attempt remains **FAILED_STOP**: the
generic structural gate incorrectly required the four large draw families on
every frame. The recipe-scoped admission repair is checked against those
immutable captured records; a fresh repaired-source process remains required.
No GPU fault was observed; the separate post-failure fence retained 30 C/P8,
90 W and no new System fault events. This checkpoint supplies bounded physical
correctness evidence, not whole-issue, dense-shadow, performance or stability
acceptance. The remaining native cells and exact-head normal CI still govern
integration, and #11 remains open.
