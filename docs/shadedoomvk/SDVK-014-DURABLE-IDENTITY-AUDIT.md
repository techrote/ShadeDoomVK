# SDVK-014 durable allocation and resource identity audit

## Disposition

**Audit performed; clean lifetime acceptance FAILED / BLOCKED. No production repair
is included in this audit increment.** Issue #153 reblocks the retained probe-map
consumer across live descriptor-cache reset. The accepted #150 semantic probe-set
builder repair remains accepted; it solves a different ownership boundary.

Assessed master: `ca254b6ea08228c8408562ebba26bbc1060a0311`.
Assessed tree: `ea20650fefbe454b5a43f82119e879df75ed8e4f`.
Branch: `sdvk014-durable-identity-audit`.

The actual source was recovered from source-evidence run **38930148555**, artifact
**12057998317**, ZIP SHA-256
`f74d6f3630af5b3e7cd27a66b05f3f9bfbcd58afb6a3fce41e309c0b5ff975be`.
The internal bundle checksums were verified. Its CI merge-ref
`1b97276ea1358087c818fcfc10216efd06d6aed7` has the same tree as assessed master;
the local checkout is that tree-equivalent merge-ref, not a claim that its commit
identity equals master. Production file hashes are in the
[executable audit receipt](evidence/SDVK-014-DURABLE-IDENTITY-AUDIT.json).

**Physical STOP ACTIVE.** No renderer or Vulkan device was executed locally.
Physical bake/update cost, scaling and hardware stability remain HELD / NOT
ACCEPTED. Historical physical root cause remains **UNDETERMINED**. This report
neither closes #14 nor promotes it to software-complete.

## Coverage and conclusions

| Requested boundary | Actual owner and identity | Invalidation/publication and consumer | Audit disposition |
| --- | --- | --- | --- |
| Atlas page reuse/repack | `LevelMesh::Lightmap` owns `RectPacker`; item pointer plus coordinates/page | `PackLightmapAtlas` allocates added tiles and updates added surfaces. `Free` recycles items; scratch `Clear` recycles item storage. | A copied old receipt can pass the region guard after identical reuse. No allocation incarnation is captured. Finding A below. |
| Tile retirement/reallocation | `Lightmap.Tiles` integer slots; `DoomLevelMesh` surface references | Last `ReleaseTiles` reference frees the atlas item, nulls it, tombstones via `FreeTile`, and clears the surface tile index. | Ordinary release is source-bounded by tombstoning. Do not equate an injected copied receipt with a demonstrated surviving production surface. |
| Lightmap/probe descriptor generations | Reserved page pairs; PF-003 dynamic span generations; probe image epoch; #150 semantic owner revision | Full image replacement advances image epoch. Dynamic pair retirement advances slot generation. Probe-map texels retain raw dynamic bases. | Reserved removed-page fallback control passes. Raw probe-map texels bypass slot generations across filter reset: **#153 blocker**. |
| Old page/region after rebuild | Image/page owner, tile item pointer, mutation domains and dirty ranges | Appending pages retains the prefix; full replacement creates/clears new pages. Surface rebuild updates new atlas indices. | Bounds and zero initialization do not authenticate a previous same-coordinate allocation. No claim that arbitrary live atlas compaction is supported. |
| Save/load/rebake | `LIGHTMAP` tile binding, transform, extent and RGB span; current LevelMesh on load | Loader rebinds current live semantic tile keys and allocates new runtime coordinates. Device consumes pending RGB data after successful upload. | Runtime descriptor/page identities are not serialized. The format does not authenticate bake-content freshness against geometry/light/material changes. Explicit limitation below. |
| Plausible recycled bindings | CPU owner tokens versus retained shader-visible integers | Exact filter-reset/lookup/upload path plus real allocator reassigns an old texel to another valid adjacent pair. | **Not safe to assert that all recycled references are rejected.** Clean audit fails despite deterministic, live, nonzero span-2 state. |

The existing PF-002/003/004, PF-012/PF-113 and SDVK-010 contracts are consumed,
not replaced. The accepted #151 repairs are not reversed. Existing viewmodel,
material channel, shader lighting, portal selection and quality policies are
unchanged. No native image, leak-soak or physical performance claim is made.

## Finding A: atlas pointer and coordinate ABA

### Exact source boundary

`src/common/rendering/hwrenderer/data/hw_rectpacker.h/.cpp` owns item storage.
Free-list reuse can return the same `RectPackerItem*` with identical `X`, `Y`,
`Width`, `Height` and `PageIndex`. `Clear()` keeps item objects for reuse while
clearing page/shelf state. Neither the item nor `LightmapTile::AtlasLocation`
captures a durable allocation incarnation.

`hw_lightmaptile.h::HasValidAtlasRegion` checks a live tile count, nonnull item,
page range, extents, coordinates and agreement with that item. Those are useful
shape/range checks, but an old copied tile can agree with the **new allocation**
now occupying the same object and region.

The fixture uses the real packer and tile type. It retains tile binding 100,
frees a 16-by-16 full-page allocation, then creates binding 200 in the same page.
A second case exercises `Clear` followed by identical allocation. Both require
same-pointer/same-region reuse as an explicit precondition and produce:

```text
old_binding=100 new_binding=200 same_item=1 same_region=1 old_guard=1
BLOCKED stale-atlas-receipt-accepted
```

The valid current receipt passes. Deliberately changing its X coordinate fails
the guard, establishing that ordinary bounds checking works but misses ABA
(old A identity, recycled to B, with the same observable pointer/shape).

### Reachability limit and correct existing behavior

This is an **injected durable-receipt counterexample**, not evidence that an
ordinary production draw still holds such a copied tile. The actual
`doom_levelmesh.cpp::ReleaseTiles` releases the last reference and invalidates
its current surface. `hw_levelmesh.h::FreeTile` refuses live ownership, clears
the tile object before returning its index to the free pool, and records the
lightmap/probe mutation. The existing retirement and atlas suites remain in the
normal CPU gate.

Also, `DoomLevelMesh::FullRefresh` queues side/flat rebuilds. It is **not** an
atomic full-atlas compaction operation. The audited `PackLightmapAtlas` packs
added tiles and updates added surfaces, rather than relocating every live
allocation. The active LevelMesh packer has no `Clear()` caller in these ordinary
refresh paths; the lightmapper's separate scratch packer does use `Clear()`.
Do not manufacture a supported live-repack route from the shared method name.

A future durable tile/allocation handle must capture owner plus allocation
incarnation and reject old handles before reading/freeing recycled storage.
Extending one helper with a counter without auditing all producers and consumers
would not prove that contract. Finding A remains explicit #14 work; no speculative
renderer redesign or unproven guard-only repair is included here.

## Finding B: raw probe-map texels survive unrelated descriptor reset

### Actual production chain

1. `hw_cvars.cpp` routes live `gl_texture_filter` and
   `gl_texture_filter_anisotropic` changes to `SetTextureFilterMode`.
2. `vk_renderdevice.cpp::SetTextureFilterMode` calls
   `VkDescriptorSetManager::ResetHWTextureSets` then `ResetHWSamplers`.
3. `vk_descriptorset.cpp::ResetHWTextureSets` frees all cached `LightProbes`
   pairs and clears their lookup vector. It does not invalidate probe-map
   texels, dirty their lightmap tiles, or change the semantic probe-set owner.
4. `VkSamplerManager::ResetHWSamplers` rebuilds hardware **material** samplers.
   Irradiance/prefilter samplers are separately owned and are not rebuilt there.
5. `VkLightmapper::UploadProbeSelection` stores runtime descriptor starts in
   candidates. `frag_copy.glsl` selects those starts and writes the R16_UINT
   probe map. They are not authored ordinals.
6. `lightmodel_pbr.glsl` gathers the retained unsigned texels and samples each
   nonzero base plus its adjacent prefilter. The texel contains no captured
   PF-003 generation token to reject a recycled slot.

`StartPrecaching` also calls `ResetHWTextureSets`. Its map/rebuild ordering needs
separate repair qualification; this audit does not claim every precache use is
incorrect. The live filter/anisotropy route is already enough to falsify the
claimed lifetime boundary without invoking a map teardown.

### Executed counterexample and independent controls

The fixture extracts the **actual current** reset, device filter, probe lookup
and candidate-upload definitions. It uses the real `VkBindlessSlotAllocator`
and `HWProbeSelection::FindClosest`. Two symbolic image families identify their
authored owner independently of the descriptor index. Material/colormap sets
are empty to isolate probe-slot retirement. Descriptor-write sinks represent the
state after queued writes are submitted; no Vulkan submission is performed.

The initial ordered publication assigns probe 0 base 259 and probe 1 base 261.
The selected retained probe-0 texel is 259. After the real filter-reset route,
exact-size LIFO reuse reverses the owners:

```text
retained_texel=259 fresh_ordinal0=261 fresh_ordinal1=259 retained_texel_owner=1 live_span=2
BLOCKED retained-probemap-texel-rebound-to-other-owner
```

The old PF token correctly rejects. Both newly allocated pairs are live,
nonzero, adjacent and span 2; the stale texel nevertheless points to another
owner. This is the requested **plausible, deterministic and wrong** identity
counterexample. It proves the source/CPU ownership failure, not measured wrong
GPU pixels or historical crash causality. Actual runtime descriptor numbers with
other material populations need not be 259/261.

No-reset lookup passes. A temporary **counterfactual control** removes only the
probe-pair retirement loop from the extracted reset body, retaining all other
behavior. It preserves old owner 0 and passes. This isolates retirement/reuse as
the cause; it is not a production fix and does not establish that all uses of
`ResetHWTextureSets` may safely retain all pairs forever.

Issue **#153** owns the upstream repair and affected-scope release. Preserve
stable semantic pair identity while its image/sampler owners remain live, or
invalidate/republish every retained raw consumer before reuse. Audit material
pressure, reversed allocation order, filter and anisotropy changes, precaching,
map transition and teardown. Do not substitute a global emergency flush,
silent loss of IBL, lower bake quality, or an observer-controlled workaround.

## Boundaries that held within the audited scope

### Reserved atlas descriptor pages and resource epochs

`VkPlanLightmapDescriptorPublication` plans the union of current and previous
page counts. The CPU control shrinks 128 pages to one and verifies all 127 removed
page pairs receive the reserved typed fallback, with dynamic allocation starting
after descriptor 258. A 129-page request is rejected. This guards **reserved page
slots**, not dynamic environment-probe slots embedded in existing texels.

`VkTextureManager::CreateLightmap` advances `LightmapEpoch`, retires old page
resources through the existing delete-list path, clears new probe pages to typed
zero and clears light pages when no retained RGB payload is supplied. The
reserved descriptor update publishes the current views/fallbacks. Appending with
`SetLightmapCount` retains existing prefix resources; lack of a new whole-array
epoch on an append is not by itself evidence of stale prefix ownership.

`FRendererEpoch` rejects an old snapshot after invalidation in the CPU control.
The real slot allocator similarly rejects old span tokens after free/reuse.
These are necessary substrate checks, not proof that a raw downstream integer
actually carries or consults the token. #153 is precisely that missing consumer
boundary.

### Tile and dynamic-copy lifetime

Existing release/tombstone ordering prevents ordinary current surface ownership
from surviving a freed tile slot. The audited update path selects and processes
its tiles synchronously; no interleaved tile recycle during that sequence was
demonstrated. `CopyResult` retains dirty flags until actual copy recording and
shader-read transition, as repaired by #151. It is not claimed to authenticate
an arbitrarily retained region snapshot across another rebuild.

The broader native repeated/multi-page and moving-geometry freshness campaign
remains outstanding. This audit does not convert source order into executed
end-to-end image equivalence or a device-completion guarantee.

### Probe content reset versus descriptor identity

`ResetLightProbes` advances the probe-content epoch and clears existing images;
existing image/view objects can retain their identity. Grow-only irradiance and
prefilter vectors retain their prefix. The accepted #150 builder now resets
progress on a new semantic owner revision, including equal-count replacement
and empty transitions. None of those facts invalidates existing probe-map texels
when an unrelated descriptor cache recycles their raw bases. Pair adjacency,
content epoch, slot incarnation and authored ordinal are distinct identities.

## Save, load and rebake identity

The `LIGHTMAP` format binds a tile through surface type, type index and control
sector, plus extents, transform and RGB pixel span. The loader validates entries
before mutation, finds current live semantic bindings, calls `PackLightmapAtlas`,
and copies retained pixels into the newly allocated runtime locations. Saved
page coordinates, bindless slots and probe ordinals are not restored as runtime
identities. Save validates current tile regions and uses separate RGBA readback
scratch; successful pending RGB upload is consumed by `BeginFrame`.

However, this format has **no source geometry/light/material digest** that can
prove the authored bake is still fresh when keys and shape remain compatible.
A manually retained old lump can be structurally admissible without being the
right bake for changed content. Map-local binding is not content authentication.
This is an explicit provenance/freshness limitation, not a new claim that an
unchanged map's ordinary loader is broken. No format migration or digest policy
is invented by the audit.

No physical or hosted renderer save/load/rebake sequence ran in this turn.
Full lifecycle correctness, multi-page stress and special-surface/material
coverage remain their own #14 acceptance work.

## Reproduction and evidence semantics

```sh
python3 -m unittest tools.pf_oracle.tests.test_sdvk014_identity_audit -v
python3 tools/pf_oracle/sdvk014_identity_audit.py --out audit.json
python3 tools/pf_oracle/sdvk014_identity_audit.py --out clean-check.json --require-clean
python3 tools/check.py --output build/sdvk014-identity-audit-checks
```

The unittest and collector deliberately retain named failing clean invariants:
child exit **11** means `BLOCKED`, not a repaired behavior. Collector exit **0**
means the prescribed evidence was reproduced. `--require-clean` returns **2**
while the audit is blocked. Compiler errors, missing source and unexpected child
failures remain errors; they are not expected counterexamples.

Focused GCC and Clang CPU cases pass this evidence contract. The initial local
fixture omitted BBox constructor definitions and failed linking; those exact
production constructor bodies were then included. Clang also flagged the
inherited unused `TArray(ENoInit dummy)` parameter. A fixture-only diagnostic
push/pop encloses that header; strict warnings remain enabled for extracted
producer bodies and audit assertions. Neither correction changes renderer code.

The receipt pins the production source hashes, outputs and adapters. The
separate CPU validation receipt records the complete normal CPU gate and its
logs. Native CI, if subsequently green, qualifies only its executed existing
workloads and this evidence collector; it does **not** repair or accept #153.

## Programme handoff and prospective native qualification

After #153 has a reviewed production correction, use two authored probes and a
retained probe-map consumer in the existing Avrea 16-vCPU llvmpipe lane. Exercise
live filter and anisotropy changes **without** a map switch, bake reset or forced
refresh concealing reuse. Capture the pre/post raw probe-map values, semantic
pair owners, slot generations, image epochs and independent consumer state.
Include reversed lookup order and material span pressure. Require correct owner
association or an explicit valid republish transition, bounded pair counts and
unchanged material sampling semantics. Keep a retained pre-fix rejection.

That protocol is prospective, not executed or fully preregistered by this report.
Exact content/driver commands and comparison policy belong to the repair PR;
normal CI runs it once, without a benchmark-only duplicate. A renderer/device
fault or any attempt to select a physical Vulkan device stops the affected run.

Issue #14 remains open. #153 release, a defensible durable atlas/allocation
contract, repeated native transitions and supported surface/material coverage
are still required before any software-complete disposition. Physical acceptance
remains separate and held throughout.
