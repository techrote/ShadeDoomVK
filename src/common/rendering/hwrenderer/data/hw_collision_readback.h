#pragma once

// SDVK-009 diagnostic-only semantic copy planning and fence identity. This
// header has no Vulkan/device dependency, so tests execute the production
// planner and all rejection paths without starting a renderer.
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace CollisionReadback
{
constexpr uint64_t MaxBytes = 4ull * 1024 * 1024;
constexpr uint64_t MaxRunBytes = 256ull * 1024 * 1024;
constexpr uint32_t MaxRegions = 16384;
constexpr uint32_t MaxElements = 1000000;
constexpr uint32_t MaxPlans = 4096;
constexpr uint64_t NodeHeader = 16, NodeStride = 48, VertexStride = 32;

inline void Require(bool valid, const char* reason)
{
	if (!valid) throw std::runtime_error(reason);
}

enum class Source : unsigned int { Node, Vertex, Index };
enum class Field : unsigned int { Root, NodeCenter, NodeExtents, NodeLinks, Index, Vertex };

inline const char* FieldName(Field field)
{
	switch (field)
	{
	case Field::Root: return "root";
	case Field::NodeCenter: return "node_center";
	case Field::NodeExtents: return "node_extents";
	case Field::NodeLinks: return "node_links";
	case Field::Index: return "index";
	case Field::Vertex: return "vertex";
	}
	return "invalid";
}

struct Allocation
{
	uint64_t Id = 0, Bytes = 0;
};

struct Snapshot
{
	uint32_t Object = 0, Event = 0, ExportedCount = 0;
	uint32_t VertexExtent = 0, IndexExtent = 0, OccupiedCount = 0;
	int32_t Root = -1;
};

struct Region
{
	Source Buffer = Source::Node;
	Field Semantic = Field::Root;
	uint32_t Identity = 0;
	uint64_t SrcOffset = 0, DstOffset = 0, Bytes = 0;
};

struct Plan
{
	Snapshot State;
	std::array<Allocation, 3> Sources;
	std::vector<uint32_t> ReachableNodes, ReferencedVertices;
	std::vector<Region> Regions;
	uint64_t Bytes = 0;
};

inline void Validate(const Plan& plan, const std::array<Allocation, 3>& current)
{
	Require(plan.State.Object && plan.State.Event, "missing-complete-snapshot-identity");
	Require(plan.State.ExportedCount && plan.State.ExportedCount <= MaxElements &&
		plan.State.VertexExtent <= MaxElements && plan.State.IndexExtent <= MaxElements &&
		plan.State.OccupiedCount <= plan.State.IndexExtent && plan.State.OccupiedCount % 3 == 0,
		"invalid-snapshot-extents");
	for (unsigned int i = 0; i < current.size(); ++i)
	{
		Require(plan.Sources[i].Id && current[i].Id == plan.Sources[i].Id &&
			current[i].Bytes == plan.Sources[i].Bytes, "source-allocation-generation-changed");
		for (unsigned int j = 0; j < i; ++j)
			Require(current[i].Id != current[j].Id, "source-allocation-identity-alias");
	}
	Require(plan.Bytes && plan.Bytes <= MaxBytes && plan.Regions.size() <= MaxRegions, "readback-plan-budget");
	Require(plan.State.Root >= -1 && (plan.State.Root == -1 ||
		static_cast<uint32_t>(plan.State.Root) < plan.State.ExportedCount), "invalid-root");
	Require((plan.State.Root == -1) == plan.ReachableNodes.empty(), "root-reachability-mismatch");
	uint64_t destination = 0;
	size_t next = 0;
	auto expect = [&](Source source, Field field, uint32_t identity, uint64_t offset, uint64_t bytes)
	{
		Require(next < plan.Regions.size(), "missing-semantic-copy");
		const auto& r = plan.Regions[next++];
		Require(r.Buffer == source && r.Semantic == field && r.Identity == identity &&
			r.SrcOffset == offset && r.DstOffset == destination && r.Bytes == bytes,
			"wrong-semantic-copy-field-offset-or-size");
		const auto& allocation = current[static_cast<unsigned int>(source)];
		Require(bytes && offset <= allocation.Bytes && bytes <= allocation.Bytes - offset,
			"semantic-copy-outside-source-allocation");
		Require(destination <= MaxBytes && bytes <= MaxBytes - destination, "readback-byte-budget");
		destination += bytes;
	};
	expect(Source::Node, Field::Root, 0, 0, 4);
	uint32_t previous = 0;
	bool first = true;
	for (uint32_t node : plan.ReachableNodes)
	{
		Require(node < plan.State.ExportedCount && (first || node > previous), "node-identity-order-or-extent");
		first = false; previous = node;
		expect(Source::Node, Field::NodeCenter, node, NodeHeader + uint64_t(node) * NodeStride, 12);
		expect(Source::Node, Field::NodeExtents, node, NodeHeader + uint64_t(node) * NodeStride + 16, 12);
		expect(Source::Node, Field::NodeLinks, node, NodeHeader + uint64_t(node) * NodeStride + 32, 12);
	}
	if (plan.State.OccupiedCount)
		expect(Source::Index, Field::Index, 0, 0, uint64_t(plan.State.OccupiedCount) * 4);
	first = true;
	for (uint32_t vertex : plan.ReferencedVertices)
	{
		Require(vertex < plan.State.VertexExtent && (first || vertex > previous), "vertex-identity-order-or-extent");
		first = false; previous = vertex;
		expect(Source::Vertex, Field::Vertex, vertex, uint64_t(vertex) * VertexStride, 12);
	}
	Require(next == plan.Regions.size() && destination == plan.Bytes, "extra-copy-or-incomplete-destination");
}

template<typename NodeAt, typename IndexAt>
Plan Build(const Snapshot& state, const std::array<Allocation, 3>& sources,
	NodeAt nodeAt, IndexAt indexAt)
{
	Require(state.Object && state.Event, "missing-complete-snapshot-identity");
	Require(state.ExportedCount && state.ExportedCount <= MaxElements &&
		state.VertexExtent <= MaxElements && state.IndexExtent <= MaxElements &&
		state.OccupiedCount <= state.IndexExtent && state.OccupiedCount % 3 == 0,
		"invalid-snapshot-extents");
	Require(state.Root >= -1 && (state.Root == -1 || static_cast<uint32_t>(state.Root) < state.ExportedCount), "invalid-root");
	Plan result;
	result.State = state;
	result.Sources = sources;
	std::vector<unsigned char> visited(state.ExportedCount, 0);
	std::vector<uint32_t> pending;
	if (state.Root != -1) pending.push_back(static_cast<uint32_t>(state.Root));
	while (!pending.empty())
	{
		const auto id = pending.back(); pending.pop_back();
		Require(id < state.ExportedCount && !visited[id], "invalid-or-repeated-reachable-node");
		visited[id] = 1;
		const auto& node = nodeAt(id);
		result.ReachableNodes.push_back(id);
		if (node.element_index != -1)
		{
			Require(node.element_index >= 0 && node.element_index % 3 == 0 &&
				uint64_t(node.element_index) + 3 <= state.OccupiedCount && node.left == -1 && node.right == -1,
				"invalid-reachable-leaf");
		}
		else
		{
			Require(node.left >= 0 && node.right >= 0 &&
				static_cast<uint32_t>(node.left) < state.ExportedCount && static_cast<uint32_t>(node.right) < state.ExportedCount,
				"invalid-reachable-child");
			pending.push_back(static_cast<uint32_t>(node.right));
			pending.push_back(static_cast<uint32_t>(node.left));
		}
		Require(result.ReachableNodes.size() <= (MaxRegions - 1) / 3, "reachable-node-region-budget");
	}
	std::sort(result.ReachableNodes.begin(), result.ReachableNodes.end());
	std::vector<unsigned char> referenced(state.VertexExtent, 0);
	for (uint32_t i = 0; i < state.OccupiedCount; i += 3)
	{
		if (indexAt(i) == indexAt(i + 1)) continue;
		for (unsigned int j = 0; j < 3; ++j)
		{
			const auto vertex = indexAt(i + j);
			Require(vertex < state.VertexExtent, "invalid-occupied-vertex-reference");
			referenced[vertex] = 1;
		}
	}
	for (uint32_t i = 0; i < state.VertexExtent; ++i)
		if (referenced[i]) result.ReferencedVertices.push_back(i);
	auto append = [&](Source source, Field field, uint32_t identity, uint64_t offset, uint64_t bytes)
	{
		Require(result.Regions.size() < MaxRegions && bytes <= MaxBytes - result.Bytes, "readback-plan-budget");
		result.Regions.push_back({ source, field, identity, offset, result.Bytes, bytes });
		result.Bytes += bytes;
	};
	append(Source::Node, Field::Root, 0, 0, 4);
	for (uint32_t node : result.ReachableNodes)
	{
		append(Source::Node, Field::NodeCenter, node, NodeHeader + uint64_t(node) * NodeStride, 12);
		append(Source::Node, Field::NodeExtents, node, NodeHeader + uint64_t(node) * NodeStride + 16, 12);
		append(Source::Node, Field::NodeLinks, node, NodeHeader + uint64_t(node) * NodeStride + 32, 12);
	}
	if (state.OccupiedCount) append(Source::Index, Field::Index, 0, 0, uint64_t(state.OccupiedCount) * 4);
	for (uint32_t vertex : result.ReferencedVertices)
		append(Source::Vertex, Field::Vertex, vertex, uint64_t(vertex) * VertexStride, 12);
	Validate(result, sources);
	return result;
}

struct FenceIdentity
{
	uint64_t Submission = 0, Handle = 0;
	unsigned int Slot = 0;
};

class Completion
{
public:
	void Record(uint64_t command, uint64_t recording)
	{
		Require(Phase == 0 && command && recording, "invalid-readback-command-generation");
		Command = command; Recording = recording; Phase = 1;
	}
	void Submit(uint64_t command, uint64_t recording, FenceIdentity fence)
	{
		Require(Phase == 1 && command == Command && recording == Recording && fence.Submission && fence.Handle,
			"readback-submit-identity-mismatch");
		Fence = fence; Phase = 2;
	}
	void Complete(FenceIdentity fence, bool success)
	{
		Require(Phase == 2 && success && fence.Submission == Fence.Submission &&
			fence.Handle == Fence.Handle && fence.Slot == Fence.Slot, "readback-fence-generation-mismatch");
		Phase = 3;
	}
	void RequireReadable() const { Require(Phase == 3, "readback-before-successful-original-fence"); }
	uint64_t Command = 0, Recording = 0;
	FenceIdentity Fence;
private:
	unsigned int Phase = 0;
};
}
