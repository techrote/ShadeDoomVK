#pragma once

class VkRenderState;
class VulkanRenderDevice;
class VulkanPipeline;

// Explicit -pf113observe <fresh-prefix> only. These observe the real immediate
// scene command/publication route; they never select probes or defer baking.
namespace Pf113ProbeDiagnostics
{
bool Observing();
void BoundPipeline(VkRenderState* state, VulkanPipeline* pipeline);
void DrawEmitted(VkRenderState* state, int count, bool indexed);
void Publication(VulkanRenderDevice* device, bool completed);
}
