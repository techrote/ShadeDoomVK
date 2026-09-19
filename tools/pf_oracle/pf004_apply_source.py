from pathlib import Path
import re

ROOT = Path.cwd()

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def write(path, text):
    (ROOT / path).write_text(text, encoding="utf-8", newline="\n")

def replace(path, old, new):
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one literal match, got {count}")
    write(path, text.replace(old, new, 1))

def regex(path, pattern, new):
    text = read(path)
    text, count = re.subn(pattern, new, text, count=1, flags=re.MULTILINE | re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, got {count}")
    write(path, text)

h = "src/common/rendering/hwrenderer/data/hw_levelmesh.h"
replace(h, '#include "hw_resourcegeneration.h"\n#include "engineerrors.h"', '#include "hw_resourcegeneration.h"\n#include "hw_levelmesh_contract.h"\n#include "engineerrors.h"')
regex(h, r'struct MeshBufferRange\n\{.*?class MeshBufferUploads', 'class MeshBufferUploads')
replace(h, '\tconst FRendererEpochStats& GetResourceEpochStats() const { return ResourceEpoch.GetStats(); }\n\n\tvirtual void GetVisibleSurfaces', '\tconst FRendererEpochStats& GetResourceEpochStats() const { return ResourceEpoch.GetStats(); }\n\n\tvoid MarkMutation(LevelMeshMutationDomain domain) { MutationEpochs.Mark(domain); }\n\tconst LevelMeshMutationEpochSnapshot& GetMutationEpochs() const { return MutationEpochs.Snapshot(); }\n\n\tvirtual void GetVisibleSurfaces')
replace(h, 'private:\n\tFRendererEpoch ResourceEpoch;\n};', 'private:\n\tFRendererEpoch ResourceEpoch;\n\tLevelMeshMutationEpochs MutationEpochs;\n};')
replace(h, '\tMesh.IndexCount = std::max(Mesh.IndexCount, info.IndexStart + info.IndexCount);\n\n\treturn info;', '\tMesh.IndexCount = std::max(Mesh.IndexCount, info.IndexStart + info.IndexCount);\n\tMarkMutation(LevelMeshMutationDomain::Geometry | LevelMeshMutationDomain::Query);\n\n\treturn info;')
replace(h, '\tUploadRanges.LightUniforms.Add(info.Start, info.Count);\n\n\treturn info;', '\tUploadRanges.LightUniforms.Add(info.Start, info.Count);\n\tMarkMutation(LevelMeshMutationDomain::Surface);\n\n\treturn info;')
replace(h, '\tinfo.Count = count;\n\tUploadRanges.LightIndex.Add(info.Start, info.Count);\n\treturn info;', '\tinfo.Count = count;\n\tUploadRanges.LightIndex.Add(info.Start, info.Count);\n\tif (info.Count > 0) MarkMutation(LevelMeshMutationDomain::Lights);\n\treturn info;')
replace(h, '\tUploadRanges.Light.Add(info.Index, 1);\n\treturn info;', '\tUploadRanges.Light.Add(info.Index, 1);\n\tMarkMutation(LevelMeshMutationDomain::Lights);\n\treturn info;')
replace(h, '\tinfo.Count = count;\n\tUploadRanges.Surface.Add(info.Index, info.Count);\n\treturn info;', '\tinfo.Count = count;\n\tUploadRanges.Surface.Add(info.Index, info.Count);\n\tMarkMutation(LevelMeshMutationDomain::Surface | LevelMeshMutationDomain::Query);\n\treturn info;')
regex(h, r'inline int LevelMesh::AllocTile\(const LightmapTile& tile\)\n\{.*?\n\}', '''inline int LevelMesh::AllocTile(const LightmapTile& tile)\n{\n\tLightmap.UsedTiles++;\n\tif (Lightmap.FreeTiles.Size() != 0)\n\t{\n\t\tint index = Lightmap.FreeTiles.Last();\n\t\tLightmap.FreeTiles.Pop();\n\t\tLightmap.Tiles[index] = tile;\n\t\tMarkMutation(LevelMeshMutationDomain::LightmapProbe);\n\t\treturn index;\n\t}\n\tint index = Lightmap.Tiles.Size();\n\tLightmap.Tiles.Push(tile);\n\tMarkMutation(LevelMeshMutationDomain::LightmapProbe);\n\treturn index;\n}''')
regex(h, r'inline void LevelMesh::FreeGeometry\(int vertexStart, int vertexCount, int indexStart, int indexCount\)\n\{.*?\n\}', '''inline void LevelMesh::FreeGeometry(int vertexStart, int vertexCount, int indexStart, int indexCount)\n{\n\tif (!FreeLists.Vertex.CanFree(vertexStart, vertexCount) || !FreeLists.Index.CanFree(indexStart, indexCount))\n\t\tI_FatalError("Invalid LevelMesh geometry free: vertices %d+%d, indexes %d+%d", vertexStart, vertexCount, indexStart, indexCount);\n\n\tfor (int i = 0; i < indexCount; i++)\n\t\tMesh.Indexes[indexStart + i] = 0;\n\tUploadRanges.Index.Add(indexStart, indexCount);\n\n\tif (!FreeLists.Vertex.Free(vertexStart, vertexCount) || !FreeLists.Index.Free(indexStart, indexCount))\n\t\tI_FatalError("LevelMesh geometry free failed after validation");\n\tMarkMutation(LevelMeshMutationDomain::Geometry | LevelMeshMutationDomain::Query);\n}''')
replace(h, 'inline void LevelMesh::FreeUniforms(int start, int count)\n{\n\tFreeLists.Uniforms.Free(start, count);\n}', 'inline void LevelMesh::FreeUniforms(int start, int count)\n{\n\tif (!FreeLists.Uniforms.Free(start, count))\n\t\tI_FatalError("Invalid LevelMesh uniform free: %d+%d", start, count);\n\tif (count > 0) MarkMutation(LevelMeshMutationDomain::Surface);\n}')
replace(h, 'inline void LevelMesh::FreeLightList(int start, int count)\n{\n\tFreeLists.LightIndex.Free(start, count);\n}', 'inline void LevelMesh::FreeLightList(int start, int count)\n{\n\tif (!FreeLists.LightIndex.Free(start, count))\n\t\tI_FatalError("Invalid LevelMesh light-list free: %d+%d", start, count);\n\tif (count > 0) MarkMutation(LevelMeshMutationDomain::Lights);\n}')
replace(h, 'inline void LevelMesh::FreeSurface(unsigned int surfaceIndex, int count)\n{\n\tFreeLists.Surface.Free(surfaceIndex, count);\n}', 'inline void LevelMesh::FreeSurface(unsigned int surfaceIndex, int count)\n{\n\tif (!FreeLists.Surface.Free((int)surfaceIndex, count))\n\t\tI_FatalError("Invalid LevelMesh surface free: %u+%d", surfaceIndex, count);\n\tif (count > 0) MarkMutation(LevelMeshMutationDomain::Surface | LevelMeshMutationDomain::Query);\n}')
replace(h, 'inline void LevelMesh::FreeTile(int index)\n{\n\tLightmap.UsedTiles--;\n\tLightmap.FreeTiles.Push(index);\n}', '''inline void LevelMesh::FreeTile(int index)\n{\n\tif (index < 0 || index >= (int)Lightmap.Tiles.Size() || Lightmap.UsedTiles <= 0)\n\t\tI_FatalError("Invalid LevelMesh lightmap tile free: %d", index);\n\tfor (int freeIndex : Lightmap.FreeTiles)\n\t\tif (freeIndex == index)\n\t\t\tI_FatalError("Duplicate LevelMesh lightmap tile free: %d", index);\n\tLightmap.UsedTiles--;\n\tLightmap.FreeTiles.Push(index);\n\tMarkMutation(LevelMeshMutationDomain::LightmapProbe);\n}''')
replace(h, '\tUploadRanges.Portals.Add(0, (int)Portals.Size());\n}', '\tUploadRanges.Portals.Add(0, (int)Portals.Size());\n\tMarkMutation(LevelMeshMutationDomain::Portals | LevelMeshMutationDomain::Query);\n}')

cpp = "src/common/rendering/hwrenderer/data/hw_levelmesh.cpp"
replace(cpp, 'void LevelMesh::Reset()\n{\n\tResourceEpoch.Invalidate();', 'void LevelMesh::Reset()\n{\n\tResourceEpoch.Invalidate();\n\tMutationEpochs.Reset();')
replace(cpp, '''\t\t\tfor (int i = 0; i < surface->MeshLocation.NumVerts; i++)\n\t\t\t{\n\t\t\t\tauto& vertex = Mesh.Vertices[surface->MeshLocation.StartVertIndex + i];\n\t\t\t\tFVector2 uv = tile.ToUV(vertex.fPos(), (float)Lightmap.TextureSize);\n\t\t\t\tvertex.lu = uv.X;\n\t\t\t\tvertex.lv = uv.Y;\n\t\t\t\tvertex.lindex = (float)tile.AtlasLocation.ArrayIndex;\n\t\t\t}\n''', '''\t\t\tfor (int i = 0; i < surface->MeshLocation.NumVerts; i++)\n\t\t\t{\n\t\t\t\tauto& vertex = Mesh.Vertices[surface->MeshLocation.StartVertIndex + i];\n\t\t\t\tFVector2 uv = tile.ToUV(vertex.fPos(), (float)Lightmap.TextureSize);\n\t\t\t\tvertex.lu = uv.X;\n\t\t\t\tvertex.lv = uv.Y;\n\t\t\t\tvertex.lindex = (float)tile.AtlasLocation.ArrayIndex;\n\t\t\t}\n\t\t\tUploadRanges.Vertex.Add(surface->MeshLocation.StartVertIndex, surface->MeshLocation.NumVerts);\n\t\t\tMarkMutation(LevelMeshMutationDomain::LightmapProbe | LevelMeshMutationDomain::Surface);\n''')
regex(cpp, r'/////////////////////////////////////////////////////////////////////////////\n\nvoid MeshBufferAllocator::Reset\(int size\).*?/////////////////////////////////////////////////////////////////////////////\n\nvoid MeshBufferUploads::Clear', '/////////////////////////////////////////////////////////////////////////////\n\nvoid MeshBufferUploads::Clear')

col = "src/common/rendering/hwrenderer/data/hw_collision.cpp"
replace(col, '''\t\tfor (const MeshBufferRange& range : Mesh->UploadRanges.Index.GetRanges())\n\t\t{\n\t\t\tint start = range.Start / IndexesPerBLAS;\n\t\t\tint end = range.End / IndexesPerBLAS;\n\t\t\tfor (int i = start; i < end; i++)\n\t\t\t{\n\t\t\t\tneedsUpdate[i] = true;\n\t\t\t}\n\t\t}\n''', '''\t\tfor (const MeshBufferRange& range : Mesh->UploadRanges.Index.GetRanges())\n\t\t{\n\t\t\tint start = MeshBufferChunkStart(range, IndexesPerBLAS);\n\t\t\tint end = std::min(MeshBufferChunkEndExclusive(range, IndexesPerBLAS), InstanceCount);\n\t\t\tfor (int i = start; i < end; i++)\n\t\t\t{\n\t\t\t\tneedsUpdate[i] = true;\n\t\t\t}\n\t\t}\n''')

vk = "src/common/rendering/vulkan/vk_levelmesh.cpp"
replace(vk, '''\t\tfor (const MeshBufferRange& range : Mesh->UploadRanges.Index.GetRanges())\n\t\t{\n\t\t\tint start = range.Start / IndexesPerBLAS;\n\t\t\tint end = (range.End + IndexesPerBLAS - 1) / IndexesPerBLAS;\n\t\t\tfor (int i = start; i < end; i++)\n\t\t\t{\n\t\t\t\tDynamicBLAS[i].NeedsUpdate = true;\n\t\t\t}\n\t\t}\n''', '''\t\tfor (const MeshBufferRange& range : Mesh->UploadRanges.Index.GetRanges())\n\t\t{\n\t\t\tint start = MeshBufferChunkStart(range, IndexesPerBLAS);\n\t\t\tint end = std::min(MeshBufferChunkEndExclusive(range, IndexesPerBLAS),\n\t\t\t\tstd::min(InstanceCount, (int)DynamicBLAS.size()));\n\t\t\tfor (int i = start; i < end; i++)\n\t\t\t{\n\t\t\t\tDynamicBLAS[i].NeedsUpdate = true;\n\t\t\t}\n\t\t}\n''')

doom = "src/rendering/hwrenderer/doom_levelmesh.cpp"
replace(doom, '''\tfor (line_t* line : sector->Lines)\n\t{\n\t\tif (line->sidedef[0])\n\t\t\tUpdateSide(line->sidedef[0]->Index(), SurfaceUpdateType::Full);\n\t\telse if (line->sidedef[1])\n\t\t\tUpdateSide(line->sidedef[1]->Index(), SurfaceUpdateType::Full);\n\t}\n}\n\nvoid DoomLevelMesh::OnSideTextureChanged''', '''\tfor (line_t* line : sector->Lines)\n\t{\n\t\tif (line->sidedef[0])\n\t\t\tUpdateSide(line->sidedef[0]->Index(), SurfaceUpdateType::Full);\n\t\tif (line->sidedef[1])\n\t\t\tUpdateSide(line->sidedef[1]->Index(), SurfaceUpdateType::Full);\n\t}\n}\n\nvoid DoomLevelMesh::OnSideTextureChanged''')
replace(doom, '\t\tUploadRanges.LightUniforms.Add(uinfo.Start, uinfo.Count);\n\t}\n}\n\nvoid DoomLevelMesh::SetFlatLights', '\t\tUploadRanges.LightUniforms.Add(uinfo.Start, uinfo.Count);\n\t}\n\tMarkMutation(LevelMeshMutationDomain::Surface);\n}\n\nvoid DoomLevelMesh::SetFlatLights')
replace(doom, '\t\tUploadRanges.LightUniforms.Add(uinfo.Start, uinfo.Count);\n\t}\n}\n\nvoid DoomLevelMesh::CreateWallSurface', '\t\tUploadRanges.LightUniforms.Add(uinfo.Start, uinfo.Count);\n\t}\n\tMarkMutation(LevelMeshMutationDomain::Surface);\n}\n\nvoid DoomLevelMesh::CreateWallSurface')
replace(doom, '\t\tsurf = DoomSurfaceInfos[surf].NextSurface;\n\t}\n}\n\nvoid DoomLevelMesh::UpdateFlatLightList', '\t\tsurf = DoomSurfaceInfos[surf].NextSurface;\n\t}\n\tMarkMutation(LevelMeshMutationDomain::Lights | LevelMeshMutationDomain::Surface | LevelMeshMutationDomain::LightmapProbe);\n}\n\nvoid DoomLevelMesh::UpdateFlatLightList')
replace(doom, '\t\tsurf = DoomSurfaceInfos[surf].NextSurface;\n\t}\n}\n\nvoid DoomLevelMesh::UpdateSideShadows', '\t\tsurf = DoomSurfaceInfos[surf].NextSurface;\n\t}\n\tMarkMutation(LevelMeshMutationDomain::Lights | LevelMeshMutationDomain::Surface | LevelMeshMutationDomain::LightmapProbe);\n}\n\nvoid DoomLevelMesh::UpdateSideShadows')
replace(doom, '\t\tsurf = DoomSurfaceInfos[surf].NextSurface;\n\t}\n}\n\nvoid DoomLevelMesh::UpdateFlatShadows', '\t\tsurf = DoomSurfaceInfos[surf].NextSurface;\n\t}\n\tMarkMutation(LevelMeshMutationDomain::LightmapProbe);\n}\n\nvoid DoomLevelMesh::UpdateFlatShadows')
replace(doom, '\t\tsurf = DoomSurfaceInfos[surf].NextSurface;\n\t}\n}\n\nvoid DoomLevelMesh::UpdateSide(unsigned int sideIndex', '\t\tsurf = DoomSurfaceInfos[surf].NextSurface;\n\t}\n\tMarkMutation(LevelMeshMutationDomain::LightmapProbe);\n}\n\nvoid DoomLevelMesh::UpdateSide(unsigned int sideIndex')
replace(doom, '\tUploadRanges.DynLight.Add(0, sizeof(int) * 4 + totalsize * sizeof(FDynLightInfo));\n}', '\tUploadRanges.DynLight.Add(0, sizeof(int) * 4 + totalsize * sizeof(FDynLightInfo));\n\tMarkMutation(LevelMeshMutationDomain::Lights);\n}')

print("PF-004 source patch applied")
