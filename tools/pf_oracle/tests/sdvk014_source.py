"""Exact source-boundary extraction for SDVK-014 CPU fixtures, not a renderer."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
MASK = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)


def block(text: str, signature: str) -> str:
    """Extract one actual definition, ignoring braces inside comments/strings."""
    if text.count(signature) != 1:
        raise AssertionError(f'Expected exactly one source boundary: {signature}')
    start = text.index(signature)
    masked = MASK.sub(lambda match: ' ' * len(match.group()), text)
    opening = masked.index('{', start)
    depth = 0
    for at in range(opening, len(masked)):
        if masked[at] == '{':
            depth += 1
        elif masked[at] == '}':
            depth -= 1
            if depth == 0:
                return text[start:at + 1]
    raise AssertionError(f'Unclosed source boundary: {signature}')


PATHS = {
    'mesh_h': 'src/common/rendering/hwrenderer/data/hw_levelmesh.h',
    'mesh_cpp': 'src/common/rendering/hwrenderer/data/hw_levelmesh.cpp',
    'doom': 'src/rendering/hwrenderer/doom_levelmesh.cpp',
    'draw': 'src/rendering/hwrenderer/scene/hw_drawinfo.cpp',
    'device': 'src/common/rendering/vulkan/vk_renderdevice.cpp',
    'probe': 'src/common/rendering/hwrenderer/data/hw_lightprobe.cpp',
    'maploader': 'src/maploader/maploader.cpp',
    'lightmapper': 'src/common/rendering/vulkan/vk_lightmapper.cpp',
    'texture': 'src/common/rendering/vulkan/textures/vk_texture.cpp',
}
FUNCTIONS = {
    'alloc': ('mesh_h', 'inline int LevelMesh::AllocTile('),
    'free': ('mesh_h', 'inline void LevelMesh::FreeTile('),
    'stats': ('mesh_cpp', 'LevelMeshTileStats LevelMesh::GatherTilePixelStats('),
    'release': ('doom', 'void DoomLevelMesh::ReleaseTiles('),
    'save': ('doom', 'void DoomLevelMesh::SaveLightmapLump('),
    'invalidate': ('doom', 'static int InvalidateLightmap()\n'),
    'update': ('draw', 'void HWDrawInfo::UpdateLightmaps('),
    'frame': ('device', 'void VulkanRenderDevice::BeginFrame('),
    'probe_step': ('probe', 'void LightProbeIncrementalBuilder::Step('),
    'probe_full': ('probe', 'void LightProbeIncrementalBuilder::Full('),
    'lightmap_span': ('maploader', 'static bool IsValidLightmapPixelSpan('),
    'load_lightmap': ('maploader', 'bool MapLoader::LoadLightmap('),
    'select_tiles': ('lightmapper', 'void VkLightmapper::SelectTiles('),
    'copy_result': ('lightmapper', 'void VkLightmapper::CopyResult('),
    'set_lightmap_count': ('texture', 'void VkTextureManager::SetLightmapCount('),
}


def current(key: str) -> str:
    path, signature = FUNCTIONS[key]
    return block((ROOT / PATHS[path]).read_text(), signature)
