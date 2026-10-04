# PF-020 bounded view, sprite and native key evidence

Status: **PREPARATION ONLY / NATIVE ACCEPTANCE PENDING**, 2026-10-04.
This protocol fills the missing applicable PF-006/PF-009/PF-010 evidence in
[the freeze matrix](PF-FREEZE-EVIDENCE-MATRIX.md). It does not accept PF-020,
unblock SDVK-001, qualify P400, or change the [equivalence contract](PF-EQUIVALENCE-PROTOCOL.md).

## Source and baseline identity

`tools/pf_oracle/derive_freeze_view_baseline.py` reads exact Git objects from one
full pinned freeze commit. It produces two disposable source exports under the
sole repository's ignored `build` directory; neither is another Git checkout or
an instruction source. `current` contains the frozen current source.
`original-seams` reverses all22 exact historical PF-006/PF-009/PF-010 hunks and
removes their three introduced headers. Full hunk identities, historical
before/after blob identities, unique matches, reverse roundtrips and complete
export closures must pass. No fuzzy/context-only application is permitted.

This is a **source-derived diagnostic baseline**, not an unchanged historical
binary or a founding performance baseline. Both variants retain later accepted
material, probe, CFX lifetime, shadow/query and sprite-sentinel repairs. In
particular PF-014's initialized ceiling sentinel is preserved. Only the
qualified three original seams differ; identical observer additions remain in
both. `PF020_ORIGINAL_SEAMS=ON` is private to the real `zengine` compilation
target and rejects the current tree while any of the three current headers exists.
Legacy observations mark unavailable production context/surface/named-key
metadata explicitly; they do not construct replacement production objects.

Fresh VS2022 x64 RelWithDebInfo builds and stages require frozen clean Git state,
unchanged exported bytes through configure/compile, compiler/log identities,
EXE/PDB/package hashes and all build/stage counterparts. Old Dense and accepted
repair build/stage directories remain sealed. Failed attempts are retained.

## Healthy authored input

`tools/pf_oracle/prepare_freeze_view_fixture.py` authors the PFVTEST map and
minimal fixture actors from reviewed source, references verified stock Doom2
assets, and copies no IWAD assets. Its manifest pins authored ZIP members,
stock-directory identities and relevant engine source. Regenerate into a fresh
directory after the final observer/hook commit; the earlier v1 preparation
retains earlier source identities and is not final-build qualification.

Required actual runtime witnesses are main view; reciprocal linked line portal;
nested linked-to-mirror traversal; visible PFVCAM camera texture with a producer
update requested after its first initialization; all six naturally produced
probe faces; and representative rotating/frame-mirrored, face/wall/flat,
explicit X/Y flip and interpolated sprites. Authored placement is an **intent**,
not a claim that any route was reached. The line portal must report its runtime
type, reciprocal backlink, endpoint indices/groups and displacement; a silently
downgraded visual/teleport portal does not satisfy the linked witness.

The fixture also binds PFVUSR to a source-pinned identity user shader, using the
current default SetupMaterial body and a verified stock STARTAN3 reference.
Explicit `gl_customshader=true` and an actual production user-shader key/draw
are required. Authored GLDEFS alone does not establish execution; classification
uses the emitted FIRST_USER_SHADER and NUM_BUILTIN_SHADERS constants.

Use fixed declared camera/time/content/seed/quality and identical settings in a
pair: ordinary BSP, immediate specialized rendering, nearest filtering, no
shadows, fixed resolution/render scale and identical portal/mirror recursion.
The separately explicit `-pf020viewfraction 0.5` sets only fixture visual actor
interpolation for main/camera roots without changing simulation values;
probe roots retain their actual inherited fraction. The separate explicit
`-pf020viewclock single-tic` correctness fixture uses the engine's existing
`singletics`/`D_SingleTick` path: one complete game tic per displayed frame,
including synchronous `NetUpdate` behavior. Arm only after actual PFVTEST
loads, before its first tic, with fresh diagnostics/fraction and no preexisting
single-tic, network or demo mode. Normal adaptive scheduling stays the default.
Changing the fixture map or synchronous mode fails closed. Retain actual
activation/end tics and the real `singletics` flag; compare clock lifetimes and
every observed tic exactly. This changes fixture pacing and supplies no
wall-clock or performance acceptance. Observe actor previous,
current and interpolated positions/angles plus the effective emitted sprite
angles to verify that premise. A separate controlled Uber=true variant is needed
for the actual generalized/library maps when the tested adapter supports them;
unsupported or unexecuted routes remain explicit limitations.

## Actual scene and GPU observations

The runner requests `+map PFVTEST` through the actual early autostart interface;
the delayed command script cannot substitute a startup `map` command. Explicit
observer/cache arguments and the dump command use the same console-safe forward
slash path representation. A fresh `+logfile` captures startup capability output,
including PRINT_LOG lines that ordinary stdout omits. All requested CVars require
one exact actual query. The six source-verified built-ins with flags0 must be
absent from the normal-exit INI; archived settings must retain their exact values.
Neither omission nor the authored INI substitutes for the actual query.

First core attempt01 used the frozen41c63 builds and exited0 on the GTX, but its
PNG showed the title sequence, frontend scene/sprite counts were zero and the
Vulkan dump rejected unequal argv/console prefix strings. It is retained as
failed launcher qualification, with no view/image acceptance. Corrected retries
use fresh output/cache directories and reauthenticate every frozen build input.
The clean committed tool revision is pinned separately from the frozen engine
head. A later tool/docs revision can reuse those builds only when every runtime
source and build counterpart still matches the authenticated frozen export.

Core attempt02 uses clean tool head1be5127 and the same frozen engine builds03.
Its first unelevated GTX child reaches PFVTEST, produces both camera captures,
all six probe faces and the main screenshot, and exits0. Core validation reports
zero errors/warnings; actual startup reports pipeline-library support. The
packet nevertheless **FAILS** strict frontend JSON decoding: `AActor::frame`
is a byte and direct stream insertion emits a raw NUL for frame0. No later child
was launched. Original outputs remain immutable; diagnostic in-memory recovery
is not acceptance. The observer now emits the frame as an unsigned number,
guarded using the actual byte type and control/quote/high-byte boundaries in
both compiled source variants. This engine edit needs fresh exports/builds and
a fresh native packet.

Native key parsing preserves source-defined `EFF_NONE=-1` only for SpecialEffect.
Other scalar/layout fields remain nonnegative. Shader binary cache identity is
the complete production `<ShaderType>-<SHA1>-<final-source-size>` string, with
the six source-defined shader types, lowercase40-hex SHA1 and canonical decimal
size. Missing/malformed components fail; a bare SHA1 cannot replace the key.

`-pf020viewobserve <fresh-prefix>` enables bounded frontend records only on
actual PFVTEST roots. Record actual root/eye/face, parent/depth/parity, published
production context where present, viewpoint index/group/fraction, live view and
projection matrices, camera uniform and completed postprocess routes. Observe
actual four emitted sprite vertices in world XYZ plus UV, frame/texture/style/
translation, actor endpoints and current presentation metadata where present.
`FFlatVertex`'s memory ordering is not a different world-coordinate convention.

`pf020view_begin <phase>` preserves startup rows and cumulative counters;
deduplication includes phase. One-time probe production must not be lost when
warm collection begins. It must not be manufactured by resetting or rerendering
production probes. Completed image keys preserve invocation IDs; key aggregation
uses the stable semantic view projection. Worker key events have an explicit
worker marker and null scene, without unsynchronized frontend state access.

Each captured producer also carries its own bounded `completedView` snapshot,
taken before its actual scene stack pop. Compare its actual tic, fraction,
position, angles, matrices and camera uniform exactly. First semantic rows can
belong to an earlier invocation and cannot substitute for this capture-time
state. Only invocation tokens and explicitly unavailable legacy production
metadata are excluded from semantic comparison.

The existing Vulkan screenshot path uses the retained previous frame through
its ordinary screenshot presentation pass and RGB conversion, including its
capture-time presentation settings. It is not a direct swapchain readback.
Immediately after this production `GetScreenshotBuffer` readback, the observer
retains its RGB bytes and completed main-view snapshot as `mainPresentation`.
Independent PNG decoding must match those exact bytes; paired presentation
snapshots must also match. No diagnostic substitute scene is rendered.

Camera/probe producers lack TRANSFER_SRC usage. The Vulkan observer must sample
their actual completed images through a private 2D per-layer view and same-format
texelFetch pass, then copy only its private transfer-capable target. Record
actual producer/view/layer/mip/format/extent, barriers, normal completion fence,
mapped-memory invalidation and restoration. No production source copy, alternate
producer render, reduced resolution, format conversion or quality change is
allowed. Keep startup raw failures and images. Core and synchronization validation
must exercise this new API/resource path separately before claiming correctness.

`pf020vk_dump <launch-prefix>` precedes `pf020view_dump`; normal process exit then
supplies completed cache shutdown events. Observer JSON deliberately remains
pending/state-only until independently validated. It is not a passing freeze
receipt. Both diagnostic translation units disable fast-math so nonfinite-data
guards cannot be optimized away.

## Native cache/key and comparison gates

Require explicit `-pf020viewcache <project-build-child>` to isolate both actual
shader and pipeline disk caches. A fresh cold process must prove both files
absent; its normal shutdown must record completed saves. A new warm process
reuses only that variant's exact two files, with independent before/after SHA256
and actual successful load/entry/lookup records. Never delete or borrow the
ordinary shared cache. Cache paths, source/build, adapter/capability and process
identities remain part of qualification.
"Cold" here names those two application cache files. The opaque driver-global
cache is untouched and is not claimed cold. Private sampling pipelines do not
use the production pipeline cache.

The recorder observes actual production shader, specialized/generalized pipeline,
render-pass and supported library map lookup arguments/results. Compare named
semantic fields and partition identities between variants, rather than treating
raw padding, addresses, scheduling-dependent lookup counts or invocation IDs as
renderer meaning. Cold/warm behavior needs actual file/load/hit evidence; a
shadow cache model is insufficient. Zero observed generalized records cannot be
reported as generalized parity.

Compare a separate nonempty set of every complete actual shader-binary cache
key, including null-scene and worker records. Lookup precedes the cache-hit
return, so access counts, hit outcomes, thread and scene association are not
binary identity. Identical source requests in these frozen current/original
pairs must produce identical key sets; any missing/additional key fails rather
than being dismissed as scheduling. This gate supplements meaningful native
shader/pipeline partitions and does not replace them.

Before native execution, register the exact runner, fresh output paths, ordered
cold/warm variants, input hashes, settings, watchdogs and expected positive
witnesses. Each child is serial and exits normally. Compiler/check/profiling work
must not compete with its measured windows. Every paired image needs corresponding
state, complete source/build/content/device identities and independent decoding.
For these fixed healthy paths the initial image gate is exact equality of decoded
same-format components/RGB pixels; retain any mismatch without widening tolerance,
discarding an outlier or relabeling a missing capture. Intended structural context
IDs and legacy unavailable metadata must be explicitly mapped to the same actual
semantic view. This packet measures correctness/equivalence, not GPU performance.

Core attempt03 uses clean tool4997491 and both repaired0791911 builds04.
The first child passes strict scene/key/private-image/main RGB validation and
reports zero core validation findings, then fails cache-event path comparison:
the observer retains the forward-slash launch prefix while Windows `str(Path)`
uses backslashes. Its normal-exit event file exists with six ordered load/save
records. The packet remains failed and unchanged, with no later child launched.
The corrected tool uses the same exact-private-path, no-link, positive-size and
byte-bound artifact guard as sampled images, and pins the event file. Cache
lifecycle, independent file hashes, actual warm loads/hits and all prior source,
device/state/image gates remain mandatory. Retry only in a new registered packet.

## Current verification boundary

Core attempt04 uses clean toolc6643 and both0791911 builds04. All four actual
unelevated children validate independently, including strict native observations,
private images/main RGB, zero core findings and isolated cold/warm cache loads
and hits. The overall packet nevertheless **FAILS** paired scene state: eleven
first warmup scene/restoration rows carry tic386 versus385 in the cold pair.
All other semantic fields, actual completed capture states, eight camera/probe
images, main RGB and all37 production binary keys match in both pairs; the warm
subset compares exactly. None of these partial findings relabels packet04.
Adaptive `TryRunTics` can execute multiple `G_Ticker` calls after the delayed
phase command and before `D_Display`; FPS caps still permit catch-up batches.
The explicit one-tic fixture revision requires fresh exports/builds/inputs and
a new packet. No tic is normalized, dropped or tolerated.

CPU source-derivation, fixture-authoring and actual production observer-TU guard
tests establish bounded preparation. They do not prove native ZScript compilation,
linked traversal, camera demand, six-face production, cache reuse, API validity,
pixel parity, or full-engine build success. Those gates remain pending until fresh
native receipts exist. The separate ordinary Dense CPU concern requires its own
recorded profiling and aggregate disposition; this observer does not explain it.
