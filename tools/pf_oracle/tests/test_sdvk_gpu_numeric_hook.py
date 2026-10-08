"""Execute the production GPU-result hook with host-only query/device doubles.

The extracted C++ function is compiled, rather than reimplementing timestamp
math in Python. This verifies consumer arithmetic, availability and opt-in
behavior; it is not evidence of Vulkan execution or physical GPU timings.
"""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture


def update_function(source):
    signature = "void VkCommandBufferManager::UpdateGpuStats()"
    start = source.index(signature)
    if source.find(signature, start + 1) >= 0:
        raise AssertionError("ambiguous UpdateGpuStats definition")
    begin = source.index("{", start)
    depth = 0
    for offset in range(begin, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return source[start:offset + 1]
    raise AssertionError("unterminated UpdateGpuStats definition")


PREFIX = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <initializer_list>
#include <limits>
#include <string>
#include <utility>
#include <vector>
using std::max;

struct FString
{
    std::string value;
    FString() = default;
    FString(const char* text) : value(text) {}
    FString& operator=(const char* text) { value = text; return *this; }
    FString& operator+=(const FString& text) { value += text.value; return *this; }
    const char* GetChars() const { return value.c_str(); }
    void Format(const char* format, const char* name, double elapsed)
    {
        char buffer[256];
        std::snprintf(buffer, sizeof(buffer), format, name, elapsed);
        value = buffer;
    }
};

bool gpuStatActive = false;
bool keepGpuStatActive = false;
FString gpuStatOutput;
namespace SdvkDiagnostics
{
    bool requested = false;
    std::vector<std::pair<std::string, double>> groups;
    std::vector<std::string> unavailable;
    bool GpuTimingRequested() { return requested; }
    void GpuGroup(const char* name, double elapsed) { groups.emplace_back(name, elapsed); }
    void GpuUnavailable(const char* reason) { unavailable.emplace_back(reason); }
}

enum { VK_QUERY_RESULT_64_BIT = 1, VK_QUERY_RESULT_WAIT_BIT = 2 };
struct QueryPool
{
    std::vector<uint64_t> values;
    bool ready = true;
    unsigned reads = 0;
    bool getResults(unsigned first, unsigned count, size_t bytes, void* target,
                    size_t stride, int flags)
    {
        ++reads;
        assert(first == 0 && bytes == sizeof(uint64_t) * count);
        assert(stride == sizeof(uint64_t));
        assert(flags == (VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT));
        assert(count <= values.size());
        if (ready) std::copy_n(values.begin(), count, static_cast<uint64_t*>(target));
        return ready;
    }
};
struct QueueFamily { uint32_t timestampValidBits = 64; };
struct Limits { double timestampPeriod = 1.0; };
struct Properties { Limits limits; };
struct PropertySet { struct Properties Properties; };
struct PhysicalDevice
{
    PropertySet Properties;
    std::vector<QueueFamily> QueueFamilies = { QueueFamily{} };
};
struct Device
{
    bool GraphicsTimeQueries = true;
    int GraphicsFamily = 0;
    struct PhysicalDevice PhysicalDevice;
};
struct VulkanRenderDevice
{
    Device device;
    Device* GetDevice() { return &device; }
};
struct VkCommandBufferManager
{
    enum { MaxTimestampQueries = 100 };
    struct TimestampQuery { FString name; uint32_t startIndex; uint32_t endIndex; };
    VulkanRenderDevice* fb = nullptr;
    QueryPool* mTimestampQueryPool = nullptr;
    int mNextTimestampQuery = 0;
    std::vector<TimestampQuery> timeElapsedQueries;
    std::vector<size_t> mGroupStack;
    void UpdateGpuStats();
};
'''


SUFFIX = r'''
struct Fixture
{
    VulkanRenderDevice fb;
    QueryPool pool;
    VkCommandBufferManager commands;
    Fixture()
    {
        SdvkDiagnostics::requested = true;
        SdvkDiagnostics::groups.clear();
        SdvkDiagnostics::unavailable.clear();
        gpuStatActive = true;
        keepGpuStatActive = false;
        commands.fb = &fb;
        commands.mTimestampQueryPool = &pool;
        SetQueries();
    }
    void SetQueries()
    {
        pool.values = { 100, 1234667 };
        commands.timeElapsedQueries = { { "postprocess.bloom", 0, 1 } };
        commands.mNextTimestampQuery = 2;
    }
    void ClearQueries()
    {
        commands.timeElapsedQueries.clear();
        commands.mNextTimestampQuery = 0;
    }
    void ExpectUnavailable(const char* reason)
    {
        commands.UpdateGpuStats();
        assert(SdvkDiagnostics::groups.empty());
        assert(SdvkDiagnostics::unavailable == std::vector<std::string>{reason});
    }
};

int main()
{
    {
        Fixture f;
        f.ClearQueries();
        SdvkDiagnostics::requested = false;
        gpuStatActive = false;
        f.commands.UpdateGpuStats();
        assert(!gpuStatActive && !keepGpuStatActive);
        assert(f.pool.reads == 0);
        assert(SdvkDiagnostics::groups.empty() && SdvkDiagnostics::unavailable.empty());
    }
    {
        Fixture f;
        SdvkDiagnostics::requested = false;
        keepGpuStatActive = true;
        f.commands.UpdateGpuStats();
        assert(gpuStatActive && !keepGpuStatActive && f.pool.reads == 1);
        assert(gpuStatOutput.value == "postprocess.bloom=1.23 ms\n");
        assert(SdvkDiagnostics::groups.empty() && SdvkDiagnostics::unavailable.empty());
    }
    {
        Fixture f;
        f.commands.UpdateGpuStats();
        assert(f.pool.reads == 1 && gpuStatActive && !keepGpuStatActive);
        assert(SdvkDiagnostics::groups.size() == 1);
        assert(SdvkDiagnostics::groups[0].first == "postprocess.bloom");
        assert(std::abs(SdvkDiagnostics::groups[0].second - 1.234567) < 1e-12);
        assert(gpuStatOutput.value == "postprocess.bloom=1.23 ms\n");
        assert(f.commands.timeElapsedQueries.empty() && f.commands.mGroupStack.empty());
        SdvkDiagnostics::requested = false;
        f.SetQueries();
        f.commands.UpdateGpuStats();
        assert(!gpuStatActive && SdvkDiagnostics::groups.size() == 1);
    }
    {
        Fixture f;
        f.pool.values = { 100, 200, 260, 410 };
        f.commands.timeElapsedQueries = { { "outer", 0, 3 }, { "inner", 1, 2 } };
        f.commands.mNextTimestampQuery = 4;
        f.commands.UpdateGpuStats();
        assert(SdvkDiagnostics::groups.size() == 2 && f.pool.reads == 1);
        assert(SdvkDiagnostics::groups[0].first == "outer");
        assert(SdvkDiagnostics::groups[1].first == "inner");
        assert(std::abs(SdvkDiagnostics::groups[0].second - 0.00031) < 1e-12);
        assert(std::abs(SdvkDiagnostics::groups[1].second - 0.00006) < 1e-12);
    }
    for (uint32_t bits : { 36u, 64u })
    {
        Fixture f;
        f.fb.device.PhysicalDevice.QueueFamilies[0].timestampValidBits = bits;
        const uint64_t mask = bits == 64 ? std::numeric_limits<uint64_t>::max() : (uint64_t(1) << bits) - 1;
        f.pool.values = { mask - 2, 4 };
        f.fb.device.PhysicalDevice.Properties.Properties.limits.timestampPeriod = 2.5;
        f.commands.UpdateGpuStats();
        assert(SdvkDiagnostics::unavailable.empty() && SdvkDiagnostics::groups.size() == 1);
        assert(std::abs(SdvkDiagnostics::groups[0].second - 0.0000175) < 1e-12);
    }
    {
        Fixture f;
        f.ClearQueries();
        gpuStatActive = false;
        f.ExpectUnavailable("gpu_timestamp_profiler_warmup");
        assert(gpuStatActive && f.pool.reads == 0);
        f.SetQueries();
        f.commands.UpdateGpuStats();
        assert(SdvkDiagnostics::groups.size() == 1);
        assert(SdvkDiagnostics::unavailable.size() == 1);
    }
    {
        Fixture f;
        f.ClearQueries();
        f.fb.device.GraphicsTimeQueries = false;
        f.ExpectUnavailable("graphics_queue_timestamp_queries_unsupported");
        assert(f.pool.reads == 0);
    }
    {
        Fixture f;
        f.fb.device.PhysicalDevice.QueueFamilies[0].timestampValidBits = 0;
        f.ExpectUnavailable("graphics_queue_timestamp_queries_unsupported");
    }
    for (uint32_t bits : { 35u, 65u })
    {
        Fixture f;
        f.fb.device.PhysicalDevice.QueueFamilies[0].timestampValidBits = bits;
        f.ExpectUnavailable("graphics_queue_timestamp_metadata_invalid");
    }
    for (int family : { -1, 1 })
    {
        Fixture f;
        f.fb.device.GraphicsFamily = family;
        f.ExpectUnavailable("graphics_queue_timestamp_metadata_invalid");
    }
    for (double period : { 0.0, -1.0, std::numeric_limits<double>::infinity(),
                           std::numeric_limits<double>::quiet_NaN() })
    {
        Fixture f;
        f.fb.device.PhysicalDevice.Properties.Properties.limits.timestampPeriod = period;
        f.ExpectUnavailable("graphics_queue_timestamp_metadata_invalid");
    }
    {
        Fixture f;
        f.pool.ready = false;
        f.ExpectUnavailable("gpu_timestamp_query_results_unavailable");
        assert(f.pool.reads == 1 && gpuStatOutput.value.empty());
    }
    {
        Fixture f;
        f.ClearQueries();
        f.ExpectUnavailable("no_gpu_timestamp_groups_recorded");
    }
    {
        Fixture f;
        f.commands.timeElapsedQueries[0].endIndex = 0;
        f.ExpectUnavailable("gpu_timestamp_groups_incomplete_or_capacity_reached");
    }
    {
        Fixture f;
        f.commands.mGroupStack.push_back(0);
        f.ExpectUnavailable("gpu_timestamp_groups_incomplete_or_capacity_reached");
    }
    {
        Fixture f;
        f.pool.values.resize(VkCommandBufferManager::MaxTimestampQueries, 0);
        f.commands.mNextTimestampQuery = VkCommandBufferManager::MaxTimestampQueries;
        f.ExpectUnavailable("gpu_timestamp_groups_incomplete_or_capacity_reached");
    }
    std::puts("SDVK GPU numeric hook: host-only positive and negative cases passed");
}
'''


class SdvkGpuNumericHookTests(unittest.TestCase):
    def test_production_result_consumer_with_positive_and_negative_queries(self):
        source = (ROOT / "src/common/rendering/vulkan/commands/vk_commandbuffer.cpp").read_text(encoding="utf-8")
        body = update_function(source)
        self.assertEqual(body.count("mTimestampQueryPool->getResults("), 1)
        for extra_wait in ("WaitForCommands(", "vkWaitForFences(", "vkDeviceWaitIdle("):
            self.assertNotIn(extra_wait, body)
        with tempfile.TemporaryDirectory(prefix="sdvk-gpu-numeric-") as directory:
            fixture = Path(directory) / "sdvk_gpu_numeric_fixture.cpp"
            fixture.write_text(PREFIX + body + SUFFIX, encoding="utf-8")
            result = run_fixture(fixture, root=ROOT, capture_output=True)
        self.assertIn("positive and negative cases passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
