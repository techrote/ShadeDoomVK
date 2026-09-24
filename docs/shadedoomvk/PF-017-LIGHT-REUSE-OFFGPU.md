# PF-017 light reuse off-GPU qualification — 2026-09-24

Status: **OFF-GPU GATE COMPLETE; PHYSICAL ACCEPTANCE PENDING.** PF-017 / #34 is not accepted, PR #74 remains draft/unmerged, and PF-019 / #36 remains blocked.

## Source and scope

The candidate branch `pf-017-light-reuse-acceptance` starts from accepted `master@8c9e92458d1b08d8ff00f7c7874441433e63e5a9`. Renderer/test source was frozen at `e028fd88b29aa2d0d82e4e04a09ea644bfa56670` before this documentation-only reconciliation.

This pass deliberately performed no GTX 1650 SUPER launch. It completed everything that can be established without the physical acceptance GPU: source reconstruction, lifecycle/identity design, adversarial fixtures, deterministic PF oracle, and the inherited cross-platform build matrix.

The retained candidate is the second PF-017 design previously measured at 6.83% lower median `S: Setup` and 13.83% fewer mapped bytes. It is **not** the rejected frame-local hash/reference/shader-indirection design that reduced writes by 94.24% while regressing setup by 133.25%.

## Candidate contract

- `FDynamicLight` owns four packing snapshots for the existing force-attenuation/trace combinations.
- First qualified use in each PF-010 top-level render epoch executes the accepted packing math. Later same-epoch uses may reuse that source snapshot.
- A changed packed record, light class or portal group receives a new process-monotonic non-zero revision. Equal bytes from a different source object do not share identity.
- Freelist/arena allocation already zeroes the complete `FDynamicLight`, so destruction/recreation at a reused address cannot inherit an old snapshot.
- Spot lights, alpha-dependent `RF2_LIGHTMULTALPHA` records, foreign portal groups, sunlight and missing/invalid contexts remain on the accepted pack/copy path with revision `0`.
- Portal recursion inherits the PF-010 parent epoch, while foreign-group records still fail qualification.
- `FDynLightData` keeps the same ordered normal/subtractive/additive arrays and adds a parallel revision sequence.
- `LightBufferSSO` physical layout, range semantics and shader fetches are unchanged. A mapped class write is skipped only when every non-zero revision exactly matches the persistent shadow at the same physical offsets.
- A new `VkRSBuffers` owner initializes mapped-buffer shadows together with the new storage. Per-frame cursor reset does not erase shadows that still describe resident bytes.
- Revision exhaustion and epoch rollback/reuse/wrap fail closed instead of allowing an old identity to become current.
- `UploadLights` now rejects `UploadIndex == Count`, closing the prior one-past-range boundary while preserving the accepted data-capacity check.

## Deterministic and adversarial verification

`tools/pf_oracle/tests/light_reuse_fixture.cpp` and `test_light_reuse_contract.py` cover:

- source-owned same-epoch reuse and first use after an epoch transition;
- equal packed bytes from different source objects;
- repeated references to the same source at multiple physical positions;
- source reincarnation/freelist clearing;
- packed-state mutation;
- normal/subtractive/additive class transitions;
- portal-group transitions and foreign-group fallback;
- the four attenuation/trace snapshot identities;
- unsupported/sun revision-zero fallback;
- mixed qualified/unqualified class copy behavior;
- exact mapped revision-position matching;
- mapped-buffer recreation versus per-frame cursor reset;
- range-index capacity;
- revision exhaustion/wrap fail-closed behavior;
- PF-010 epoch rollback/reuse fail-closed behavior;
- scope ordering after shadow-map selection and attenuation finalization;
- portal recursion inheriting the root PF-010 epoch.

The inherited PF-011 lighting compatibility assertions were updated only for the packer's local variable rename (`i` → `lightClass`); their additive/subtractive/GLDEFS semantic assertions remain intact.

## CI evidence

Implementation-only source head `e028fd88b29aa2d0d82e4e04a09ea644bfa56670` passed Continuous Integration run **36047117838**:

- PF renderer contract oracle: pass; 110 unit/contract tests plus deterministic PF baseline and inherited compiled fixtures.
- Visual Studio 2022 RelWithDebInfo: pass.
- Visual Studio 2022 Debug: pass.
- macOS Release: pass.
- macOS Debug: pass.
- Linux GCC 12 RelWithDebInfo: pass.
- Linux Clang 11 Debug: pass.
- Linux Clang 15 Release: pass.

Two earlier branch runs were useful negative evidence rather than acceptance: the first exposed a stale source-string assertion in the PF-011 contract after the packer variable rename; the second exposed a CVAR declaration-order compile error on MSVC/Apple Clang. Both were repaired without weakening semantic coverage. Run 36047117838 is the clean source-freeze result.

## Remaining physical gate

No further design or lifecycle work should be added before physical qualification unless CI exposes a source defect.

On the **exact final renderer source**, use the GTX 1650 SUPER only for the final PF-017 acceptance campaign:

1. Build accepted baseline and candidate with matched configuration.
2. Run the representative PF-016 dense light workload using alternating baseline/candidate order for at least five physical pairs.
3. Confirm the previously observed setup benefit remains repeatable and there is no material whole-frame regression.
4. Capture the same deterministic state/range/packed-buffer checkpoints used by prior PF-017 evidence.
5. Compare final rendered images/state exactly under the established PF equivalence protocol.
6. If the benefit survives and equivalence is exact, finish PR #74 acceptance/merge/master verification. If it does not, restore/reject the candidate and record a light-path no-go.

Driver-crash investigation and the prior NVIDIA error 153 are separate from this acceptance campaign. Do not broaden PF-017 into PWAD driver-crash diagnosis.

## Non-claims

This off-GPU pass does not prove the final candidate is faster on the GTX 1650 SUPER, does not claim a GPU-time improvement, and does not accept or merge PF-017. It establishes that the candidate's identity/lifetime model, deterministic state contract, and supported build surfaces are ready for the single remaining physical acceptance gate.
