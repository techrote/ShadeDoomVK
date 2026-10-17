# SDVK-153: probe descriptor identity across material resets

## Disposition and assessed authority

**Implemented software repair candidate; native and exact-head CI acceptance
pending. #153 remains a blocker until its required qualification/merge. #14 is
not software-complete.** Physical STOP remains ACTIVE. Physical GPU bake/update
cost, scaling and stability remain HELD / NOT ACCEPTED. Historical physical
root cause is UNDETERMINED.

Assessed master is `ca254b6ea08228c8408562ebba26bbc1060a0311`, tree
`ea20650fefbe454b5a43f82119e879df75ed8e4f`. The initial candidate used the
already-published evidence-only PR #154, audit head
`0b6e12d2aa942792a2c7e2d3f8d52fdc18db6c59`, tree
`3de46ed9d9c66520994035510f49dd7f073d91b1`. The audit then merged as `d57137c3a383e912e2e7376759ec45d4503adfb9`
with that exact tree; the local branch was reconciled to the actual merge commit
without changing source content. It does not relabel that audit's
blocked findings as passes. #150's accepted semantic owner revision is unchanged.

The audit source bundle was recovered from run 38947611123, artifact 12067586538,
ZIP SHA-256 `d1a166e10241fa92ce5e19b204cb935a49eb55d481aa51bcb6b9313b9cf04e93`.
Its checksums and tree were verified. This work introduces no donor code.

## Defect and minimal repair

The former `ResetHWTextureSets` freed cached probe descriptor pairs during live
filter/anisotropy changes and precaching, although retained R16_UINT probe-map
texels still encoded their raw descriptor bases. A valid base/span/generation
in the current allocator could therefore belong to another probe or material.

The repair leaves `VkDescriptorSetManager::LightProbes` intact across **material**
resets. It is a persistent ordinal-to-pair mapping tied to the device's bindless
set and the existing probe image/view/sampler owners. It is not a material-cache
entry. Material and colormap descriptors still retire and rebuild normally.
No emergency global flush, extra rebake, selection change or quality reduction
is used to conceal stale state.

`GetLightProbeTextureIndex` also rejects negative, out-of-range and missing-half
ordinals **before** cache growth or indexing. Authored ordinal 0 remains valid;
runtime descriptor 0 remains the fallback. An unpublished pair is not cached
as success and may be published normally when both view owners exist.

Review exposed a second defect in the same setting-reset transaction. The old
`SetTextureFilterMode` republished fixed descriptors 0..2 with hardware samplers
that it immediately retired. The repair preserves the accepted SDVK-004 material-retirement-before-rebuild
invariant with a three-phase transaction: retire material/colormap consumers;
create replacement hardware samplers; call the new `UpdateFixedTextureDescriptors`
to publish slots 0..2. `StartPrecaching` explicitly publishes those fixed slots
following material retirement without recreating samplers. Retired hardware
samplers still follow the existing draw delete-list/fence mechanism. No shader,
material sampling rule or descriptor layout changes.

## Production ownership proof and limits

| Identity | Actual owner | Lifetime/reset rule and consumer |
| --- | --- | --- |
| Authored probe set | FLevelLocals process-unique revision, accepted #150 | Replacement/clear/runtime authoring changes revision; the builder resets content/progress. Unchanged. |
| Irradiance/prefilter views | VkTextureManager grow-only vector prefixes | `CheckIrradiancemapSize` / `CheckPrefiltermapSize` append new owners; retained prefix views are not replaced or shrunk. Upload/copy/reset writes existing images. |
| Probe samplers | VkSamplerManager dedicated objects | Constructor creates them; hardware material sampler reset does not replace them. |
| Probe raw pair base | VkDescriptorSetManager persistent LightProbes entry | Allocate once per published pair ordinal; keep two adjacent slots reserved for its view/sampler owners until device teardown. |
| Material/colormap bases | Existing material variant cache / colormap Renderdev | Continue to retire under `ResetHWTextureSets`; use replacement hardware sampler on re-publication. |
| Content epoch | VkTextureManager LightProbeEpoch | Reset clears both image families in place and advances content epoch, independently of stable descriptor identity. No old image content is excused by a stable base. |
| Final teardown | VulkanRenderDevice | Existing device-idle boundary precedes descriptor/texture deinitialization. Reverse member destruction retires descriptor manager before its texture/sampler owners. No new asynchronous destruction path. |

The two inspected call sites of `ResetHWTextureSets` are the filter-mode reset
and `StartPrecaching`. Both are now stable for probe raw bases. Same-count and
zero/nonzero map transitions still use #150's content reset and re-publication;
this change does not reset its accepted progress policy.

Persistent pairs consume **two dynamic slots per maximum published probe-view
prefix**, not two more per setting/map reset. The existing image families already
retain that high-water prefix. The real PF-003 allocator bounds the address
space. Exhaustion keeps the existing fail-closed allocation failure; it does
not free or recycle live probe pairs to manufacture capacity.

This proof depends on the audited grow-only view and dedicated-sampler lifetime.
A future implementation replacing a view/sampler or recreating the bindless set
while retaining raw consumers must introduce a corresponding publication barrier;
it may not inherit this proof just because the ordinal is unchanged.

## Falsifiable CPU evidence

`tools/pf_oracle/tests/fixtures/sdvk153-pre-fix.json` retains exact original
reset/filter/precache/lookup/candidate-upload definitions and source hashes.
Its whole-file SHA-256 is
`770c900ee93196a33104ee022eb5ef9f7328c70f3f3b76cac9ec7fd1be5b4ad1`.
The original audit replays those pinned fragments explicitly. No original audit
receipt or accepted #150/PF historical evidence is rewritten.

The new compiled fixture executes exact current producer bodies, the real PF-003
allocator and PF-012 CPU selector, and accepted #150 Step/Full. Only GPU objects,
writes, sampler construction and fence completion are symbolic services. It does
not prove actual GPU execution or image contents.

Twelve positive case programs cover unchanged use, filter/anisotropy/precache,
reversed probe lookup, material pressure, fixed sampler re-publication, real
material/colormap retirement, absent/half-pair/ordinal-0 admission, bounded invalid
ordinal lookup, 128 mixed-count owner cycles, and exhaustion without a flush.

Six original-source named failures must still reject: filter/precache aliasing,
retired pair generation despite a plausible restored raw base, material takeover,
fixed descriptors naming retired hardware samplers, and invalid-ordinal cache
growth. Four compiled current-source mutants restore probe retirement, old
fixed-publication order, early sampler rebuild or unbounded lookup and must fail for their specific reasons.
PF113 preservation removes only the exact owned admission prefix before checking
its historical function hash; unrelated allocation/sampling changes still fail.

The stress workload is bounded at eight probe pairs, with two mixed-span material
allocations per cycle. It checks stable base/generation/span tokens, separate
content resets, unchanged material retirement, neutral inactive symbolic content,
and zero outstanding symbolic owners at teardown. See the machine CPU receipt
for exact observed counters and compiler results. The executed case receipt is
[evidence/SDVK-153-DESCRIPTOR-LIFETIME-CPU.json](evidence/SDVK-153-DESCRIPTOR-LIFETIME-CPU.json).

## Prospective hosted correctness gate

Two new scenes, `probe-sampler-reset-control` and `probe-sampler-reset`, share
identical geometry, two probes, two PBR actor consumers and image/material bytes.
Only their generated fixture input driver differs. A fixed RenderOverlay counter
changes filter 0 -> 4 at main view 40, anisotropy 1 -> 2 at 48, filter 4 -> 0 at
56, and anisotropy 2 -> 1 at 64. It reads no observer/builder completion state.

The gate uses 32 warmup views and 48 retained views, a 300-second process deadline,
and no automatic retry. Each frame must show both authored ordinals with the
same raw pair bases, slot generations/epochs/spans and content epoch as that
process's first retained frame. Dedicated probe sampler arguments remain exact.
Actual emitted material sampler arguments and frame CVar readback must follow
the scheduled changes; merely printing the driver's markers is not sufficient.

The first hosted attempt on PR #155 head
`3f01e7064174192bdd793371ad27126fb09af4a9` retained a useful negative packet:
normal corpus, SDVK-010, SDVK-150 and the unchanged-setting SDVK-153 control all
passed, then reset-1 aborted after eight retained frames because fixture ZScript
called `CVar.SetInt` on the non-`CVAR_MOD` `gl_texture_filter` outside menu code.
Stderr was empty and there was no renderer/device fault. Run 38963610141, job
117185471214, artifact 12074328517 (SHA-256
`00d9ca1c829e4408b1d389ff19eeb79d3e487da00b3602c1da40a07c6d8124fe`)
is retained as **INVALID_FIXTURE_INPUT_DRIVER_NOT_GPU_FAULT**.

The corrected input route removes all direct ZScript CVAR mutation. With the
explicit `-sdvk153samplerresetdriver` opt-in, the native fixture scheduler counts
newly presented main views and queues the same four ordinary console CVAR
commands with `AddCommandString` at views 40/48/56/64. It reads no observer
record, probe identity, resource epoch or acceptance outcome. The next retained
frame independently proves the real CVAR callback and material sampler change.
The reset and control PK3s are now byte-identical; only the executable input flag
differs. This correction changes no production descriptor ownership or threshold.

One unchanged-setting control and two independent reset captures are scheduled
inside the existing normal GitHub-hosted Ubuntu 24.04 llvmpipe lane, reusing its build and
content. The reset runs require exact state/RGB repeatability under the existing
comparison policy, and final reset RGB must equal the unchanged-setting control.
No duplicate full runner, benchmark-only run, physical GPU or local Vulkan device
is authorized or introduced.

**Native evidence scope is deliberately narrow:** existing diagnostics observe
actual immediate actor pair uniforms and selected material/probe sampler state.
They do not read every retained probe-map texel. The raw texel namespace proof
is the exact-source/allocator evidence above; the native gate corroborates live
setting transitions and final imagery, not per-texel GPU readback. Generated
ZScript compilation/execution remains pending until hosted CI actually runs it.

## Remaining SDVK-014 boundaries

The injected old-atlas-receipt ABA case from PR #154 remains unresolved by this
repair; ordinary tile tombstoning is not a durable incarnation handle. No claim
is made that an actual native surface survived retirement. Retained LIGHTMAP
content freshness lacks an authored geometry/light/material digest even though
runtime descriptors/pages are rebound rather than serialized. Repeated/multi-page
native lightmap transitions and the full supported special-surface/material
matrix remain separate #14 work.

Only exact-head full source/CPU/native CI, adversarial review, merge and
exact-master verification can release #153. This local candidate neither closes
#153 nor grants SDVK-014 software-complete status.
