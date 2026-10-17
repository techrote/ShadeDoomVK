# SDVK-158 — retained LIGHTMAP freshness and repeated multi-page transitions

## Disposition

**Implementation candidate. Hosted exact-head acceptance pending.**

Parent SDVK-014 remains open. This increment is deliberately bounded to retained
LIGHTMAP authored-source freshness plus repeated/multi-page lifecycle correctness.
It does not complete the later special-surface/material matrix and does not
authorize or infer physical GPU performance.

Assessed parent is `master@d6b089d53bf53295604757f3924ce9ad3517ad3a`,
tree `8d3b6b928cb109abaaf24ce25858843d948a0216`.

## Minimum retained-freshness contract

LIGHTMAP is upgraded from version 4 to version 5. The persistent header is:

```text
int32    version = 5
uint32   tileCount
uint32   pixelCount
uint8    sourceDigest[16]
TileEntry tiles[tileCount]
uint16   rgb[pixelCount * 3]
```

`sourceDigest` is the engine's existing `MapData::GetChecksum` result already
stored as `FLevelLocals::md5` before map loading. That authority is deliberately
non-circular:

- UDMF: exact `TEXTMAP` bytes;
- binary maps: map label/header, THINGS, LINEDEFS, SIDEDEFS and SECTORS;
- BEHAVIOR is included when present;
- generated node data is excluded;
- LIGHTMAP itself is excluded.

For this minimum contract, the digest therefore authenticates the authored map
geometry, authored thing/light inputs, sector/side material bindings and map
behavior source that define the bake. `LIGHTMAPVER` separately identifies the
engine-side retained format/bake interpretation contract.

### Explicit limit

This is **not** a general content-addressed asset system. Replacing external
texture/material resource bytes while preserving the same authored map binding is
not authenticated by `MapData::GetChecksum`. Such external-resource freshness is
outside this minimum v5 contract and must not be silently described as covered.

## Fail-closed load ordering

`MapLoader::LoadLightmap` now:

1. rejects every pre-v5 or unknown LIGHTMAP version;
2. reads the v5 source digest;
3. compares it byte-for-byte with the current level source checksum;
4. returns false on mismatch **before** reading/admitting retained tile ownership
   into current transforms/extents/completion state;
5. retains the existing complete structural admission pass for bindings, ranges,
   transforms, duplicate bindings and pixel spans;
6. only then applies admitted retained transforms/pixels and clears completion
   flags for those admitted tiles.

Returning false preserves the existing ordinary path: current tiles retain their
fresh bake state and are packed/baked normally. No stale retained state is
partially applied before fallback.

`Lightmap.RetainedTilesLoaded` records only entries that passed both source
provenance and structural admission. It is passive qualification state and does
not alter rendering policy.

## Repeated/multi-page native fixture

The hosted SDVK-158 fixture contains one large authored UDMF room and an embedded
version-5 LIGHTMAP. The retained ceiling and floor are each 513×513 texels using
the exact production `SetupTileTransform` math, including the +0.1 origin bias.
Two 513×513 allocations cannot share one 1024×1024 atlas page in either axis, so
the fixture requires at least two current pages. Ordinary wall tiles are left
unretained/dirty, preventing the fixture from passing solely by copying prepared
pixels.

A state-only, opt-in and outcome-blind input driver queues ordinary console
commands after fixed newly presented main-view ordinals:

| Main views | Input |
| ---: | --- |
| 40 | `invalidatelightmap` |
| 56 | `map SDV158` (same-map retained reload) |
| 72 | `invalidatelightmap` |

The driver reads no renderer result and cannot decide whether to advance.
Acceptance comes from passive resource records.

## Passive lifecycle witness

Each retained state frame records:

- CPU atlas texture size/page count;
- current Vulkan lightmap page count;
- live/current-valid/invalid tile counts;
- accepted retained tile count;
- `NeedsInitialBake`, `GeometryUpdate` and `ReceivedNewLight` partitions;
- submitted `UpdateLightmaps` tile count and, separately, tiles that actually
  transition dirty→clean after synchronous copy/publication recording;
- per-page live tile occupancy;
- current page-bound receipt validity;
- Lightmap resource epoch and LevelMesh mutation epochs.

The gate requires every retained frame to have at least two current pages, exact
CPU/Vulkan page-count agreement, zero invalid live receipts and complete
per-page accounting. Both forced invalidation phases must perform real
dirty→clean completions and finish with all three dirty categories clear. Reload
must perform real completion work, retire `NeedsInitialBake` and
`GeometryUpdate`, replace the Vulkan lightmap resource epoch and retain valid
current-page ownership; ordinary post-load `ReceivedNewLight` may remain pending
until the following forced invalidation, which must then drain it to zero.

The state capture keeps the established 32-view warmup but retains only 48
state frames. The three input boundaries occur at main-view ordinals 40/56/72,
leaving retained-frame windows 9–24, 25–40 and 41–48 for the two invalidations
and reload. Per-draw collection is bounded to those actual `RenderView`
intervals, leaving at least eight frames after the final six-tile invalidation at
`lm_max_updates=1`.

Two independent clean-state processes execute the full invalidate → reload →
invalidate schedule and must repeat exact semantic state and final RGB.

## CPU/source falsifiers

The retained lifecycle suite requires:

- exact source-digest equality passes;
- first-byte and last-byte digest mutations fail;
- a deliberately bypassed equality check fails its named negative;
- v5 digest admission occurs before any retained tile mutation;
- save writes the current level digest and accounts for the 16-byte header field;
- the source checksum authority contains the declared authored map inputs and
  excludes LIGHTMAP/generated node lumps;
- existing retained structural admission, post-copy completion and page
  initialization negatives remain intact.

The dedicated native-oracle tests additionally reject single-page substitution,
invalid live receipts, missing completed tile work, incomplete dirty convergence,
missing reload epoch replacement, missing retained admission and changed driver
boundaries.

## Remaining SDVK-014 boundary

After this increment, the major remaining software campaign item is the supported
special-surface/material lifecycle matrix (decals, warped/reflective/translucent,
portals/Line_Horizon/3D floors and semantic material/height combinations) plus any
negative controls it exposes.

Physical GPU bake/update cost, representative scaling and hardware stability
remain separately **HELD / NOT ACCEPTED**. **Physical STOP remains ACTIVE.**
Historical physical root cause remains **UNDETERMINED**.


## Retained first-native failure and causal correction

Normal CI run `38991258032`, software-Vulkan job `117274393400`, retained
artifact `12085488397`, passed PF/oracle, every ordinary platform build, the
generic software-Vulkan corpus, SDVK-010, SDVK-150 and SDVK-153 before SDVK-158
transition-1 stopped.

The renderer did not fault. Its passive receipt reached 59 retained frames with
two CPU/Vulkan atlas pages, six valid live receipts, zero invalid receipts and
per-page occupancy `[5,1]`, then stopped with
`SDVK observation record/byte limit reached` after 13,036 records. The oversized
120-frame request was therefore a fixture-capacity error.

The retained state also exposed a real production bug before the cap: after the
first `invalidatelightmap`, `NeedsInitialBake` remained 6 indefinitely while
one tile was submitted every frame. `InvalidateLightmap()` set only
`NeedsInitialBake=true`, but `VkLightmapper::SelectTiles` admits actual bake
work only when `ReceivedNewLight` is true. A previously clean retained tile
could therefore be repeatedly scheduled yet never selected/copied/completed.

The correction sets both flags for every live forced-invalidated tile. Diagnostic
bookkeeping now separates submitted tiles from actual dirty→clean transitions
observed after `Raytrace` returns from its copy/publication path. Source tests pin
both the admission flag and post-Raytrace completion ordering. The native state
window is reduced to 48 retained frames without removing any lifecycle phase.
No quality, shader, light-selection, atlas-allocation or physical-performance
policy changes.

## CI-505 observer interval repair

Normal CI run [`38994329016`](https://github.com/techrote/ShadeDoomVK/actions/runs/38994329016),
job [`117284165714`](https://github.com/techrote/ShadeDoomVK/actions/runs/38994329016/job/117284165714),
at PR #159 head `009cc2347fad173977fbffef7d787f1775e2c5ab` again reached
SDVK-158 after the generic corpus and SDVK-010/#150/#153 gates passed.
`transition-1` stopped with `SDVK_OBSERVATION_FAILED`; the failed output remains
in artifact `12085874925` (artifact ZIP SHA-256
`8b8273c2bb6eed7ae3ced69f7029c56d90d2f0cc040d8d41d5cde251ee4d94cc`).
The second transition process and dependent publication gate did not run.

The observer's state flag remained enabled after `RenderView` returned.
`D_Display` then emitted HUD/console/menu work and the reload screen wipe;
`PerformWipe` can call `screen->Update()` repeatedly without another observed
main view or `FramePresented`. Those out-of-interval draws therefore appended
records under the completed frame's identity and could exhaust the 16 MiB
store independently of the 48-view request. The retained frame limit alone
cannot bound that producer loop.

`SdvkDiagnostics::EndFrame` now closes only `StateFlag`, after the frame,
probe-builder and Vulkan owner snapshots, and also after its exception handler.
The placement preserves the state-only light-upload snapshot. It leaves the
retained frame identity, observer enablement and GPU timing flag intact for
ordinary fence resolution, lifecycle callbacks between views and the existing
presentation/input/screenshot completion path. All in-view producers remain
covered, including camera/probe/portal views, HUD models and weapon draws, and
canvas draws with explicitly unavailable `HWDrawInfo` context.

The compiled CPU regression executes the production observer boundary methods
with the real bounded `RecordStore` and explicit engine-service doubles. Its
pre-fix control removes only the new state reset, showing that a post-view draw
flood exhausts the unchanged byte bound. The repaired path must preserve every
in-interval record, next-frame re-arming, the final state-enabled resource
snapshot, GPU results through presentation and between-view lifecycle events.
Warmup/timing behavior and real in-interval overflow remain separate negatives.
This replay is observer-control-flow evidence; fresh normal CI remains the
authority for native rendering.

The 32-view warmup, 48 retained frames, 40/56/72 input schedule, two independent
captures, exact state/RGB requirements, 600-second deadline and all record
limits are unchanged. No rendering, quality, atlas or lightmap behavior is
changed by this interval repair.
