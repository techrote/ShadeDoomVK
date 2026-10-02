#include "zvulkan/cfxaddress.h"
#include <cassert>
#include <cstring>
#include <thread>

int main(int argc, char** argv)
{
	assert(argc == 2);
	const std::string mode = argv[1];
	if (mode == "unavailable")
	{
		assert(!CfxAddress::Enabled() && CfxAddress::State().requested);
		CfxAddress::Snapshot("device-lost");
		return 0;
	}
	if (mode == "disabled")
	{
		assert(!CfxAddress::Enabled());
		assert(CfxAddress::Callback(VK_DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT,
			VK_DEBUG_UTILS_MESSAGE_TYPE_DEVICE_ADDRESS_BINDING_BIT_EXT,
			reinterpret_cast<VkDebugUtilsMessengerCallbackDataEXT*>(uintptr_t(1)), nullptr) == VK_FALSE);
		return 0;
	}
	assert(CfxAddress::Enabled());
	VkDeviceAddressBindingCallbackDataEXT binding = { VK_STRUCTURE_TYPE_DEVICE_ADDRESS_BINDING_CALLBACK_DATA_EXT };
	binding.baseAddress = 0x1da00000; binding.size = 4096;
	binding.flags = VK_DEVICE_ADDRESS_BINDING_INTERNAL_OBJECT_BIT_EXT;
	binding.bindingType = VK_DEVICE_ADDRESS_BINDING_TYPE_BIND_EXT;
	VkDebugUtilsObjectNameInfoEXT objects[17] = {};
	for (auto& obj : objects)
	{
		obj.sType = VK_STRUCTURE_TYPE_DEBUG_UTILS_OBJECT_NAME_INFO_EXT;
		obj.objectType = VK_OBJECT_TYPE_BUFFER; obj.objectHandle = 0xab;
		obj.pObjectName = "temporary\tname\n";
	}
	VkDebugUtilsMessengerCallbackDataEXT data = { VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CALLBACK_DATA_EXT };
	data.pNext = &binding; data.objectCount = 1; data.pObjects = objects;
	auto emit = [&] { assert(CfxAddress::Callback(VK_DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT,
		VK_DEBUG_UTILS_MESSAGE_TYPE_DEVICE_ADDRESS_BINDING_BIT_EXT, &data, nullptr) == VK_FALSE); };
	if (mode == "content")
	{
		// Wrong message stream is ignored; null pMessage is legal for this stream.
		assert(!CfxAddress::Callback(VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT,
			VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT, &data, nullptr));
		assert(CfxAddress::State().records.load() == 0);
		VkBaseInStructure prefix = { VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CALLBACK_DATA_EXT,
			reinterpret_cast<const VkBaseInStructure*>(&binding) };
		data.pNext = &prefix;
		emit();
		binding.bindingType = VK_DEVICE_ADDRESS_BINDING_TYPE_UNBIND_EXT; emit();
		CfxAddress::Write("name", 0, 0, 0, VK_OBJECT_TYPE_BUFFER, 0xab, 0, 0, "persistent-name");
		objects[0].pObjectName = nullptr; // Prior callback cannot retain or reread it.
		CfxAddress::Snapshot("device-lost");
		assert(CfxAddress::State().records.load() == 4);
	}
	else if (mode == "bounded")
	{
		data.objectCount = 17; emit();
		assert(CfxAddress::State().omitted.load() == 1);
		assert(CfxAddress::State().records.load() == 16);
		CfxAddress::State().records.store(CfxAddress::RecordLimit); emit();
		assert(CfxAddress::State().records.load() == CfxAddress::RecordLimit);
		assert(CfxAddress::State().omitted.load() == 18);
		// Capacity exhaustion is explicit and never waits on the file writer.
		std::thread worker(emit); worker.join();
		CfxAddress::Snapshot("device-lost");
	}
	else if (mode == "concurrent")
	{
		std::thread workers[8];
		for (auto& worker : workers) worker = std::thread([&] { for (unsigned n = 0; n < 1000; ++n) emit(); });
		for (auto& worker : workers) worker.join();
		// Callback-owned name memory can disappear before the queued file drain.
		objects[0].pObjectName = nullptr;
		CfxAddress::Snapshot("device-lost");
		assert(CfxAddress::State().records.load() == 8001);
		assert(CfxAddress::State().flushed.load() == 8001);
		assert(CfxAddress::State().omitted.load() == 0);
	}
	else if (mode == "unpublished")
	{
		// Model a preempted producer at slot0: drain cannot pass it. Another
		// callback still completes and snapshot returns within its fixed budget.
		auto& s = CfxAddress::State(); s.records.store(1);
		std::thread worker(emit); worker.join();
		const auto start = std::chrono::steady_clock::now();
		CfxAddress::Snapshot("device-lost");
		assert(std::chrono::steady_clock::now() - start < std::chrono::seconds(1));
		assert(s.flushed.load() == 0 && s.records.load() == 3);
		// Resume and publish the reserved immutable payload; draining recovers.
		auto& r = s.slots[0]; std::strcpy(r.event, "bind");
		r.base = binding.baseAddress; r.bytes = binding.size; r.type = VK_OBJECT_TYPE_BUFFER; r.handle = 0xab;
		r.ready.store(true, std::memory_order_release);
		CfxAddress::Snapshot("device-teardown");
		assert(s.flushed.load() == 4);
	}
	else if (mode == "malformed")
	{
		VkBaseInStructure cycle = { VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CALLBACK_DATA_EXT, nullptr };
		cycle.pNext = &cycle; data.pNext = &cycle; emit();
		data.pNext = &binding; data.pObjects = nullptr; emit();
		assert(CfxAddress::State().omitted.load() == 1);
		CfxAddress::Snapshot("device-lost");
	}
	else assert(false);
}
