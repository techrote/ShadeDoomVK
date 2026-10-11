# SDVK-008 physical tooling checkpoint — 11 October 2026

Status: **IMPLEMENTED TOOLS / HOST TESTED / NATIVE CONTROL PENDING / PHYSICAL BLOCKED**.
This checkpoint grants no SDVK-008 acceptance and changes no renderer default.

The physical renderer remains pinned to implementation merge
`9536324ce33ea418af5a8efe733b4659f6b4ad9b`, tree
`3123bc7fd3dd9074487cbe3487f9336ef3589003`. New fixture/tooling sources are
separately hashed in each packet. No production renderer/shader source is
changed. The SDVK-009 campaign and source identity remain independent.

The separate native Windows RelWithDebInfo frozen build passed both executable
identity checks; [build-only manifest](evidence/sdvk008-build-20261011.json) pins
the executable/packages, toolchain and host. Its scene rendering was not launched.

`tools/renderer_oracle/sdvk008_physical.py` reuses `run.py` preparation, capture,
integrity validation, exact repeat comparison and raw distribution summaries.
It requires explicit execution, fresh output, authenticated Vulkan inventory,
exact clean executable commit, and stable executable/engine/IWAD hashes before
each renderer launch. Runtime Vulkan name/vendor/device/type and all repeated
build/content/settings/host identities must agree. It never retries a failure.

The finite recipes implement single-card LOW/MEDIUM/HIGH, overlapping cards,
mixed grazing cards and PBR+normal+height, each with matched OFF controls; all
eleven variants retain the original three orders and 120+120 frame budgets.
Additional correctness controls cover implicit/explicit OFF, heightless paths,
binary-alpha background masks, hard grazing fallback and independent actor
X/Y flips. RGB effect, preregistered marker direction, emitted signed-UV state
and alpha masks are distinct witnesses. Read ceilings remain theoretical.

Full physical mode fails **before rendering** while required fixture gates are
missing. Explicit `--correctness-only` can collect the available bounded subset
without timing. Remaining gates include frame/portal direction/parity, native
invalid-height/view cases, general grazing/distance bounds, atlas/filter
footprints and normal/specular/PBR UV coherence. Implemented oracles are not
successful physical evidence; their real captures may expose defects.

The local physical session was stopped by the programme owner after an SDVK-009
GPU fault. This SDVK-008 tooling lane launched **no local GPU process**. Further
physical launches remain stopped pending the host/device investigation.

The separate hosted `--software-fixture-control` smoke requires one CPU type-4
llvmpipe device, an explicit exact hosted build commit and the IWAD license. It
collects two independent 640×480 captures for default-OFF, heightless, medium
effect/direction and alpha-background pairs. Actual failed state/images are
retained and fail CI; the expected direction and image policy are not adapted to
the result. No high-resolution physical workload or timing is collected in this
mode. Its distinct receipt and full checksum inventory keep all physical
evidence/qualification/performance flags false.

Statistical tooling enforces exact retained sample limits, type-7 percentiles,
paired ON−OFF milliseconds and ratios, both process-median MADs, the >5% OFF
variability gate and strict `max(0.05 ms, 2 × OFF MAD)` detection rule. Named GPU
groups are evaluated separately, never summed into a fabricated frame duration.
Below-detection effects are not zero-cost claims. All outcomes still require
reviewed quality/cost acceptance. SDVK-016 retains tiers/default ownership; #8
stays OPEN and SDVK-012 remains blocked.

Local host-test results and exact commits belong in the final PR receipt. Hosted
native control, hosted CI and physical results are not claimed by this document.

The first hosted software control at renderer commit
`b4dff1fcb07044bc4b41d7f427bf62b84c6d9138` failed its first
`sdvk008-alpha-background` pose assertion: the old recipe expected authored yaw
27 degrees, while the emitted view was `26.999999983236194`. The failed packet
remains retained under
`C:/ShadeDoomVK/physical-evidence/20261011/hosted008-first-failure/renderer-sdvk008-control/state/640x480/sdvk008-alpha-background/1`.
Its `run.json` remains **FAIL**, SHA-256
`aa7de0eaafafa078d4cfeebb340bb243f0f63ce0983c77a0db3325d96bee1f0d`;
`recipe.json` SHA-256 is
`00180f2c9117bb10e182ecb7c2d2f638555bd34053d3abc0aece55c293328a92`,
and `native.renderer.json` SHA-256 is
`f427397adb77b8df0dab3ad647c114bad1e26de2da3093e50785b82fc104f01d`.
The llvmpipe type-4 observation is software evidence only and receives no
physical qualification or performance status.

Fixture revision `sdvk008-camera-bam-v2` separates integer
`native.authored_camera_angles` from `native.camera` expected observed angles.
The source path is UDMF `CheckInt`/short angle authoring, actor
`DAngle::fromDeg(mthing->angle)`, then `R_InterpolateView` normalizing each view
angle via `TAngle::Normalized180` in `vectors.h`. Its `BAMs` uses
`xs_CRoundToInt` (nearest, ties even), followed by signed BAM times
`90 / 0x40000000`; it is not a general floor conversion. Thus 27 maps to
`26.999999983236194`, and 87 maps to `87.00000001117587`. A CPU fixture compiles
the production header and checks all integer angles from -180 through 180
against the canonical recipe conversion. Catalog preparation rejects any
expected pose that differs from that conversion. The existing pose tolerance
and renderer source remain unchanged.

All 25 authored SDVK-008 PK3 hashes remain identical to the preceding tooling
revision, including all eight PK3s retained by the failed hosted control. The
alpha-background package remains SHA-256
`b9fc66c4628e732fd2e18e2859cdde4046d4796d9e09c5204dffa53dffe624f2`.
UDMF yaw remains exactly 27 or 87 as originally authored. Recipe/source hashes
change, so a fresh preparation and new control packet are required; the failed
packet is neither rewritten nor reclassified. This correction establishes
expected pose semantics, not successful native rendering or visual gates.
Local CPU validation with MSVC 14.44.35207 passes all 130 renderer-oracle tests,
including the compiled production-angle check and all 25 unchanged package
identities. No renderer/GPU process was launched for this correction.

Image oracle revision `sdvk008-image-oracle-v2-alpha-active` strengthens the
alpha fixture gate before fresh hosted results are inspected. The production
`material.glsl` samples relieved RGB while retaining `baseTexel.a`, and uses the
original texel when the relieved alpha fails its threshold. Therefore the alpha
OFF/ON control must retain a nonempty, exactly equal binary RGB-versus-background
mask **and** exhibit at least one changed RGB pixel in that same fixture. An
identical OFF/ON image now fails, even when the separate opaque SM fixture shows
an effect. This avoids vacuous preservation from an entirely inactive or
fallback alpha path. The receipt and each image witness identify this oracle
revision. CPU tests retain unchanged-ON failure, interior color-shift success,
silhouette escape failure and missing-sprite failure. The authored packages,
poses, image tolerance and direction algorithm are unchanged; previous packets
retain their original identities and outcomes.
All 34 targeted SDVK-008 physical-driver CPU tests pass for this revision; no
renderer or GPU process was launched.

The red-marker check remains a finite aggregate centroid direction witness.
Its preregistered right/up sign follows the final wall-card tangent, V-down
bitangent and `original - depth * ray` sampling. It does not match individual
pixels: marker reshaping or deletion can also move the centroid, including
retaining only the top-right portion of a stationary marker. A passing centroid
is neither pixel-correspondence proof nor general UV correctness, depth,
usefulness, mirror/portal parity or PBR coherence. Those broader gates remain
unqualified; this audit does not adapt the expected sign to rendered results.

The next hosted control, workflow `38102402396` at submitted head `95404ea8`,
retained two completed alpha-background captures and failed
`sdvk008-alpha-off/1` with `Required material semantic bindings differ:
SDVEA0`. Its emitted renderer identity is
`44f7b52280315889321788ab74f48c9f02bcfeab`; native observation SHA-256 is
`4457fef11ee2633424d98294ded1c78f46841202e65cb16216b640244132d6a2`.
The renderer exited successfully, but the run remains an oracle **FAIL**.
The original 80-file control archive remains retained separately, ZIP SHA-256
`7eabb8a61afbd0e08456ac368a350e35bc2c5ffea017fd5c13677e2b2e97cab5`.
An unmodified copy of its SDVEA0 material record is retained as a CPU negative
fixture; it reproduces the old semantic assertion failure. No old packet is
rewritten or awarded acceptance.

Material assertion revision `sdvk008-material-bindings-v3` corrects the recipe
to require the authored height binding even while relief is OFF. The binding
order follows `FMaterial` in `hw_material.cpp`: authored base/normal/PBR prefix,
three fixed fallback slots (brightmap, detail, glow), then appended height.
Height is not part of the contiguous authored prefix. Every required material
now has an exact total layer count, positive authored texture extent and explicit
requested and actual sampler checks. The existing generic semantic validator
still requires ordered 1×1 lump-zero fallback placeholders; it is not relaxed.

| Fixture material | Authored prefix | Height binding | Total layers |
| --- | --- | --- | --- |
| Plain height-bearing SDVEA0 | albedo | 4 | 5 |
| PBR SDVEA0 | albedo, normal, metallic, roughness, AO | 8 | 9 |
| Heightless SDVEA0 | albedo | absent | 4 |
| Mirror SDVRA1 | albedo, normal, legacy specular | 6 | 7 |
| Other mirror SDVR frames | albedo, normal, legacy specular | absent | 6 |
| Mirror SDVPA0 | albedo, normal, metallic, roughness, AO | absent | 8 |
| Mirror SDVLA0 | albedo | absent | 4 |
| No-card background SDVW/SDVFL | albedo | absent | 4 |

Generated SDVE channels and every relief height channel must be 128×128.
Inherited mirror albedos remain 64×64 and their non-height material channels
16×16; background channels remain 16×16. All albedos request default sampling
(-1) with actual nearest min/mag/mipmap (0/0/0), because the recipe selects
`gl_texture_filter=0`. Height, the generated PBR channels and SDVRA1's explicitly
linear normal request 1 and require actual linear min/mag/mipmap (1/1/1), as
selected by `VkSamplerManager`'s `LinearMipLinear` override. Other inherited
mirror channels retain their authored default/nearest policy. Source lump
ordinals are not pinned across package loads; positive authored lump identity,
exact dimensions, semantic roles, package hashes and sampler state are checked.

CPU regressions apply the corrected assertions to the retained material record,
derive all 25 recipe layouts independently from their actual GLDEFS/PNG member
bytes, and reject missing height/fallback/PBR channels, wrong binding/index,
placeholder substitutions, wrong extent, wrong filter and removed recipe
requirements. Heightless and unmapped mirror controls continue to reject height.
All 25 original PK3 identities remain required by the existing golden-byte test.
The new recipe/source hashes require a fresh prepared packet. Authored content,
camera, oracle image thresholds and renderer source are unchanged; fresh native
and physical qualification remain outstanding.
Local validation passes all 147 renderer-oracle CPU tests, including the MSVC
production-angle fixture and unchanged-package checks. The retained alpha-off
observation and both completed background observations also satisfy the new
scene assertions in an offline check; their original receipts remain unchanged.

The frozen SDVK-008 renderer does not emit an ordinary immediate-scene GPU
timestamp span. Its CPU and available postprocess GPU distributions remain
descriptive; they cannot establish sprite POM scene cost. `timing_analysis`
reports `INCONCLUSIVE_GPU_SCENE_SCOPE` unless every one of the 11×3 processes
retains `scene.immediate` exactly once in each consecutive raw frame 1..120 and
complete retained GPU groups. Each timing capture authenticates the retained
native observation before the next launch; unresolved batches, duplicate frames
and incomplete named groups fail with the packet retained. Raw-coverage metadata
is carried into analysis; a 120-element summary alone cannot establish scope.
An absent scene span never becomes a zero-cost or acceptance
claim. The separately proposed instrumentation candidate in PR #140 requires
a new preregistered renderer/build identity and fresh qualification; it cannot
silently replace the frozen implementation used by this driver.

The post-review harness rejects retained `[vulkan error]`, validation-error,
device-fault/device-lost and existing startup/observer failure markers from
either stdout or stderr, including otherwise successful completion. Failed logs
and receipts remain archived, with no retry. Retained-packet validation repeats
the same check. SDVK-008 also converts the preflight driver version to its raw
uint32 representation and requires the renderer's `driver_version_raw` to agree
on the first process and every subsequent process. Missing or unsupported driver
versions fail closed. The decimal/hex raw, NVIDIA, Intel Windows and standard
Vulkan formatted encodings follow the
[vulkaninfo display formats](https://github.com/KhronosGroup/Vulkan-Tools/blob/main/vulkaninfo/vulkaninfo.h#L1934).
These tool-only guards do not revise any previously sealed physical packet.

Packet inventory generation and verification exclude only the root
`checksums.json`, whose bytes cannot hash themselves. Nested files with the
same name remain authenticated artifacts; changing or adding one fails the
packet check. The regression uses temporary files on the CPU and launches no
renderer. This integrity correction grants no physical or performance status.

The subsequent hosted run `38104689836`, submitted head
`01e75260820659f746417eef0503c9ba8d3c174c`, failed the first independent
`sdvk008-alpha-background` repeat. Both processes completed with exact identical
640×480 RGB images, but protected resource generations and the texture epoch
were 3 versus 4. The strict comparison correctly remains **FAIL**; image equality
does not excuse this protected-state difference. Native full-corpus collection
was not launched because the earlier controls failed. All eight other full-CI
jobs and source-evidence run `38104689838` passed; the full workflow failed.
The new packet is retained separately and its complete control checksum
inventory passes. Its lossless archive SHA-256 is
`f1f15ce80534f18b1c3bc4317a2d9b6a0c163dde823929cf71ae028e977ca1af`.
See [the bounded failure receipt](evidence/sdvk008-software-repeat-failure-20261011.json).
No generation/epoch normalization, image tolerance change, retry or acceptance
is authorized by this observation. Source/bootstrap investigation is pending.
