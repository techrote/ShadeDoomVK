#include "hw_levelmesh_contract.h"
#include <cassert>
#include <iostream>

int main()
{
	MeshBufferAllocator allocator;
	allocator.Reset(16);
	assert(allocator.GetTotalSize() == 16);
	assert(allocator.GetUsedSize() == 0);

	const int a = allocator.Alloc(4);
	const auto a0 = allocator.CurrentIdentity(a);
	assert(a == 0 && a0.IsSet() && allocator.ValidateIdentity(a0));
	const int b = allocator.Alloc(4);
	const auto b0 = allocator.CurrentIdentity(b);
	assert(b == 4 && b0.IsSet());
	assert(allocator.GetUsedSize() == 8);

	// Wrong span, duplicate free and out-of-bounds frees must fail closed.
	assert(!allocator.Free(b, 3));
	assert(allocator.ValidateIdentity(b0));
	assert(allocator.Free(a, 4));
	assert(!allocator.Free(a, 4));
	assert(!allocator.ValidateIdentity(a0));
	assert(!allocator.Free(-1, 1));
	assert(!allocator.Free(15, 2));

	// Reuse the same integer range and prove the old PF-002 identity is stale.
	const int aReuse = allocator.Alloc(4);
	const auto a1 = allocator.CurrentIdentity(aReuse);
	assert(aReuse == a);
	assert(a1.IsSet() && a1.Generation != a0.Generation);
	assert(!allocator.ValidateIdentity(a0));
	assert(allocator.ValidateIdentity(a1));

	assert(allocator.Free(aReuse, 4));
	assert(allocator.Free(b, 4));
	assert(allocator.GetUsedSize() == 0);
	assert(allocator.GetFreeRanges().size() == 1);
	assert(allocator.GetFreeRanges()[0].Start == 0 && allocator.GetFreeRanges()[0].End == 16);
	assert(allocator.GetStats().InvalidFrees >= 4);

	assert(allocator.Alloc(-1) == -1);
	assert(allocator.GetStats().InvalidAllocations == 1);

	const int beforeReset = allocator.Alloc(2);
	const auto beforeResetId = allocator.CurrentIdentity(beforeReset);
	allocator.Reset(8);
	assert(!allocator.ValidateIdentity(beforeResetId));

	// Adversarial BLAS partition boundaries. The pre-PF-004 CPU path used
	// floor(End / chunk), so {1,2} incorrectly selected zero partitions.
	assert(MeshBufferChunkStart({ 1, 2 }, 8) == 0);
	assert(MeshBufferChunkEndExclusive({ 1, 2 }, 8) == 1);
	assert(MeshBufferChunkStart({ 0, 8 }, 8) == 0);
	assert(MeshBufferChunkEndExclusive({ 0, 8 }, 8) == 1);
	assert(MeshBufferChunkStart({ 7, 9 }, 8) == 0);
	assert(MeshBufferChunkEndExclusive({ 7, 9 }, 8) == 2);
	assert(MeshBufferChunkStart({ 8, 16 }, 8) == 1);
	assert(MeshBufferChunkEndExclusive({ 8, 16 }, 8) == 2);
	assert(MeshBufferChunkStart({ 16, 17 }, 8) == 2);
	assert(MeshBufferChunkEndExclusive({ 16, 17 }, 8) == 3);
	assert(MeshBufferChunkEndExclusive({ 8, 8 }, 8) == 0);
	assert(MeshBufferChunkEndExclusive({ -1, 3 }, 8) == 0);
	assert(MeshBufferChunkEndExclusive({ 1, 2 }, 0) == 0);

	LevelMeshMutationEpochs epochs;
	const auto initial = epochs.Snapshot();
	epochs.Mark(LevelMeshMutationDomain::Geometry | LevelMeshMutationDomain::Query);
	const auto geometry = epochs.Snapshot();
	assert(geometry.Geometry == initial.Geometry + 1);
	assert(geometry.Query == initial.Query + 1);
	assert(geometry.Surface == initial.Surface);
	epochs.Reset();
	const auto reset = epochs.Snapshot();
	assert(reset.Resets == initial.Resets + 1);
	assert(reset.Geometry == geometry.Geometry + 1);
	assert(reset.Surface == geometry.Surface + 1);
	assert(reset.Lights == geometry.Lights + 1);
	assert(reset.Query == geometry.Query + 1);
	assert(reset.Portals == geometry.Portals + 1);
	assert(reset.LightmapProbe == geometry.LightmapProbe + 1);

	std::cout << "PF-004 LevelMesh allocator/mutation fixture passed\n";
	return 0;
}
