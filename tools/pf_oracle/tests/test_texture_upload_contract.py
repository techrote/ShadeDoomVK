#!/usr/bin/env python3
"""Focused PF-005 source-contract coverage for Vulkan texture uploads.

The hosted matrix has no deterministic GPU/IWAD workload, so the compiled
staging planner fixture is paired with source-route assertions for lifetime,
ordering and quality-policy invariants owned by PF-005.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def function_body(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError(f"missing function signature: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise AssertionError(f"missing function body: {signature}")

    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1 : index]
    raise AssertionError(f"unterminated function body: {signature}")


class TextureUploadContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.texture_h = source("src/common/rendering/vulkan/textures/vk_texture.h")
        cls.texture_cpp = source("src/common/rendering/vulkan/textures/vk_texture.cpp")
        cls.hw_h = source("src/common/rendering/vulkan/textures/vk_hwtexture.h")
        cls.hw_cpp = source("src/common/rendering/vulkan/textures/vk_hwtexture.cpp")
        cls.staging_h = source("src/common/rendering/hwrenderer/data/hw_uploadstaging.h")

    def test_reset_advances_target_generation_and_destruction_cancels_all_owner_tickets(self) -> None:
        reset = function_body(self.hw_cpp, "void VkHardwareTexture::Reset()")
        destructor = function_body(self.hw_cpp, "VkHardwareTexture::~VkHardwareTexture()")
        cancel_start = self.texture_h.index("void CancelUploads(VkHardwareTexture* texture)")
        cancel_end = self.texture_h.index("void RecordTargetUploadStale()", cancel_start)
        cancel = self.texture_h[cancel_start:cancel_end]

        self.assertIn("mUploadEpoch.Invalidate();", reset)
        self.assertIn("textureManager->CancelUploads(this);", destructor)
        self.assertLess(
            destructor.index("textureManager->CancelUploads(this);"),
            destructor.index("textureManager->RemoveTexture(this);")
        )
        self.assertIn("for (auto it = PendingUploads.begin(); it != PendingUploads.end();)", cancel)
        self.assertIn("it = PendingUploads.erase(it);", cancel)
        self.assertNotIn("break;", cancel)

    def test_async_completion_consumes_manager_ticket_before_target_dereference(self) -> None:
        body = function_body(
            self.hw_cpp,
            "void VkHardwareTexture::CreateImage(VkTextureImage* image, FTexture *tex, int translation, int flags)",
        )
        self.assertIn("CreateUploadTicket(this, mUploadEpoch.Snapshot())", body)
        self.assertIn("textureManager->CheckUploadTicket(uploadTicket)", body)
        self.assertIn("mUploadEpoch.Validate(uploadTicket.TargetEpoch)", body)
        self.assertLess(
            body.index("textureManager->CheckUploadTicket(uploadTicket)"),
            body.index("mUploadEpoch.Validate(uploadTicket.TargetEpoch)"),
        )
        self.assertIn("textureManager->RecordTargetUploadStale();", body)
        self.assertIn("textureManager->RecordUploadCompleted();", body)

    def test_ticket_carries_manager_and_target_pf002_epochs(self) -> None:
        self.assertIn("FRendererEpochToken ManagerEpoch;", self.texture_h)
        self.assertIn("FRendererEpochToken TargetEpoch;", self.texture_h)
        self.assertIn("ticket.ManagerEpoch = AsyncUploadEpoch.Snapshot();", self.texture_h)
        self.assertIn("ticket.TargetEpoch = targetEpoch;", self.texture_h)
        self.assertIn("AsyncUploadEpoch.Validate(ticket.ManagerEpoch)", self.texture_h)
        self.assertIn("FRendererEpoch mUploadEpoch;", self.hw_h)

    def test_worker_exception_and_shutdown_epoch_paths_remain_intact(self) -> None:
        stop = function_body(self.texture_cpp, "void VkTextureManager::StopWorkerThread()")
        worker = function_body(self.texture_cpp, "void VkTextureManager::WorkerThreadMain()")
        self.assertIn("AsyncUploadEpoch.Invalidate();", stop)
        self.assertIn("Worker.Thread.join();", stop)
        self.assertIn("Worker.WorkerTasks.clear();", stop)
        self.assertIn("Worker.MainTasks.clear();", stop)
        self.assertIn("std::rethrow_exception(exception)", worker)

    def test_arena_waits_before_wrapped_bytes_are_mapped(self) -> None:
        body = function_body(
            self.hw_cpp,
            "VkTextureManager::FUploadStagingAllocation VkTextureManager::StageTextureUpload(const void* pixels, std::size_t size)",
        )
        self.assertIn("UploadStagingPlanner.Acquire(size, 4)", body)
        self.assertIn("if (slice.RequiresWait)", body)
        self.assertIn("WaitForCommands(false, true);", body)
        self.assertIn("UploadStagingBuffer->Map(slice.Offset, slice.Size)", body)
        self.assertLess(
            body.index("WaitForCommands(false, true);"),
            body.index("UploadStagingBuffer->Map(slice.Offset, slice.Size)"),
        )
        self.assertIn("VkTextureManager.UploadStagingArena", body)
        self.assertIn("VkTextureManager.OversizeUploadStagingBuffer", body)
        self.assertIn("static constexpr std::size_t UploadStagingCapacity = 64u * 1024u * 1024u;", self.texture_h)

    def test_oversize_fallback_is_bounded_by_an_immediate_transfer_wait(self) -> None:
        finish = function_body(
            self.hw_cpp,
            "void VkTextureManager::FinishTextureUpload(const FUploadStagingAllocation& allocation)",
        )
        self.assertIn("if (allocation.Dedicated)", finish)
        self.assertIn("WaitForCommands(false, true);", finish)
        self.assertIn("DedicatedWaits++", finish)

    def test_create_and_completion_uploads_share_arena_without_changing_mip_policy(self) -> None:
        create = function_body(
            self.hw_cpp,
            "void VkHardwareTexture::CreateTexture(VkTextureImage* image, int w, int h, int pixelsize, VkFormat format, const void *pixels, bool mipmap)",
        )
        upload = function_body(
            self.hw_cpp,
            "void VkHardwareTexture::UploadTexture(VkTextureImage* image, int w, int h, int pixelsize, VkFormat format, const void* pixels, bool mipmap)",
        )
        for body in (create, upload):
            self.assertIn("StageTextureUpload", body)
            self.assertIn("region.bufferOffset = staging.Offset;", body)
            self.assertIn("copyBufferToImage(staging.Buffer->buffer", body)
            self.assertIn("if (mipmap) image->GenerateMipmaps(cmdbuffer);", body)
            self.assertIn("FinishTextureUpload(staging);", body)
        self.assertNotIn("VkHardwareTexture.mStagingBuffer", self.hw_cpp)

    def test_indexed_truecolor_and_canvas_format_policy_is_unchanged(self) -> None:
        create_image = function_body(
            self.hw_cpp,
            "void VkHardwareTexture::CreateImage(VkTextureImage* image, FTexture *tex, int translation, int flags)",
        )
        self.assertIn("bool indexed = flags & CTF_Indexed;", create_image)
        self.assertIn("indexed ? VK_FORMAT_R8_UNORM : VK_FORMAT_B8G8R8A8_UNORM", create_image)
        self.assertIn("VK_FORMAT_R32G32B32A32_SFLOAT : VK_FORMAT_R8G8B8A8_UNORM", create_image)
        self.assertIn("flags | CTF_ProcessData", create_image)

    def test_staging_planner_has_no_vulkan_or_gameplay_dependency(self) -> None:
        self.assertNotIn("Vulkan", self.staging_h)
        self.assertNotIn("FTexture", self.staging_h)
        self.assertNotIn("game", self.staging_h.lower())

    def test_compiled_staging_boundary_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "upload-staging-fixture"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Isrc/common/rendering/hwrenderer/data",
                    "tools/pf_oracle/tests/upload_staging_fixture.cpp",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
