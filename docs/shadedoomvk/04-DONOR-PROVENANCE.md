# Donor and upstream provenance register

Status: founding research snapshot  
Date: 2026-09-17

## Baseline

ShadeDoomVK starts from VKDoom commit:

`09634479ab5bf9adf691074fffe85a006a398cd0`

This matters because many forks that appear to contain useful features are actually ancestors of the current baseline. Do not re-import an ancestral patch under a new provenance story.

## Confirmed useful non-ancestral donor concepts

### jalovisko/VkDoom — configurable bindless budget

Commit: `033a3c5cb35c82708e4eeb3619373c33ddc40b75`  
Concept: make maximum bindless texture count configurable, clamp it to Vulkan device descriptor limits and improve exhaustion diagnostics.

ShadeDoomVK disposition: **port/adapt early**, then extend from capacity into safe reuse/lifetime/generation handling.

### Waffle-Iron-Studios/GriddleVK — per-material-layer sampling

Commit: `97eaa46b69a19966e1a802b15081bcdf56eff718`  
Concept: custom material layers carry their own sampling override and Vulkan samplers can differ per layer.

ShadeDoomVK disposition: **reimplement/generalize** as semantic material sampling rather than copying the narrow historical enum unchanged.

### MrRaveYard/MAD-VKDoom — small-actor light gathering

Commit: `2c433f2a495ec208c6cc9e248c2c85e3bb14a6f5`  
Concept: for sufficiently small actors, gather dynamic lights from the actor's section light list instead of walking the BSP.

Known limitation in donor: portal-group handling contains a TODO/assumption.

ShadeDoomVK disposition: **benchmark hypothesis, not blind cherry-pick**.

### MrRaveYard/MAD-VKDoom — dynamic-light bookkeeping experiments

Commits:

- `807043b995264f166e333bca54c4e0b281bd8669` — dynamic-light optimization attempt;
- `773c53489663040697e744b50bf1b89e06525930` — remove linked lists entirely from lights.

ShadeDoomVK disposition: **study data-layout/cost evidence**. Reimplement only after deterministic selected-light equivalence and profiling.

### MrRaveYard/MAD-VKDoom — render-frame delta time

Commit: `316b18a4d96b1a120c681d368ac670286234bcc8`  
Concept: expose rendered-frame delta time and physics timestep to scripting, resetting across loads/wipes to avoid giant visual-time jumps.

ShadeDoomVK disposition: **adapt**, with explicit renderer-only semantics.

### MrRaveYard/MAD-VKDoom — opt-in scale/alpha interpolation

Commit: `7d1f2df404711986a3cc742dad1f9e6e0ac69cde`

ShadeDoomVK disposition: **adapt where useful** for high-FPS visual effects while preserving gameplay state.

### MrRaveYard/MAD-VKDoom — viewmodel light-level option

Commit: `346f4c0e87139ec8eb0d94d5792d8521b9d17a85`

ShadeDoomVK disposition: **take the problem, not necessarily the exact solution**. Build a general viewmodel lighting mode compatible with probes/local lights/PBR.

### MrRaveYard/MAD-VKDoom — bindless flush mitigation

Commit: `e2de04134c4654d38dd4b5452a0306036a5e0911`  
Concept: increase the bindless limit, request a texture flush near exhaustion and avoid flushing canvas textures.

Critical donor note: the commit itself states that LevelMesh can retain old texture indices.

ShadeDoomVK disposition: **negative design evidence**. Do not adopt a flush strategy that can leave stale indices.

## Ancestral/already inherited lines

During the founding audit, these apparent donors compared as ancestors of the ShadeDoom baseline and therefore should not be counted as missing features without a specific later divergence:

- `the-phinet/VkDoom` — includes the 2025 probe-map/AABB-tree, sunlight-specular and light-bleed work that later flowed into the baseline;
- `Talon1024/VkDoom`;
- `madame-rachelle/VkDoom`;
- `SanyaWaffles/VkDoom`;
- `AJMJ2012/VkDoom`;
- `coelckers/VkDoom`;
- `RicardoLuis0/VkDoom`;
- `River-Salmon/VkDoom`;
- `Gutawer/VkDoom`;
- `heitaoflower/VkDoom`.

The correct action is normally to test/qualify the inherited feature, not port it again.

## Cacodemon345/VkDoom

A later unique divergence found in the founding audit was `4956821df0c8eaf5b9c64001dbc1f68c043e6b0c`, interpolating non-burn screen wipes. This is optional UI polish and is not on the founding renderer critical path.

Earlier Cacodemon345 work such as multi-BLAS map updates, pipeline sorting and shadow-acne trace bias had already flowed into the current ShadeDoom baseline by the time of this fork.

## UZDoom/GZDoom relationship

UZDoom/GZDoom remain active related code lines and should be evaluated as maintenance/upstream donors, especially for:

- engine compatibility and mod semantics;
- platform/toolchain/security fixes;
- Vulkan backend fixes;
- scripting and resource-system maintenance.

Do not assume their current renderer contains every VKDoom lightmapper/probe feature or that VKDoom contains every later engine fix. SDVK-003 owns the pinned differential and future sync policy.

## Provenance update rule

Whenever donor work is introduced, add:

- exact source repository;
- exact commit/tag;
- file/function scope;
- license/copyright handling;
- whether the change was cherry-picked, adapted, reimplemented or only inspired by the source;
- tests proving the transplanted concept still means the same thing in ShadeDoomVK.
