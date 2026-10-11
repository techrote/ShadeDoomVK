# Renderer reference corpus and evidence harness

This is the SDVK-002 extension of the accepted PF oracle. It prepares a compact
corpus, captures the actual renderer, checks evidence, compares fixed-camera
state and pixels, and describes repeated timing runs. The canonical scope is
[SDVK-002](../../docs/shadedoomvk/issues/SDVK-002.md); acceptance still follows
[AGENTS.md](../../AGENTS.md) and the
[validation/performance contract](../../docs/shadedoomvk/06-VALIDATION-PERFORMANCE-CONTRACT.md).

**The catalog declares intended workloads, with native qualification pending.**
Generating a PK3, passing CPU contracts, collecting a native receipt, and
qualifying a renderer workload are distinct results. No catalog entry asserts
that native compilation, rendering, image repeatability, or a timing baseline
has already succeeded. A failed workload gate must be investigated and fixed
from its retained evidence; do not remove the gate to make an attempt pass.

## Files and prerequisites

Run commands below from the repository root. Preparation, evidence validation,
image comparison and statistics use the Python standard library (Python 3.10
or later). The retained CPU contracts also use the repository's supported C++
compiler. Native capture needs a built ShadeDoomVK runtime, its accompanying
packages, a working Vulkan/display environment, and an externally supplied
compatible IWAD.

| File | Responsibility |
| --- | --- |
| [corpus.json](corpus.json) | Eleven scene recipes, eight classes, exact settings/cameras, image policy, source references and 19 executable retained CPU contracts. |
| [prepare.py](prepare.py) | Deterministic authored assets and unchanged PF package members; pure prepared-input verification. |
| [run.py](run.py) | Fresh process capture, artifact validation, state/image comparison, repeated-process baselines, PF import and CI entry points. |
| [validate.py](validate.py) | Native schema, bounds, per-frame channel presence, context lineage and other state invariants. |
| [images.py](images.py) | Bounded RGB8 PNG decoding and exact or preregistered tolerant comparison. |
| [benchmark.py](benchmark.py) | Descriptive distributions of actual CPU samples and separately named GPU groups. |
| [adapters.py](adapters.py) | Index original PF documents while retaining their original scope and validators. |

New texture pixels, maps and actors are authored here. Preparation copies no
IWAD bytes into a PK3. The three retained PF recipes require the accepted Doom2
IWAD SHA-256
`31740ef23994b3959800134b41aaf86b04a2847336d328af8c4ae890450630ab`.
The eight new authored scenes accept an externally supplied Doom2-compatible
IWAD whose actual hash is pinned before capture. A legal compatible IWAD such
as Freedoom2 may be used for those scenes, subject to actual native
compatibility validation. It does not replace the retained PF IWAD requirement.

## Corpus and coverage

The class names in the machine-readable catalog are `sprite_orientation`,
`semantic_materials`, `lights_occlusion`, `probes_sun`, `portals_views`,
`decals_canvas_translucency`, `shadows`, and `resource_stress`.

| Scene ID / map | Prepared workload | Declared classes and native limits |
| --- | --- | --- |
| `pf-sprite-views` / `PFVTEST` | Unchanged PF sprite rotations/mirroring, linked portal, mirror, camera and probe fixture. | Sprite orientation, portals/views, probes. Requires its retained fixed-fraction PF state driver; generic capture rejects this entry. Plane mirrors, stereo and SavePicture remain outside this native fixture. |
| `pf-indexed-material` / `PF110` | Unchanged indexed/palette/translation/RedIsAlpha and SWCanvas fixture assets. | Semantic materials and canvas/translucency class. Generic capture uses the public truecolour overlay. Hardware-palette, SWCanvas, private readbacks and restart controls retain their separate PF recipes. |
| `pf-pbr-probes` / `PF113` | Unchanged generated PBR and missing-to-published probe fixture. | Semantic materials and probes. Startup/publication convergence and actual sampling still need native evidence. No sunlight qualification is inferred. |
| `compositing` / `SDVCMP` | Two overlapping translucent wall sprites, a permanent decal near a wall, a deliberately distant negative decal and a sampled camera texture. | Decals/canvas/translucency, sprite orientation and views. Requires real decal drawing, `main` and `camera-texture` contexts and material `SDVCAM`; preparation does not establish successful attachment or blending. |
| `lights-zero` / `SDVL0` | Static room, solid occluder and two marker sprites; zero dynamic lights. | Light/occlusion and shadow fallback. Zero candidates, selected shadows and drops are required. Empty light/shadow decision streams are permitted. |
| `lights-one` / `SDVL1` | Same room with one colored point light. | Light/occlusion and shadows. Exactly one eligible/selected shadow light and no drops are required; actual decisions and images remain necessary. |
| `lights-many` / `SDVLMANY` | Same room with 64 deterministic colored point lights. | Light/occlusion and shadows. Exactly 64 eligible/selected shadow lights and no drops are required. |
| `shadow-boundary` / `SDVSHDW` | 1,025 deterministic point lights around the solid occluder. | Light/occlusion and shadow capacity. Explicit `--include-stress`; requires exactly 1,025 candidates, 1,024 selected and one dropped. |
| `material-stress` / `SDVMAT` | 64 distinct authored wall materials: albedo, normal/specular, PBR, zero-roughness, optional height and custom-shader inputs. | Semantic materials and resource stress. Every panel must be observed with its declared binding sequence; SDVK-005 height cases additionally prove actual dynamic height binding and independently filtered data while custom binding 8 remains stable. Authoring alone cannot pass. Descriptor exhaustion, async races and stale reuse retain their CPU negatives. |
| `sprite-mirror` / `SDVROT` | Eight stationary authored rotation actors, five asymmetric paired-rotation textures with normal/specular layers, wall/flat/X/Y-flip variants and an east-wall mirror. | Requires actual line-mirror context, all five material bindings and their declared semantics. Supplements the original PF fixed-fraction/linked-portal fixture; it does not relabel that fixture or its IWAD. |
| `sun-probes` / `SDVSUN` | Raised-floor PBR room, two explicit probes, generated sky, authored sunlight input and a separate point-light/two-marker query control. | Probes/sun and semantic materials. Explicit `--include-stress`; requires at least two published irradiance/prefilter pairs, a live observed probe binding and actual authored sun intensity. Per-surface sunlight visibility and full bake convergence remain outside this receipt. No baked asset, full-bake command or broad bake-robustness claim is supplied. |

The positive authored light workloads request `gl_light_shadows=2`. In the
current light owner, mode 1 can additionally depend on whether the influence
hits a one-sided back wall. Mode 2 makes the intended eligible-count workload
explicit; the harness still requires actual counts. The zero-light scene uses
shadow mode 0. All four require at least two rendered marker sprites.
The authored light and sun scenes explicitly select `gl_lights=true`,
`gl_light_sprites=true` and `gl_spritelight=2`, so their actor query route does
not depend on backend-dependent defaults. The sun scene includes one point
light and two marker sprites to exercise that route before a lightmap exists;
that control does not establish successful sunlight or probe sampling.

The compositing workload requires at least two rendered sprites and one
rendered decal in each recorded frame. Its state assertions require both root
context types and the sampled camera material. The distant decal is an
authored negative whose failed attachment still needs actual observation.
If camera-texture update cadence or actor authoring prevents a required state
from appearing, retain that failed attempt and repair the demonstrated cause.

The 19 CPU contracts cover retained bindless capacity, indexed input/material
semantics, LevelMesh mutation, light-query correctness, lighting compatibility,
material correctness/layers, PBR/probe sampling, pipeline keys, probe/lightmap
selection, render contexts, resource generations, sampler slots, shadow
visibility, portal sprites, sprite surfaces, SWCanvas and PF view inputs.
Each catalog contract resolves to an existing exact test or compiled fixture,
with its command and minimized negative sources retained. This is a tractable
CPU subset, not full native coverage of every class or compatibility path.

## Prepare and verify assets

```sh
python tools/renderer_oracle/prepare.py --out /absolute/evidence/prepared
python tools/renderer_oracle/prepare.py --out /absolute/evidence/selected --scene compositing --scene lights-many
```

The output directory must not already exist. A preparation writes
`prepared.json` and `scenes/<id>/{scene.pk3,fixture.ini,capture.cfg}`. Its status is
`prepared_only`, with `native_executed=false` and `native_qualified=false`.
Selecting a subset is explicit and recorded in the manifest.

New archives use sorted members, fixed metadata and stored ZIP entries. New
PNG pixels use a deterministic stored-DEFLATE stream. Retained PF members and
their archive construction come directly from the original generator callables.
The manifest includes package/member SHA-256 values and sizes, catalog identity,
actual source-input hashes, retained negative references and the source commit.
It contains no absolute output paths or generation timestamps, so two fresh
preparations of the same checkout have identical bytes. Source cleanliness is
not inferred from a commit string; source files are pinned independently.

The reusable Python entry points are:

```python
from pathlib import Path
from tools.renderer_oracle import prepare

catalog = prepare.load_catalog()
prepare.validate_catalog(catalog)
manifest = prepare.prepare(Path("/absolute/evidence/new-preparation"))
verified = prepare.verify_prepared(Path("/absolute/evidence/new-preparation"))
```

`verify_prepared()` checks current catalog/source identities, purely regenerates
expected members/config/scripts, and checks the recorded and actual bytes. It
rejects altered assets even if their manifest hashes were recomputed. Native
capture verifies preparation before copying inputs and checks copied identities
again. Reprepare after changing the corpus or its pinned sources; do not edit a
prepared receipt to relabel older inputs.

## Capture and validate one native attempt

```sh
python tools/renderer_oracle/run.py capture --exe /absolute/runtime/vkdoom --iwad /absolute/content/freedoom2.wad --prepared /absolute/evidence/prepared --scene compositing --out /absolute/evidence/compositing-state-a --mode state --warmup 180 --frames 1 --timeout 180
python tools/renderer_oracle/run.py validate /absolute/evidence/compositing-state-a
```

Use the actual runtime executable name on your platform. Every attempt uses
a fresh output, configuration, save directory, application cache and process.
Automatic autoload/autoexec are disabled; the actually loaded engine packages,
isolated IWAD and scene are enumerated and hashed. A same-named hidden package
or an omitted preregistered package cannot silently stand in for an input.
Global driver caches and external host scheduling/power policy remain
uncontrolled and are described as such in the evidence.

The script uses a fixed 640×480 client extent, camera position/angles/FOV,
seed, UI policy and explicit settings from the catalog. Every declared CVar is
checked against a real source declaration and queried through the engine after
assignment; actual frame settings are also checked where the observer exposes
them. PNG is explicitly selected with the string CVar `screenshot_type=png`.
`fov 90`, `vid_setsize 640 480` and `unbindall` are console commands, not invented
CVars. Native map/camera/extent and workload assertions are mandatory.

The driver passes the production observer options:

```text
-sdvkobserve PREFIX
-sdvkobserveframes N
-sdvkobservewarmup N
-sdvkobservemode state|timing
-sdvkobservecache DIRECTORY
-sdvkobservequit
```

`--gpu` additionally requests `-sdvkobservegpu`. The observer finishes the exact
recorded frame budget, captures `PREFIX.png` in state mode after presentation
through the ordinary screenshot writer, writes `PREFIX.renderer.json`, then
requests ordinary quit. `capture.cfg` has no timed wait, screenshot, freeze or
quit sequence which could truncate the observation. Defaults are one recorded
state frame or 120 timing frames, with each recipe's preregistered correctness
warmup. Ordinary authored scenes use 120; the 1,025-light shadow-capacity witness
uses one warmup frame and the lowest valid 128 shadow-map resolution. It still
must prove 1,025 candidates, exactly 1,024 selected and one dropped. This is the
smallest true capacity-overflow correctness witness and is never an image-quality
or benchmark-performance claim. The bounded interface permits
1–4,096 recorded frames, 0–100,000 warmup frames and a 1–3,600 second timeout.

The eight new scenes use static authored cameras and no animated/random scene
actors. Their correctness clock is `static_after_initialization`; timing uses
`ordinary_engine_clock`. The interpolated PFVTEST actor remains tied to its
retained PF single-tic/half-fraction correctness driver. Never use the PF fixed
clock to claim ordinary renderer performance.

## Native state and integrity gates

Native observations use `sdvk-renderer-observation/v1`. Each record has
`kind`, a one-based recorded `frame`, `count` and `data`.

| Kind | Actual state and its limits |
| --- | --- |
| `frame` | Actual map/camera/tic/fraction/extent/settings, CPU RenderView duration, draw/geometry and light/shadow counters. |
| `context` | Main, portal, camera-texture, probe or save-picture context, epoch/id/parent, camera and eligibility/mirror flags. |
| `material` | Immediate draw material, ordered semantic layers, selected sampler creation arguments and live resource token when available. A no-material draw is explicit and cannot satisfy required material coverage. |
| `light-query` | Actual actor per-pixel or CPU aggregate decisions and query summaries, candidate source, actor/query position and current-frame light identity. It is not complete LevelMesh per-surface or shader-consumption evidence. |
| `probe` | Actual immediate-draw authored index, runtime irradiance uniform, fallback/sentinel and resource/sampler state. Per-texel gathered mapping retains its PF producer. |
| `shadow` | Actual shadow row selection or immediate shader policy, with world-geometry caster scope. This does not claim sprite silhouette geometry. |
| `resource` | Current descriptor capacity/usage/high water, generations/lifetimes, upload/staging, optional LevelMesh and authored sun state. Many counters are cumulative owner snapshots. |
| `pipeline` | Canonical fields of the emitted immediate draw's pipeline/shader key and target state. A key is not proof of executed shader instructions. |
| `timing` | Resolved named Vulkan timestamp groups or explicit unavailability. Groups may nest and never establish whole-frame GPU time. |

Missing/unsupported state is represented with `available=false` and a reason.
Required kinds are checked in every recorded state frame; a previous frame
cannot cover missing later instrumentation. Context references must equal the
observed context, and parents must exist at the correct depth. Resource indices
and generation/epoch/span, samplers, probe sentinels, shadow modes and descriptor
accounting are validated. Authored material-semantic assertions require their
declared ordered prefix and must carry the explicit `authored-layer` role.
Extra `brightmap-emissive`, `detail` or `glow` layers are accepted only when
the engine reports the explicit `fallback-placeholder` role and their source is
the canonical one-pixel lump-0 fallback; arbitrary extra semantics remain a failure. Timing mode rejects per-draw state instrumentation.

The native record store preserves order and may coalesce only adjacent equal
records with the same kind and frame. It retains at most 65,536 records, 16 KiB
per record and 16 MiB of retained payload. Dropped/truncated/nonfinite records,
an incomplete interval, a failed collector or an unresolved required workload
gate fail validation. Bounds are not a reason to discard observations silently.

## Compare independent state captures

Make a second capture in a different fresh output directory with the same
prepared scene and explicit options, then compare:

```sh
python tools/renderer_oracle/run.py compare /absolute/evidence/compositing-state-a /absolute/evidence/compositing-state-b --out /absolute/evidence/compositing-comparison.json
```

Both input packets are revalidated. Identical directories and two archived copies
of one original process are rejected; copying a packet does not create repetition evidence. Reproduction profiles, actual
device/driver/backend, content and clean build identities must meet the
comparison gates. An intentional candidate build comparison uses
`--allow-build-change`; it does not relax scene/settings/device or image/state
requirements. Keep both immutable source packets and the comparison manifest.

State comparison preserves the ordered record stream and multiplicities,
semantic decisions, resource generation/epoch/span and aliasing, pipeline fields,
fallbacks and all resource failure/rejection diagnostics. Renderer-local live
descriptor slot numbers and selected shadow-map row numbers are normalized to
first-seen identities; raw values are still validated within each capture. The
shadow `-1` rejection sentinel and row aliasing remain exact comparison state. After validating context links, renderer-local
context epoch/id/parent tokens and the redundant derived `semantic_key` label
are normalized. The actual context producer is a separate validated field and is
never discarded. Context and frame-view positions/angles/FOV are canonicalized
only to 1e-9, matching the fixed-camera assertion tolerance; larger motion still
changes semantic state. Each parent link is replaced by a SHA-256 of its full
normalized parent context, recursively including ancestry.

Resource records retain every raw counter in the immutable run packet. Semantic
state equality excludes only process-cumulative/lazy workload telemetry:
descriptor current/high-water/allocation/reuse/free counts, hardware-texture
count, lifetime activation/retirement counts, async queued/completed counts, and
staging request/byte/high-water/reuse counts. Capacity/limit state, resource
epochs, page/probe counts, descriptor failures/invalid frees, lifetime reset/
stale/invalid/duplicate diagnostics, async cancellation/epoch/ticket rejection
diagnostics, staging wrap-waits/dedicated usage, LevelMesh state and authored sun
state remain compared. Timing/baseline reports
continue to consume the raw counters. For explicitly static scenes, frame/context
tic and interpolation-fraction labels are also removed. CPU durations and GPU
timing records do not enter correctness state comparison. No image mask,
light-list sorting, generation reset or broad state-field deletion is used to
obtain equivalence.

Image comparison decodes bounded, CRC-checked noninterlaced RGB8 PNG pixels.
Compressed PNG bytes are not pixel identity. The default `exact-rgb8` policy
requires every decoded channel to match. It is a same-device/driver/profile
policy, with no portable exact-pixel promise across different hardware.

Choose `--image-policy tolerant` **at capture time for both attempts** to use
the catalog's preregistered `rgb8-absolute` policy. All three conditions must
hold together:

| Metric | Maximum allowed |
| --- | --- |
| Absolute error in any RGB channel | 2 out of 255 |
| Mean absolute error over all RGB channels | 0.25 |
| Fraction of pixels with any changed RGB channel | 0.01 (1%) |

There is no CLI to raise tolerance after seeing a comparison failure. Exact or
tolerant image success always requires state equality and the mandatory scene
assertions. A comparison emits `PASS` only for both; it does not award issue or
performance acceptance.

## Repeated timing workloads

First qualify the corresponding correctness workload. Record at least three
independent ordinary-clock timing attempts with the same clean runtime,
workload, warmup, device and settings. For example, run the following once per
fresh output name `lights-many-timing-a`, `-b` and `-c`:

```sh
python tools/renderer_oracle/run.py capture --exe /absolute/runtime/vkdoom --iwad /absolute/content/freedoom2.wad --prepared /absolute/evidence/prepared --scene lights-many --out /absolute/evidence/lights-many-timing-a --mode timing --warmup 180 --frames 240 --timeout 300 --gpu
python tools/renderer_oracle/run.py benchmark /absolute/evidence/lights-many-timing-a /absolute/evidence/lights-many-timing-b /absolute/evidence/lights-many-timing-c --minimum-samples 30 --out /absolute/evidence/lights-many-baseline.json
```

Timing mode omits per-draw correctness instrumentation and screenshots, while
retaining CPU samples, actual frame/counter state and resource snapshots.
The CPU interval is the steady-clock duration of RenderView, including canvas,
probe and scene work inside that call. Simulation and later finish/presentation
outside the call are excluded. This interval is not whole application frame
time, and resource serialization or optional timestamp collection still have
their documented observation cost.

Baselines require matching reproduction profiles, executable/package bytes,
clean source identity, actual device information and recorded host/loader/layer/
thread environments. A duplicate path or a copied receipt from the same
original process is rejected. External contention, thermals, host power policy
and driver-global cache state are not controlled by this harness.

The report retains raw per-frame values, min/max/mean and p50/p90/p95/p99. Its
percentiles use Hyndman–Fan type 7, linear interpolation at `(n-1)*p/100`.
The default minimum is 30 CPU samples per run. Each process has its own
distribution, and the report also describes between-run CPU medians. Three or
more independent processes set `repeatability_evidence=true`; that flag is not
a statistical significance or stability threshold.

Resolved GPU samples are grouped only by their actual timestamp-group names,
with raw values and independent distributions. Groups can nest or occur more
than once per frame: do not sum them, equate them to full-frame GPU time, or
assume sample counts match CPU frames. Unavailable groups are explicit.
Frame draw/geometry counters are summarized; raw frame light/shadow counts and
descriptor/resource snapshots remain in the native packet for workload review.
Counters retain their actual units and cumulative scope. No outlier removal,
average-FPS optimization claim, automatic speedup/significance decision or
performance acceptance is made. `benchmark` emits `DESCRIPTIVE`.

## Retained PF evidence remains independent

Each retained scene's `native.legacy_recipe` identifies the original callable
generator, command/script builder, native diagnostic and required arguments.
The original PF sources, minimized negatives and acceptance receipts remain
unchanged. Dedicated PF drivers remain authoritative for their complete
artifact packets, pinned IWADs, source-equivalence controls and private
readbacks. A generic observation does not supersede those protocols.

```sh
python tools/renderer_oracle/run.py import-pf /absolute/pf-evidence/observer.json --out /absolute/evidence/pf-index.json
```

Import recognizes the retained PF020 scene/Vulkan, PF110 indexed, and PF113
startup/probe-control schemas. It retains the entire original JSON and its
byte identity, indexes available source fields, and records the original
validator. The result says `indexed_only`, `fresh_execution=false` and
`current_build_equivalence_established=false`. Referenced private artifacts
still need the original validator; an import is neither a fresh run nor a new
qualification. Existing PF/CFX/P400 limitations and stop conditions remain in
force unless their owning issue supplies the required separate evidence.

## CI, failed attempts and qualification records

```sh
python -m unittest discover -s tools/renderer_oracle/tests -p 'test_*.py' -v
python tools/renderer_oracle/run.py ci --out /absolute/evidence/cpu-ci --with-contracts
```

`ci` prepares all eleven scenes twice and compares manifests/bytes. With
`--with-contracts` it also executes each of the 19 named retained CPU commands
once, preserving logs. No display or Vulkan runtime is required for this subset.
Its `PASS` is explicitly `native_execution=false` and
`image_or_gpu_acceptance=false`; this CPU subset does not assert GPU pixels.

The separate Ubuntu software Vulkan CI lane uses the actual built engine under
Xvfb and an isolated llvmpipe ICD. It verifies the CPU device and required
descriptor-indexing features before launching a scene, retains system/driver/
package/IWAD provenance, and runs this command:

```sh
xvfb-run -a -s '-screen 0 640x480x24 -nolisten tcp' python3 tools/renderer_oracle/native_ci.py --exe build/vkdoom --iwad /usr/share/games/doom/freedoom2.wad --out build/renderer-native --full
```

`VK_DRIVER_FILES` and/or `VK_ICD_FILENAMES` must identify one llvmpipe manifest;
when both are set they must agree. `--full` selects all eight newly authored
scenes. Without it, the tractable default is `compositing` and `lights-one`;
`--scene` may be repeated to choose a declared subset. The runner creates two
independent state captures per selected scene, requires exact RGB/state
comparison, and collects three separate 120-frame `lights-one` timing runs.
Every timing run must supply actual numeric GPU groups as well as CPU samples.
Independent scenes continue after a failed attempt; no attempt is retried, and
any required failure makes `native-ci.json` fail. A failed software-device
preflight prevents all renderer launches.

The complete artifact includes copied inputs and the matching Freedoom
copyright notice. A different licensed IWAD needs `--iwad-license PATH`.
Software Vulkan verifies this documented software/device profile and collection
path; it does not supply physical-GPU performance or new qualification of the
three independently pinned PF native recipes.

Each native attempt retains `request.json` preregistration, `recipe.json`,
`prepared.json`, executable version output, stdout/stderr, immutable copied
inputs, native observations and the state-mode PNG. `run.json` records status,
timestamps, elapsed time, identities, loaded packages, validation and artifact
hashes. Files are written fresh, automatic retries are disabled, and capture
failures retain their output directory and error instead of replacing the
attempt. A failure before an output directory is created is reported directly.

Run inputs include an isolated IWAD copy. Keep that private when its license
requires it; public evidence should use identities, authored assets and the
appropriate permitted outputs, not automatically publish the entire run folder.

The evidence stages are deliberately distinct:

| Result | What it establishes |
| --- | --- |
| `prepared_only` | Deterministic, authenticated asset preparation only. |
| CI `PASS` | Deterministic preparation and the explicitly executed CPU subset. |
| Native `COLLECTED_PENDING_VALIDATION` | Producer finished its bounded interval; external checks still required. |
| Run `COLLECTED` / validation `PASS` | Packet integrity, actual settings/map/camera and declared workload/state gates passed. |
| Comparison `PASS` | Two validated matching-profile captures have equal normalized state and satisfy the preregistered image policy. |
| Baseline `DESCRIPTIVE` | Raw repeated timing/counter distributions with declared measurement limits. |
| Issue/workload qualification | Separately reviewed evidence for the intended native paths, independent repeatability, applicable CPU/GPU/counter baseline and repository merge/verification gates. |

No command promotes the final row automatically. Record native compilation,
unsupported hardware, missing channels, instability or unmet workload gates
as concrete pending evidence. Later SDVK defects should add a minimized
positive/negative fixture and update the corresponding catalog/source
references without erasing the old failing evidence.

## SDVK-008 independent physical collection

`sdvk008_physical.py` consumes the finite `sdvk008-*` corpus recipes and the
original #8 protocol. Its renderer identity is the immutable implementation
commit `9536324ce33ea418af5a8efe733b4659f6b4ad9b`, tree
`3123bc7fd3dd9074487cbe3487f9336ef3589003`. Fixture/tooling hashes are recorded
separately; these newer authored packages do not relabel the renderer build.
The original #9 driver is independent.

```sh
python tools/renderer_oracle/sdvk008_physical.py --exe /absolute/frozen/vkdoom --iwad /absolute/private/doom2.wad --out /absolute/fresh/sdvk008-device-packet --device-name "EXACT Vulkan DeviceName" --vulkan-summary /absolute/preflight/vulkaninfo-summary.txt --execute --correctness-only
```

The operator first verifies Vulkan/device, build, host/driver/thermal and licensed
IWAD provenance according to the physical protocol. The device name above must
match the renderer's actual `build.device`; device type must be physical (1/2).
The retained `vulkaninfo --summary` must identify that unique physical Vulkan
device before the first renderer process. Actual renderer vendor/device/type
must subsequently agree. OS/CUDA inventory cannot substitute for this input.
Every capture authenticates source, executable, engine/IWAD/content, effective
settings and actual readbacks. Fresh config, saves and application caches are
isolated by `run.py`; OS/driver caches remain externally controlled.

Default execution without `--correctness-only` fails before any renderer launch
while `sdvk008_fixtures.MISSING_GATES` is nonempty. The partial option explicitly
collects available 640×480 correctness pairs twice and all eleven timing variant
**state** captures twice at 1904×1001. It never collects timing samples or grants
full correctness. Repeat comparisons use exact state/RGB policies; paired OFF/ON
images must share package bytes, camera and non-relief settings. Positive RGB
differences establish a visible effect only. Unimplemented mirror/portal,
grazing/distance, invalid height/view, atlas and PBR semantic witnesses remain
explicit acceptance blockers. Descriptive image checks never unlock timing.
Single-card direction uses a preregistered red-marker centroid and expected
screen signs; failures are retained without adapting the sign. Alpha/cutout
evidence compares exact OFF/ON masks against an independently repeated
no-card-background capture. Both witnesses apply only to their finite authored
fixtures. A missing directional marker is reported inconclusive. Source-level
`AVAILABLE_GATES` means an oracle is implemented, never that physical evidence
already passed.

After a complete correctness contract exists, the timing path uses the original
three 11-variant counterbalanced orders, with exactly 120 warmup and 120 retained
frames per independent serial process. CPU and each consistently available GPU
group are evaluated separately: interpolated p50/p90/p95/p99, matched ON−OFF
milliseconds/ratios, process-median MAD, >5% OFF variability, and the strict
`max(0.05 ms, 2 × OFF median MAD)` detection threshold. Resolved GPU groups with
incomplete or repeated unnamed per-frame scopes cannot become an invented
whole-frame duration. No nested groups are summed or samples discarded. An
effect below the detection limit is not reported as zero cost.

`sdvk008-physical-campaign.json` and `checksums.json` retain completion/failure
status and the entire file inventory, including raw attempts and private IWAD
copies. `verify_checksums(packet_path)` rejects altered, missing or added files.
Keep the raw packet outside Git; only publish licensed, suitably sized summaries.
Both complete and partial receipts keep `physical_gpu_qualified=false` and
`performance_accepted=false`; reviewed physical quality/cost, hosted CI and
issue-specific acceptance remain separate gates. The global default stays OFF.

The host-only tests launch no renderer:

```sh
python -m unittest discover -s tools/renderer_oracle/tests -p 'test_sdvk008*.py' -v
```

The Linux CI lane additionally runs `--software-fixture-control` with explicit
`--correctness-only`, the exact hosted renderer commit, a retained license and
one identified CPU (type 4) llvmpipe ICD. This separate smoke covers only
default-OFF, heightless, medium single-card direction/effect and binary-alpha
background-mask pairs, twice at 640×480. It collects no timing or high-resolution
physical variant state. Its distinct `sdvk008-software-fixture-control.json`
reports `software_vulkan_evidence_collected=true` only after success; every
physical evidence/qualification/performance flag stays false. CI retains the
full raw attempts beside the inherited software-Vulkan packet. This can expose
content grammar or image-oracle defects while a physical session is stopped;
it cannot substitute for #8's physical quality/cost programme.
