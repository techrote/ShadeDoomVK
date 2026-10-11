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

The frozen SDVK-008 renderer does not emit an ordinary immediate-scene GPU
timestamp span. Its CPU and available postprocess GPU distributions remain
descriptive; they cannot establish sprite POM scene cost. `timing_analysis`
reports `INCONCLUSIVE_GPU_SCENE_SCOPE` unless every one of the 11×3 processes
retains exactly 120 raw `scene.immediate` samples and complete retained GPU
groups. An absent or incomplete span never becomes a zero-cost or acceptance
claim. The separately proposed instrumentation candidate in PR #140 requires
a new preregistered renderer/build identity and fresh qualification; it cannot
silently replace the frozen implementation used by this driver.
