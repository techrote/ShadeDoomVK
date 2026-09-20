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

	// PF-018: equal-size fragmented holes resolve deterministically by address,
	// while the size index examines only the selected best-fit candidate.
	MeshBufferAllocator fragmented;
	fragmented.Reset(32);
	const int f0 = fragmented.Alloc(4);
	const int f1 = fragmented.Alloc(8);
	const int f2 = fragmented.Alloc(4);
	const int f3 = fragmented.Alloc(8);
	const int f4 = fragmented.Alloc(8);
	assert(f0 == 0 && f1 == 4 && f2 == 12 && f3 == 16 && f4 == 24);
	assert(fragmented.Free(f1, 8));
	assert(fragmented.Free(f3, 8));
	const auto searchesBefore = fragmented.GetStats().AllocationSearches;
	const auto candidatesBefore = fragmented.GetStats().AllocationCandidates;
	const int bestFit = fragmented.Alloc(6);
	assert(bestFit == 4);
	assert(fragmented.GetStats().AllocationSearches == searchesBefore + 1);
	assert(fragmented.GetStats().AllocationCandidates == candidatesBefore + 1);
	assert(fragmented.GetLargestFreeRange() == 8);
	assert(fragmented.GetFreeSize() == 10);

	// Coalescing after a best-fit split must keep both indexes synchronized.
	assert(fragmented.Free(bestFit, 6));
	assert(fragmented.Free(f0, 4));
	assert(fragmented.Free(f2, 4));
	assert(fragmented.Free(f4, 8));
	assert(fragmented.GetUsedSize() == 0);
	assert(fragmented.GetFreeRanges().size() == 1);
	assert(fragmented.GetLargestFreeRange() == 32);

	// PF-018 bounded growth: small misses grow by 50%, large misses grow only
	// by the demanded amount, and pre-existing allocation identities do not move.
	MeshBufferAllocator growth;
	growth.Reset(16);
	const int stable = growth.Alloc(16);
	const auto stableIdentity = growth.CurrentIdentity(stable);
	growth.Grow(1);
	assert(growth.GetTotalSize() == 24);
	assert(growth.ValidateIdentity(stableIdentity));
	assert(growth.GetStats().GrownElements == 8);
	assert(growth.Alloc(4) == 16);
	growth.Grow(40);
	assert(growth.GetTotalSize() == 64);
	assert(growth.ValidateIdentity(stableIdentity));
	assert(growth.GetStats().Grows == 2);
	assert(growth.GetStats().GrownElements == 48);
	assert(growth.GetStats().PeakTotalSize == 64);

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

	std::cout << "PF-004/PF-018 LevelMesh allocator/mutation fixture passed\n";
	return 0;
}
