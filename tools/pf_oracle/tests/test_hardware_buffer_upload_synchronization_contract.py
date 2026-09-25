#!/usr/bin/env python3
"""Regression coverage for #87 hardware-buffer upload synchronization.

Hosted CI cannot reproduce the physical synchronization-validation workload,
so this pins the production transfer-write publication contract and both
VkHardwareBuffer upload call sites.
"""

from __future__ import annotations

from pathlib import Path
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


class HardwareBufferUploadSynchronizationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = source("src/common/rendering/vulkan/buffers/vk_hwbuffer.cpp")
        cls.publish = function_body(cls.text, "void PublishTransferWrite(")
        cls.set_data = function_body(cls.text, "void VkHardwareBuffer::SetData(")
        cls.set_sub_data = function_body(cls.text, "void VkHardwareBuffer::SetSubData(")

    def test_transfer_write_is_source_scope(self) -> None:
        self.assertIn(
            "barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;",
            self.publish,
        )
        self.assertIn(
            "VK_PIPELINE_STAGE_TRANSFER_BIT,\n\t\tdstStageMask",
            self.publish,
        )

    def test_index_and_vertex_consumers_have_vertex_input_visibility(self) -> None:
        self.assertIn(
            "VK_BUFFER_USAGE_VERTEX_BUFFER_BIT | VK_BUFFER_USAGE_INDEX_BUFFER_BIT",
            self.publish,
        )
        self.assertIn(
            "dstStageMask |= VK_PIPELINE_STAGE_VERTEX_INPUT_BIT;",
            self.publish,
        )
        self.assertIn(
            "dstAccessMask |= VK_ACCESS_VERTEX_ATTRIBUTE_READ_BIT;",
            self.publish,
        )
        self.assertIn(
            "dstAccessMask |= VK_ACCESS_INDEX_READ_BIT;",
            self.publish,
        )

    def test_uniform_and_storage_consumers_have_shader_visibility(self) -> None:
        self.assertIn(
            "VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT | VK_BUFFER_USAGE_STORAGE_BUFFER_BIT",
            self.publish,
        )
        self.assertIn(
            "VK_PIPELINE_STAGE_ALL_GRAPHICS_BIT | VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT",
            self.publish,
        )
        self.assertIn(
            "dstAccessMask |= VK_ACCESS_UNIFORM_READ_BIT;",
            self.publish,
        )
        self.assertIn(
            "dstAccessMask |= VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_SHADER_WRITE_BIT;",
            self.publish,
        )

    def test_later_transfer_use_and_repeated_uploads_are_ordered(self) -> None:
        self.assertIn(
            "VkPipelineStageFlags dstStageMask = VK_PIPELINE_STAGE_TRANSFER_BIT;",
            self.publish,
        )
        self.assertIn(
            "VkAccessFlags dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;",
            self.publish,
        )
        self.assertIn("VK_BUFFER_USAGE_TRANSFER_SRC_BIT", self.publish)
        self.assertIn(
            "dstAccessMask |= VK_ACCESS_TRANSFER_READ_BIT;",
            self.publish,
        )

    def test_dependency_is_scoped_to_uploaded_buffer_range(self) -> None:
        self.assertIn(
            "VkBufferMemoryBarrier barrier = { VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER };",
            self.publish,
        )
        self.assertIn("barrier.buffer = buffer->buffer;", self.publish)
        self.assertIn("barrier.offset = offset;", self.publish)
        self.assertIn("barrier.size = size;", self.publish)
        self.assertIn("barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;", self.publish)
        self.assertIn("barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;", self.publish)
        self.assertNotIn("VK_PIPELINE_STAGE_ALL_COMMANDS_BIT", self.publish)
        self.assertNotIn("debugFullPipelineBarrier", self.publish)

    def test_set_data_publishes_after_copy(self) -> None:
        copy = self.set_data.index("commands->copyBuffer(mStaging.get(), mBuffer.get());")
        publish = self.set_data.index(
            "PublishTransferWrite(commands, mBuffer.get(), mBufferType, 0, mBuffer->size);"
        )
        self.assertLess(copy, publish)

    def test_set_sub_data_publishes_after_copy(self) -> None:
        copy = self.set_sub_data.index(
            "commands->copyBuffer(mStaging.get(), mBuffer.get(), offset, offset, size);"
        )
        publish = self.set_sub_data.index(
            "PublishTransferWrite(commands, mBuffer.get(), mBufferType, offset, size);"
        )
        self.assertLess(copy, publish)


if __name__ == "__main__":
    unittest.main()
