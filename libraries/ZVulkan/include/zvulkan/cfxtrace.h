#pragma once

// CFX-002: synchronous, bounded forensic breadcrumbs. Only a launch with both
// environment variables writes a trace. Keep this independent of engine shutdown.
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <mutex>
#include <string>
#include <thread>

namespace CfxTrace
{
struct TraceState
{
	std::mutex mutex;
	std::FILE* file = nullptr;
	std::string path;
	std::string run;
	std::atomic<uint64_t> frame{ 0 };
	std::atomic<uint64_t> tic{ 0 };
	std::atomic<uint64_t> submission{ 0 };
	std::atomic<bool> deviceLost{ false };
	unsigned int records = 0;
	bool resources = false;
	std::atomic<uint64_t> resourceId{ 0 };
	std::atomic<unsigned> resourceRecords{ 0 };
	std::atomic<uint64_t> hashBytes{ 0 };
	TraceState()
	{
		const char* path = std::getenv("CFX_TRACE_FILE");
		const char* run = std::getenv("CFX_RUN_ID");
		if (path && *path && run && *run)
		{
			this->path = path;
			this->run = run;
			file = std::fopen(path, "wb");
			if (file)
			{
				std::fprintf(file, "# CFX-002 trace v1 run=%s\nms_utc\tthread\tframe\ttic\tsubmission\tstage\tevent\tdetail\tresult\n", run);
				std::fflush(file);
				const char* resources = std::getenv("CFX_RESOURCE_TRACE");
				this->resources = resources && std::string(resources) == "1";
			}
		}
	}
	~TraceState() { if (file) std::fclose(file); }
};

inline TraceState& State() { static TraceState state; return state; }
inline bool Enabled() { return State().file != nullptr; }
inline const char*& CurrentStage() { static thread_local const char* stage = "startup"; return stage; }
inline void Mark(const char* event, const char* detail = "", int result = 0)
{
	auto& s = State();
	if (!s.file) return;
	std::lock_guard<std::mutex> guard(s.mutex);
	if (s.records >= 100000)
	{
		std::fclose(s.file);
		s.file = std::fopen(s.path.c_str(), "wb");
		s.records = 0;
		if (!s.file) return;
		std::fprintf(s.file, "# CFX-002 trace v1 run=%s (rotated tail)\nms_utc\tthread\tframe\ttic\tsubmission\tstage\tevent\tdetail\tresult\n", s.run.c_str());
	}
	const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
	const auto thread = std::hash<std::thread::id>{}(std::this_thread::get_id());
	std::fprintf(s.file, "%lld\t%llu\t%llu\t%llu\t%llu\t%s\t%s\t%s\t%d\n",
		static_cast<long long>(ms), static_cast<unsigned long long>(thread),
		static_cast<unsigned long long>(s.frame.load()), static_cast<unsigned long long>(s.tic.load()),
		static_cast<unsigned long long>(s.submission.load()),
		CurrentStage(), event, detail, result);
	std::fflush(s.file);
	++s.records;
}
// Resource evidence has its own cap so it cannot displace the CPU/failure timeline.
inline bool ResourcesEnabled() { return Enabled() && State().resources; }
inline uint64_t NewResourceId()
{
	if (!ResourcesEnabled()) return 0;
	const auto id = ++State().resourceId;
	if (id == 1) Mark("resource-trace-config", "records=8192 hash_per_upload=16777216 hash_per_run=67108864 algorithm=fnv1a64");
	return id;
}
inline bool ResourceRecord()
{
	if (!ResourcesEnabled()) return false;
	const unsigned n = State().resourceRecords.fetch_add(1);
	if (n == 8192) Mark("resource-trace-truncated", "records=8192; subsequent resource records omitted");
	return n < 8192;
}
inline void ResourceMark(const char* event, const char* detail)
{
	if (ResourceRecord()) Mark(event, detail);
}
inline void Object(const char* event, const char* kind, uint64_t id, uint64_t handle, uint64_t size = 0, const char* name = "")
{
	if (!ResourcesEnabled()) return;
	char detail[320];
	std::snprintf(detail, sizeof(detail), "kind=%s id=%llu handle=0x%llx bytes=%llu name=%.120s",
		kind, (unsigned long long)id, (unsigned long long)handle, (unsigned long long)size, name);
	ResourceMark(event, detail);
}
inline void Upload(uint64_t srcId, uint64_t dstId, uint64_t srcOffset, uint64_t dstOffset, const void* bytes, uint64_t size)
{
	if (!ResourceRecord()) return;
	// Full FNV-1a byte fingerprint, not a cryptographic/content identity. Never sample
	// an over-budget upload and label it complete. Reserve before dereferencing bytes.
	const char* coverage = "omitted-budget";
	uint64_t hash = 14695981039346656037ull;
	constexpr uint64_t perUpload = 16ull * 1024 * 1024, perRun = 64ull * 1024 * 1024;
	uint64_t used = State().hashBytes.load();
	bool reserved = false;
	if (bytes && size <= perUpload)
	{
		while (used <= perRun && size <= perRun - used)
		{
			if (State().hashBytes.compare_exchange_weak(used, used + size)) { reserved = true; break; }
		}
	}
	if (reserved)
	{
		coverage = "complete";
		const auto* data = static_cast<const unsigned char*>(bytes);
		for (uint64_t i = 0; i < size; ++i) { hash ^= data[i]; hash *= 1099511628211ull; }
	}
	else if (!bytes) coverage = "unavailable";
	char detail[320];
	std::snprintf(detail, sizeof(detail), "src_id=%llu dst_id=%llu src_offset=%llu dst_offset=%llu bytes=%llu coverage=%s fnv1a64=0x%llx",
		(unsigned long long)srcId, (unsigned long long)dstId, (unsigned long long)srcOffset,
		(unsigned long long)dstOffset, (unsigned long long)size, coverage, (unsigned long long)(reserved ? hash : 0));
	Mark("upload-packed", detail);
}
inline void NextFrame() { if (Enabled()) { State().frame++; Mark("frame", "begin"); } }
inline void SetTic(uint64_t tic) { if (Enabled()) State().tic.store(tic); }
inline uint64_t NextSubmission() { return ++State().submission; }

class Stage
{
public:
	explicit Stage(const char* name) : active(Enabled()), previous(active ? CurrentStage() : nullptr)
	{ if (active) { CurrentStage() = name; Mark("stage-enter", name); } }
	~Stage() { if (active) { Mark("stage-complete", CurrentStage()); CurrentStage() = previous; } }
private:
	bool active;
	const char* previous;
};
}
