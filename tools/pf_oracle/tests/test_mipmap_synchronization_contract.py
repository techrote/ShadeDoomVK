#!/usr/bin/env python3
"""Regression coverage for #83 Vulkan mipmap synchronization scopes.

Hosted CI cannot reproduce the physical Vulkan validation run, so this pins
the production GenerateMipmaps barrier/access contract that the validation
layer identified as incorrect.
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


class MipmapSynchronizationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        text = source("src/common/rendering/vulkan/textures/vk_imagetransition.cpp")
        cls.body = function_body(text, "void VkTextureImage::GenerateMipmaps(VulkanCommandBuffer *cmdbuffer)")

    def test_per_level_barrier_scopes_match_blit_accesses(self) -> None:
        source_to_read = (
            ".AddImage(Image.get(), Layout, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, "
            "VK_ACCESS_TRANSFER_WRITE_BIT, VK_ACCESS_TRANSFER_READ_BIT, "
            "VK_IMAGE_ASPECT_COLOR_BIT, i - 1)"
        )
        undefined_to_write = (
            ".AddImage(Image.get(), VK_IMAGE_LAYOUT_UNDEFINED, "
            "VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 0, "
            "VK_ACCESS_TRANSFER_WRITE_BIT, VK_IMAGE_ASPECT_COLOR_BIT, i)"
        )

        self.assertIn(source_to_read, self.body)
        self.assertIn(undefined_to_write, self.body)

    def test_completed_source_and_final_destination_publish_correct_accesses(self) -> None:
        source_to_shader = (
            ".AddImage(Image.get(), VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, "
            "VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, VK_ACCESS_TRANSFER_READ_BIT, "
            "VK_ACCESS_SHADER_READ_BIT, VK_IMAGE_ASPECT_COLOR_BIT, i - 1)"
        )
        final_write_to_shader = (
            ".AddImage(Image.get(), VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, "
            "VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, VK_ACCESS_TRANSFER_WRITE_BIT, "
            "VK_ACCESS_SHADER_READ_BIT, VK_IMAGE_ASPECT_COLOR_BIT, i - 1)"
        )

        self.assertIn(source_to_shader, self.body)
        self.assertIn(final_write_to_shader, self.body)

    def test_barrier_and_blit_order_is_preserved(self) -> None:
        first_source_transition = self.body.index(
            ".AddImage(Image.get(), Layout, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL"
        )
        destination_transition = self.body.index(
            ".AddImage(Image.get(), VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL"
        )
        blit = self.body.index("cmdbuffer->blitImage(")
        completed_source_transition = self.body.index(
            ".AddImage(Image.get(), VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL"
        )
        final_destination_transition = self.body.index(
            ".AddImage(Image.get(), VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL"
        )

        self.assertLess(first_source_transition, destination_transition)
        self.assertLess(destination_transition, blit)
        self.assertLess(blit, completed_source_transition)
        self.assertLess(completed_source_transition, final_destination_transition)

    def test_known_invalid_access_pairs_do_not_return(self) -> None:
        self.assertNotIn(
            "VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, "
            "VK_ACCESS_TRANSFER_WRITE_BIT, VK_ACCESS_TRANSFER_READ_BIT",
            self.body,
        )
        self.assertNotIn(
            "VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, "
            "VK_ACCESS_TRANSFER_READ_BIT, VK_ACCESS_SHADER_READ_BIT",
            self.body,
        )


if __name__ == "__main__":
    unittest.main()
