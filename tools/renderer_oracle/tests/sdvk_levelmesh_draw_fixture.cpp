// SPDX-License-Identifier: GPL-3.0-or-later
// CPU services for extracted production submission/diagnostic functions.
// No renderer, Vulkan device or GPU work is created by this fixture.
#include <atomic>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include "hw_sdvkdiagnostics.h"
#include "hw_sdvkdiagnosticcore.h"
#include "vk_keyidentity.h"
#include "levelmesh_surface.inc"

using namespace SdvkObservation;
template<class T> using TArray = std::vector<T>;
struct MeshBufferRange
{
    int Start = 0, End = 0;
    int Count() const { return End - Start; }
};
struct VkPipelineKey
{
    VkKeyIdentity::PipelineState Fields;
    VkKeyIdentity::PipelineState CanonicalState() const { return Fields; }
};
#include "levelmesh_serializers.inc"

static std::vector<std::string> Events, Records, PipelineIDs;
static int ContextReads = 0, ImmediateCalls = 0;
static bool ContextFailure = false;
static std::string Failure;

static std::string Array(const std::vector<std::string>& values)
{
    std::string result = "[";
    for (const auto& value : values)
    {
        if (result.size() > 1) result += ',';
        result += value;
    }
    return result + ']';
}

class VulkanCommandBuffer
{
public:
    VkPipelineKey Bound;
    void drawIndexed(int count, int instances, int firstIndex, int vertexOffset, int firstInstance)
    {
        if (instances != 1 || vertexOffset != 0 || firstInstance != 0)
            throw std::logic_error("Unexpected production indexed command arguments");
        Events.push_back(Object().Str("event", "draw").Int("first_index", firstIndex)
            .Int("draw_count", count).Raw("bound_key", Pipeline(Bound)).Json());
    }
};

class VulkanRenderDevice
{
public:
    std::vector<VkPipelineKey> Keys = std::vector<VkPipelineKey>(4);
    const VkPipelineKey& GetLevelMeshPipelineKey(int pipelineID)
    {
        PipelineIDs.push_back(std::to_string(pipelineID));
        return Keys.at(pipelineID);
    }
};

class VkRenderState
{
public:
    VulkanRenderDevice* fb = nullptr;
    VulkanCommandBuffer* mCommandBuffer = nullptr;
    VkPipelineKey mPipelineKey;
    struct Target
    {
        int Width = 640, Height = 480, Format = 44, Samples = 4, DrawBuffers = 2;
        const void* DepthStencil = this;
    } mRenderTarget;
    // Deliberately no immediate material/probe/surface uniform services: a
    // callback that borrows their stale state will fail to compile here.
    void ApplyLevelMeshPipeline(VulkanCommandBuffer* command, VkPipelineKey key,
                               bool masked, bool noFragmentShader)
    {
        Events.push_back(Object().Str("event", "apply").Raw("seed_key", Pipeline(key)).Json());
        // Explicit application double: alter seed state before the actual
        // production loop submits the command and invokes its observer.
        key.Fields.CullMode = 2;
        key.Fields.ColorMask = 5;
        key.Fields.ShaderKey.UseLevelMesh = 1;
        key.Fields.ShaderKey.ShadeVertex = 1;
        key.Fields.ShaderKey.GBufferPass = mRenderTarget.DrawBuffers > 1;
        key.Fields.ShaderKey.AlphaTestOnly = masked && noFragmentShader;
        key.Fields.ShaderKey.NoFragmentShader = noFragmentShader && !masked;
        mPipelineKey = key;
        command->Bound = key;
    }
#include "levelmesh_declaration.inc"
};

namespace SdvkDiagnostics
{
std::atomic<bool> EnabledFlag{false}, StateFlag{false}, GpuFlag{false};
std::string CurrentContextJson()
{
    ++ContextReads;
    if (ContextFailure) throw std::runtime_error("fixture current context failure");
    return Object().Bool("available", true).Int("fixture_id", 17).Json();
}
void Emit(const char* kind, const std::string& object, bool deduplicate)
{
    Events.push_back(Object().Str("event", "observe").Str("kind", kind).Json());
    Records.push_back(Object().Str("kind", kind).Raw("data", object)
        .Bool("deduplicate", deduplicate).Json());
}
void Fail(const char* message)
{
    Failure = message;
    StateFlag.store(false);
}
void VulkanDraw(VkRenderState*, int, bool)
{
    ++ImmediateCalls;
    throw std::logic_error("LevelMesh cannot borrow immediate draw observation");
}
}

#include "levelmesh_access.inc"
#include "levelmesh_callback.inc"
#include "levelmesh_loop.inc"

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    try
    {
        const std::string scenario = argv[1];
        if (scenario != "side" && scenario != "flat" && scenario != "empty" && scenario != "zero" &&
            scenario != "off" && scenario != "timing" && scenario != "failure")
            throw std::logic_error("Unknown CPU fixture scenario");
        const bool observe = scenario != "off" && scenario != "timing";
        SdvkDiagnostics::EnabledFlag.store(scenario != "off");
        SdvkDiagnostics::StateFlag.store(observe);
        SdvkDiagnostics::GpuFlag.store(scenario == "timing");
        ContextFailure = scenario == "failure";
        VulkanRenderDevice device;
        // Keep pipeline groups distinguishable while leaving overridden seed
        // fields different from the values installed by application.
        device.Keys[1].Fields.ShaderKey.VertexFormat = 7;
        device.Keys[3].Fields.ShaderKey.VertexFormat = 11;
        VulkanCommandBuffer commands;
        VkRenderState state;
        state.fb = &device;
        state.mCommandBuffer = &commands;
        const auto surface = scenario == "flat" ? LevelMeshDrawSurface::Flat : LevelMeshDrawSurface::Side;
        if (scenario == "empty")
        {
            state.DrawLevelMeshList({}, surface, false, false);
            state.DrawLevelMeshList({{}, {}, {}}, surface, false, false);
        }
        else if (scenario == "zero")
            state.DrawLevelMeshList({{{11, 11}}}, surface, false, false);
        else
            state.DrawLevelMeshList({{}, {{7, 13}, {40, 43}}, {}, {{90, 102}}},
                                   surface, scenario == "flat", scenario == "flat");
        if (!observe)
        {
            // Independently exercise the production wrapper's dormant gate;
            // any attempt to dereference the state pointer is invalid.
            SdvkDiagnostics::VulkanLevelMeshDraw(nullptr, 123, 9, surface);
        }
        std::cout << Object().Raw("events", Array(Events)).Raw("records", Array(Records))
            .Raw("pipeline_ids", Array(PipelineIDs)).Int("context_reads", ContextReads)
            .Int("immediate_calls", ImmediateCalls).Str("error", Failure).Json() << '\n';
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 11;
    }
}
