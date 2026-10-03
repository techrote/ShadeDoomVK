"""Pin the dependency required by CFX007's hardware INDEX_READ hazard.

Source contract only; the independent synchronization-validation fixture is
the runtime oracle. Check both AS and software-traversal branches so adding
ray-query support cannot reintroduce the same mesh input visibility hole.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]


def publications(source):
    begin = source.split('void VkLevelMesh::BeginFrame()', 1)[1].split('void VkLevelMesh::UploadMeshes()', 1)[0]
    return re.findall(r'\.AddMemory\(VK_ACCESS_TRANSFER_WRITE_BIT, ([^)]+)\)\s*\.Execute\([^;]+VK_PIPELINE_STAGE_TRANSFER_BIT, ([^)]+)\);', begin)


class LevelMeshUploadSync(unittest.TestCase):
    def test_both_upload_paths_publish_mesh_inputs(self):
        source = (ROOT / 'src/common/rendering/vulkan/vk_levelmesh.cpp').read_text()
        dependencies = publications(source)
        self.assertEqual(len(dependencies), 2)
        for access, stages in dependencies:
            for bit in ('VK_ACCESS_SHADER_READ_BIT', 'VK_ACCESS_VERTEX_ATTRIBUTE_READ_BIT', 'VK_ACCESS_INDEX_READ_BIT'):
                self.assertIn(bit, access)
            for bit in ('VK_PIPELINE_STAGE_VERTEX_INPUT_BIT', 'VK_PIPELINE_STAGE_VERTEX_SHADER_BIT', 'VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT'):
                self.assertIn(bit, stages)
        self.assertTrue(any('VK_ACCESS_ACCELERATION_STRUCTURE_READ_BIT_KHR' in access and 'VK_PIPELINE_STAGE_ACCELERATION_STRUCTURE_BUILD_BIT_KHR' in stages for access, stages in dependencies))


if __name__ == '__main__':
    unittest.main()
