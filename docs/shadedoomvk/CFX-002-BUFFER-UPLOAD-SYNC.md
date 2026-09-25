# CFX-002 follow-up: hardware-buffer transfer publication (#87)

CFX-002 safe Doom II MAP01 synchronization validation originally reported ten `SYNC-HAZARD-READ-AFTER-WRITE` messages (duplicate limit) for a transfer copy to an index buffer followed by `vkCmdDrawIndexed` (`cfx-20260925T061257Z-ba0e52633bfa`).

PR88 first added range-scoped transfer-write publication after `VkHardwareBuffer::SetData` and `SetSubData`. On current `master` with PR85 merged, local run `cfx-20260925T073550Z-6501c97581d3` reduced the signature to one. A debug-named repeat, `cfx-20260925T073722Z-dbaf240cddca`, identified the remaining resource as `Flatbuffer.IndexBuffer`, uploaded in `VkRenderState::SetShadowData` outside the hardware-buffer methods. A buffer-scoped transfer-write to index-read barrier was added directly after that copy.

## Safe verification on GTX 1650 SUPER

| Check | Evidence |
| --- | --- |
| RelWithDebInfo `zdoom` build | Passed locally, MSVC 17.14.51 |
| Doom II MAP01 sync validation | `cfx-20260925T073908Z-63c0c4aaf262`: exit 0, Khronos synchronization validation activation confirmed by loader and `CURRENT-VALIDATION-ENABLED` |
| #87 signature | Pre-fix 10; hardware-buffer-only fix 1; final fix 0 |
| Other sync findings | Ten swapchain-clear write-after-write reports remain on PR88 alone; independently fixed in open PR89 for #86. No new error type appeared. |
| Fixed-frame off-mode control | `cfx-20260925T073946Z-90f007bdca4f`: exit 0; identical IWAD, starting config hash, map and 1904 x 1001 resolution to pre-fix `cfx-20260925T052427Z-bcd26d97aaa4` |
| Image/state | 1,949 of 1,905,904 RGB pixels differ; mean absolute channel delta 0.027905, within preserved off/off variation of 0.029983; LevelMesh object/face counts match at 547/2,408 |
| Device loss/reset | None observed; no matching system or application GPU reset event in the safe-run window |

The barriers publish uploaded bytes to their actual consumers without changing buffer contents, allocation policy or render output semantics. The [Vulkan synchronization guide](https://docs.vulkan.org/guide/latest/synchronization_examples.html) describes a transfer-write to vertex-input memory dependency on a unified graphics/transfer queue.

This proves only the #87 signature is absent on the safe scene. It does not prove all synchronization is valid or establish a historical watchdog cause. No DBP37 MAP01, Sunlust MAP24 or DBP50 crash route was launched.
