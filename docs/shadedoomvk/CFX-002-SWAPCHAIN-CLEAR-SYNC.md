# CFX-002 follow-up: swapchain clear synchronization (#86)

The safe combined validation control reported ten `SYNC-HAZARD-WRITE-AFTER-WRITE` messages (duplicate limit) at `vkCmdBeginRenderPass`. The named objects were `SwapchainImageView` and `VkPPRenderPassSetup.RenderPass`. The color `loadOp=CLEAR` write lacked destination color-write access after the attachment layout transition. Pre-fix local run: `cfx-20260925T061257Z-ba0e52633bfa`.

`VkPPRenderPassSetup::CreateRenderPass` now includes `VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT` in the destination access mask of both external-to-subpass dependencies. Both already include `VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT` in the destination stage. Attachment operations, layouts, pipeline and rendering state are unchanged. The [Vulkan synchronization guide](https://docs.vulkan.org/guide/latest/synchronization_examples.html) describes the layout transition as a write that must be synchronized with following attachment writes.

## Safe verification on GTX 1650 SUPER

| Check | Evidence |
| --- | --- |
| RelWithDebInfo `zdoom` build | Passed locally, MSVC 17.14.51 |
| Doom II MAP01 sync validation | `cfx-20260925T072541Z-714a3c74419c`: exit 0, synchronization validation activation confirmed by loader and `CURRENT-VALIDATION-ENABLED` |
| #86 signature | Pre-fix: 10; post-fix: 0; no `SwapchainImageView` validation messages |
| Other sync findings | 10 `SYNC-HAZARD-READ-AFTER-WRITE` messages remain for separate #87 hardware-buffer upload issue |
| Fixed-frame off-mode control | `cfx-20260925T072712Z-9911e966bb8d`: exit 0; identical IWAD, starting config hash, map and 1904 x 1001 resolution to `cfx-20260925T052427Z-bcd26d97aaa4` |
| Image/state | 1,515 of 1,905,904 RGB pixels differ; mean absolute channel delta 0.029615, within preserved off/off variation of 0.029983; LevelMesh object/face counts match at 547/2,408 |
| Device loss/reset | None observed during these safe controls; no matching GPU reset event in the run window |

This proves only the specific #86 synchronization signature is absent on the safe scene. It does not prove all synchronization is valid or establish a historical watchdog cause. No DBP37 MAP01, Sunlust MAP24 or DBP50 crash route was launched.
