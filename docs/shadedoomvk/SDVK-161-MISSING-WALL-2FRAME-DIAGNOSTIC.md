# SDVK-161 targeted missing-wall discriminator (nonqualifying)

**Status:** isolated diagnostic. Not accepted source, not publication evidence.

After the narrowly revised authored `special-surface-lifecycle` recipe
adds `-nostartup`, the original intermittent, independent missing-wall
finding remains unresolved. In [publication CI #627](https://github.com/techrote/ShadeDoomVK/actions/runs/43549214686),
one independently admitted frame-37 capture contained 80 immediate wall
vertices and 22 empty successful Vulkan light-range uploads, while the
other contained 84 and 23. Each had 17 BSP traversals and five scene
contexts; original final RGB was byte-for-byte equal. Only that frame's
protected counters differ. The original capture did not carry
per-wall identities at frame 37. The mismatch also occurred historically
at frame 4 on an earlier master.

Source evidence places the actual wall counter increase in
`HWWall::RenderWall` after `state.Draw()`, and the empty 16-byte
light-buffer entry in `VkRenderState::UploadLights`. The unchanged BSP
traversal count does not prove every wall was queued or submitted.
The main view uses LevelMesh, whereas immediate mirror/portal recursive
views can use `gl_multithread` worker submission. This is a **candidate
causal boundary**, not an established race or fix.

The previous eight-attempt default-off passive wall probe captured 5,808
events per process across 96 frames and did not reproduce the original
missing quad; it perturbed frame pacing. This follow-up limits its
default-off, fixed-size POD recordings to the *two original failure
frame indices*, **4 and 37**, while retaining all 96 original native
frame observations. Every traced issue-draw count is independently
joined to the original CPU wall-vertex count, and every indexed light
upload is joined to the unchanged Vulkan resource ledger. Queue,
draw entry, geometry completed, actual issued draw, draw exit and
successful light upload are distinguishable, with wall side/line/type/
sector/portal-context/geometry identity. Missing or forged calls and
non-matching counts fail closed. Original 35 negative controls, exact
RGB/state comparison, input schedule, 32+96 views, and twelve detailed
witness frames remain unchanged.

This experiment has **16 preregistered independent native attempts**,
zero automatic retries, and eight within-host original strict pairs.
If any original 80/84 mismatch is reproduced, the exact side/line,
stage and context must be identified from the bounded sidecar.
If no mismatch is reproduced, do not claim the original defect fixed.
The workflow always ends PRECHECK_ONLY, even if every attempt passes.
The release cannot be accepted or merged from this diagnostic branch.

No threading disablement, renderer geometry change or tolerance
normalization is authorized by a mere non-reproduction. A demonstrable
failure must drive a separate pre-fix regression and causal repair,
followed by native qualification. PRs #196 and #201 remain Draft/HOLD.
