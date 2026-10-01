# CFX-006 / #95: bounded capture identity revision

Status: implementation and offline verification; PR review/CI acceptance remains separate. Base master `83a7ac25ec581a10e72248a39d5d206f248a2d1d`. This addresses the capture gaps accepted in #79/#92, not the initiating crash. **Zero GPU launches**, including no capability probe, game or intentional reset. All six STOP guards remain active and unchanged. Both CFX-005 three-loss budgets remain exhausted; #75 and PF-020/#37 remain open/blocked.

## Enablement and files

Use the existing `tools/cfx_capture.py` run/manifest mechanism. `--mode capture --resource-trace` requests the new evidence; core/sync/GPU-assisted remain separate existing modes. `--resource-trace` is rejected with `--mode off`. Child environment sets `CFX_RESOURCE_TRACE=1` only when requested and clears inherited CFX variables for an off control. Direct launches require all three: `CFX_RUN_ID`, `CFX_TRACE_FILE`, `CFX_RESOURCE_TRACE=1`. Fault-query spans are part of ordinary enabled CFX tracing after an observed loss, independent of the resource switch.

The unchanged `cfx-002-run-v1` manifest adds `environment.resource_trace` (`cfx-006-resource-v1`, enablement, record/byte limits, algorithm). The manifest boolean is requested enablement, not activation proof: require `resource-trace-config` plus resource records in the retained timeline. Missing activation records remain unproven (including after tail rotation). No incompatible incident index is introduced. Existing per-run files remain: `manifest.json`, `timeline.tsv`, `stdout.log`, `stderr.log`, loader/layer and OS records, prelaunch cache/config snapshots; conditional `device-fault.bin` and watchdog `process.dmp`. See [CFX-002 capture procedure](CFX-002-CAPTURE.md) for exact dump-before-kill commands and matching-PDB stack analysis. Use the **new build's PDB** for any future run; the age-28 offline reader is restricted to old captured binaries.

This revision is not a new physical protocol and does not reopen #78/#92. Do not reuse old approval switches/plans to bypass stopped lanes. A future plan must pin the new EXE/PDB/source/resource identities, registration of this extra CPU overhead, workload, predicted discriminator, controls, capture directory and loss/launch budget. Hardware activation/image equivalence of this revision has **not** been measured.

## Fault/checkpoint query outcomes

| Record | Meaning |
|---|---|
| `device-fault-unavailable` | EXT not enabled, feature not enabled, or entry point missing; no query called |
| `device-fault-count-enter` / `-return` | First `vkGetDeviceFaultInfoEXT`; returned VkResult and advertised address/vendor/binary counts |
| `device-fault-data-enter` / `-return` | Supplied capacities then actual returned VkResult/counts; at most one data call, no retry loop |
| `device-fault-cap-truncated` | Advertised count clipped to 128 addresses, 128 vendor records, 32 MiB binary |
| `device-fault-return-truncated` | Returned counts exceed supplied storage; interpretation clipped to allocation |
| `device-fault-empty` | Success/incomplete query supplies no description, retained addresses/vendor records or binary; distinguish this from unavailability/error |
| `device-fault-binary*` | Actual binary write, open failure or short/failed write; cap/incomplete records still determine whether the binary is partial |
| `checkpoint-query-unavailable` | NV not enabled, entry point missing, or queue absent |
| `checkpoint-count-enter` / `-return` | Queue/name, count, capacity (max 256), truncation; count zero is explicit |
| `checkpoint-data-enter` / `-return` | Read attempt and returned count versus capacity, including a later zero count |
| `gpu-checkpoint-confirmed` | Returned queue/stage/opaque marker pointer; join to the existing recorded-marker pointer |
| `fault-collection-exception` | Collection abandoned on exception; original device-loss error still raised |

NV's query returns **void**. Its `api=void` records' numeric result-column zero is the trace placeholder, not VK_SUCCESS. Only EXT `*-return` spans give the queried function's VkResult; enter/cap records are context, not additional returns. Initial errors skip the data call; data errors produce no interpreted payload. `VK_INCOMPLETE`, caps and returned-count clipping are retained explicitly. No EXT/KHR interface mixing: this code uses the repository's EXT headers/entry point only.

Host allocations and query counts are bounded. Driver API calls cannot be given an application-side hard time guarantee: an enter span without return identifies a collector stall for the external watchdog/process dump. No new renderer/device wait, GPU command, teardown recovery or retry is introduced. Specification review found and removed the inherited completed-frame NV smoke query: `vkGetQueueCheckpointDataNV` requires a lost device (VUID 02025). Safe activation uses capability/recorded-marker evidence; only the observed-loss handler retrieves NV queue data. Historical zero counts from the healthy-device smoke are not valid retrieval evidence. Existing NV/EXT loss queries remain on the error path even when tracing is off; this revision adds **no extra** Vulkan query on an off/normal-rendering path. Logging is opt-in. Exceptions in collection no longer replace the original error. The collector takes no command-manager/resource lock; the existing trace mutex and synchronous file IO remain.

This cannot retroactively distinguish why native P400 emitted no payload. Historical raw evidence stays immutable. Unsupported/empty/error/count cases are demonstrated by injected callbacks, not manufactured hardware faults. Current hardware/tool capability is not re-inventoried here; the dated CFX-002/005 inventories remain the provenance for historical support/Aftermath status.

## Resource and upload correlation

Resource records use the existing run/thread/frame/tic/stage columns. Renderer-local IDs are monotonic within the run and assigned to buffer, descriptor-set, command-buffer and retirement-list **allocations**, not handles or semantic Doom objects. IDs remain distinct if Vulkan recycles a handle. They do not replace PF generation ownership.

1. `resource-create` / `resource-name` identify buffer ID, Vulkan handle, allocated bytes and existing builder debug name. `resource-destroy` is logged immediately before the inherited destroy/free call; it does not prove that destruction is GPU-safe.
2. `upload-packed` fingerprints the actual packed LevelMesh staging range **after** the memcpy/generated fields and before copy recording, including the collision header/nodes. Hardware-buffer `SetData`/`SetSubData` staging writes are similarly covered. Source/destination buffer IDs, byte offsets/length and coverage join to `buffer-copy-recorded`.
3. `buffer-copy-recorded` adds the actual command-buffer allocation ID/handle and unchanged copy offsets/length. Texture loading during LevelMesh packing can flush/replace transfer commands; the copy's **actual recording ID** is authoritative. Do not assign an upload to the current submission column: that column is the latest CPU submission ordinal, not a prediction of its future submission.
4. `submit-buffer` maps that recording ID/handle to the actual submission ordinal, queue, fence handle and existing fence slot. Join the recorded checkpoint pointer/command handle and a returned `gpu-checkpoint-confirmed` separately. A successful submit return is not proof that the GPU consumed all copies.
5. `descriptor-buffer-write-enter` identifies descriptor-set allocation ID/handle, binding/type, buffer ID/handle and offset/range at `WriteDescriptors::Execute`; `descriptor-write-return` follows the unchanged void `vkUpdateDescriptorSets`. An enter without return does not prove application update completion. Dynamic offsets and actual GPU descriptor consumption are not recorded.
6. `bindless-allocate` and `bindless-free-enter` log the **existing PF token** (`index/generation/epoch/span`) with descriptor-set ID. `bindless-write-queued` logs index, available token, image-view and sampler handles. Only allocation starts have PF tokens; interior/fixed slots have zero token fields and must be correlated with allocation spans/reserved-layout semantics. Queued writes are not executed writes. Image handle reuse is not fully instrumented here.
7. `resource-retire` maps buffer ID to retirement-list allocation ID; `retirement-list-release` names transfer/draw list and bytes before the inherited release. The normal wait/reset/delete ordering is unchanged. A failure before the checked fence wait returns still prevents normal frame-list release. Other resource types' retirement and all mapped/persistent writes are not exhaustively captured.

No per-draw trace or new descriptor validation/lifetime scheme is added. Renderer submissions, buffer copy ranges, descriptors, barriers, upload bytes and policy remain unchanged. The invalid diagnostic healthy-frame NV query is removed as described above.

### Bounds and overhead

- At most **8192 resource records per run**, then one `resource-trace-truncated` record; further resource records omitted. The CPU/submission/failure records retain the existing bounded trace path (100,000-record rotated file), independently of this cap. Preserve the run directory before later launches; tail rotation can discard early evidence.
- Full-byte **FNV-1a 64-bit fingerprints**, max **16 MiB per upload / 64 MiB per run**. Larger or budget-exhausted records say `coverage=omitted-budget` with zero hash, never a sampled hash labeled complete. Missing input says `unavailable`. This is a collision-prone diagnostic fingerprint, not SHA-256/proprietary-content proof. It may include padding copied by the inherited uploader. No raw geometry is written.
- Fingerprinting and synchronous record flushing add CPU overhead and can affect timing; enabled mode is not performance-equivalent. Disabled mode performs no hashing, ID increments or resource trace formatting, and the mock copy callback sees exactly the same operation/range.

The fingerprints prove which **CPU staging bytes were prepared** within coverage. They do not prove flush/visibility, final GPU buffer contents, overlapping later writes or the bytes consumed by the faulting shader. Those remain causal evidence gaps.

## Pipeline creation inputs

`pipeline-first-use` keeps its existing event name for consumers but means **creation input**, not execution/first draw. It now includes the prior pipeline/shader packed words and render style plus shader layout DWORD, SpecialEffect, EffectState, VertexFormat, render-pass depth/sample/buffer/format inputs, and `path=full|library-link`. Both full creation and graphics-library link seams are observed. PF canonical key/cache/specialization semantics are unchanged. Background workers retain their thread IDs; packed words are exact-build correlators. The existing shader-cache input key and prelaunch cache SHA-256 remain available; this patch does not supply exact draw-to-SPIR-V mapping, shader instruction decoding or per-draw specialization state.

## Offline verification

Nine focused tests compile real inline query/trace/buffer/command wrappers with injected CPU-only Vulkan callbacks. No loader/GPU is linked or invoked. They cover EXT absent feature/extension/entry point, empty/error/success/incomplete/count caps, NV void zero/changing/oversized counts and valid sTypes/opaque markers, collector exception preserving -4, full known-byte fingerprint, invalid pointer skipped before over-budget hashing, independent record cap/failure preservation, resource IDs/copy/submit records, unchanged disabled copy callbacks and no hashes, PF slot generation reuse, source wiring, manifest preparation with a mocked probe and off-mode environment isolation. The mock process has a ten-second test timeout. This is diagnostic plumbing evidence, not Vulkan validity of the crash route.

Windows MSVC 19.44.35228 / VS Build Tools 17.14.40 ran all nine with AddressSanitizer enabled. Existing eight failure-classifier tests pass. The PF oracle matches its baseline twice: SHA-256 `2f8d95cfe4184dba7b432e701146e1275ef8ff5edc25910a086bd02539028f88`. The separate RelWithDebInfo renderer build is at `C:/ShadeDoomVK/build-cfx006/`; the original captured EXE/PDB hashes remain unchanged. Raw build/test/oracle/guard logs live in `C:/ShadeDoomVK/pf-local-evidence/cfx006-*`; [verification index](evidence/cfx006-offline-verification.json) records identities/results. Required Linux oracle and platform build CI remain a PR gate; no new image/state hardware equivalence is claimed.

Reproduce the focused fixture from the repo in a VS x64 developer shell:

```powershell
$env:CFX_TEST_ASAN = '1'
python -m unittest discover -s tools/pf_oracle/tests -p test_cfx_instrumentation.py -v
```

On Linux the same test discovers `c++` and compiles the legal CPU fixture. The Windows build command is `cmake --build C:/ShadeDoomVK/build-cfx006 --config RelWithDebInfo --target zdoom -- /m:4 /v:minimal`. Never overwrite the captured `source/build-relwithdebinfo` forensic input.

## Remaining acceptance boundary

This supplies observable query outcomes and prepared/upload/descriptor lifetime identities. It does not map any preserved fault to an initiating resource/shader/submission, prove historical/future GPU bytes, repair the crash or clear PF-020. Review/CI and a new human-reviewed physical measurement remain separate. No new loss/reset occurred because no GPU workload was launched.

Initial CI run `36929221484` exposed a test-isolation error: the mocked subprocess intercepted Linux stdlib `platform.platform()` calling `uname -p`. The fixture now supplies synthetic OS identity explicitly; it still mocks the Vulkan probe and cannot call a GPU. Renderer/compiled fixture checks passed in that run; fresh complete CI is required.

Query contracts checked against primary Vulkan references: [EXT fault query](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetDeviceFaultInfoEXT.html), [EXT fault output](https://docs.vulkan.org/refpages/latest/refpages/source/VkDeviceFaultInfoEXT.html), and [NV checkpoint query](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetQueueCheckpointDataNV.html). Both retrieval APIs require a lost device; supplied capacities bound writes and returned counts describe elements actually written. Oversized returned counts in fixtures are defensive malformed-implementation cases, not valid enumeration semantics. Local EXT headers/entry point are retained; current online KHR aliases do not select a different interface.

A read-only check of the six matching-dump timelines confirms one healthy-frame `gpu-checkpoint-smoke queue-returned-zero` record in each, at frame 1/tic 0/submission 3 before the later loss. Their original hashes/lines are preserved in the verification index. This is an additional diagnostic confounder: removal corrects demonstrated API misuse, but its contribution to any crash is unknown. Historical pre-CFX DBP37 failure predates this instrumentation, so this cannot explain that historical failure. Do not call the crash repaired or group incidents based on this correction.
