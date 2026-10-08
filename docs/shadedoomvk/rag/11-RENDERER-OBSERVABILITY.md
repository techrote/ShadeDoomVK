# Renderer observation and evidence ownership

Primary issue: SDVK-002 / #2. Status: implementation; native/release acceptance
is recorded separately in [the owning contract](../SDVK-002-OBSERVABILITY.md).

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
parent state is hashed into the child. View position/angle/FOV representation
is canonicalized only to 1e-9, and the context label retains its nonnumeric
portal-kind prefix while rebuilding its derived numeric suffix. Static-scene
tic/fraction labels may be normalized only under the recipe's declared clock
policy. Renderer-local live slot numbers are normalized to first-seen identities
while generation/epoch/span and aliasing remain. Raw resource-owner telemetry
stays in each packet, but process-cumulative/lazy allocation, upload and staging
workload counters are excluded from semantic equality; capacity state and all
failure/rejection diagnostics remain compared. Probe/light/shadow/material/
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
draw bindings, and authored sun intensity. Extra brightmap/detail/glow layers
pass only when they are the engine's canonical one-pixel lump-0 placeholders.
A generated asset is not a draw witness.
The new static `sprite-mirror` recipe uses authored asymmetric paired rotations
and the accepted PF line-mirror special. Original PF byte inventories and
fixed-fraction/IWAD contracts are preserved. Two copies of one capture cannot
satisfy independent-repeat comparison.

The 1,056-light shadow-capacity correctness witness retains 1,056 candidate,
1,024 selected and 32 dropped assertions but uses a two-frame warmup on software
Vulkan. The earlier 120-frame warmup exceeded the bounded llvmpipe run before
observation and was not a benchmark requirement; timing workloads remain separate.
