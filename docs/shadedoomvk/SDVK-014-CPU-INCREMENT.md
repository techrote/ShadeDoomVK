# SDVK-014 first software increment — atlas and tile retirement

## Disposition

**IMPLEMENTED CPU INCREMENT / COMPLETE SOFTWARE CAMPAIGN NOT ACCEPTED.**
**Cross-map probe lifecycle REBLOCKED by issue #150. Physical performance HELD.**
This is not `SOFTWARE-COMPLETE / PHYSICAL-PERFORMANCE-HELD`: software requirements
also remain outstanding. Issue #14 must stay open. Physical STOP is ACTIVE and
historical physical root cause is UNDETERMINED.

Branch: `sdvk014-lightmapper-probe-robustness`, from audited master
`04a3596115eb397d9e7237aa1ff3625ece1bc5b4`. The [production audit](SDVK-014-PRODUCTION-AUDIT.md)
records the 18 actual ownership paths and complete coverage matrix before fixtures.
The [CPU receipt](evidence/SDVK-014-CPU-INCREMENT.json) pins the tested file bytes;
its audited base is not falsely presented as the eventual publication commit.
Exact PR head, required source/normal CI and any merge verification belong in the
PR/issue publication receipt. They are not predeclared passing by this document.

## Demonstrated defects and bounded repairs

| Defect | Production repair | Independent witness |
| --- | --- | --- |
| Exact page-height rejected, including padded exact-fit request | Validate original positive dimensions before mutation; accept equality in both dimensions | Full-height and padded-full-page real RectPacker allocations; retained original rejects both |
| Invalid/overflowing dimensions mutate atlas owner before failure | Validate dimensions and padding before arithmetic/allocation; overflow-safe shelf threshold | Zero/negative/oversize/INT_MAX controls and before/after page ownership |
| Clear leaves debug occupancy from the previous page set | Clear validation occupancy at the real Clear boundary | Actual VALIDATE_RECTPACKER rebuild fails on retained original and passes after repair |
| Retired tile slot remains a plausible old semantic/atlas producer | FreeTile requires surfaces/item already relinquished and retires the whole slot; unallocated page is -1; pool-wide scheduler/statistics/invalidators exclude retired slots | Shared last-reference release; A/B/C→free B/C→D reuses C ordinal and B+C rectangle; stale B is rejected |
| Saving can serialize retired B with pixels now owned by D | Save validates live allocation against actual packer page/coordinates/extent before readback and serializes only live owners | Independently decoded LIGHTMAP v4 entries, fixed A/D bindings, offsets and literal RGB channel pattern |
| Save RGBA readback overwrites persistent RGB upload input | Use checked-size local RGBA scratch; keep pending RGB input unchanged | Save leaves the original RGB shape/bytes untouched; pre-fix overwrites them |
| std::move into a const-reference upload does not consume old pixels | Clear pending RGB input only after successful CreateLightmap return | Exact BeginFrame publication block: first upload consumed, later changed page count cannot replay it; injected upload failure retains input |

No bake resolution, lighting coefficients, sampler semantics, material binding
order, shaders, probe descriptor publication, portal transforms or viewmodel
policy are changed. The new region check is a consistency check against the
current packer item, **not a durable allocation generation token**. Retaining an
arbitrary stale raw pointer across owner destruction is not qualified.

The upload lifetime review inspected `VkTextureManager::CreateLightmap`: it copies
all RGB source elements into its mapped staging buffer synchronously before return;
the existing transfer deletion list owns that staging buffer afterward. Clearing
the CPU source on successful return therefore does not shorten submitted GPU
buffer lifetime. Failure is not treated as successful publication. This is a
source/CPU conclusion, not a new device-lifetime experiment.

## Executed tests and counterexamples

`python -m unittest tools.pf_oracle.tests.test_sdvk014_atlas_lifecycle tools.pf_oracle.tests.test_sdvk014_tile_lifecycle tools.pf_oracle.tests.test_sdvk014_probe_owner_boundary -v`

The focused suite passes **22 positive case programs**, **15 retained-source
intended rejections**, four independent atlas-receipt mutations and eleven live
region mutations. The eleven include shifted coordinates and a wrong page that
are individually in range but disagree with the actual allocation. Rejections
name the intended reason; nonzero exit alone is not accepted as sensitivity.

The production probe-owner negatives remain **two current failures, explicitly
BLOCKED**, not added to the positive total. Initial owner, unchanged terminal
owner, changed count, direct empty Step and a fresh-owner control distinguish the
failure from a broken capture sink. The complete original functions and original
RectPacker source are hash-pinned, not a hand-written approximation of old logic.

The complete local CPU preflight also passed: 784 PF tests, eight CFX tests, 196
renderer-oracle tests, deterministic corpus preparation, two byte-identical PF
oracle runs and four standalone compiled contracts. The final small region-check
strengthening was additionally covered by the focused suite. Required exact-head
CI remains the final integration gate, not this pre-commit local run.

Reproduce the retained receipt with:

```sh
python tools/pf_oracle/sdvk014_evidence.py --out build/sdvk014/cpu.json
```

Exit 0 here qualifies **only this CPU increment**. The JSON still reports campaign
`BLOCKED_NOT_ACCEPTED`. Add `--require-campaign-complete` to return failure on that
unaccepted campaign. No local command above launches a renderer or creates Vulkan.
The normal CI CPU discovery already runs the new smoke tests; no second full
matrix or benchmark-only Avrea lane is added.

### Resource bounds actually observed

The real allocator completed 128 deterministic clear/rebuild cycles, 12,288
allocations, five high-water pages and 94 high-water item objects, with zero final
pages. Independent occupied-region checks run after allocation, free and reuse.
The real tile pool completed 128 cycles / 256 allocations / 256 retirements with
two retained slots, two free slots, one retained reusable page and 512 recorded
mutation calls. These are bounded CPU ownership counts, not general fragmentation
bounds, GPU memory measurements or physical performance evidence. The receipt
retains descriptive CPU process/compilation wall times; they are not renderer
bake/update costs. Readback channel contents in the serialization test are authored
CPU data, not native captured illumination.

## Foundational stop: issue #150

`hw_entrypoint.cpp` owns one global `LightProbeIncrementalBuilder`; `ClearLevelData`
deletes the level mesh and clears probes but does not reset that builder. Step
tracks count and progress, not owner identity. Its caller excludes empty sets.
After A completes five passes over two probes, both A→B and A→empty→B with two
new probe positions produce, over 32 further frame calls:

```text
old_owner_captures=10 new_owner_captures=0 reset_delta=0 pass_delta=0
BLOCKED new-owner-not-rebuilt
```

This executes exact current Step/Full code and the actual entry condition with
CPU callback sinks. It does not claim observed GPU pixels, descriptor contents or
historical physical fault causality. The defect's introduction commit is unknown;
historical PF-012/PF-113 bounded acceptance is not rewritten. Under the governing
hard stop, cross-map probe reset/rebake/publication acceptance is reblocked by
[issue #150](https://github.com/techrote/ShadeDoomVK/issues/150). No compensating
refresh, weaker oracle, alternate probe system or viewmodel workaround is added.
Unrelated single-map accepted semantics are not automatically revoked.

## Separate adversarial review and remaining requirements

A second source/test review examined release-before-slot-reuse ordering, shared
UseCount, current-item rectangle identity, bounded readback arithmetic, RGB/RGBA
separation, successful-vs-failed upload consumption, and source extraction boundaries.
It strengthened the save guard to reject **plausible in-range wrong page/coordinates**
and changed row address arithmetic to 64-bit. This is an additional review pass,
not a claim of review by an independent person or a second model.

The following remain unresolved/unqualified and prevent software completion:

- #150 owner identity and subsequent live cubemap pair/map reset/republication;
  stale ordinal/pair half/generation/epoch/span admission across those transitions.
- Malformed LIGHTMAP loader read/count/span/duplicate-binding/control-sector
  admission and atomic failure. The save repair does not validate the reader.
- Dynamic-update completion flags cleared during selection before successful
  rendering, buffer-capacity scheduling, all moving lights/sectors/polyobjects,
  and active atlas/probe-map initialization before complete writes.
- Durable tile/region generation protection, native repeated/multi-page transitions,
  and the supported portal/mirror/3D-floor/Line_Horizon/decal/warp/reflection/
  translucency/material/height lifecycle matrix. Unchanged policy is not proof.
- Native repeatable state/captures under the declared policy, required exact-head
  source/normal CI, review/merge and exact-master verification.

`OnMidTex3DHeightChanged` remains the pre-existing explicitly unowned/no-op callback;
no generic FullRefresh is used to conceal that exclusion. Height remains SDVK-005
semantic data rather than new world POM. Unsupported or untested combinations in
the audit remain visible; no full portal/material compatibility result is invented.

## Prospective physical gate — not executable authorization

Physical work requires separate explicit owner authorization **after** applicable
software blockers and correctness gates are satisfied. Before that work, retain
an approved protocol pinning commit/tree, content/settings, actual GPU/driver/host,
bake/update workloads (single/multiple pages, dynamic geometry/lights and reset/
rebake), CPU/GPU timing method, memory/upload counters, repetitions and unchanged
comparison thresholds. Record normal workload cost/scaling and hardware stability
separately from software-Vulkan evidence. Abort on a renderer/device fault, unknown
resource/device identity or a mismatch with the approved protocol; retain the failed
packet and do not retry or intervene in hardware. This increment supplies none of
those missing physical measurements and does not identify the historical fault.


## 15 October continuation — retained-load, completion and page initialization

The same branch now carries a second bounded software hardening slice. It remains
part of the incomplete SDVK-014 campaign and does not cross the #150 probe-owner
hard stop.

- `MapLoader::LoadLightmap` now validates retained LIGHTMAP payload sizing with
  overflow-safe component arithmetic; only live current tiles are candidates;
  non-finite transforms, oversize extents, misaligned/out-of-range pixel spans
  and duplicate current-tile bindings are rejected before current tile state is
  mutated. Invalid retained entries remain on the ordinary current-tile bake path.
- `VkLightmapper::SelectTiles` no longer treats selection as completion.
  `ReceivedNewLight`, `NeedsInitialBake` and `GeometryUpdate` are cleared
  only for tiles that were actually rendered and copied, after the destination
  pages have been transitioned back to shader-readable state. Overflowed or
  otherwise unrendered tiles remain dirty for a later attempt.
- `VkTextureManager::SetLightmapCount` initializes every newly expanded lightmap
  page and probe-map page to their typed zero fallbacks before publishing them as
  shader-readable resources. Unwritten regions therefore cannot expose undefined
  but plausible prior allocation contents.

`tools/pf_oracle/tests/test_sdvk014_retained_lifecycle.py` adds exact executable
pixel-span boundaries and deliberate controls for missing alignment/end checks,
premature dynamic completion, missing post-copy completion, missing probe-page
initialization and admission-before-mutation ordering. These tests are candidates
for exact-head CI qualification; this text does **not** predeclare their CI result.

The earlier “remaining requirements” list above is therefore superseded for the
three items just described. Outstanding software scope still includes #150 and
its cross-map probe pair/epoch publication boundary, durable stale allocation
identity review, native repeated/multi-page transitions, supported special-
surface/material lifecycle coverage, exact-head CI/review/merge and exact-master
verification. Physical GPU bake/update cost, scaling and stability remain held.


### Retained control-sector namespace

Continuation review found that retained `ControlSector` values are serialized from
`sector_t::Index()`, while loader admission still bounded them against the
subsector table. Admission now uses `level.sectors.Size()`. A deliberate source
mutation restores the old subsector-count check and must be rejected by the
retained-lifecycle oracle. This is relevant to 3D-floor/control-sector identity
and does not change rendering policy.
