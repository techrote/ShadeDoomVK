"""Actual scope owner execution plus source/queue boundaries; no GPU proof."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture


class SceneGpuScopeTests(unittest.TestCase):
    def test_production_group_push_reports_ownership_and_survives_command_buffer_change(self):
        source = (ROOT / "src/common/rendering/vulkan/commands/vk_commandbuffer.cpp").read_text()
        def function(signature):
            start = source.index(signature)
            begin = source.index("{", start)
            depth = 0
            for offset in range(begin, len(source)):
                depth += (source[offset] == "{") - (source[offset] == "}")
                if depth == 0:
                    return source[start:offset + 1]
            self.fail("unterminated production function")
        prefix = r'''
#include <cassert>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>
using FString = std::string;
bool gpuStatActive = false;
enum { VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT = 1 };
struct Pool {};
struct VulkanCommandBuffer {
    std::vector<unsigned> writes;
    void writeTimestamp(int stage, Pool*, unsigned index) {
        assert(stage == VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT);
        writes.push_back(index);
    }
};
struct Device { bool GraphicsTimeQueries = true; };
struct Framebuffer { Device device; Device* GetDevice() { return &device; } };
struct VkCommandBufferManager {
    enum { MaxTimestampQueries = 100 };
    struct TimestampQuery { FString name; uint32_t startIndex; uint32_t endIndex; };
    Framebuffer framebuffer;
    Framebuffer* fb = &framebuffer;
    std::unique_ptr<Pool> mTimestampQueryPool = std::make_unique<Pool>();
    int mNextTimestampQuery = 0;
    std::vector<size_t> mGroupStack;
    std::vector<TimestampQuery> timeElapsedQueries;
    bool PushGroup(VulkanCommandBuffer*, const FString&);
    void PopGroup(VulkanCommandBuffer*);
};
'''
        suffix = r'''
int main() {
    VkCommandBufferManager manager;
    VulkanCommandBuffer first, afterFlush;
    assert(!manager.PushGroup(&first, "disabled"));
    assert(first.writes.empty() && manager.mGroupStack.empty());
    gpuStatActive = true;
    manager.framebuffer.device.GraphicsTimeQueries = false;
    assert(!manager.PushGroup(&first, "unsupported"));
    manager.framebuffer.device.GraphicsTimeQueries = true;
    assert(manager.PushGroup(&first, "scene.immediate"));
    assert(manager.mGroupStack.size() == 1 && first.writes == std::vector<unsigned>{0});
    manager.PopGroup(&afterFlush);
    assert(manager.mGroupStack.empty() && afterFlush.writes == std::vector<unsigned>{1});
    assert(manager.timeElapsedQueries[0].name == "scene.immediate");
    assert(manager.timeElapsedQueries[0].startIndex == 0 && manager.timeElapsedQueries[0].endIndex == 1);
    manager.PopGroup(&afterFlush);
    assert(afterFlush.writes.size() == 1);
    manager.mNextTimestampQuery = manager.MaxTimestampQueries;
    assert(!manager.PushGroup(&afterFlush, "capacity"));
    assert(manager.mGroupStack.empty());
}
'''
        actual = function("bool VkCommandBufferManager::PushGroup(") + "\n" + function("void VkCommandBufferManager::PopGroup(")
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "scene_group_commands.cpp"
            fixture.write_text(prefix + actual + suffix)
            run_fixture(fixture)

    def test_production_scope_default_off_unavailable_double_close_and_unwinding(self):
        run_fixture(ROOT / "tools/pf_oracle/tests/sdvk_scene_gpu_scope_fixture.cpp",
                    includes=[ROOT / "src/rendering/hwrenderer/diagnostics"])

    def test_scene_span_includes_end_scene_and_excludes_postprocess(self):
        source = (ROOT / "src/rendering/hwrenderer/hw_entrypoint.cpp").read_text()
        begin = source.index("SdvkDiagnostics::ScopedSceneGpuGroup sceneGpu(")
        process = source.index("di->ProcessScene(", begin)
        end_scene = source.index("di->EndDrawScene(", process)
        end = source.index("sceneGpu.End();", end_scene)
        postprocess = source.index("screen->PostProcessScene(", end)
        self.assertLess(begin, process)
        self.assertLess(process, end_scene)
        self.assertLess(end_scene, end)
        self.assertLess(end, postprocess)
        self.assertIn("contextType == HWRenderContextType::MainView && !gl_levelmesh && !gl_raytrace",
                      source[begin:process])
        self.assertEqual(source.count("ScopedSceneGpuGroup sceneGpu("), 1)

    def test_mid_scene_flushes_keep_timestamps_and_final_readback_follows_scene(self):
        source = (ROOT / "src/common/rendering/vulkan/commands/vk_commandbuffer.cpp").read_text()
        flushes = source.split("void VkCommandBufferManager::FlushCommands(VulkanCommandBuffer**", 1)[1].split(
            "void VkCommandBufferManager::DeleteFrameObjects", 1)[0]
        for forbidden in ("resetQueryPool", "mNextTimestampQuery =", "mGroupStack.clear", "timeElapsedQueries.clear"):
            self.assertNotIn(forbidden, flushes)
        self.assertIn("submit.AddWait(VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT", flushes)
        update = (ROOT / "src/common/rendering/vulkan/vk_renderdevice.cpp").read_text().split(
            "void VulkanRenderDevice::Update()", 1)[1].split("bool VulkanRenderDevice::CompileNextShader", 1)[0]
        self.assertLess(update.index("mRenderState->EndFrame()"), update.index("mCommands->WaitForCommands(true)"))
        self.assertLess(update.index("mCommands->WaitForCommands(true)"), update.index("mCommands->UpdateGpuStats()"))

    def test_scope_uses_existing_timestamp_commands_without_extra_wait_or_submit(self):
        source = (ROOT / "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text()
        body = source.split("bool BeginSceneGpuGroup()", 1)[1].split("void BeginFrame()", 1)[0]
        self.assertIn('commands->PushGroup(commands->GetDrawCommands(), "scene.immediate")', body)
        self.assertIn("commands->PopGroup(commands->GetDrawCommands())", body)
        self.assertIn("!GpuTimingRequested() || !screen->IsVulkan()", body)
        for forbidden in ("WaitForCommands", "FlushCommands", "getResults", "resetQueryPool", "vkQueueSubmit"):
            self.assertNotIn(forbidden, body)


if __name__ == "__main__":
    unittest.main()
