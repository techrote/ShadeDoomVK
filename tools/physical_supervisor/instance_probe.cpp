// Instance-only attestation worker. No device, queue, surface or renderer APIs.
// Build without linking a Vulkan import library. A separate reviewed controller
// must pin/contain this worker and its loader before permitting the live flag.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define VK_NO_PROTOTYPES
#include <windows.h>
#include <psapi.h>
#include <tlhelp32.h>
#include <vulkan/vulkan.h>
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace sdvk_attestation {
constexpr uint32_t max_devices = 16;
constexpr uint32_t max_extensions = 1024;

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

std::string quote(const std::string& value) {
    std::ostringstream out;
    out << '"';
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') out << '\\' << c;
        else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(c) << std::dec;
        else out << c;
    }
    return out.str() + '"';
}

std::string hex(const uint8_t* bytes, size_t count) {
    std::ostringstream out;
    for (size_t i = 0; i < count; ++i) out << std::hex << std::setw(2) << std::setfill('0') << unsigned(bytes[i]);
    return out.str();
}

struct Backend {
    virtual ~Backend() = default;
    virtual VkResult create(const VkInstanceCreateInfo*, VkInstance*) = 0;
    virtual void bind(VkInstance) = 0;
    virtual VkResult devices(VkInstance, uint32_t*, VkPhysicalDevice*) = 0;
    virtual VkResult extensions(VkPhysicalDevice, uint32_t*, VkExtensionProperties*) = 0;
    virtual void properties(VkPhysicalDevice, VkPhysicalDeviceProperties2*) = 0;
    virtual std::vector<std::string> modules() = 0;
    virtual void destroy(VkInstance) = 0;
};

std::string collect(Backend& api) {
    VkApplicationInfo app{};
    app.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app.pApplicationName = "SDVK009 instance-only attestation";
    app.apiVersion = VK_API_VERSION_1_1;
    VkInstanceCreateInfo create{};
    create.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    create.pApplicationInfo = &app;
    VkInstance instance = VK_NULL_HANDLE;
    require(api.create(&create, &instance) == VK_SUCCESS, "vkCreateInstance failed; no retry");
    require(instance != VK_NULL_HANDLE, "Successful create returned null instance");
    try {
        api.bind(instance);
        uint32_t count = 0;
        require(api.devices(instance, &count, nullptr) == VK_SUCCESS, "Physical device count failed");
        require(count > 0 && count <= max_devices, "Physical device count outside bounded capacity");
        std::array<VkPhysicalDevice, max_devices> devices{};
        const uint32_t capacity = count;
        require(api.devices(instance, &count, devices.data()) == VK_SUCCESS, "Device enumeration incomplete/failed; no retry");
        require(count > 0 && count <= capacity, "Physical device enumeration changed capacity");
        std::ostringstream out;
        out << "{\"schema\":\"sdvk009-instance-readback/v1\",\"instance_create_calls\":1,"
               "\"logical_devices_created\":0,\"queue_submissions\":0,\"devices\":[";
        for (uint32_t i = 0; i < count; ++i) {
            require(devices[i] != VK_NULL_HANDLE, "Null physical device");
            uint32_t extension_count = 0;
            require(api.extensions(devices[i], &extension_count, nullptr) == VK_SUCCESS, "Extension count failed");
            require(extension_count <= max_extensions, "Extension count exceeds bounded capacity");
            std::array<VkExtensionProperties, max_extensions> extensions{};
            const uint32_t extension_capacity = extension_count;
            if (extension_count) {
                require(api.extensions(devices[i], &extension_count, extensions.data()) == VK_SUCCESS,
                        "Extension enumeration incomplete/failed; no retry");
                require(extension_count <= extension_capacity, "Extension count changed capacity");
            }
            bool pci_supported = false;
            for (uint32_t j = 0; j < extension_count; ++j) {
                require(std::memchr(extensions[j].extensionName, 0, VK_MAX_EXTENSION_NAME_SIZE) != nullptr,
                        "Unterminated extension name");
                pci_supported |= std::strcmp(extensions[j].extensionName, VK_EXT_PCI_BUS_INFO_EXTENSION_NAME) == 0;
            }
            VkPhysicalDevicePCIBusInfoPropertiesEXT pci{};
            pci.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PCI_BUS_INFO_PROPERTIES_EXT;
            VkPhysicalDeviceIDProperties ids{};
            ids.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ID_PROPERTIES;
            ids.pNext = pci_supported ? &pci : nullptr;
            VkPhysicalDeviceProperties2 properties{};
            properties.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2;
            properties.pNext = &ids;
            api.properties(devices[i], &properties);
            const auto& p = properties.properties;
            require(std::memchr(p.deviceName, 0, VK_MAX_PHYSICAL_DEVICE_NAME_SIZE) != nullptr, "Unterminated device name");
            if (i) out << ',';
            out << "{\"vendor_id\":" << p.vendorID << ",\"device_id\":" << p.deviceID
                << ",\"device_type\":" << uint32_t(p.deviceType) << ",\"driver_version_raw\":" << p.driverVersion
                << ",\"api_version_raw\":" << p.apiVersion << ",\"device_name\":" << quote(p.deviceName)
                << ",\"device_uuid_hex\":" << quote(hex(ids.deviceUUID, VK_UUID_SIZE))
                << ",\"driver_uuid_hex\":" << quote(hex(ids.driverUUID, VK_UUID_SIZE))
                << ",\"pci_bus_info_available\":" << (pci_supported ? "true" : "false");
            if (pci_supported) out << ",\"pci\":{\"domain\":" << pci.pciDomain << ",\"bus\":" << pci.pciBus
                                   << ",\"device\":" << pci.pciDevice << ",\"function\":" << pci.pciFunction << '}';
            out << '}';
        }
        const auto modules = api.modules();
        require(!modules.empty() && modules.size() <= 1024, "Empty/oversized loaded-module inventory");
        out << "],\"modules_during_instance\":[";
        for (size_t i = 0; i < modules.size(); ++i) {
            if (i) out << ',';
            out << quote(modules[i]);
        }
        // Success is published only after destruction returns. If cleanup hangs,
        // the external owned-process deadline must preserve failure and contain it.
        api.destroy(std::exchange(instance, VK_NULL_HANDLE));
        out << "],\"instance_destroyed\":true,\"status\":\"NATIVE_READBACK_ONLY_NOT_PHYSICAL_QUALIFICATION\"}";
        return out.str();
    } catch (...) {
        if (instance != VK_NULL_HANDLE) api.destroy(std::exchange(instance, VK_NULL_HANDLE));
        throw;
    }
}

#ifndef SDVK_PROBE_CPU_TEST
class LifetimeGuard {
    HANDLE parent = nullptr;
    HANDLE finished = nullptr;
    std::thread watcher;
public:
    LifetimeGuard(DWORD parent_pid, uint64_t expected_creation) {
        HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        require(snapshot != INVALID_HANDLE_VALUE, "Cannot snapshot parent identity");
        PROCESSENTRY32W entry{};
        entry.dwSize = sizeof(entry);
        DWORD observed_parent = 0;
        if (Process32FirstW(snapshot, &entry)) do {
            if (entry.th32ProcessID == GetCurrentProcessId()) { observed_parent = entry.th32ParentProcessID; break; }
        } while (Process32NextW(snapshot, &entry));
        CloseHandle(snapshot);
        require(parent_pid != 0 && parent_pid == observed_parent, "Controller PID differs from native parent");
        parent = OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, FALSE, parent_pid);
        require(parent != nullptr, "Cannot retain controller handle");
        try {
            FILETIME created{}, exited{}, kernel{}, user{};
            require(GetProcessTimes(parent, &created, &exited, &kernel, &user) != 0, "Cannot authenticate controller creation time");
            const uint64_t actual = (uint64_t(created.dwHighDateTime) << 32) | created.dwLowDateTime;
            require(actual == expected_creation && WaitForSingleObject(parent, 0) == WAIT_TIMEOUT,
                    "Controller creation identity changed or already exited");
            finished = CreateEventW(nullptr, TRUE, FALSE, nullptr);
            require(finished != nullptr, "Cannot create owned lifetime event");
            watcher = std::thread([this] {
                const HANDLE handles[] = {parent, finished};
                const DWORD status = WaitForMultipleObjects(2, handles, FALSE, 30000);
                if (status != WAIT_OBJECT_0 + 1) {
                    // Self-termination only: no PID lookup or external process kill.
                    TerminateProcess(GetCurrentProcess(), status == WAIT_OBJECT_0 ? 125 : 126);
                }
            });
        } catch (...) {
            if (finished) CloseHandle(finished);
            CloseHandle(parent);
            parent = finished = nullptr;
            throw;
        }
    }
    ~LifetimeGuard() {
        SetEvent(finished);
        watcher.join();
        CloseHandle(finished);
        CloseHandle(parent);
    }
};

class NativeBackend final : public Backend {
    HMODULE loader = nullptr;
    PFN_vkGetInstanceProcAddr get = nullptr;
    PFN_vkCreateInstance create_instance = nullptr;
    PFN_vkDestroyInstance destroy_instance = nullptr;
    PFN_vkEnumeratePhysicalDevices enumerate = nullptr;
    PFN_vkEnumerateDeviceExtensionProperties enumerate_extensions = nullptr;
    PFN_vkGetPhysicalDeviceProperties2 get_properties = nullptr;
public:
    NativeBackend() {
        std::array<wchar_t, 32768> directory{};
        const UINT length = GetSystemDirectoryW(directory.data(), UINT(directory.size()));
        require(length > 0 && length < directory.size(), "Cannot resolve native system directory");
        const std::wstring path = std::wstring(directory.data()) + L"\\vulkan-1.dll";
        loader = LoadLibraryExW(path.c_str(), nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
        require(loader != nullptr, "Cannot load pinned system Vulkan loader");
        try {
            get = reinterpret_cast<PFN_vkGetInstanceProcAddr>(GetProcAddress(loader, "vkGetInstanceProcAddr"));
            require(get != nullptr, "Loader has no vkGetInstanceProcAddr");
            create_instance = reinterpret_cast<PFN_vkCreateInstance>(get(VK_NULL_HANDLE, "vkCreateInstance"));
            require(create_instance != nullptr, "Loader has no vkCreateInstance");
        } catch (...) {
            FreeLibrary(loader);
            loader = nullptr;
            throw;
        }
    }
    ~NativeBackend() override { if (loader) FreeLibrary(loader); }
    VkResult create(const VkInstanceCreateInfo* info, VkInstance* value) override { return create_instance(info, nullptr, value); }
    void bind(VkInstance value) override {
        destroy_instance = reinterpret_cast<PFN_vkDestroyInstance>(get(value, "vkDestroyInstance"));
        enumerate = reinterpret_cast<PFN_vkEnumeratePhysicalDevices>(get(value, "vkEnumeratePhysicalDevices"));
        enumerate_extensions = reinterpret_cast<PFN_vkEnumerateDeviceExtensionProperties>(get(value, "vkEnumerateDeviceExtensionProperties"));
        get_properties = reinterpret_cast<PFN_vkGetPhysicalDeviceProperties2>(get(value, "vkGetPhysicalDeviceProperties2"));
        require(destroy_instance && enumerate && enumerate_extensions && get_properties, "Missing required instance-level entry point");
    }
    VkResult devices(VkInstance value, uint32_t* count, VkPhysicalDevice* values) override { return enumerate(value, count, values); }
    VkResult extensions(VkPhysicalDevice value, uint32_t* count, VkExtensionProperties* values) override {
        return enumerate_extensions(value, nullptr, count, values);
    }
    void properties(VkPhysicalDevice value, VkPhysicalDeviceProperties2* result) override { get_properties(value, result); }
    void destroy(VkInstance value) override {
        if (!destroy_instance) destroy_instance = reinterpret_cast<PFN_vkDestroyInstance>(get(value, "vkDestroyInstance"));
        require(destroy_instance != nullptr, "Cannot resolve instance cleanup");
        destroy_instance(value, nullptr);
    }
    std::vector<std::string> modules() override {
        std::array<HMODULE, 1024> values{};
        DWORD needed = 0;
        require(K32EnumProcessModulesEx(GetCurrentProcess(), values.data(), DWORD(sizeof(values)), &needed, 3) != 0,
                "Cannot enumerate actual loaded modules");
        require(needed > 0 && needed <= sizeof(values) && needed % sizeof(HMODULE) == 0, "Invalid loaded-module capacity");
        std::vector<std::string> result;
        for (size_t i = 0; i < needed / sizeof(HMODULE); ++i) {
            std::array<wchar_t, 32768> path{};
            const DWORD length = K32GetModuleFileNameExW(GetCurrentProcess(), values[i], path.data(), DWORD(path.size()));
            require(length > 0 && length < path.size() - 1, "Cannot identify actual loaded module");
            const int size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, path.data(), int(length), nullptr, 0, nullptr, nullptr);
            require(size > 0, "Invalid UTF-16 module identity");
            std::string text(size_t(size), '\0');
            require(WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, path.data(), int(length), text.data(), size, nullptr, nullptr) == size,
                    "Module UTF-8 conversion failed");
            result.push_back(std::move(text));
        }
        std::sort(result.begin(), result.end());
        require(std::adjacent_find(result.begin(), result.end()) == result.end(), "Duplicate loaded modules");
        return result;
    }
};
#endif
} // namespace sdvk_attestation

#ifndef SDVK_PROBE_CPU_TEST
int main(int argc, char** argv) {
    // Reject every other invocation before even loading the Vulkan loader.
    if (argc != 4 || (std::strcmp(argv[1], "--instance-attestation-only") != 0 &&
                     std::strcmp(argv[1], "--cpu-parent-watch-control") != 0)) {
        std::cerr << "Only a reviewed, externally contained instance-attestation invocation is supported.\n";
        return 64;
    }
    try {
        size_t pid_end = 0, creation_end = 0;
        const auto pid = std::stoull(argv[2], &pid_end);
        const auto creation = std::stoull(argv[3], &creation_end);
        sdvk_attestation::require(pid_end == std::strlen(argv[2]) && creation_end == std::strlen(argv[3]) &&
                                 pid > 0 && pid <= 0xffffffff && creation > 0, "Invalid controller identity arguments");
        sdvk_attestation::LifetimeGuard lifetime(DWORD(pid), creation);
        if (std::strcmp(argv[1], "--cpu-parent-watch-control") == 0) {
            std::cout << "CPU_PARENT_WATCH_STARTED\n" << std::flush;
            Sleep(20000);
            return 0;
        }
        sdvk_attestation::NativeBackend backend;
        std::cout << sdvk_attestation::collect(backend) << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cout << "{\"status\":\"FAILED_STOP\",\"error\":" << sdvk_attestation::quote(error.what()) << "}\n";
        return 1;
    }
}
#endif
