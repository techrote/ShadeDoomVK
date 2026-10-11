/*
**  Level mesh collision detection
**  Copyright (c) 2018 Magnus Norddahl
**
**  This software is provided 'as-is', without any express or implied
**  warranty.  In no event will the authors be held liable for any damages
**  arising from the use of this software.
**
**  Permission is granted to anyone to use this software for any purpose,
**  including commercial applications, and to alter it and redistribute it
**  freely, subject to the following restrictions:
**
**  1. The origin of this software must not be misrepresented; you must not
**     claim that you wrote the original software. If you use this software
**     in a product, an acknowledgment in the product documentation would be
**     appreciated but is not required.
**  2. Altered source versions must be plainly marked as such, and must not be
**     misrepresented as being the original software.
**  3. This notice may not be removed or altered from any source distribution.
**
*/


CPUAccelStruct::CPUAccelStruct(LevelMesh* mesh) : Mesh(mesh)
{
	// Find out how many segments we should split the map into
	DynamicBLAS.resize(32);
	IndexesPerBLAS = ((Mesh->Mesh.Indexes.size() + 2) / 3 / DynamicBLAS.size() + 1) * 3;
	InstanceCount = (Mesh->Mesh.IndexCount + IndexesPerBLAS - 1) / IndexesPerBLAS;

	// Create a BLAS for each segment in use
	for (int instance = 0; instance < InstanceCount; instance++)
	{
		int indexStart = instance * IndexesPerBLAS;
		int indexEnd = std::min(indexStart + IndexesPerBLAS, Mesh->Mesh.IndexCount);
		DynamicBLAS[instance] = CreateBLAS(indexStart, indexEnd - indexStart);
	}

	CreateTLAS();
	Upload();
}
void CPUAccelStruct::Update()
{
	if (Mesh->UploadRanges.Index.GetRanges().Size() == 0)
		return;

	DynamicBLASTime.ResetAndClock();
	InstanceCount = (Mesh->Mesh.IndexCount + IndexesPerBLAS - 1) / IndexesPerBLAS;

	bool reCreated = false;

	if(InstanceCount > DynamicBLAS.size())
	{
		IndexesPerBLAS = ((Mesh->Mesh.Indexes.size() + 2) / 3 / DynamicBLAS.size() + 1) * 3;
		InstanceCount = (Mesh->Mesh.IndexCount + IndexesPerBLAS - 1) / IndexesPerBLAS;
		reCreated = true;
	}


	if(reCreated)
	{
		for (int instance = 0; instance < InstanceCount; instance++)
		{
			int indexStart = instance * IndexesPerBLAS;
			int indexEnd = std::min(indexStart + IndexesPerBLAS, Mesh->Mesh.IndexCount);
			DynamicBLAS[instance] = CreateBLAS(indexStart, indexEnd - indexStart);
		}
	}
	else
	{
		std::vector<bool> needsUpdate(InstanceCount);

		for (const MeshBufferRange& range : Mesh->UploadRanges.Index.GetRanges())
		{
			int start = MeshBufferChunkStart(range, IndexesPerBLAS);
			int end = std::min(MeshBufferChunkEndExclusive(range, IndexesPerBLAS), InstanceCount);
			for (int i = start; i < end; i++)
			{
				needsUpdate[i] = true;
			}
		}

		for (int instance = 0; instance < InstanceCount; instance++)
		{
			if (needsUpdate[instance])
			{
				int indexStart = instance * IndexesPerBLAS;
				int indexEnd = std::min(indexStart + IndexesPerBLAS, Mesh->Mesh.IndexCount);
				DynamicBLAS[instance] = CreateBLAS(indexStart, indexEnd - indexStart);
			}
		}
	}

	DynamicBLASTime.Unclock();

	CreateTLAS();
	Upload();
}
void LevelMesh::Reset()
{
	ResourceEpoch.Invalidate();
	MutationEpochs.Reset();

	Mesh.Vertices.Clear();
	Mesh.UniformIndexes.Clear();

	Mesh.Surfaces.Clear();
	Mesh.Uniforms.Clear();
	Mesh.LightUniforms.Clear();
	Mesh.Materials.Clear();

	int maxLights = 20'000;

	Mesh.Lights.Resize(maxLights);
	Mesh.LightIndexes.Clear();
	Mesh.DynLights.Resize((sizeof(int) * 4) + MAX_LIGHT_DATA * sizeof(FDynLightInfo));

	Mesh.Indexes.Clear();
	Mesh.SurfaceIndexes.Clear();

	FreeLists.Vertex.Reset(Mesh.Vertices.Size());
	FreeLists.Index.Reset(Mesh.Indexes.Size());
	FreeLists.Uniforms.Reset(Mesh.Uniforms.Size());
	FreeLists.Surface.Reset(Mesh.Surfaces.Size());
	FreeLists.LightIndex.Reset(Mesh.LightIndexes.Size());
	FreeLists.Light.Reset(Mesh.Lights.Size());
}
