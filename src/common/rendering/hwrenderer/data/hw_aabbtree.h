
#pragma once

#include "tarray.h"
#include "vectors.h"
#include <cstdint>

namespace hwrenderer
{

// Node in a binary AABB tree
struct AABBTreeNode
{
	AABBTreeNode(const FVector2 &aabb_min, const FVector2 &aabb_max, int line_index) : aabb_left(aabb_min.X), aabb_top(aabb_min.Y), aabb_right(aabb_max.X), aabb_bottom(aabb_max.Y), left_node(-1), right_node(-1), line_index(line_index) { }
	AABBTreeNode(const FVector2 &aabb_min, const FVector2 &aabb_max, int left, int right) : aabb_left(aabb_min.X), aabb_top(aabb_min.Y), aabb_right(aabb_max.X), aabb_bottom(aabb_max.Y), left_node(left), right_node(right), line_index(-1) { }

	// Axis aligned bounding box for the node
	float aabb_left, aabb_top;
	float aabb_right, aabb_bottom;

	// Child node indices
	int left_node;
	int right_node;

	// AABBTreeLine index if it is a leaf node. Index is -1 if it is not.
	int line_index;

	// Padding to keep 16-byte length (this structure is uploaded to the GPU)
	int padding;
};

// Line segment for leaf nodes in an AABB tree
struct AABBTreeLine
{
	float x, y;
	float dx, dy;
};

// PF-018: observational counters for the dynamic AABB update path. These do
// not participate in tree/query semantics and are intentionally cumulative.
struct AABBTreeUpdateStats
{
	uint64_t PathCacheBuilds = 0;
	uint64_t PathLookups = 0;
	uint64_t PathParentSteps = 0;
	uint64_t UpdateCalls = 0;
	uint64_t MovedLines = 0;
	uint64_t UpdatedNodes = 0;
	uint64_t UpdateNanoseconds = 0;
};

class LevelAABBTree
{
protected:
	// Nodes in the AABB tree. Last node is the root node.
	TArray<AABBTreeNode> nodes;

	// Line segments for the leaf nodes in the tree.
	TArray<AABBTreeLine> treelines;

	int dynamicStartNode = 0;
	int dynamicStartLine = 0;

	// PF-018: topology is immutable after construction for the current Doom
	// implementation. Cache leaf->parent relationships once so moving lines do
	// not recursively rediscover the same route through the complete tree.
	TArray<int> nodeParents;
	TArray<int> lineLeafNodes;
	AABBTreeUpdateStats UpdateStats;

public:
	// Shoot a ray from ray_start to ray_end and return the closest hit as a fractional value between 0 and 1. Returns 1 if no line was hit.
	double RayTest(const DVector3 &ray_start, const DVector3 &ray_end);

	const void *Nodes() const { return nodes.Data(); }
	const void *Lines() const { return treelines.Data(); }
	size_t NodesSize() const { return nodes.Size() * sizeof(AABBTreeNode); }
	size_t LinesSize() const { return treelines.Size() * sizeof(AABBTreeLine); }
	unsigned int NodesCount() const { return nodes.Size(); }

	const void *DynamicNodes() const { return nodes.Data() + dynamicStartNode; }
	const void *DynamicLines() const { return treelines.Data() + dynamicStartLine; }
	size_t DynamicNodesSize() const { return (nodes.Size() - dynamicStartNode) * sizeof(AABBTreeNode); }
	size_t DynamicLinesSize() const { return (treelines.Size() - dynamicStartLine) * sizeof(AABBTreeLine); }
	size_t DynamicNodesOffset() const { return dynamicStartNode * sizeof(AABBTreeNode); }
	size_t DynamicLinesOffset() const { return dynamicStartLine * sizeof(AABBTreeLine); }
	const AABBTreeUpdateStats &GetUpdateStats() const { return UpdateStats; }

	virtual bool Update() = 0;

	virtual ~LevelAABBTree() = default;

protected:

	// Rebuild after any topology mutation. Bounding-box-only updates do not
	// invalidate the cache.
	void RebuildNodePathCache();
	TArray<int> FindNodePath(unsigned int line, unsigned int node);
	// Test if a ray overlaps an AABB node or not
	bool OverlapRayAABB(const DVector2 &ray_start2d, const DVector2 &ray_end2d, const AABBTreeNode &node);

	// Intersection test between a ray and a line segment
	double IntersectRayLine(const DVector2 &ray_start, const DVector2 &ray_end, int line_index, const DVector2 &raydelta, double rayd, double raydist2);


};

} // namespace
