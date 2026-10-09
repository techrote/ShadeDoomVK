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

## SDVK-004 pressure-observation reuse

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

The deterministic 75% pressure number is a CPU contract baseline. Native
resource events record the actual software-Vulkan workload pressure separately;
the two must not be conflated.
