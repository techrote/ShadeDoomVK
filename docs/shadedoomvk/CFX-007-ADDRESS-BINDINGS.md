# CFX-007 offline continuation: address-to-resource evidence

## Why this is the next discriminator

The six #97 targets ended in device loss. Five reported invalid-read address `0x1da00000` at 4096-byte precision; GPUAV target002 reported a different address. Copy/descriptor allocation extents were valid, but none of those files identifies the Vulkan object associated with the fault interval. Pipeline creation identity does not establish the executed shader. The direct-LevelMesh-off target still failed with a different checkpoint bracket.

Read-only `vulkaninfo` on the actual GTX 1650 SUPER / 616.92 runtime exposes `VK_EXT_device_address_binding_report` revision1 with `reportAddressBinding=true`. Local headers provide exactly that EXT interface. The next discriminator is whether the invalid-read interval overlaps a reported buffer/image/other object binding or unbinding. This is focused localization, not a claimed repair.

## Implemented opt-in path

- `tools/cfx_capture.py --address-bindings --resource-trace` requests a separate `address-bindings.tsv` inside the stable run directory. It records the request/schema/cap before launch. Off and ordinary capture remove inherited address environment settings. Existing STOP, source/runtime identity and finite-budget checks still apply.
- `VulkanInstance` registers a **separate INFO / DEVICE_ADDRESS_BINDING messenger** before device allocations, independent of validation's warning/error log and deduplication. It copies the typed `VkDeviceAddressBindingCallbackDataEXT` and `pObjects` fields. Null `pMessage` is allowed; no message parsing is needed.
- The device extension/feature is optional and enabled only with a working opt-in writer/messenger and advertised feature. Unsupported paths retain ordinary rendering and record `address-binding-report-unavailable`. `vk_debug` and validation layers are not required for this stream.
- Rows carry run header, sequence, UTC milliseconds, thread, CPU frame/tic/submission snapshot, bind/unbind range/flags, object type/handle/count, and a bounded name. Later engine debug names are separate name rows. CPU submission snapshots are **not proof of the actual consuming submission**; use the command-buffer/submission timeline and GPU checkpoint data separately.
- No Vulkan or engine API is called from the callback. It retains no callback pointers, cannot throw through Vulkan, caps at32768 rows and16 object associations per callback, and uses `try_lock` to avoid waiting behind another diagnostic write. Lost contention/cap associations are explicit counters, never silently complete evidence. This changes opt-in CPU/I/O overhead; no hardware overhead/equivalence claim is made yet.
- The loss path writes a cutoff/snapshot and CPU `address-binding-summary` before bounded fault collection. Normal device teardown writes another summary. File/mutex state survives renderer/driver teardown until process termination. I/O failures disable the writer and leave `writer_ok=0` in the CPU summary. A collector cannot make an OS-level blocked filesystem call bounded; the existing external process watchdog remains necessary.

## Offline interpretation

After a future **separately authorized** run, for the original reported read:

```powershell
C:\Python314\python.exe tools/cfx_address_correlate.py `
  --bindings <run-directory>\address-bindings.tsv `
  --timeline <run-directory>\timeline.tsv `
  --address 0x1da00000 --precision 4096 `
  --output <run-directory>\address-overlap.json
```

Use the actual address/precision from that run, not an assumed historical value. The output contains source-file hashes, matching bind/unbind **event history**, name hints, candidate buffer allocation-ID history from the CPU trace, and coverage gaps. It computes the inclusive precision interval using the specification's mask, not just an exact-address comparison. It rejects malformed ranges/sequence, partial records, invalid precision and mismatched run IDs.

Aliases and partial/unmatched unbinds are legal. Internal/pre-creation handles cannot be used as Vulkan API inputs. Object handles may be reused; names are not generations. The tool deliberately does not infer a unique live allocation or collapse historical matches into a use-after-free diagnosis. No overlap does not prove that an address was unbound, and an overlap does not prove that the shader accessed that object correctly. Driver-reported GPU addresses are not host pointers. An instruction address may associate with a pipeline object, but that is not SPIR-V/instruction decoding.

## Verification and current limits

**Offline only. No additional game/GPU launch occurred.** MSVC RelWithDebInfo build and nine injected callback/overlap tests pass; callback tests run under MSVC AddressSanitizer. Positive tests preserve aliased ranges, partial unbinds and transient callback names; negative tests cover disabled invalid-pointer callbacks, cap/contended callbacks, unavailable output file, malformed chains, missing objects, wrong run, bad precision and partial files. Manifest preparation uses a mocked Vulkan probe, not the physical GPU.

The six physical targets and safe image/state evidence used the earlier barrier candidate executable, not this later address collector. The current 16-launch/6-loss lane remains STOPPED; its guards/plans/binaries are not changed. Driver callback emission, safe activation and actual opt-in overhead still require a new reviewed finite protocol. First verify a known-safe control, registered messenger + enabled feature + actual bind/unbind rows + healthy summaries, then preregister one target that discriminates the leading resource hypothesis. Do not reset the old budget or repeat targets without a new question.

Existing historical files have no address-binding stream. This implementation cannot retroactively map their addresses. Aftermath/NVIDIA binary decoding remains unavailable locally; no global driver/Monitor setting is changed.

## Recommended next physical protocol (proposal, not authorization)

At most **two launches / one confirmed loss episode**: one known-safe control, then one original-input DBP37 target. First review this opt-in change, satisfy required CI and merge/verify the accepted substrate. Record a new issue/protocol with explicit owner approval, exact merged source/EXE/PDB/runtime/config/cache identities, all historical STOP hashes and a fresh healthy GTX1650 SUPER/expected-driver baseline. The existing #97 executor rejects the spent lane; this document does not open another lane or grant a launch.

Control gate: actual INFO messenger registration, enabled EXT feature, correctly named run/file, real bind/unbind records, healthy complete loss/teardown coverage summary, coherent artifacts, normal renderer exit and automated recovery. Resolve truncation/contention/malformed reports or writer failures offline before the target. Do not silently call incomplete coverage clean, and do not infer object absence from a missing event.

Target discriminator: does the **new run's** fault-precision interval overlap reported buffer/image/other object bindings or unbindings, and which candidate resource-ID/name histories correspond? Keep original primary content, map/startup, config, cache, resolution/cap/vsync/MSAA and direct-LevelMesh/generalized settings. Add only the address-reporting capture factor. Capture fault binary, CPU/submission/checkpoint timeline, pre-kill matching-PDB process dump and recovery/OS events; correlate once, then return to source. No blind second target is included. Any candidate repair subsequently needs its own available budget for the owner's three-success validation rule.

Specification references: [binding callback fields and INFO stream](https://docs.vulkan.org/refpages/latest/refpages/source/VkDeviceAddressBindingCallbackDataEXT.html), [aliases/internal allocations/partial unbind semantics](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_device_address_binding_report.html), [feature enablement](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceAddressBindingReportFeaturesEXT.html), [fault precision interval (EXT alias included)](https://docs.vulkan.org/refpages/latest/refpages/source/VkDeviceFaultAddressInfoKHR.html). Runtime support is established by the saved machine query, not these documents.
