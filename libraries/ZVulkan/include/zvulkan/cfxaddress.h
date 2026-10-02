#pragma once

// CFX-007 offline follow-up: driver-reported virtual bindings, not queried BDA.
// No Vulkan/engine calls from the driver callback. Never retain callback pointers.
#include "vulkan/vulkan_core.h"
#include "cfxtrace.h"

namespace CfxAddress
{
constexpr unsigned RecordLimit = 32768;
struct AddressState
{
	std::mutex mutex;
	std::FILE* file = nullptr;
	std::atomic<bool> enabled{ false };
	std::atomic<unsigned> records{ 0 }, omitted{ 0 }, contended{ 0 };
	bool requested = false;
	AddressState()
	{
		const char* mode = std::getenv("CFX_ADDRESS_TRACE");
		const char* path = std::getenv("CFX_ADDRESS_FILE");
		requested = CfxTrace::ResourcesEnabled() && mode && std::string(mode) == "1";
		if (!requested || !path || !*path) return;
		file = std::fopen(path, "wb");
		if (!file) return;
		std::fprintf(file, "# CFX address bindings v1 run=%s\nseq\tms_utc\tthread\tframe\ttic\tsubmission\tevent\tbase\tbytes\tflags\tobject_type\thandle\tobject_index\tobject_count\tname\n", CfxTrace::State().run.c_str());
		enabled.store(std::fflush(file) == 0);
	}
};
// Same process lifetime as CFX's CPU trace, including driver teardown callbacks.
inline AddressState& State() { static AddressState* state = new AddressState(); return *state; }
inline bool Enabled() { return State().enabled.load(); }
inline void Write(const char* event, uint64_t base, uint64_t bytes, unsigned flags,
	VkObjectType type, uint64_t handle, unsigned index, unsigned count, const char* name) noexcept
{
	AddressState* state = nullptr;
	try
	{
		auto& s = State();
		state = &s;
		if (!s.enabled.load()) return;
		std::unique_lock<std::mutex> lock(s.mutex, std::try_to_lock);
		if (!lock.owns_lock()) { ++s.contended; return; }
		if (s.records.load() >= RecordLimit) { ++s.omitted; return; }
		char clean[121] = {};
		for (unsigned i = 0; name && name[i] && i < 120; ++i)
			clean[i] = static_cast<unsigned char>(name[i]) < 32 ? ' ' : name[i];
		const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
		const auto thread = std::hash<std::thread::id>{}(std::this_thread::get_id());
		auto& cpu = CfxTrace::State();
		const int written = std::fprintf(s.file, "%u\t%lld\t%llu\t%llu\t%llu\t%llu\t%s\t0x%llx\t%llu\t%u\t%u\t0x%llx\t%u\t%u\t%s\n",
			++s.records, (long long)ms, (unsigned long long)thread,
			(unsigned long long)cpu.frame.load(), (unsigned long long)cpu.tic.load(), (unsigned long long)cpu.submission.load(),
			event, (unsigned long long)base, (unsigned long long)bytes, flags, (unsigned)type,
			(unsigned long long)handle, index, count, clean);
		if (written < 0 || std::fflush(s.file) != 0) s.enabled.store(false);
	}
	catch (...)
	{
		if (state) { state->enabled.store(false); ++state->omitted; }
		// A diagnostic must never unwind through a Vulkan callback.
	}
}
inline VKAPI_ATTR VkBool32 VKAPI_CALL Callback(VkDebugUtilsMessageSeverityFlagBitsEXT severity,
	VkDebugUtilsMessageTypeFlagsEXT types, const VkDebugUtilsMessengerCallbackDataEXT* data, void*) noexcept
{
	try
	{
		if (!Enabled() || severity != VK_DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT ||
			types != VK_DEBUG_UTILS_MESSAGE_TYPE_DEVICE_ADDRESS_BINDING_BIT_EXT || !data) return VK_FALSE;
		const auto* node = static_cast<const VkBaseInStructure*>(data->pNext);
		for (unsigned depth = 0; node && depth < 16; ++depth, node = node->pNext)
		{
			if (node->sType != VK_STRUCTURE_TYPE_DEVICE_ADDRESS_BINDING_CALLBACK_DATA_EXT) continue;
			const auto* binding = reinterpret_cast<const VkDeviceAddressBindingCallbackDataEXT*>(node);
			const char* event = binding->bindingType == VK_DEVICE_ADDRESS_BINDING_TYPE_BIND_EXT ? "bind" :
				binding->bindingType == VK_DEVICE_ADDRESS_BINDING_TYPE_UNBIND_EXT ? "unbind" : "unknown-binding";
			const unsigned count = data->pObjects ? std::min(data->objectCount, 16u) : 0;
			if (data->objectCount > count) State().omitted.fetch_add(data->objectCount - count);
			if (!count) Write("binding-no-object", binding->baseAddress, binding->size, binding->flags, VK_OBJECT_TYPE_UNKNOWN, 0, 0, data->objectCount, "");
			for (unsigned i = 0; i < count; ++i)
			{
				const auto& obj = data->pObjects[i];
				Write(event, binding->baseAddress, binding->size, binding->flags, obj.objectType, obj.objectHandle, i, data->objectCount, obj.pObjectName);
			}
			return VK_FALSE;
		}
		Write("binding-payload-missing", 0, 0, 0, VK_OBJECT_TYPE_UNKNOWN, 0, 0, 0, "");
	}
	catch (...) { }
	return VK_FALSE;
}
inline void Snapshot(const char* reason) noexcept
{
	try
	{
		auto& s = State();
		if (!s.requested) return;
		Write("snapshot", 0, 0, 0, VK_OBJECT_TYPE_UNKNOWN, 0, 0, 0, reason);
		char line[200];
		std::snprintf(line, sizeof(line), "reason=%s records=%u omitted=%u contended=%u writer_ok=%u limit=%u",
			reason, s.records.load(), s.omitted.load(), s.contended.load(), (unsigned)s.enabled.load(), RecordLimit);
		CfxTrace::Mark("address-binding-summary", line);
	}
	catch (...) { /* Never replace the original failure or break driver teardown. */ }
}
}
