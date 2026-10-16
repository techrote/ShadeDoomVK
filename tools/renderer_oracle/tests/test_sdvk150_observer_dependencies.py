"""SDVK-150 observer include ownership; source contracts, not native execution.

The actual Vulkan manager dereferences need its complete definition in this
translation unit. CI's full compiler matrix is authoritative for native builds.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp"
OWNER_HEADER = '#include "vulkan/textures/vk_texture.h"'
COMMENTS = re.compile(r'//[^\n]*|/\*.*?\*/', re.S)


def validate_owner_dependency(text: str) -> None:
    active = COMMENTS.sub("", text)
    boundary = active.index("void ProbeBuilderLifecycle(")
    prefix = active[:boundary]
    if re.search(r'^\s*#\s*include\s+"vulkan/textures/vk_texture\.h"\s*$',
                 prefix, re.M) is None:
        raise AssertionError("probe-observer-missing-complete-texture-owner")


class ProbeObserverDependencyTests(unittest.TestCase):
    def test_actual_observer_declares_its_complete_resource_owner(self):
        text = SOURCE.read_text(encoding="utf-8")
        validate_owner_dependency(text)
        # This is a real ownership dependency, not an unused include policy.
        for member in ("GetLightProbeEpoch()", "Irradiancemaps.size()", "Prefiltermaps.size()"):
            self.assertIn("textures->" + member, text)
        manager = (ROOT / "src/common/rendering/vulkan/textures/vk_texture.h").read_text()
        self.assertIn("class VkTextureManager\n{", manager)

    def test_missing_commented_and_late_includes_fail_for_the_same_reason(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertEqual(text.count(OWNER_HEADER), 1)
        for name, replacement in (("missing", ""), ("commented", "// " + OWNER_HEADER),
                                  ("forward-only", "class VkTextureManager;")):
            with self.subTest(case=name):
                mutated = text.replace(OWNER_HEADER, replacement, 1)
                with self.assertRaisesRegex(AssertionError, "missing-complete-texture-owner"):
                    validate_owner_dependency(mutated)
        with self.subTest(case="late"):
            mutated = text.replace(OWNER_HEADER, "", 1) + "\n" + OWNER_HEADER + "\n"
            with self.assertRaisesRegex(AssertionError, "missing-complete-texture-owner"):
                validate_owner_dependency(mutated)


if __name__ == "__main__":
    unittest.main()
