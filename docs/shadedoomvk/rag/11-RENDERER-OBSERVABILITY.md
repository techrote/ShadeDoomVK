# Renderer observation and evidence ownership

Primary issue: SDVK-002 / #2. Status: **accepted, merged and verified** on repaired `master@a05743fb428c0d7c66defccfb577834d012b4e31`. [Owning contract](../SDVK-002-OBSERVABILITY.md) and [release receipt](../SDVK-002-RELEASE-ACCEPTANCE.json) record the exact evidence and limitations.

## Entry points

- `tools/renderer_oracle/corpus.json`: declared classes, retained PF contracts,
  generated recipes, settings, fixed cameras and explicit pending coverage.
- `prepare.py`: deterministic asset/config generation and source/member
  verification. A preparation is never a native result.
- `run.py`: fresh capture, integrity checks, controlled state/image comparison,
  benchmark summaries, scoped PF import and the CPU CI preparation check.
- `observation.schema.json` and `validate.py`: shape plus complete interval,
  per-frame channel, parent/context, numeric and availability invariants.
- `native_ci.py`: software Vulkan capability qualification and real independent
  state/timing processes under a caller-provided display.

## Production boundaries

`SdvkDiagnostics::BeginFrame/EndFrame` surround hardware `RenderView`. The CPU
clock excludes later finish/presentation and end-of-interval serialization.
`HWDrawInfo::DrawScene` owns the observed context stack. The post-presentation
hook in `d_main.cpp` closes the exact requested interval; state/GPU tracing is
off before the ordinary `M_ScreenShot` writer and normal quit.

`VkRenderState` calls the diagnostic only after ordinary draw state has been
applied. `vk_sdvkdiagnostics.cpp` reads the existing descriptor entry selected by
the actual uniform index, semantic layers, selected sampler creation arguments,
probe uniform, canonical pipeline state and owner counters. It must not call
descriptor/image creation or probe resolution just to observe a value.

`hw_spritelight.cpp` emits actual selected/rejected leaves from both actor
per-pixel and CPU aggregate routes. Qualification/reference-only traversals do
not masquerade as rendering decisions. `CollectLights` reports actual shadow
candidate/selected/rejected rows. Frame-local light ordinals are comparison
labels paired with semantics, not persistent gameplay identities.

`vk_commandbuffer.cpp` forwards successfully resolved named GPU timestamp
groups. Missing groups carry reasons. A group may include nested groups and
cannot be summed into a total. The observer and timestamp-validation translation
units use precise math so finite-value rejection remains meaningful.

## Claims consumers may make

The validated native envelope establishes complete bounded collection. It does
not establish image correctness, executed shader identity, arbitrary LevelMesh
surface state, whole-frame GPU time or a performance improvement. Explicit
unavailable fields remain unavailable; PF's private indexed/probe controls keep
their own schemas, validators, input requirements and earlier evidence.

Ordered state comparison preserves draw/query interleaving and repeated-event
counts. Only adjacent identical producer rows may coalesce. Context epoch/id
numbers can be normalized after ancestry validation; the full normalized
parent state is hashed into the child. View position/angle/FOV representation is canonicalized only to 1e-9. The
derived context label is redundant and excluded from equality; an explicit
validated producer field retains the actual root/portal/camera producer. Static-scene
tic/fraction labels may be normalized only under the recipe's declared clock
policy. Renderer-local descriptor slot numbers and selected non-negative shadow-map row numbers are normalized bijectively to first-seen frame-local identities while generation/epoch/span, the shadow `-1` rejection sentinel and aliasing remain exact. Raw resource-owner telemetry
stays in each packet, but process-cumulative/lazy allocation, upload and staging
workload-volume counters are excluded from semantic equality; capacity state,
resets, cancellations, staging wrap/dedicated state and all failure/rejection
diagnostics remain compared. Probe/light/shadow/material/
pipeline decisions are never erased to obtain a pass.

Exact or preregistered tolerant RGB comparison is paired with state. Both
inputs must share actual device/driver/content/settings; changing a build is an
explicit comparison option. A failure is retained and an output directory is
never reused. The CPU CI subset and software Vulkan lane have different proof
scopes. Consult the owning release receipt before treating a recipe as newly
native-qualified or unblocking dependent feature work.

## Native workload assertions

The catalog's `state_assertions` are checked in every recorded state frame by
`run.py::_scene_assertions`: required material names and ordered authored semantic
prefixes, root producers, actual line-mirror contexts, published probe pairs/live
draw bindings, and authored sun intensity. Authored layers and fallback slots
carry distinct roles; extra brightmap/detail/glow layers pass only when marked
`fallback-placeholder` and backed by the canonical one-pixel lump-0 resources.
A generated asset is not a draw witness.
The new static `sprite-mirror` recipe uses authored asymmetric paired rotations
and the accepted PF line-mirror special. Original PF byte inventories and
fixed-fraction/IWAD contracts are preserved. Two copies of one capture cannot
satisfy independent-repeat comparison.

The shadow-capacity correctness witness uses exactly 1,025 candidate lights,
requires 1,024 selected and one dropped, the lowest valid 128 shadow-map
resolution and one warmup frame. This is the smallest true overflow witness for
software Vulkan; it does not change the 1,024-row capacity invariant and is not a
quality or benchmark workload.

## SDVK-004 accepted pressure-observation reuse

SDVK-004 adds no second renderer diagnostic channel. It consumes the accepted
SDVK-002 resource event fields for requested/device/effective bindless capacity,
dynamic start, current/high-water allocation, allocation/reuse/free/failure
counters, lifetime generations/epochs and texture/lightmap/probe owner/resource
counts.

The existing `material-stress` recipe is extended with eight authored PBR
custom-shader bindings. Their screenshots remain paired with ordinary material
events. The fixed semantic prefix remains under `material_semantics`, while
`material_custom_layers` separately requires the observed custom binding/index
and requested sampling on the named panels. Descriptor slot numbers may still
normalize only as renderer-local
identities; generation/epoch/span and aliasing remain exact. A generated member
or authored GLDEFS entry is not a draw witness.

The deterministic 75% pressure number is a CPU contract baseline. Native resource events separately recorded the actual llvmpipe workload: `material-stress` reached 438 current/high-water descriptors, 72 allocations, 4 reuses, 4 frees, zero failures/invalid frees and 142 hardware textures. Both independent captures agreed. These numbers must not be conflated with the synthetic 75% capacity fixture. Exact evidence pins are in [SDVK-004 release acceptance](../SDVK-004-RELEASE-ACCEPTANCE.json).

## SDVK-006 visual-time observation

Frame and context records now include nested `visual_time` state. Context records identify `main-owner`, `main-sibling`, `main-portal` or `non-main-fallback` plus whether that context conceptually advances the main clock. Delta, accumulated visual time, generation, main-frame ordinal, validity, interpolation validity, clamp state and discontinuity reason are emitted from the production clock. Non-main fallback is explicitly zero/invalid; merely observing a portal/camera/probe context is side-effect free. This extends SDVK-002 diagnostics rather than creating a second evidence mechanism.


### Visual-time comparison policy

Raw native records retain exact visual delta, accumulated visual time, generation/main-frame ordinals, validity, clamp and discontinuity diagnostics. The structural validator checks finite/bounded clock fields and enforces PF-010 scope: only a main eye-0 root is a `main-owner`; main portals/stereo siblings are read-only; non-main roots and descendants must expose zero/invalid fallback state. Cross-process **scene-state** comparison deliberately projects visual-time records to stable scope/ownership only. Wall-clock magnitudes, generations and pacing-dependent discontinuities are evidence but not semantic scene equality, just as CPU frame duration is not compared as renderer state. This prevents driver/scheduler pacing from manufacturing false corpus differences without normalizing away context ownership defects.

## SDVK-009 many-light observation

State mode now records a bounded light census (authored/active/spot/additive/
subtractive), aggregate actor-query work (queries/candidates/selected/filtered/
duplicates/traces) and immediate Vulkan light-upload work. Upload evidence
includes range/record capacity and usage, capacity bytes, attempts/failures,
class record totals, transferred logical bytes, peak list size and six bounded
list-size buckets. Any observed immediate upload capacity failure fails semantic
validation rather than disappearing as an accepted unlit fallback.

These counters deliberately reuse the existing SDVK-002 state oracle. The light
census already traverses the state-mode light map; per-upload bookkeeping is
also state-only. Timing mode reports the upload channel unavailable and keeps
existing CPU/GPU timing collection free of that per-draw instrumentation.
The full hosted software-Vulkan lane adds paired state/image checks for the two
256-light SDVK-009 scenes plus separate short descriptive dense timing receipts;
those receipts are not physical-GPU performance evidence.

## SDVK-007 emitted sprite-basis evidence

In default-off SDVK state observation only, `HWSprite::CreateVertices` records a temporary PF-009 final-quad source identity, signed UV span, frame/actor flips, sprite mode, camera roll/pitch, portal parity and explicit/fallback disposition. `FSdvkDiagnosticAccess::Draw` emits `sprite-basis` **after Vulkan command submission**, including the actual `SurfaceUniforms` tangent, normal, sign/mode, material semantic name, height index, shader identity and PF-010 context. This distinguishes actual drawing from a CPU tangent generated but never consumed. Transient metadata is cleared at sprite-draw boundaries; it has no effect on policy or publication.

`observation.schema.json` and `validate.py` reject nonfinite, nonunit, nonorthogonal and degenerate axes, impossible handedness, inconsistent signed-UV/mirror parity, invalid/absent canonical source, stale fallback uniforms and context mirror mismatches. `sprite-mirror` requires actual emitted `sprite-basis` records and observed specular/PBR/no-map control materials in the full software-Vulkan lane. Timing-only mode is unchanged, and the record never implies physical-GPU qualification or general PBR performance evidence.

The accepted [SDVK-007 qualification](../SDVK-007-FINAL-ACCEPTANCE.md) and [release receipt](../SDVK-007-RELEASE-ACCEPTANCE.json) pin emitted-draw negative controls, software-Vulkan repeatability and exact master CI (9/9 after same-SHA Windows Debug rerun). Initial failures remain explicitly retained, not waived.

## SDVK-008 bounded relief emitted-draw diagnostics

State-mode `VkRenderState` emits `sprite-relief` after the actual sprite Vulkan draw, associated with accepted `sprite-basis` PF-009 source and PF-010 current render-context mirror identity. The record includes material semantic name/shader index, height descriptor index, final signed UV bounds, opt-in candidate flag, explicit basis enable, provisional depth/quality, draw eligibility, and the **theoretical upper height-read limit of 0/10/15/23 per fragment**. It does *not* assert a per-fragment traversal count, actual pixels visited, GPU timestamp, POM visibility success or hardware cost.

`validate.py` checks finite depth/UV, signed-bound identity, shader/height/basis agreement, candidate-fallback zeroed uniform state, impossible quality/work claim, unaccepted PF-009 source and conflicting PF-010 context. The `sprite-mirror` native state contract demands an observed bound height+specular eligible draw and mirrored context, plus heightless PBR/no-map negative draws. The default-off material/shader ABI is checked by host fixtures and full inherited corpus. Physical timing and visual usefulness remain a separate preregistered #8 gate; [off-GPU report](../SDVK-008-OFFGPU-QUALIFICATION.md).
## SDVK-010 emitted actor probe evidence (candidate)

The state-only Vulkan observer's existing `probe` draw record adds `actor_selection` with interpolated actor source XYZ, PF-009 portal context, candidate count, sector target, selected ordinal, policy, distance and fallback. The same record retains the **actual** emitted surface uniform's authored/runtime descriptor, bindless generation/resource identity, published pairs and texture-owner epoch. Strict state validation enforces ordinal bounds, portal-conservative selection, radius/finiteness, correct zero IBL and publication backing. New `sun-probes` positive native scene and `sprite-mirror` zero-probe control are required; their successful **hosted** execution and the independent sunlight/linked-portal world-occlusion gate are still unproven. This evidence must not be promoted to IBL/sun acceptance based only on an offline fixture. [Policy](../SDVK-010-ACTOR-ENVIRONMENT-CONTRACT.md).

## SDVK-008 independent campaign tooling checkpoint

`sdvk008_physical.py` and `sdvk008_fixtures.py` keep authored content/tooling
hashes distinct from the frozen SDVK-008 renderer build. The wrapper authenticates
actual emitted relief eligibility/read ceilings and X/Y signed-UV witnesses;
image oracles separately check OFF equality, a preregistered marker direction and
binary-alpha masks against a no-card background. These finite witnesses do not
prove general portal, atlas, invalid-input or material-UV correctness. Missing
fixture gates block full physical timing before launch. The explicit hosted CPU
llvmpipe smoke has a distinct software-only receipt and cannot award physical
evidence or acceptance. Raw failed attempts and checksums are retained. See the
[tooling checkpoint](../SDVK-008-PHYSICAL-TOOLING-CHECKPOINT.md); the local physical
programme is stopped after the separately recorded SDVK-009 GPU fault.
