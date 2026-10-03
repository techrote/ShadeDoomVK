"""Actual production planner with fake descriptor/image retirement; no GPU."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


def function_body(path, signature):
    source = (ROOT / path).read_text(encoding='utf-8')
    start = source.index('{', source.index(signature))
    depth = 1
    end = start + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


class LightmapDescriptorPublication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.exe = cls.directory / ('fixture.exe' if os.name == 'nt' else 'fixture')
        compiler = os.environ.get('CFX_CXX') or shutil.which('cl' if os.name == 'nt' else 'c++')
        if not compiler:
            raise RuntimeError('Lightmap fixture needs a VS developer shell or c++')
        source = str(ROOT / 'tools/pf_oracle/tests/cfx_lightmap_publication_fixture.cpp')
        include = str(ROOT / 'src/common/rendering')
        if Path(compiler).name.lower() in ('cl', 'cl.exe'):
            command = [compiler, '/nologo', '/std:c++17', '/EHsc', '/W4', '/UNDEBUG',
                       *(['/fsanitize=address'] if os.environ.get('CFX_TEST_ASAN') == '1' else []),
                       source, '/I' + include, '/Fe:' + str(cls.exe), '/Fo:' + str(cls.directory / 'fixture.obj')]
        else:
            command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-UNDEBUG',
                       source, '-I' + include, '-o', str(cls.exe)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout + compiled.stderr)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def fixture(self, scenario):
        result = subprocess.run([str(self.exe), scenario], capture_output=True, text=True,
                                check=True, timeout=10)
        self.assertEqual(result.stdout.strip(), scenario + ' passed')

    def test_removed_one_to_zero_rewrites_before_old_owner_release(self): self.fixture('retirement')
    def test_growth_equal_shrink_zero_preserve_active_and_typed_fallback_views(self): self.fixture('growth-shrink')
    def test_full_128_pages_never_touch_dynamic_slots(self): self.fixture('full-reservation')
    def test_invalid_counts_capacity_reject_before_any_mutation(self): self.fixture('invalid-ranges')
    def test_failed_execute_keeps_prior_publication_count_and_owners(self): self.fixture('failed-execute')


class LightmapPublicationSourceContract(unittest.TestCase):
    def test_actual_manager_validates_before_writes_and_commits_after_execute(self):
        source = function_body('src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp',
                               'void VkDescriptorSetManager::UpdateBindlessDescriptorSet()')
        self.assertLess(source.index('VkPlanLightmapDescriptorPublication('), source.index('AddCombinedImageSampler('))
        self.assertLess(source.index('if (!publication.IsValid())'), source.index('AddCombinedImageSampler('))
        self.assertIn('page < publication.WritePages', source)
        self.assertIn('publication.UsesFallback(page)', source)
        self.assertIn('GetLightmapFallbackView()', source)
        self.assertIn('GetProbemapFallbackView()', source)
        self.assertLess(source.index('Bindless.Writer.Execute('),
                        source.index('Bindless.PublishedLightmapPages = publication.NextPublishedPages'))

    def test_fallback_reuses_typed_pair_and_clears_before_shader_read_publication(self):
        path = 'src/common/rendering/vulkan/textures/vk_texture.cpp'
        fallback = function_body(path, 'void VkTextureManager::CreateLightmap()')
        self.assertIn('CreateLightmap(1, 1,', fallback)
        self.assertIn('LightmapFallback = std::move(Lightmaps.front())', fallback)
        self.assertNotIn('ImageBuilder()', fallback)  # no extra image allocation
        self.assertIn('VkClearColorValue zero = {}', fallback)
        for member in ('Light', 'Probe'):
            transfer = fallback.index(f'AddImage(&LightmapFallback.{member}, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL')
            clear = fallback.index(f'clearColorImage(LightmapFallback.{member}.Image->image')
            read = fallback.index(f'AddImage(&LightmapFallback.{member}, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL')
            self.assertLess(transfer, clear)
            self.assertLess(clear, read)
        active = function_body(path, 'void VkTextureManager::CreateLightmap(int size, int count,')
        self.assertIn('VK_FORMAT_R16G16B16A16_SFLOAT', active)
        self.assertIn('VK_FORMAT_R16_UINT', active)
        self.assertIn('uint16_t one = 0x3c00', active)  # valid atlas alpha remains unchanged
        self.assertNotIn('LightmapFallback', active)  # map reset must not retire the fallback

    def test_descriptor_publication_precedes_submit_and_fences_precede_owner_release(self):
        path = 'src/common/rendering/vulkan/commands/vk_commandbuffer.cpp'
        flush = function_body(path, 'void VkCommandBufferManager::FlushCommands(bool finish,')
        self.assertLess(flush.index('UpdateBindlessDescriptorSet()'),
                        flush.index('FlushCommands(mFlushCommands.data()'))
        wait = function_body(path, 'void VkCommandBufferManager::WaitForCommands(bool finish, bool uploadOnly)')
        self.assertLess(wait.index('vkWaitForFences('), wait.index('DeleteFrameObjects(uploadOnly)'))
        self.assertLess(wait.index('CheckVulkanError(result, "Could not wait for commands")'),
                        wait.index('DeleteFrameObjects(uploadOnly)'))
        reset = function_body('src/common/rendering/vulkan/textures/vk_imagetransition.h',
                              'void Reset(VulkanRenderDevice* fb)')
        self.assertIn('DrawDeleteList.get()', reset)
        self.assertIn('deletelist->Add(std::move(View))', reset)
        self.assertIn('deletelist->Add(std::move(Image))', reset)


if __name__ == '__main__': unittest.main()
