# R-001 implementation: routine, targeted and deep verification

**Status: proposed implementation / Draft / HOLD.** This branch can qualify its
own changed workflows. Master policy changes only after explicit owner approval,
successful applicable checks, independent review and a verified merge. Physical
GPU STOP remains active. No historical issue is closed by this implementation.

## What changes

The regular `Continuous Integration` workflow retains the CPU oracle and all
seven ordinary platform builds. Its eighth configuration, Linux software Vulkan,
becomes one exact-source native build with separately selected parallel consumers. It replaces the unconditional full native
publication campaign with a small hosted software-Vulkan capture set and
change-triggered safety suites. The original complete workflow is preserved in
`renderer_deep.yml`, invoked explicitly through `workflow_dispatch`.

No legacy oracle, publication proof, old failed observation, renderer source,
fixture frame budget, or physical-GPU guard is altered. The new routine result
has its own schema and explicitly does **not** award legacy campaign acceptance.

## Gate matrix

| Lane / trigger | Actual work | Claim |
| --- | --- | --- |
| A: every PR | Existing CPU contract suite; tested routing; exact-source builds and runtime identity for all eight compiler configurations | Source/build and CPU correctness |
| A: renderer, tools or executable inputs | Four single-process authored captures: compositing, zero-light, one-light, ordinary gameplay | Native admission, real OFF/ON light response, movement/fire/map-resource checks; no cross-process counter equality |
| B: sprite/actor/gameplay | Sprite-mirror capture and original `sdvk010_acceptance` | Rotation/mirroring, actor sunlight/probe compatibility |
| B: material/texture/shader | Material-stress capture; original probe-owner and live sampler-reset suites | Semantic material sampling and resource lifetime |
| B: descriptors/probes/resource owners | Original `sdvk150_probe_owner` and `sdvk153_probe_reset` | Stale owner/reset regressions |
| B: lightmap/LevelMesh/atlas | Original 158, 161 and 014 controlled-plane suites plus resource suites | Retained freshness, special surfaces, current plane ownership |
| B: portals/mirrors | Sprite-mirror capture, actor/portal acceptance and original 161 special-surfaces suite | Current recursion/actor and special-surface compatibility |
| B: light-query/shadow-selection | Shadow-boundary capture and actor suites | Capacity, eligibility and actor-light compatibility |
| B: workflow/selector | Routine, actor and resource suites | Exercise the changed executor and an escalated source-matched lane |
| B: new/unclassified executable paths, shared build inputs or empty change information | All targeted groups | Conservative escalation, never a silent docs-only result |
| C: explicit deep dispatch | Original full corpus, timing, collision replay, 008, 010, 150, 153, 158, 161, 014 and 009 publication | Original full contracts, independently reported |

Documentation-only changes still run CPU and ordinary compiler checks. The stable
software-Vulkan summary explicitly reports `NOT_APPLICABLE` and skips native build
and rendering. It never claims it rendered those changes.

Paths are read from the authenticated event base/head through `git diff
--no-renames`: both names of a rename remain visible, including deletions.
The checkout must equal the event's full source SHA. Missing commits, malformed
input or an unknown event fail the CPU check. No label or PR body can disable a
gate. `build/ci-routing.json` exposes every path and selected reason. Risk matches accumulate, so a sprite-portal or material-lightmap file receives
both groups. An unknown path receives all targeted groups; empty input is conservative rather than PASS.

## Visual and gameplay scope

`tools/ci/routine_native.py` reuses the existing isolated llvmpipe guard,
preflight, content preparation, capture and per-scene validators. The ordinary
gameplay fixture keeps its original 128 observed / 32 warmup frames and nine
completed-view images. Every capture requires the exact built commit and clean
source identity. Shader compilation and actual Vulkan submission occur in the
native processes. A failed process or invalid native packet fails the lane.

Routine captures do not compare two independent internal event histories. Their
single-process resource and semantic checks remain strict. The zero/one-light
pair additionally rejects a missing light effect: at least 64 pixels must differ
by at least four RGB levels in one channel, in the same 640×480 authored view.
This deliberately coarse test detects disabled lighting; it is not a beauty
score, a shadow acceptance test, or an exact-image claim. Negative tests reject
identical images, small uniform noise, one-pixel changes and extent mismatch.
Feature-specific OFF/ON and temporal evidence belongs beside the affected
feature's tests; SHADOW-001 supplies its own projected-shadow demonstration.

## Required check identities and adoption

The live branch API was inspected on 15 November 2026 at
`f787f7199fc7560588bb9440b3dd0aa663cb53de`: `protected=false`, status enforcement
`off`, empty `contexts`/`checks`; the rulesets API returned an empty array. Direct
branch-protection administration returned HTTP 403 for this integration. These
observations are not permission to waive the repository's own required checks.

All nine established regular check names remain:

- `PF renderer contract oracle`
- `Visual Studio 2022 | RelWithDebInfo`
- `Visual Studio 2022 | Debug`
- `macOS | Release`
- `macOS | Debug`
- `Linux GCC 12 | RelWithDebInfo`
- `Linux Clang 11 | Debug`
- `Linux Clang 15 | Release`
- `Linux software Vulkan | RelWithDebInfo`

The software check's future scope changes explicitly to Lane A plus applicable
Lane B. It does not disappear or impersonate a completed Lane C campaign. Manual deep check names carry a `Deep |` prefix so they cannot
impersonate a regular required status.
Required identities are covered by a CPU regression. If server rules change
before integration, re-read them; do not silently migrate or delete statuses.

## Existing CI work examined

| PR / source | Reuse decision |
| --- | --- |
| #187 / `194c8fe740782817174dc90472fe6df5bfd8cb3b` | Reimplement the simple fast lossless XZ idea and expose separate native suite steps; do not import its repeated full-measurement campaign |
| #196 / `da017d82d74d4681164c0aac8b031bdeea0543a7` | Preserve its stable-name and source-matching principles; no cross-worker runtime transport needed |
| #197 / `3d09f5f7313930a4c3181ae4da87fefb09b4bc49` | A/B experiment only; no source changes imported |
| #198 / `0b6a623799f4ba0e6dddf21c450598528c852df7` | A/B experiment only; no source changes imported |
| #201 / `9b465d1ce1c73050d6a0b52cd51f592e5523b2ad` | Five-worker publication design not imported; failed full acceptance remains failed |

No external donor code is imported. The workflow extraction starts from current
master. Historical #201 run `43549214686` remains FAIL: SDVK-161's frame-37 wall
submission/empty-upload discrepancy is unexplained. Identical final RGB does
not prove either source-side observation was correct. Its absence from an
unrelated routine sprite PR is a declared applicability change, not a fix.
Changes touching its lightmap/LevelMesh domain still select the unchanged gate.

## Evidence and duration

Routine and targeted software evidence retains the existing
`renderer-software-vulkan` artifact and `.tar.xz` format. Compression is lossless
XZ `-1 -T0`, with stream integrity and a SHA-256 sidecar. Successful routine
artifacts retain seven days; failed evidence retains 30 days. Deep evidence
retains 30 days. Raw failing native output remains included, with no retry or
status conversion. Packaging failure itself fails the job.

The separate existing source-history bundle retains its format and full history;
its checkout now matches the same exact PR head as the runtime. Its artifact
size is not included in any claimed renderer-only budget. The initial 50 MiB
routine evidence budget and 10–20 minute duration are targets awaiting the first
source-matched hosted result. No successful duration, speedup or total artifact
reduction is claimed from local CPU tests or incomplete runs.

## Qualification and owner decision

Local command:

```sh
python3 -m unittest discover -s tools/ci -p 'test_*.py' -v
python3 tools/check.py --output build/r001-cpu
```

One normal PR run qualifies the proposed routing, builds, routine capture and
selected actor/resource escalation. Do not dispatch the full deep campaign just
to prove it exists: CPU workflow-contract checks preserve its invocable recipe;
its native result remains `NOT_RUN` until explicitly requested. An independently
reviewed owner merge and verified master SHA are still required for adoption.

The owner has separately authorized SHADOW-001 M1 implementation in parallel
with this Draft migration. That permits source work and bounded software
qualification; it grants neither policy adoption on master nor a physical test.

## Parallel native fanout — implementation revision, 15 November 2026

The exact source/base route now runs separately from the CPU oracle. All seven
ordinary platform compiler jobs start immediately, while one hosted Ubuntu 24.04
native build begins after the short route, only when native work is applicable.
The runtime is packaged once with SHA-256, commit and tree identities; all
independent native workers verify those identities and the embedded executable
before running with the isolated llvmpipe ICD. No native worker recompiles.

The route selects just the applicable suites: `routine`, `actors`, `resources`,
`lightmaps` and `surfaces`. Materials additionally select the original routine
material-stress capture and the resources suite; portal changes select surfaces.
Unclassified executable changes select all suites. Each suite runs the original
native oracle programs and publishes unfiltered lossless success/failure evidence.
Missing, failed or skipped applicable suites cause the stable `Linux software
Vulkan | RelWithDebInfo` aggregate to FAIL. On all-green runs, it verifies each
suite checksum and receipt and recreates the established
`renderer-software-vulkan.tar.xz` evidence format. Individual failed-suite
artifacts remain retrievable if aggregation does not run.

The historical full publication, negative controls and image comparisons remain
preserved as explicitly invoked Deep qualification, not asserted by routine PASS.
This is a topology and applicability optimisation, not validation that physical
flashlight movement is correct. The owner's observed flickering flashlight remains
an unresolved hands-on visual failure irrespective of green hosted CI.

Prior #211 qualifying run took 23m17s, with 18m27s in the native build/test job.
The #213 reference demonstrated working shared-runtime transport and passing
routine/actor workers but a genuine SDVK-150 repeatability failure on its
resources worker. This revision needs its own exact-head measurements and full
qualification before any performance or merge claim.
