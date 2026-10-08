# Upstream synchronization ownership and conflict policy

Primary issue: SDVK-003 / #3. Evidence: [SDVK-003 upstream differential](../SDVK-003-UPSTREAM-DIFFERENTIAL.md).

## Default ownership rule

ShadeDoomVK is not a rolling mirror of VKDoom, UZDoom or GZDoom. Upstream age or path similarity never overrides an accepted PF/CFX/SDVK contract.

Recipient-owned unless a focused issue proves an equivalent replacement:

- Vulkan descriptors, bindless/resource lifetime and publication;
- LevelMesh identity, mutation, upload and stale-reference prevention;
- material channel/sampler/GLDEFS semantics and scene/lightmap shaders;
- render-context, portal, camera/probe and pass identity;
- lighting, probe/lightmap, shadow selection and light-query semantics;
- SDVK-001 build/project/compatibility identity;
- SDVK-002 renderer observation/evidence hooks and source-evidence workflow.

A donor patch touching one of these surfaces is an **owned conflict**, not automatically syncable.

## Syncable classes

After exact donor commit/path/license inspection, isolated gameplay-script guards, parsers, UI/localization, platform fixes and security/compatibility repairs may be selectively adapted when they do not cross an owned boundary. Every import needs a positive case, deliberate negative/edge coverage and the full repository CPU/build gates.

Assets, dependencies, save/network/demo state, broader ZScript semantics and platform-capability changes are conditional even when renderer code is untouched.

## Supersession rule

No PF/CFX repair is superseded because a donor has a newer or differently organized implementation. Supersession requires the old bad-state fixture, proof the donor/adaptation makes that state impossible or correct under the same constraints, and all owning regression gates.

## Capability-loss veto

Pinned SDVK-003 evidence shows several VKDoom/ShadeDoomVK lightmapper, probe, LevelMesh, descriptor and shader paths have no same-path blob in the pinned UZDoom/GZDoom trees. This does not prove donor feature absence, but it makes wholesale replacement unsafe. Missing semantic equivalence is a stop condition.

## Verification

Use exact commit/tree pins and path/blob comparison first, then source/history inspection for candidate patches. Run the PF oracle, renderer corpus preparation, full hosted build matrix and renderer source-evidence workflow. SDVK-002 native/GPU gates apply only when an imported change actually touches renderer behavior whose contract requires native evidence.
