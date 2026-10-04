"""PF113 exact source extraction for bounded CPU services, never a shader substitute.

The retained original is pinned data. Current producer bodies and shader helpers
are read from the checkout. C++ vector casts/unused annotation, GLSL scalar/vector
services, and passive observers are the only adapters; Vulkan execution is absent.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
ORIGINAL = ROOT / 'tools/pf_oracle/fixtures/pf113-original'
PINS = {
    'original_probe_fixture.cpp': '03baf5054f062ee0bd0ab45c898f43cb0702c659ff560524f34bca1d9fa22363',
    'extracted_original.hpp': 'c8dea5f3bff283ca026cdd88ed3f890e620c7a2952d33b5627e34f0732ab2af8',
    'source_constants.hpp': '3ffaba622bff816e62371518bbeaa59e43f221f1e0d619a2bdd38c97be9190c9',
    'lightmodel_pbr.glsl': '1694bfbd60b9d8aa59d3d05a0df0c6d73f47c1045382f264a86f4589c7e2d6ca',
    'original-extraction.json': '56ef9a3117723c4850ffe320350fa149c8b94bb67fa5ed9fc39fa8eae528081b',
    'namespace-derivation.json': 'd5692571f8bd5f55ff60c82de063ebb4b7d4f8c6da975eb38e4276498bf8014b',
}
PATHS = {
    'texture': 'src/common/rendering/vulkan/textures/vk_texture.cpp',
    'header': 'src/common/rendering/vulkan/textures/vk_texture.h',
    'descriptors': 'src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp',
    'step': 'src/common/rendering/hwrenderer/data/hw_lightprobe.cpp',
    'prober': 'src/common/rendering/vulkan/vk_lightprober.cpp',
    'builder': 'libraries/ZVulkan/src/vulkanbuilders.cpp',
    'builder_header': 'libraries/ZVulkan/include/zvulkan/vulkanbuilders.h',
    'objects': 'libraries/ZVulkan/include/zvulkan/vulkanobjects.h',
    'sampler': 'src/common/rendering/vulkan/samplers/vk_samplers.cpp',
    'shader': 'wadsrc/static/shaders/scene/lightmodel_pbr.glsl',
    'selector': 'wadsrc/static/shaders/lightmap/frag_copy.glsl',
}


def digest(text: str | bytes) -> str:
    return hashlib.sha256(text.encode() if isinstance(text, str) else text).hexdigest()


def definition(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError('Missing exact source signature: ' + signature)
    brace = text.find('{', start)
    if brace < 0:
        raise AssertionError('Missing source definition brace: ' + signature)
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == '{':
            depth += 1
        elif text[index] == '}':
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError('Unterminated source definition: ' + signature)


def statement(text: str, name: str) -> str:
    match = re.search(r'(?m)^\s*' + re.escape(name) + r'\s*=', text)
    if not match:
        raise AssertionError('Missing actual source assignment: ' + name)
    stop = text.find(';', match.end())
    if stop < 0:
        raise AssertionError('Unterminated assignment: ' + name)
    return text[match.start():stop + 1].strip()


def pinned_original() -> dict:
    for name, expected in PINS.items():
        if digest((ORIGINAL / name).read_bytes()) != expected:
            raise AssertionError('Retained original source hash mismatch: ' + name)
    return json.loads((ORIGINAL / 'original-extraction.json').read_text(encoding='utf-8'))


def sampling_block(shader: str) -> str:
    body = definition(shader, 'vec3 ProcessMaterialLight(')
    start = body.index('\tvec3 irradiance, prefilteredColor;')
    stop = body.index('\n\t/*', start)
    return body[start:stop]


def extract_current(root: Path = ROOT, *, shader: str | None = None, overrides: dict[str, str] | None = None) -> tuple[str, str, dict]:
    original = pinned_original()
    expected = {entry['name']: entry['original_lf_sha256'] for entry in original['extractions']}
    sources = {key: (root / path).read_text(encoding='utf-8') for key, path in PATHS.items()}
    if shader is not None:
        sources['shader'] = shader
    for key, value in (overrides or {}).items():
        if key not in sources:
            raise AssertionError('Unknown source mutation key: ' + key)
        sources[key] = value
    fragments: list[str] = []
    metadata = {'schema': 'pf113-current-cpu-extraction/v1', 'scope': 'CPU service/source evidence only',
                'sources': {PATHS[key]: digest(value) for key, value in sources.items()}, 'extractions': [], 'adapters': []}

    def add(name: str, key: str, raw: str, adapted: str | None = None, *, unchanged: bool = True) -> None:
        if unchanged and digest(raw) != expected[name]:
            raise AssertionError('Protected producer fragment changed: ' + name)
        adapted = raw if adapted is None else adapted
        fragments.append('// ACTUAL SOURCE: ' + PATHS[key] + '; ' + name + '\n' + adapted + '\n')
        metadata['extractions'].append({'name': name, 'path': PATHS[key], 'source_sha256': digest(raw), 'adapter_sha256': digest(adapted)})

    def cpp(name: str, key: str, signature: str, *, unchanged: bool = True) -> None:
        raw = definition(sources[key], signature)
        adapted = raw
        for array in ('Irradiancemaps', 'Prefiltermaps'):
            adapted = adapted.replace(f'int createStart = {array}.size();', f'int createStart = static_cast<int>({array}.size());')
        for call in ('CheckIrradiancemapSize', 'CheckPrefiltermapSize'):
            adapted = adapted.replace(f'{call}(probes.size());', f'{call}(static_cast<int>(probes.size()));')
        if name == 'check-prefilter':
            adapted = adapted.replace('int pixelsize = 8;', '[[maybe_unused]] int pixelsize = 8;')
        add(name, key, raw, adapted, unchanged=unchanged)

    cpp('view-default', 'builder', 'ImageViewBuilder::ImageViewBuilder()')
    for name, signature, variables in (
        ('fixed-null-creation', 'void VkTextureManager::CreateNullTexture()', ('NullTexture', 'NullTextureView')),
        ('fixed-brdf-creation', 'void VkTextureManager::CreateBrdfLutTexture()', ('BrdfLutTexture', 'BrdfLutTextureView')),
    ):
        body = definition(sources['texture'], signature)
        raw = '\n'.join(statement(body, item) for item in variables)
        add(name, 'texture', raw, signature + '\n{\n' + raw + '\n}')
    constructor = definition(sources['texture'], 'VkTextureManager::VkTextureManager(')
    calls = re.findall(r'(?m)^\s*(Create(?:NullTexture|BrdfLutTexture|GamePalette|Shadowmap|Lightmap|Irradiancemap|Prefiltermap)\(\);)', constructor)
    add('initial-resource-call-order', 'texture', '\n'.join(calls), 'void VkTextureManager::CreateFixtureInitial()\n{\n' + '\n'.join(calls) + '\n}')
    for name, signature in (
        ('check-irradiance', 'void VkTextureManager::CheckIrradiancemapSize'),
        ('check-prefilter', 'void VkTextureManager::CheckPrefiltermapSize'),
        ('initial-irradiance', 'void VkTextureManager::CreateIrradiancemap()'),
        ('initial-prefilter', 'void VkTextureManager::CreatePrefiltermap()'),
        ('reset-probes', 'void VkTextureManager::ResetLightProbes()'),
        ('copy-irradiance', 'void VkTextureManager::CopyIrradiancemap'),
        ('copy-prefilter', 'void VkTextureManager::CopyPrefiltermap'),
    ):
        cpp(name, 'texture', signature)
    cpp('lookup', 'descriptors', 'int VkDescriptorSetManager::GetLightProbeTextureIndex')
    reset = definition(sources['descriptors'], 'void VkDescriptorSetManager::ResetHWTextureSets()')
    fixed = re.findall(r'SetBindlessTexture\([01], [^;]+;', reset)
    add('fixed-descriptor-publication', 'descriptors', '\n'.join(fixed), 'void VkDescriptorSetManager::SetFixtureFixed()\n{\n' + '\n'.join(fixed) + '\n}')
    cpp('builder-step', 'step', 'void LightProbeIncrementalBuilder::Step')
    raw = definition(sources['prober'], 'void VkLightprober::EndLightProbePass()')
    producer = re.sub(r'\n\tif \(Pf113ProbeDiagnostics::Observing\(\)\) Pf113ProbeDiagnostics::Publication\(fb, (?:false|true)\);', '', raw)
    if digest(producer) != expected['completed-publication']:
        raise AssertionError('Protected publication producer changed')
    add('completed-publication', 'prober', raw, unchanged=False)
    for name, signature in (
        ('image-builder-default', 'ImageBuilder::ImageBuilder()'),
        ('image-size', 'ImageBuilder& ImageBuilder::Size('),
        ('view-image', 'ImageViewBuilder& ImageViewBuilder::Image('),
        ('sampler-default', 'SamplerBuilder::SamplerBuilder()'),
        ('sampler-address', 'SamplerBuilder& SamplerBuilder::AddressMode(VkSamplerAddressMode addressMode)'),
        ('view-create', 'std::unique_ptr<VulkanImageView> ImageViewBuilder::Create('),
        ('sampler-create', 'std::unique_ptr<VulkanSampler> SamplerBuilder::Create('),
    ):
        cpp(name, 'builder', signature, unchanged=False)
    for name, signature in (
        ('irradiance-sampler', 'void VkSamplerManager::CreateIrradiancemapSampler()'),
        ('prefilter-sampler', 'void VkSamplerManager::CreatePrefiltermapSampler()'),
        ('hw-sampler-reset', 'void VkSamplerManager::ResetHWSamplers()'),
        ('hw-sampler-delete', 'void VkSamplerManager::DeleteHWSamplers()'),
    ):
        cpp(name, 'sampler', signature, unchanged=False)
    for name, signature, prefiltered in (
        ('guard-irradiance', 'vec3 SampleProbeIrradiance(uint base, vec3 N)', False),
        ('guard-prefilter', 'vec3 SampleProbePrefiltered(uint base, vec3 R, float lod)', True),
    ):
        raw = definition(sources['shader'], signature)
        adapted = raw.replace('uint base', 'ObservedIndex base', 1)
        adapted = adapted.replace('{', '{\n\tObserveHelper(' + ('true' if prefiltered else 'false') + ', base.value);', 1)
        add(name, 'shader', raw, adapted, unchanged=False)
        metadata['adapters'].append(name + ': parameter becomes logging scalar; entry observer only, body unchanged')
    raw = sampling_block(sources['shader'])
    adapted = raw.replace('float t11 = t.x * t.y;', 'float t11 = t.x * t.y;\n\t\tObserveWeights(t00, t10, t01, t11);')
    add('current-pbr-sampling', 'shader', raw, 'SampleResult CurrentSampling(int vLightmapIndex, int uLightProbeIndex, ShaderLightmap vLightmap, vec3 N, vec3 R, float roughness)\n{\nconst float MAX_REFLECTION_LOD = 4.0f;\nResetSampleObserver();\n' + adapted + '\nreturn { irradiance, prefilteredColor, ObservedWeights };\n}', unchanged=False)
    selector = definition(sources['selector'], 'uint findClosestProbe(')
    if digest(selector) != expected['selector']:
        raise AssertionError('Protected actual selector changed')
    fragments.append('namespace ShaderSelection\n{\nstruct ProbeSelectionEntry { vec3 position; uint textureIndex; };\nstatic std::vector<ProbeSelectionEntry> probes;\nstatic int ProbeCount = 0;\n' + selector + '\n}\n')
    constants = []
    for name in ('MAX_REFLECTION_LOD', 'PrefiltermapSize', 'IrradiancemapSize'):
        match = re.search(r'(?m)^\s*static const int ' + name + r' = \d+;[^\n]*', sources['header'])
        if not match:
            raise AssertionError('Missing actual texture constant: ' + name)
        constants.append(match.group().strip())
    metadata['adapters'].extend(['bounded vector size casts', 'harness-only maybe_unused inherited pixelsize', 'GLSL weights entry observer', 'GLSL selector separated into namespace'])
    metadata['creation_structs'] = {
        kind: definition(sources['objects'][sources['objects'].index('class ' + kind + '\n'):], 'struct CreationArguments') + ';'
        for kind in ('VulkanImageView', 'VulkanSampler')
    }
    return '#pragma once\n' + '\n'.join(fragments), '\n'.join(constants) + '\n', metadata
