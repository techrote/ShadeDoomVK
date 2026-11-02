// CPU-only fake backend. The native Vulkan loader backend is not compiled here.
#define SDVK_PROBE_CPU_TEST
#include "instance_probe.cpp"

using namespace sdvk_attestation;

struct FakeBackend final : Backend {
    std::string fault;
    unsigned creates = 0, destroys = 0;
    explicit FakeBackend(std::string mode = {}) : fault(std::move(mode)) {}
    VkResult create(const VkInstanceCreateInfo* info, VkInstance* value) override {
        ++creates;
        require(info->enabledLayerCount == 0 && info->enabledExtensionCount == 0 && info->flags == 0,
                "CPU control: unexpected enabled layers/extensions");
        require(info->pApplicationInfo->apiVersion == VK_API_VERSION_1_1, "CPU control: wrong API contract");
        if (fault == "create-failed") return VK_ERROR_INITIALIZATION_FAILED;
        *value = fault == "null-instance" ? VK_NULL_HANDLE : reinterpret_cast<VkInstance>(uintptr_t(1));
        return VK_SUCCESS;
    }
    void bind(VkInstance) override { require(fault != "bind-failed", "Synthetic missing entry point"); }
    VkResult devices(VkInstance, uint32_t* count, VkPhysicalDevice* result) override {
        if (!result) { *count = fault == "too-many-devices" ? 17u : (fault == "no-devices" ? 0u : 1u); return VK_SUCCESS; }
        if (fault == "incomplete-devices") return VK_INCOMPLETE;
        result[0] = reinterpret_cast<VkPhysicalDevice>(uintptr_t(2));
        *count = fault == "grew-devices" ? 2u : 1u;
        return VK_SUCCESS;
    }
    VkResult extensions(VkPhysicalDevice, uint32_t* count, VkExtensionProperties* result) override {
        if (!result) { *count = fault == "too-many-extensions" ? 1025u : 1u; return VK_SUCCESS; }
        if (fault == "incomplete-extensions") return VK_INCOMPLETE;
        if (fault == "unterminated-extension") std::memset(result[0].extensionName, 'x', VK_MAX_EXTENSION_NAME_SIZE);
        else std::memcpy(result[0].extensionName, VK_EXT_PCI_BUS_INFO_EXTENSION_NAME, sizeof(VK_EXT_PCI_BUS_INFO_EXTENSION_NAME));
        *count = 1;
        return VK_SUCCESS;
    }
    void properties(VkPhysicalDevice, VkPhysicalDeviceProperties2* result) override {
        result->properties.vendorID = 1;
        result->properties.deviceID = 2;
        result->properties.deviceType = VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU;
        result->properties.driverVersion = 123;
        const char name[] = "Synthetic CPU \"device\"\n";
        if (fault == "unterminated-name") std::memset(result->properties.deviceName, 'x', VK_MAX_PHYSICAL_DEVICE_NAME_SIZE);
        else std::memcpy(result->properties.deviceName, name, sizeof(name));
        auto* ids = static_cast<VkPhysicalDeviceIDProperties*>(result->pNext);
        ids->deviceUUID[0] = 1;
        auto* pci = static_cast<VkPhysicalDevicePCIBusInfoPropertiesEXT*>(ids->pNext);
        require(pci != nullptr, "CPU control: advertised PCI extension was not queried");
        pci->pciBus = 7;
    }
    std::vector<std::string> modules() override {
        return fault == "empty-modules" ? std::vector<std::string>{} : std::vector<std::string>{"C:\\synthetic\\CPU_ONLY.dll"};
    }
    void destroy(VkInstance value) override {
        require(value != VK_NULL_HANDLE, "CPU control: null destroy");
        ++destroys;
        require(fault != "cleanup-failed", "Synthetic cleanup failure");
    }
};

int main() {
    try {
        FakeBackend positive;
        const auto json = collect(positive);
        require(positive.creates == 1 && positive.destroys == 1, "Positive lifecycle count changed");
        require(json.find("\"driver_version_raw\":123") != std::string::npos &&
                json.find("\"pci_bus_info_available\":true") != std::string::npos &&
                json.find("\\\"device\\\"\\u000a") != std::string::npos,
                "Native schema or escaping changed");
        unsigned negatives = 0;
        for (const char* fault : {"create-failed", "null-instance", "bind-failed", "too-many-devices", "no-devices",
                                  "incomplete-devices", "grew-devices", "too-many-extensions", "incomplete-extensions",
                                  "unterminated-extension", "unterminated-name", "empty-modules", "cleanup-failed"}) {
            FakeBackend api(fault);
            bool rejected = false;
            try { collect(api); } catch (const std::exception&) { rejected = true; }
            require(rejected && api.creates == 1, "Negative admitted or create retried");
            require(api.destroys == ((api.fault == "create-failed" || api.fault == "null-instance") ? 0u : 1u),
                    "Cleanup omitted or repeated");
            ++negatives;
        }
        std::cout << "{\"scope\":\"CPU_FAKE_BACKEND_NO_VULKAN_LOADER\",\"positive\":1,\"negatives\":" << negatives << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
