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

HUD models currently use explicit sector fallback in mode 2; their model-space
tangent transform still needs separate qualification. Disabled per-pixel sprite
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
