# Donor and upstream provenance register

Status: reconciled founding + deep-source-audit register  
Date: 2026-09-17

## Baseline

ShadeDoomVK starts from VKDoom commit:

`09634479ab5bf9adf691074fffe85a006a398cd0`

Many apparent donor features are already ancestral or independently present in this baseline. Always inspect current source/history before importing a patch.

## Confirmed useful non-ancestral donor concepts

### jalovisko/VkDoom — configurable/device-aware bindless budget

Commit: `033a3c5cb35c82708e4eeb3619373c33ddc40b75`

Concept:

- configurable requested bindless texture capacity;
- clamp requested capacity to Vulkan physical-device limits;
- improve descriptor-exhaustion diagnostics.

PF-003 disposition: **conceptually adapted, not cherry-picked**.

ShadeDoomVK retains the donor's `vk_max_bindless_textures` idea and actionable exhaustion reporting, but replaces the donor's ordinary sampled-image-only capacity formula with a testable model covering the actual update-after-bind/variable-count layout:

- mixed normal/update-after-bind sampler and sampled-image pipeline-layout limits;
- `maxPerStageUpdateAfterBindResources`;
- `maxUpdateAfterBindDescriptorsInAllPools`;
- the two fixed scene combined samplers and other non-bindless scene resources;
- explicit fixed/lightmap/dynamic address-space reservations.

The inherited exact-size free-bucket reuse remains; PF-003 factors it into `VkBindlessSlotAllocator` and adds PF-002 generation validation rather than reimplementing reuse as a donor feature.

PF-003 also fixes an independent baseline defect: 128 lightmap pages consume 256 descriptors (light + probe per page), while the inherited dynamic start reserved only 128. The new contract reserves all 256 descriptors and bounds-checks lightmap page writes.

### MrRaveYard/MAD-VKDoom — small-actor light gathering

Commit: `2c433f2a495ec208c6cc9e248c2c85e3bb14a6f5`

Concept: gather eligible lights for sufficiently small actors from a local section light list instead of always BSP-walking.

Known donor limitation: portal-group handling contains a TODO/assumption.

Reconciled disposition: **independently reimplemented and accepted in PF-016 / PR #67**, merge `6091d6739c4b7dc96ef7913c911bf4eba89d7715`. No donor source was cherry-picked and the donor portal TODO was not imported. The accepted path first proves one-section/one-group geometry and compares baseline/local selected identity, order and class; position/radius/section/group changes force qualification again. Actual linked-portal displacement, cross-group fallback, renderer visibility/cache behavior and images match the baseline, with a representative CPU improvement. See `PF-016-RUNTIME-EVIDENCE.md` and `PF-016-LIGHT-QUERY-CONTRACT.md` for bounded runtime coverage and retained fallback cost.

### MrRaveYard/MAD-VKDoom — dynamic-light bookkeeping experiments

Commits:

- `807043b995264f166e333bca54c4e0b281bd8669` — dynamic-light optimization attempt;
- `773c53489663040697e744b50bf1b89e06525930` — remove linked lists entirely from lights.

Disposition: **research/data-layout evidence**, not a blind cherry-pick. PF-016/PF-017 may use the concepts if current-source profiling and correctness fixtures support them.

### MrRaveYard/MAD-VKDoom — render-frame delta time

Commit: `316b18a4d96b1a120c681d368ac670286234bcc8`

Disposition: later **SDVK-006 adaptation**, after PF-010 gives render-context identity. Gameplay/tic semantics remain authoritative.

### MrRaveYard/MAD-VKDoom — opt-in scale/alpha interpolation

Commit: `7d1f2df404711986a3cc742dad1f9e6e0ac69cde`

Disposition: later **SDVK-006 adaptation** where compatibility-safe.

### MrRaveYard/MAD-VKDoom — viewmodel light-level option

Commit: `346f4c0e87139ec8eb0d94d5792d8521b9d17a85`

Disposition: **problem evidence for SDVK-011**, not a required binary-toggle design. ShadeDoomVK intends a broader compatibility/world/PBR viewmodel lighting contract.

### MrRaveYard/MAD-VKDoom — bindless flush mitigation

Commit: `e2de04134c4654d38dd4b5452a0306036a5e0911`

Concept: increase bindless limit and flush textures/slots near exhaustion.

Critical donor note: commit records that LevelMesh can still contain old texture indices.

Disposition: **negative design evidence** for PF-002/PF-003. Do not adopt a flush strategy that leaves stale renderer references.

## Corrected historical donor assumption

### Waffle-Iron-Studios/GriddleVK — per-material-layer sampling

Commit: `97eaa46b69a19966e1a802b15081bcdf56eff718`

Historical concept: custom material texture layers carry independent sampling choices.

Deep-source-audit correction: the audited VKDoom baseline **already contains materially equivalent per-layer sampling support** through `MaterialLayerSampling`, custom-layer sampling arrays, GLDEFS parsing, Vulkan override samplers and `VkMaterial` binding.

Disposition:

- retain Griddle as historical provenance/research context;
- **do not port or reimplement the feature as missing**;
- PF-008 semantically tags/exposes inherited existing channels while preserving behavior;
- SDVK-005 later extends that representation with first-class height semantics/authoring/default policy.

## Ancestral/already inherited lines

The founding fork comparison found these apparent donors behind/ancestral to the ShadeDoom baseline. Their historical commits are not automatically missing work:

- `the-phinet/VkDoom`;
- `Talon1024/VkDoom`;
- `madame-rachelle/VkDoom`;
- `SanyaWaffles/VkDoom`;
- `AJMJ2012/VkDoom`;
- `coelckers/VkDoom`;
- `RicardoLuis0/VkDoom`;
- `River-Salmon/VkDoom`;
- `Gutawer/VkDoom`;
- `heitaoflower/VkDoom`.

Important qualification: a feature being ancestral does not prove it is complete or correct. The deep audit found inherited probe-map/AABB infrastructure that is present but partially/dormantly wired. The correct action is source qualification, not re-porting the old commit.

## Cacodemon345/VkDoom

Unique later divergence noted in founding audit:

`4956821df0c8eaf5b9c64001dbc1f68c043e6b0c` — interpolate non-Burn screen wipes.

Disposition: optional UI polish, outside PF/founding renderer critical path.

Earlier Cacodemon345 multi-BLAS, pipeline-sorting and shadow-acne work was already in the baseline ancestry by the relevant fork point; do not create donor issues for it without a proven current delta.

## UZDoom/GZDoom relationship

UZDoom/GZDoom remain active related lines and potential maintenance donors for:

- engine/mod compatibility;
- platform/toolchain/security fixes;
- Vulkan/backend fixes;
- scripting/resource maintenance.

Do not assume current UZDoom contains all VKDoom lightmapper/probe experiments or that VKDoom contains all later maintenance fixes. SDVK-003 owns the pinned differential/selective-sync policy after PF-020.

## Provenance rule

Whenever donor work is materially introduced, record:

- exact repository and commit/tag;
- file/function scope;
- ancestry check against current ShadeDoomVK `master`;
- license/copyright handling;
- cherry-pick vs adaptation vs conceptual reimplementation vs rejection;
- tests proving the transplanted concept preserves intended meaning in ShadeDoomVK.

When a donor concept is already inherited, record **qualification/fix provenance** separately from donor provenance rather than claiming a new import.
