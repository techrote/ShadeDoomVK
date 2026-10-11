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

// Retained unmodified production functions from a7c5df6f for CPU regression.
static FVector3 SwapYZ(const FVector3& v)
{
	return FVector3(v.X, v.Z, v.Y);
}

void CPUAccelStruct::Upload()
{
	if (screen->IsRayQueryEnabled())
		return;

	unsigned int count = (unsigned int)TLAS.Nodes.size();
	for (auto& blas : DynamicBLAS)
	{
		if (blas)
		{
			count += (unsigned int)blas->GetNodes().size();
		}
	}

	if (Mesh->Mesh.Nodes.Size() < count)
	{
		Mesh->Mesh.Nodes.Resize(std::max(count * 2, (unsigned int)10000));
	}

	Mesh->Mesh.RootNode = TLAS.Root;

	auto& destnodes = Mesh->Mesh.Nodes;

	// Copy the BLAS nodes to the mesh node list and remember their locations
	int offset = TLAS.Nodes.size();
	int instance = 0;
	std::vector<int> blasOffsets(DynamicBLAS.size());
	for (auto& blas : DynamicBLAS)
	{
		if (blas)
		{
			int blasStart = offset;
			int indexStart = instance * IndexesPerBLAS;
			blasOffsets[instance] = blasStart;

			for (const auto& node : blas->GetNodes())
			{
				CollisionNode& info = destnodes[offset];
				info.center = SwapYZ(node.aabb.Center);
				info.extents = SwapYZ(node.aabb.Extents);
				info.left = node.left != -1 ? blasStart + node.left : -1;
				info.right = node.right != -1 ? blasStart + node.right : -1;
				info.element_index = node.element_index != -1 ? indexStart + node.element_index : -1;
				offset++;
			}
			instance++;
		}
	}

	// A single-instance TLAS has no parent whose child link can be redirected.
	// Export the BLAS root directly instead of its childless TLAS leaf: shader
	// traversal identifies leaves by element_index and cannot consume TLAS leaves.
	if (TLAS.Root >= 0 && TLAS.Nodes[TLAS.Root].blas_index != -1)
	{
		int blas_index = TLAS.Nodes[TLAS.Root].blas_index;
		Mesh->Mesh.RootNode = blasOffsets[blas_index] + DynamicBLAS[blas_index]->GetRoot();
	}

	// Copy the TLAS nodes and redirect the leafs to the BLAS roots
	offset = 0;
	for (const auto& node : TLAS.Nodes)
	{
		CollisionNode& info = destnodes[offset];
		info.center = SwapYZ(node.aabb.Center);
		info.extents = SwapYZ(node.aabb.Extents);

		if (node.left != -1 && TLAS.Nodes[node.left].blas_index != -1)
		{
			int blas_index = TLAS.Nodes[node.left].blas_index;
			info.left = blasOffsets[blas_index] + DynamicBLAS[blas_index]->GetRoot();
		}
		else
		{
			info.left = node.left;
		}

		if (node.right != -1 && TLAS.Nodes[node.right].blas_index != -1)
		{
			int blas_index = TLAS.Nodes[node.right].blas_index;
			info.right = blasOffsets[blas_index] + DynamicBLAS[blas_index]->GetRoot();
		}
		else
		{
			info.right = node.right;
		}

		info.element_index = -1;
		offset++;
	}

	Mesh->UploadRanges.Node.Clear();
	Mesh->UploadRanges.Node.Add(0, (int)count);
}

void CPUAccelStruct::CreateTLAS()
{
	Scratch.leafs.clear();
	Scratch.leafs.reserve(InstanceCount);
	Scratch.centroids.clear();
	Scratch.centroids.reserve(DynamicBLAS.size());
	for (int i = 0; i < InstanceCount; i++)
	{
		if (DynamicBLAS[i])
		{
			Scratch.leafs.push_back(i);
			Scratch.centroids.push_back(FVector4(DynamicBLAS[i]->GetBBox().Center, 1.0f));
		}
		else
		{
			Scratch.leafs.push_back(0);
			Scratch.centroids.push_back(FVector4(-1000000.0f, -1000000.0f, -1000000.0f, 1.0f));
		}
	}

	size_t neededbuffersize = InstanceCount * 2;
	if (Scratch.workbuffer.size() < neededbuffersize)
		Scratch.workbuffer.resize(neededbuffersize);

	TLAS.Nodes.clear();
	TLAS.Root = Subdivide(Scratch.leafs.data(), (int)Scratch.leafs.size(), Scratch.centroids.data(), Scratch.workbuffer.data());
}

int CPUAccelStruct::Subdivide(int* instances, int numInstances, const FVector4* centroids, int* workBuffer)
{
	if (numInstances == 0)
		return -1;

	// Find bounding box and median of the instance centroids
	FVector3 median(0.0f, 0.0f, 0.0f);
	FVector3 min = DynamicBLAS[instances[0]]->GetBBox().min;
	FVector3 max = DynamicBLAS[instances[0]]->GetBBox().max;
	for (int i = 0; i < numInstances; i++)
	{
		const CollisionBBox& bbox = DynamicBLAS[instances[i]]->GetBBox();

		min.X = std::min(min.X, bbox.min.X);
		min.Y = std::min(min.Y, bbox.min.Y);
		min.Z = std::min(min.Z, bbox.min.Z);

		max.X = std::max(max.X, bbox.max.X);
		max.Y = std::max(max.Y, bbox.max.Y);
		max.Z = std::max(max.Z, bbox.max.Z);

		median += centroids[instances[i]].XYZ();
	}
	median /= (float)numInstances;

	// For numerical stability
	min.X -= 0.1f;
	min.Y -= 0.1f;
	min.Z -= 0.1f;
	max.X += 0.1f;
	max.Y += 0.1f;
	max.Z += 0.1f;

	if (numInstances == 1) // Leaf node
	{
		TLAS.Nodes.push_back(Node(min, max, instances[0]));
		return (int)TLAS.Nodes.size() - 1;
	}

	// Find the longest axis
	float axis_lengths[3] =
	{
		max.X - min.X,
		max.Y - min.Y,
		max.Z - min.Z
	};

	int axis_order[3] = { 0, 1, 2 };
	std::sort(axis_order, axis_order + 3, [&](int a, int b) { return axis_lengths[a] > axis_lengths[b]; });

	// Try split at longest axis, then if that fails the next longest, and then the remaining one
	int left_count, right_count;
	FVector3 axis;
	for (int attempt = 0; attempt < 3; attempt++)
	{
		// Find the split plane for axis
		switch (axis_order[attempt])
		{
		default:
		case 0: axis = FVector3(1.0f, 0.0f, 0.0f); break;
		case 1: axis = FVector3(0.0f, 1.0f, 0.0f); break;
		case 2: axis = FVector3(0.0f, 0.0f, 1.0f); break;
		}
		FVector4 plane(axis, -(median | axis)); // plane(axis, -dot(median, axis));

		// Split instances into two
		left_count = 0;
		right_count = 0;
		for (int i = 0; i < numInstances; i++)
		{
			int instance = instances[i];

			float side = centroids[instance] | plane;
			if (side >= 0.0f)
			{
				workBuffer[left_count] = instance;
				left_count++;
			}
			else
			{
				workBuffer[numInstances + right_count] = instance;
				right_count++;
			}
		}

		if (left_count != 0 && right_count != 0)
			break;
	}

	// Check if something went wrong when splitting and do a random split instead
	if (left_count == 0 || right_count == 0)
	{
		left_count = numInstances / 2;
		right_count = numInstances - left_count;
	}
	else
	{
		// Move result back into instances list:
		for (int i = 0; i < left_count; i++)
			instances[i] = workBuffer[i];
		for (int i = 0; i < right_count; i++)
			instances[i + left_count] = workBuffer[numInstances + i];
	}

	// Create child nodes:
	int left_index = -1;
	int right_index = -1;
	if (left_count > 0)
		left_index = Subdivide(instances, left_count, centroids, workBuffer);
	if (right_count > 0)
		right_index = Subdivide(instances + left_count, right_count, centroids, workBuffer);

	TLAS.Nodes.push_back(Node(min, max, left_index, right_index));
	return (int)TLAS.Nodes.size() - 1;
}

TraceHit CPUAccelStruct::FindFirstHit(const FVector3& rayStart, const FVector3& rayEnd)
{
	RayBBox ray(rayStart, rayEnd);
	TraceHit hit;
	FindFirstHit(ray, TLAS.Root, &hit);
	return hit;
}
