"""PF020 observer source contracts and deliberate unsafe-boundary mutations.

These are source/API guards, not compiled C++ or Vulkan evidence. Native build,
validation, completed producer readbacks and independent pixel/cache comparisons
remain required. No engine, compiler or GPU is launched by this module.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
VK = "src/common/rendering/vulkan/"
PATHS = (
    VK + "textures/vk_pfviewdiagnostics.cpp",
    VK + "textures/vk_pfviewdiagnostics.h",
    VK + "vk_renderdevice.cpp",
    VK + "vk_lightprober.cpp",
    VK + "pipelines/vk_renderpass.cpp",
    VK + "shaders/vk_shader.cpp",
    VK + "shaders/vk_shadercache.cpp",
    VK + "shaders/vk_shader.h",
    VK + "pipelines/vk_renderpass.h",
)


def function(text, signature):
    """Bound one unambiguous definition; nested braces are retained verbatim."""
    start = text.find(signature)
    if start < 0 or text.find(signature, start + 1) >= 0:
        raise AssertionError("missing/ambiguous function: " + signature)
    begin = text.index("{", start)
    depth = 0
    for index in range(begin, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if not depth:
                return text[begin:index + 1]
    raise AssertionError("unterminated function: " + signature)


def ordered(text, *tokens):
    position = -1
    for token in tokens:
        position = text.find(token, position + 1)
        if position < 0:
            raise AssertionError("required ordered boundary absent: " + token)


def validate(sources):
    native = sources[PATHS[0]]
    render = sources[PATHS[2]]
    probe = sources[PATHS[3]]
    pipeline = sources[PATHS[4]]
    shader = sources[PATHS[5]]
    cache = sources[PATHS[6]]
    run = function(native, "std::string Run(")
    ordered(run, "GetRenderState()->EndRenderPass()", "WaitForCommands(false)",
            "SourceView = ImageViewBuilder()", "WriteDescriptors().AddCombinedImageSampler")
    ordered(run, "commands->draw(3, 1, 0, 0)", "commands->endRenderPass()",
            "VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL", "commands->copyImageToBuffer(Target.Image->image",
            "WaitForCommands(false); Waited = true", "Staging->Map(0, bytes)",
            "CheckVulkanError(vmaInvalidateAllocation", "WriteFresh(stem +", "Staging->Unmap()")
    assert "copyImageToBuffer(source->image" not in native
    assert "copyImage(source" not in native
    assert "texelFetch(Source,ivec2(gl_FragCoord.xy),0)" in run
    assert "texture(Source" not in run
    assert ".Format(creation.Format)" in run
    assert "VK_FORMAT_R8G8B8A8_UNORM || creation.Format == VK_FORMAT_R16G16B16A16_SFLOAT" in run
    assert ".Usage(VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT)" in run
    assert "source->width <= 1024 && source->height <= 1024" in run
    assert "creation.Captured && creation.Image == source->image" in run
    assert "vert[0] == 0x07230203u && frag[0] == 0x07230203u" in run
    assert "sourceLayout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL" in run
    assert "0, layer, 1, 1" in run
    capture = function(native, "void Capture(")
    ordered(capture, "!Enabled() || !Pf020ViewDiagnostics::FixtureActive()", "state.Captured.insert(semantic)", "SamplingCapture capture(fb)")
    camera = function(render, "void VulkanRenderDevice::RenderTextureView(")
    ordered(camera, "renderFunc(bounds)", "mRenderState->EndRenderPass()",
            "VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL", "SetRenderTarget(&GetBuffers()->SceneColor",
            "CameraCompleted(this, image, tex)", "tex->SetUpdated(true)")
    environment = function(probe, "void VkLightprober::RenderEnvironmentMap(")
    ordered(environment, "renderFunc(bounds, side)", "renderstate->EndRenderPass()", "ProbeFaceCompleted(side, environmentMap.renderTargets[side].View.get())",
            "VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL", "SetRenderTarget(&fb->GetBuffers()->SceneColor", "ProbeCompleted(")
    created = function(probe, "void VkLightprober::CreateEnvironmentMap()")
    assert ".Usage(VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT)" in created
    assert "VK_IMAGE_USAGE_TRANSFER_SRC_BIT" not in created
    active = function(native, "std::string ActiveSceneKey()")
    ordered(active, "std::this_thread::get_id() != State().OwnerThread", 'return "null"', "ActiveSemanticKeyJson()")
    assert "CurrentSceneKeyJson()" not in active
    enabled = function(native, "bool Enabled()")
    ordered(enabled, "state.Enabled = Pf020ViewDiagnostics::Enabled()", "if (!state.Enabled) return false", "-pf020viewcache")
    assert "Require(cache == requestedCache" in enabled
    assert "Require(Under(root, cache)" in enabled
    assert 'filename() == "shadercache.zdsc" || entry.path().filename() == "pipelinecache.zdpc"' in enabled
    assert "remove_all" not in native and "std::filesystem::remove(" not in native
    assert 'M_GetCachePath(true)' not in pipeline and 'M_GetCachePath(true)' not in cache
    ordered(pipeline, 'CacheFilename("pipelinecache.zdpc")', '"before-load"', "builder.InitialData", "builder.Create", '"after-create"')
    ordered(cache, 'CacheFilename("shadercache.zdsc")', '"before-load"', "Load();", '"after-load-return"')
    ordered(cache, "std::vector<uint32_t> code = GetFromCache(key)", "ShaderBinaryLookup(key.GetChars(), !code.empty())")
    ordered(pipeline, "StopWorkerThreads();", "PipelineCache->GetCacheData()", "fw.reset()", '"after-save-close"')
    ordered(function(cache, "void VkShaderCache::Save()"), "fw.reset()", 'CacheFile("shader", "after-save-close", CacheFilename, saved')
    ordered(function(shader, "VkShaderProgram* VkShaderManager::GetFromCache("),
            "generic.find(key.GeneralizedShaderKey())", 'ShaderLookup(key, true, it != generic.end(), "generic-find")')
    assert 'ShaderLookup(key, false, it != specialized.end(), "specialized-find")' in shader
    assert 'PipelineLookup(gkey, PassKey, "generalized-lookup", item != GeneralizedPipelines.end()' in pipeline
    assert 'PipelineLookup(key, PassKey, "specialized-worker-lookup", it != SpecializedPipelines.end()' in pipeline
    assert 'PipelineLookup(key, PassKey, "specialized-main-lookup", item != SpecializedPipelines.end()' in pipeline
    assert "key.CanonicalState()" not in native  # Must also compile literal original seams.
    assert "#ifdef PF020_ORIGINAL_SEAMS" in native
    assert 'freezeAccepted\\\":false' in native and 'performanceMeasured\\\":false' in native
    assert "COLLECTED_PENDING_VALIDATION" in native
    assert 'Quote(state.Prefix + ".cache-events.jsonl")' in native
    assert "argv.argc() == 2" in native
    assert 'FindGameTexture("PFVCAM", ETextureType::MiscPatch, TEXMAN_TryAny | TEXMAN_DontCreate)' in native
    assert "allObservedTasksCompleted" in native
    assert '<< FIRST_USER_SHADER <<' in native and '<< NUM_BUILTIN_SHADERS' in native
    assert "WorkerScheduled(precache)" in pipeline
    assert "MainTaskScheduled()" in pipeline
    ordered(function(pipeline, "void VkRenderPassManager::WorkerThreadMain()"),
            "WorkerStarted()", "task();", "WorkerFinished(failed)")
    ordered(function(pipeline, "void VkRenderPassManager::ProcessMainThreadTasks()"), "task();", "MainTaskCompleted()")


class ObserverContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {path: (ROOT / path).read_text(encoding="utf-8") for path in PATHS}

    def test_current_boundaries(self):
        validate(self.sources)

    def rejected(self, path, old, new):
        mutated = dict(self.sources)
        self.assertIn(old, mutated[path])
        mutated[path] = mutated[path].replace(old, new, 1)
        with self.assertRaises((AssertionError, ValueError)):
            validate(mutated)

    def test_reject_direct_producer_copy(self):
        self.rejected(PATHS[0], "copyImageToBuffer(Target.Image->image", "copyImageToBuffer(source->image")

    def test_reject_approximate_sampling(self):
        self.rejected(PATHS[0], "texelFetch(Source,ivec2(gl_FragCoord.xy),0)", "texture(Source,vec2(.5))")

    def test_reject_format_conversion(self):
        self.rejected(PATHS[0], ".Format(creation.Format)", ".Format(VK_FORMAT_R8G8B8A8_UNORM)")

    def test_reject_missing_invalidate(self):
        self.rejected(PATHS[0], "CheckVulkanError(vmaInvalidateAllocation", "CheckVulkanError(fakeInvalidateAllocation")

    def test_reject_source_layout_guess(self):
        self.rejected(PATHS[0], "sourceLayout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL", "true")

    def test_reject_uncaptured_view_metadata(self):
        self.rejected(PATHS[0], "creation.Captured && creation.Image == source->image", "true")

    def test_reject_missing_spirv(self):
        self.rejected(PATHS[0], "vert[0] == 0x07230203u && frag[0] == 0x07230203u", "true")

    def test_reject_unbounded_extent(self):
        self.rejected(PATHS[0], "source->width <= 1024 && source->height <= 1024", "true")

    def test_reject_worker_frontend_read(self):
        self.rejected(PATHS[0], 'if (std::this_thread::get_id() != State().OwnerThread) return "null";\n\tauto key = Pf020ViewDiagnostics::ActiveSemanticKeyJson()',
                      'auto key = Pf020ViewDiagnostics::ActiveSemanticKeyJson()')

    def test_reject_changing_scene_ids_for_key_counts(self):
        self.rejected(PATHS[0], "ActiveSemanticKeyJson()", "CurrentSceneKeyJson()")

    def test_reject_cache_alias(self):
        self.rejected(PATHS[0], "Require(cache == requestedCache", "Require(true")

    def test_reject_shared_cache(self):
        self.rejected(PATHS[4], 'Pf020VulkanDiagnostics::CacheFilename("pipelinecache.zdpc")', 'M_GetCachePath(true) + "/pipelinecache.zdpc"')

    def test_reject_camera_before_completed_producer(self):
        self.rejected(PATHS[2], "Pf020VulkanDiagnostics::CameraCompleted(this, image, tex);", "/* missing camera observation */")

    def test_reject_missing_probe_readback(self):
        self.rejected(PATHS[3], "Pf020VulkanDiagnostics::ProbeCompleted(fb, environmentMap.cubeimage.get(), environmentMap.cubeview.get());", "/* absent */")

    def test_reject_probe_usage_change(self):
        self.rejected(PATHS[3], ".Usage(VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT)",
                      ".Usage(VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT)")

    def test_reject_unobserved_probe_attachment(self):
        self.rejected(PATHS[3], "ProbeFaceCompleted(side, environmentMap.renderTargets[side].View.get())", "ProbeFaceCompleted(side, nullptr)")

    def test_reject_counterfactual_generalized_lookup(self):
        self.rejected(PATHS[4], 'PipelineLookup(gkey, PassKey, "generalized-lookup", item != GeneralizedPipelines.end()',
                      'PipelineLookup(key, PassKey, "generalized-shadow-equality", true')

    def test_reject_current_only_key_dependency(self):
        self.rejected(PATHS[0], "ShaderFields(key.ShaderKey)", "key.CanonicalState()")

    def test_reject_final_acceptance_claim(self):
        self.rejected(PATHS[0], 'freezeAccepted\\\":false', 'freezeAccepted\\\":true')

    def test_named_shader_projection_complete(self):
        declared = set(re.findall(r"state\.\w+ = (?:static_cast<[^>]+>\()?((?:Layout\.)?\w+)", self.sources[PATHS[7]]))
        fields = function(self.sources[PATHS[0]], "std::string ShaderFields(")
        emitted = set(re.findall(r"PF_FIELD\((\w+)\)", fields)) - {"name"}
        emitted |= {"Layout." + name for name in re.findall(r"PF_LAYOUT\((\w+)\)", fields) if name != "name"}
        emitted |= {"SpecialEffect", "EffectState", "VertexFormat", "Layout.UseRaytracePrecise"}
        self.assertEqual(declared, emitted)

    def test_reject_false_worker_completion(self):
        self.rejected(PATHS[4], "Pf020VulkanDiagnostics::WorkerFinished(failed);", "/* not observed */")

    def test_reject_guessed_user_shader_cutoff(self):
        self.rejected(PATHS[0], '<< FIRST_USER_SHADER <<', '<< 100 <<')

    def test_reject_shader_binary_shadow_cache(self):
        self.rejected(PATHS[6], "ShaderBinaryLookup(key.GetChars(), !code.empty())", "ShaderBinaryLookup(key.GetChars(), true)")


if __name__ == "__main__":
    unittest.main()
