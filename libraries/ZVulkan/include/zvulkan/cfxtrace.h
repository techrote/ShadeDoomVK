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
