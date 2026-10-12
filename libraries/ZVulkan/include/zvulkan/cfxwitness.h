#pragma once

// SDVK-009: optional CPU command/publication evidence. This deliberately has no
// Vulkan calls, handle lookup table, renderer wait or lifetime authority. Typed
// owners carry their own allocation identity. The exclusive output is separate
// from the historical CFX trace and its unchanged 8192-resource-record limit.
#include <array>
#include <memory>
#include <vector>
#include <limits>
#include <cstring>
#include <filesystem>

namespace CfxTrace
{
constexpr uint64_t WitnessRecordLimit = 262144;
constexpr uint64_t WitnessStreamByteLimit = 128ull * 1024 * 1024;
constexpr uint64_t WitnessBlobLimit = 16ull * 1024 * 1024;
constexpr uint64_t WitnessBlobRunLimit = 128ull * 1024 * 1024;
constexpr size_t WitnessStageLimit = 8, WitnessLibraryLimit = 8;
constexpr size_t WitnessSetLimit = 8, WitnessDynamicLimit = 16, WitnessSpecializationLimit = 64;

inline std::FILE* WitnessOpenExclusive(const char* path)
{
	std::FILE* file = nullptr;
#ifdef _MSC_VER
	fopen_s(&file, path, "wbx");
#else
	file = std::fopen(path, "wbx");
#endif
	return file;
}

struct PublicationWitnessState
{
	std::mutex mutex;
	std::FILE* file = nullptr;
	std::string directory;
	std::atomic<bool> active{false};
	uint64_t records = 0, streamBytes = 0, blobBytes = 0, uploadHashBytes = 0, operations = 0;
	bool failed = false, closed = false;
	PublicationWitnessState()
	{
		const char* dir = std::getenv("CFX_WITNESS_DIR");
		if (!ResourcesEnabled() || !dir || !*dir) return;
		directory = dir;
		const auto path = directory + "/publication-witness.tsv";
		file = WitnessOpenExclusive(path.c_str());
		if (!file)
		{
			Mark("publication-witness-failed", "reason=exclusive-open");
			return;
		}
		const int headerBytes = std::fprintf(file, "# cfx-publication-v1\nseq\tevent\tdetail\n");
		if (headerBytes < 0 || std::fflush(file) != 0)
		{
			std::fclose(file); file = nullptr;
			Mark("publication-witness-failed", "reason=header-write");
			return;
		}
		streamBytes = (uint64_t)headerBytes;
		active.store(true);
		Mark("publication-witness-enabled", "schema=cfx-publication-v1 records=262144 stream_bytes=134217728");
	}
};

inline PublicationWitnessState& WitnessState()
{
	// Like the forensic trace, remain valid during renderer atexit callbacks.
	static auto* state = new PublicationWitnessState();
	return *state;
}
inline bool WitnessEnabled() { return WitnessState().active.load(); }

class WitnessOperation
{
public:
	WitnessOperation()
	{
		auto& s = WitnessState();
		if (!s.active.load()) return;
		std::lock_guard<std::mutex> guard(s.mutex);
		if (s.active.load() && !s.closed) { ++s.operations; active = true; }
	}
	~WitnessOperation()
	{
		if (!active) return;
		auto& s = WitnessState();
		std::lock_guard<std::mutex> guard(s.mutex);
		--s.operations;
	}
	WitnessOperation(const WitnessOperation&) = delete;
	WitnessOperation& operator=(const WitnessOperation&) = delete;
private:
	bool active = false;
};

inline void WitnessFailLocked(PublicationWitnessState& s, const char* reason)
{
	if (s.failed || s.closed) return;
	s.failed = true;
	if (s.file)
	{
		std::fprintf(s.file, "%llu\twitness-failed\treason=%s\n", (unsigned long long)++s.records, reason);
		std::fflush(s.file);
	}
	s.active.store(false);
	Mark("publication-witness-failed", reason);
}
inline void WitnessFail(const char* reason)
{
	auto& s = WitnessState();
	std::lock_guard<std::mutex> guard(s.mutex);
	WitnessFailLocked(s, reason);
}
inline void WitnessMark(const char* event, const char* detail)
{
	auto& s = WitnessState();
	if (!s.active.load()) return;
	std::lock_guard<std::mutex> guard(s.mutex);
	if (!s.active.load() || !s.file) return;
	if (s.records >= WitnessRecordLimit - 2) { WitnessFailLocked(s, "record-limit"); return; }
	const uint64_t reserve = std::strlen(event) + std::strlen(detail) + 32;
	if (s.streamBytes > WitnessStreamByteLimit - 1024 || reserve > WitnessStreamByteLimit - 1024 - s.streamBytes)
	{ WitnessFailLocked(s, "stream-byte-limit"); return; }
	const int written = std::fprintf(s.file, "%llu\t%s\t%s\n", (unsigned long long)++s.records, event, detail);
	if (written < 0 || std::fflush(s.file) != 0) WitnessFailLocked(s, "record-write");
	else s.streamBytes += (uint64_t)written;
}
inline std::string WitnessFilePath(const char* leaf)
{
	if (!leaf || !*leaf) return {};
	for (const char* p = leaf; *p; ++p)
		if (!( (*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') || (*p >= '0' && *p <= '9') || *p == '.' || *p == '-' || *p == '_' ))
			return {};
	if (std::string(leaf) == "." || std::string(leaf) == "..") return {};
	return WitnessState().directory.empty() ? std::string() : WitnessState().directory + "/" + leaf;
}
inline void WitnessFinish()
{
	auto& s = WitnessState();
	std::lock_guard<std::mutex> guard(s.mutex);
	if (!s.file || s.closed) return;
	// Background pipeline workers may still own a partially emitted group or an
	// exclusive blob write. Never wait for them or claim a complete prefix while
	// they can still finish publishing evidence begun inside this interval.
	if (s.operations) WitnessFailLocked(s, "in-flight-operation-at-finish");
	const uint64_t before = s.records;
	if (std::fprintf(s.file, "%llu\twitness-summary\trecords=%llu failures=%u closed=1\n", (unsigned long long)++s.records,
		(unsigned long long)before, s.failed ? 1u : 0u) < 0 || std::fflush(s.file) != 0)
		WitnessFailLocked(s, "summary-write");
	const int closeResult = std::fclose(s.file);
	s.file = nullptr; s.closed = true; s.active.store(false);
	if (closeResult != 0) { s.failed = true; Mark("publication-witness-failed", "reason=close"); }
	if (s.failed) return;
	// Publish completion only after both files have closed successfully. An
	// atomic no-overwrite hard link never exposes a still-being-written marker.
	// Unsupported filesystems fail closed for this optional evidence mode.
	const auto pending = s.directory + "/publication-witness.complete.pending";
	const auto complete = s.directory + "/publication-witness.complete";
	auto* marker = WitnessOpenExclusive(pending.c_str());
	if (!marker) { s.failed = true; Mark("publication-witness-failed", "reason=completion-exclusive-open"); return; }
	const bool markerWritten = std::fprintf(marker, "schema=cfx-publication-complete-v1\nrecords=%llu\nfailures=0\n", (unsigned long long)s.records) >= 0;
	const bool markerClosed = std::fclose(marker) == 0;
	if (!markerWritten || !markerClosed) { s.failed = true; Mark("publication-witness-failed", "reason=completion-write"); return; }
	std::error_code error;
	std::filesystem::create_hard_link(pending, complete, error);
	if (error) { s.failed = true; Mark("publication-witness-failed", "reason=completion-link"); }
}
inline void WitnessObject(const char* event, const char* kind, uint64_t id, uint64_t handle, uint64_t size)
{
	if (!WitnessEnabled()) return;
	char detail[220];
	std::snprintf(detail, sizeof(detail), "kind=%s id=%llu handle=0x%llx bytes=%llu", kind,
		(unsigned long long)id, (unsigned long long)handle, (unsigned long long)size);
	WitnessMark(event, detail);
}
inline uint64_t WitnessFingerprint(const void* data, uint64_t size)
{
	uint64_t hash = 14695981039346656037ull;
	const auto* bytes = static_cast<const unsigned char*>(data);
	for (uint64_t i = 0; i < size; ++i) { hash ^= bytes[i]; hash *= 1099511628211ull; }
	return hash;
}
struct WitnessBlob
{
	uint64_t bytes = 0, hash = 0;
	std::string file = "none";
	bool complete = false;
};
inline WitnessBlob WitnessExportBytes(const char* leaf, const void* bytes, uint64_t size)
{
	WitnessOperation operation;
	WitnessBlob out;
	if (!WitnessEnabled()) return out;
	auto& s = WitnessState();
	{
		std::lock_guard<std::mutex> guard(s.mutex);
		if (size > WitnessBlobLimit || s.blobBytes > WitnessBlobRunLimit || size > WitnessBlobRunLimit - s.blobBytes || (size && !bytes))
		{ WitnessFailLocked(s, "blob-budget-or-unavailable"); return out; }
		s.blobBytes += size;
	}
	// Reserve the entire bounded extent before reading even one source byte.
	out.bytes = size; out.hash = WitnessFingerprint(bytes, size);
	if (size)
	{
		const auto path = WitnessFilePath(leaf);
		auto* file = path.empty() ? nullptr : WitnessOpenExclusive(path.c_str());
		if (!file) { WitnessFail("blob-exclusive-open"); return out; }
		const bool written = std::fwrite(bytes, 1, (size_t)size, file) == size;
		const bool closed = std::fclose(file) == 0;
		if (!written || !closed) { WitnessFail("blob-write"); return out; }
		out.file = leaf;
	}
	out.complete = true;
	return out;
}
inline void WitnessUpload(uint64_t srcId, uint64_t dstId, uint64_t srcOffset, uint64_t dstOffset, const void* bytes, uint64_t size)
{
	if (!WitnessEnabled()) return;
	auto& s = WitnessState();
	{
		std::lock_guard<std::mutex> guard(s.mutex);
		if (!bytes || size > WitnessBlobLimit || s.uploadHashBytes > WitnessBlobRunLimit || size > WitnessBlobRunLimit - s.uploadHashBytes)
		{ WitnessFailLocked(s, "upload-hash-budget-or-unavailable"); return; }
		s.uploadHashBytes += size;
	}
	char detail[320];
	std::snprintf(detail, sizeof(detail), "src_id=%llu dst_id=%llu src_offset=%llu dst_offset=%llu bytes=%llu coverage=complete fnv1a64=0x%llx",
		(unsigned long long)srcId, (unsigned long long)dstId, (unsigned long long)srcOffset, (unsigned long long)dstOffset,
		(unsigned long long)size, (unsigned long long)WitnessFingerprint(bytes, size));
	WitnessMark("upload-packed", detail);
}

struct WitnessAllocation
{
	uint64_t id = 0;
	std::atomic<bool> alive{true};
};
struct WitnessDescriptor : WitnessAllocation
{
	std::atomic<uint64_t> generation{0};
};
struct WitnessShader
{
	uint64_t id = 0;
	WitnessBlob code;
};
struct WitnessSpecializationEntry { uint32_t id = 0, offset = 0; uint64_t bytes = 0; };
struct WitnessPipelineStage
{
	uint64_t sourcePipeline = 0;
	uint32_t stage = 0;
	WitnessShader shader;
	std::string entry = "main";
	WitnessBlob specialization;
	std::vector<WitnessSpecializationEntry> entries;
};
struct WitnessPipeline : WitnessAllocation
{
	uint64_t layoutId = 0;
	uint32_t flags = 0, libraryFlags = 0;
	std::string kind;
	std::vector<std::shared_ptr<const WitnessPipelineStage>> stages;
	std::vector<uint64_t> libraries;
	bool complete = false;
};
inline void WitnessRecordPipeline(const WitnessPipeline& p)
{
	WitnessOperation operation;
	if (!WitnessEnabled()) return;
	if (!p.complete || p.stages.size() > WitnessStageLimit || p.libraries.size() > WitnessLibraryLimit)
	{ WitnessFail("pipeline-identity-incomplete"); return; }
	char detail[640];
	std::snprintf(detail, sizeof(detail), "pipeline_id=%llu kind=%s layout_id=%llu flags=%u library_flags=%u stages=%u libraries=%u coverage=complete",
		(unsigned long long)p.id, p.kind.c_str(), (unsigned long long)p.layoutId, p.flags, p.libraryFlags, (unsigned)p.stages.size(), (unsigned)p.libraries.size());
	WitnessMark("pipeline-created", detail);
	for (size_t i = 0; i < p.stages.size(); ++i)
	{
		const auto& stage = *p.stages[i];
		std::snprintf(detail, sizeof(detail), "pipeline_id=%llu ordinal=%u source_pipeline_id=%llu stage=%u shader_id=%llu entry=%s specialization_entries=%u specialization_bytes=%llu specialization_file=%s specialization_fnv1a64=0x%llx coverage=%s",
			(unsigned long long)p.id, (unsigned)i, (unsigned long long)stage.sourcePipeline, stage.stage, (unsigned long long)stage.shader.id,
			stage.entry.c_str(), (unsigned)stage.entries.size(), (unsigned long long)stage.specialization.bytes, stage.specialization.file.c_str(),
			(unsigned long long)stage.specialization.hash, stage.shader.code.complete && stage.specialization.complete ? "complete" : "unknown");
		WitnessMark("pipeline-stage", detail);
		for (size_t j = 0; j < stage.entries.size(); ++j)
		{
			const auto& e = stage.entries[j];
			std::snprintf(detail, sizeof(detail), "pipeline_id=%llu stage_ordinal=%u ordinal=%u constant_id=%u offset=%u bytes=%llu",
				(unsigned long long)p.id, (unsigned)i, (unsigned)j, e.id, e.offset, (unsigned long long)e.bytes);
			WitnessMark("pipeline-specialization", detail);
		}
	}
	for (size_t i = 0; i < p.libraries.size(); ++i)
	{
		std::snprintf(detail, sizeof(detail), "pipeline_id=%llu ordinal=%u library_id=%llu", (unsigned long long)p.id, (unsigned)i, (unsigned long long)p.libraries[i]);
		WitnessMark("pipeline-library", detail);
	}
}

struct WitnessBoundSet
{
	std::shared_ptr<WitnessDescriptor> identity;
	uint64_t generation = 0, bindOrdinal = 0, layoutId = 0;
	uint32_t dynamicCount = 0;
	std::array<uint32_t, WitnessDynamicLimit> dynamic{};
	bool complete = false;
};
struct WitnessBoundState
{
	std::shared_ptr<WitnessPipeline> pipeline;
	uint64_t pipelineBindOrdinal = 0;
	std::array<WitnessBoundSet, WitnessSetLimit> sets;
};
struct WitnessCommand
{
	uint64_t ordinal = 0;
	std::array<WitnessBoundState, 2> bindPoints;
	void Begin() { ordinal = 0; bindPoints = {}; }
	void BindPipeline(uint64_t cmd, uint64_t recording, uint32_t point, const std::shared_ptr<WitnessPipeline>& pipeline)
	{
		if (!WitnessEnabled()) return;
		++ordinal;
		if (point < bindPoints.size()) { bindPoints[point].pipeline = pipeline; bindPoints[point].pipelineBindOrdinal = ordinal; }
		char detail[250];
		std::snprintf(detail, sizeof(detail), "cmd_id=%llu recording=%llu ordinal=%llu bind_point=%u pipeline_id=%llu coverage=%s",
			(unsigned long long)cmd, (unsigned long long)recording, (unsigned long long)ordinal, point,
			(unsigned long long)(pipeline ? pipeline->id : 0), pipeline && point < bindPoints.size() ? "complete" : "unknown");
		WitnessMark("bind-pipeline", detail);
	}
	void BindSet(uint64_t cmd, uint64_t recording, uint32_t point, uint64_t layoutId, uint32_t index, const std::shared_ptr<WitnessDescriptor>& descriptor, uint32_t count, const uint32_t* offsets)
	{
		if (!WitnessEnabled()) return;
		++ordinal;
		const bool complete = descriptor && index < WitnessSetLimit && point < bindPoints.size() && count <= WitnessDynamicLimit && (!count || offsets);
		if (point < bindPoints.size())
		{
			// Binding through an incompatible layout can disturb other sets. We
			// have exact layout allocation identity, not a compatibility proof for
			// distinct layouts, so retained sets become unknown until rebound.
			for (auto& previous : bindPoints[point].sets)
				if (previous.bindOrdinal && (!layoutId || previous.layoutId != layoutId)) previous.complete = false;
		}
		if (index < WitnessSetLimit && point < bindPoints.size())
		{
			auto& set = bindPoints[point].sets[index];
			set = {}; set.identity = descriptor; set.generation = descriptor ? descriptor->generation.load() : 0;
			set.bindOrdinal = ordinal; set.layoutId = layoutId; set.dynamicCount = count; set.complete = complete;
			if (complete) for (uint32_t i = 0; i < count; ++i) set.dynamic[i] = offsets[i];
		}
		char detail[330];
		std::snprintf(detail, sizeof(detail), "cmd_id=%llu recording=%llu ordinal=%llu bind_point=%u layout_id=%llu set_index=%u set_id=%llu generation=%llu dynamic_count=%u coverage=%s",
			(unsigned long long)cmd, (unsigned long long)recording, (unsigned long long)ordinal, point, (unsigned long long)layoutId, index,
			(unsigned long long)(descriptor ? descriptor->id : 0), (unsigned long long)(descriptor ? descriptor->generation.load() : 0), count, complete ? "complete" : "unknown");
		WitnessMark("bind-set", detail);
	}
	void Consume(uint64_t cmd, uint64_t recording, uint32_t point, const char* kind, const char* args)
	{
		if (!WitnessEnabled()) return;
		++ordinal;
		if (point >= bindPoints.size()) { WitnessFail("unsupported-bind-point"); return; }
		const auto& state = bindPoints[point];
		char detail[700];
		std::snprintf(detail, sizeof(detail), "cmd_id=%llu recording=%llu ordinal=%llu frame=%llu bind_point=%u kind=%s pipeline_id=%llu pipeline_bind_ordinal=%llu pipeline_alive=%u coverage=%s %s",
			(unsigned long long)cmd, (unsigned long long)recording, (unsigned long long)ordinal, (unsigned long long)State().frame.load(), point, kind,
			(unsigned long long)(state.pipeline ? state.pipeline->id : 0), (unsigned long long)state.pipelineBindOrdinal,
			state.pipeline && state.pipeline->alive.load() ? 1u : 0u, state.pipeline && state.pipeline->complete ? "complete" : "unknown", args);
		WitnessMark("consume", detail);
		for (size_t i = 0; i < state.sets.size(); ++i)
		{
			const auto& set = state.sets[i];
			if (!set.bindOrdinal) continue;
			std::snprintf(detail, sizeof(detail), "cmd_id=%llu recording=%llu ordinal=%llu bind_point=%u set_index=%u set_id=%llu layout_id=%llu bind_ordinal=%llu bound_generation=%llu publication_generation=%llu set_alive=%u dynamic_count=%u coverage=%s",
				(unsigned long long)cmd, (unsigned long long)recording, (unsigned long long)ordinal, point, (unsigned)i,
				(unsigned long long)(set.identity ? set.identity->id : 0), (unsigned long long)set.layoutId, (unsigned long long)set.bindOrdinal,
				(unsigned long long)set.generation, (unsigned long long)(set.identity ? set.identity->generation.load() : 0),
				set.identity && set.identity->alive.load() ? 1u : 0u, set.dynamicCount, set.complete ? "complete" : "unknown");
			WitnessMark("consume-set", detail);
			if (set.complete) for (uint32_t j = 0; j < set.dynamicCount; ++j)
			{
				std::snprintf(detail, sizeof(detail), "cmd_id=%llu recording=%llu ordinal=%llu bind_point=%u set_index=%u offset_index=%u offset=%u",
					(unsigned long long)cmd, (unsigned long long)recording, (unsigned long long)ordinal, point, (unsigned)i, j, set.dynamic[j]);
				WitnessMark("consume-offset", detail);
			}
		}
	}
};
}
