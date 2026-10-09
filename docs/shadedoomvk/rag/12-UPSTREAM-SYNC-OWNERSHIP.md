# Upstream synchronization ownership and conflict policy

Primary issue: SDVK-003 / #3. Status: **accepted, merged and verified** through PR #122 / `ffbd7e1d9f92b8b69b675765472a58ae3e0c7ca7`, present on verified current `master@a05743fb428c0d7c66defccfb577834d012b4e31`. Evidence: [SDVK-003 upstream differential](../SDVK-003-UPSTREAM-DIFFERENTIAL.md).

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

## SDVK-004 reconciliation

SDVK-004 applies this accepted ownership veto to its only production renderer
repair. Against the exact SDVK-003 donor pins
`UZDoom/UZDoom@809e46c25fe2a2f89430de3fbac89626100df384` and
`ZDoom/gzdoom@c26ce2e6ca2a0c770f140cb25dde0d30073ca8f7`, neither donor exposes a
same-path blob for
`src/common/rendering/vulkan/descriptorsets/vk_bindless.h` or
`vk_descriptorset.cpp`. That path-level result is not a claim that donors lack
equivalent facilities; it confirms that no same-path donor implementation can
be treated as a drop-in replacement.

The accepted SDVK-004 impossible-span guard is therefore a focused recipient repair against PF-003, not an upstream transplant. The GLDEFS/custom-shader changes in SDVK-004 are fixture/evidence authoring only; runtime parser/material semantics are unchanged. No donor renderer, shader, asset, dependency or license material is imported by the issue. PR #126 and its exact merged master passed all owning gates; see [SDVK-004 release acceptance](../SDVK-004-RELEASE-ACCEPTANCE.json).

## SDVK-009 architecture ownership

SDVK-009 imports no donor renderer implementation. Its architecture decision is
recipient-source evidence: current PF semantics, inherited recipient LevelMesh/
tile code, accepted PF-017/PF-019 outcomes and SDVK-002 diagnostics. The
host-only indexed-tile model is an original bounded representation experiment,
not a donor transplant. Any later forward+/clustered implementation remains a
recipient-owned renderer conflict and must be reviewed under this RAG before
external code is considered.
