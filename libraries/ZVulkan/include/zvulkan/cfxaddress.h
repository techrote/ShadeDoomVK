#pragma once

// CFX-007 offline follow-up: driver-reported virtual bindings, not queried BDA.
// No Vulkan/engine calls from the driver callback. Never retain callback pointers.
#include "vulkan/vulkan_core.h"
#include "cfxtrace.h"

namespace CfxAddress
{
constexpr unsigned RecordLimit = 32768;
// Each producer owns one immutable slot. The sole drain thread owns stdio.
// No callback waits for a mutex, another producer or a filesystem operation.
struct AddressRecord
{
    std::atomic<bool> ready{ false };
    int64_t ms = 0;
    uint64_t thread = 0, frame = 0, tic = 0, submission = 0, base = 0, bytes = 0, handle = 0;
    unsigned flags = 0, type = 0, index = 0, count = 0;
    char event[32] = {}, name[121] = {};
};
static_assert(std::atomic<unsigned>::is_always_lock_free && std::atomic<bool>::is_always_lock_free,
    "Address callback publication requires lock-free atomics");
static_assert(sizeof(AddressRecord) <= 320, "Address capture storage must remain bounded");
struct AddressState
{
    std::FILE* file = nullptr;
    AddressRecord* slots = nullptr;
    std::atomic<bool> enabled{ false };
    std::atomic<unsigned> records{ 0 }, omitted{ 0 }, flushed{ 0 };
    bool requested = false;
    void Drain() noexcept
    {
        unsigned next = 0;
        while (enabled.load())
        {
            unsigned end = next;
            // A preempted producer leaves a visible coverage gap; the consumer
            // never reads its uncommitted payload or skips it out of order.
            while (end < RecordLimit && end < next + 256 && slots[end].ready.load(std::memory_order_acquire))
            {
                const auto& r = slots[end];
                const int written = std::fprintf(file, "%u\t%lld\t%llu\t%llu\t%llu\t%llu\t%s\t0x%llx\t%llu\t%u\t%u\t0x%llx\t%u\t%u\t%s\n",
                    end + 1, (long long)r.ms, (unsigned long long)r.thread,
                    (unsigned long long)r.frame, (unsigned long long)r.tic, (unsigned long long)r.submission,
                    r.event, (unsigned long long)r.base, (unsigned long long)r.bytes,
                    r.flags, r.type, (unsigned long long)r.handle, r.index, r.count, r.name);
                if (written < 0) { enabled.store(false); return; }
                ++end;
            }
            if (end != next)
            {
                if (std::fflush(file) != 0) { enabled.store(false); return; }
                next = end; flushed.store(next, std::memory_order_release);
            }
            else std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
    }
    AddressState()
    {
        const char* mode = std::getenv("CFX_ADDRESS_TRACE");
        const char* path = std::getenv("CFX_ADDRESS_FILE");
        requested = CfxTrace::ResourcesEnabled() && mode && std::string(mode) == "1";
        if (!requested || !path || !*path) return;
        file = std::fopen(path, "wb");
        if (!file) return;
        std::fprintf(file, "# CFX address bindings v1 run=%s\nseq\tms_utc\tthread\tframe\ttic\tsubmission\tevent\tbase\tbytes\tflags\tobject_type\thandle\tobject_index\tobject_count\tname\n", CfxTrace::State().run.c_str());
        if (std::fflush(file) != 0) return;
        try
        {
            // <=10MiB, opt-in only, allocated before registering the messenger.
            slots = new AddressRecord[RecordLimit];
            enabled.store(true);
            std::thread([this] { Drain(); }).detach();
        }
        catch (...) { enabled.store(false); }
    }
};
// Process lifetime includes queued payloads and all driver teardown callbacks.
inline AddressState& State() { static AddressState* state = new AddressState(); return *state; }
inline bool Enabled() { return State().enabled.load(); }
inline unsigned Write(const char* event, uint64_t base, uint64_t bytes, unsigned flags,
    VkObjectType type, uint64_t handle, unsigned index, unsigned count, const char* name) noexcept
{
    AddressState* state = nullptr;
    try
    {
        auto& s = State(); state = &s;
        if (!s.enabled.load()) return 0;
        if (s.records.load() >= RecordLimit) { ++s.omitted; return 0; }
        const unsigned seq = s.records.fetch_add(1) + 1;
        if (seq > RecordLimit) { ++s.omitted; return 0; }
        auto& r = s.slots[seq - 1];
        for (unsigned i = 0; event && event[i] && i < sizeof(r.event) - 1; ++i) r.event[i] = event[i];
        for (unsigned i = 0; name && name[i] && i < sizeof(r.name) - 1; ++i)
            r.name[i] = static_cast<unsigned char>(name[i]) < 32 ? ' ' : name[i];
        r.ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
        r.thread = std::hash<std::thread::id>{}(std::this_thread::get_id());
        auto& cpu = CfxTrace::State();
        r.frame = cpu.frame.load(); r.tic = cpu.tic.load(); r.submission = cpu.submission.load();
        r.base = base; r.bytes = bytes; r.flags = flags; r.type = static_cast<unsigned>(type);
        r.handle = handle; r.index = index; r.count = count;
        r.ready.store(true, std::memory_order_release);
        return seq;
    }
    catch (...)
    {
        if (state) { state->enabled.store(false); ++state->omitted; }
        // A diagnostic must never unwind through a Vulkan callback.
        return 0;
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
        const unsigned cutoff = Write("snapshot", 0, 0, 0, VK_OBJECT_TYPE_UNKNOWN, 0, 0, 0, reason);
        // Loss/teardown waits only here, outside the callback, for <=100ms.
        // A blocked filesystem or unpublished producer remains an explicit gap.
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(100);
        const unsigned target = cutoff ? cutoff : std::min(s.records.load(), RecordLimit);
        while (target && s.enabled.load() && s.flushed.load() < target && std::chrono::steady_clock::now() < deadline)
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        char line[240];
        std::snprintf(line, sizeof(line), "reason=%s records=%u omitted=%u contended=0 writer_ok=%u limit=%u flushed=%u cutoff=%u",
            reason, std::min(s.records.load(), RecordLimit), s.omitted.load(), (unsigned)s.enabled.load(),
            RecordLimit, s.flushed.load(), cutoff);
		CfxTrace::Mark("address-binding-summary", line);
	}
	catch (...) { /* Never replace the original failure or break driver teardown. */ }
}
}
