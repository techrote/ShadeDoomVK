// Executes the production atomic allocator against the actual renderer ABI.
#include "vk_actorshadowpolicy.h"
#include "hw_dynlightdata.h"
#include <array>
#include <cassert>
#include <climits>
#include <iostream>
#include <thread>
#include <vector>

int main()
{
    constexpr int capacity = MaxActorShadowCastersPerFrame;
    constexpr int maxRange = MaxActorShadowCastersPerLight;
    static_assert(capacity == 4096 && maxRange == 4, "Update the qualified capacity deliberately");
    static_assert(sizeof(FActorShadowCaster) == 48 + ActorShadowMaskWords * sizeof(uint32_t), "Caster ABI mismatch");
    static_assert(sizeof(FDynLightInfo) == 80, "Default light stride must not inflate");
    std::atomic<int> next{0};
    std::atomic<uint64_t> overflow{0};
    const auto reserve = [&](int count) {
        return VkActorShadowPolicy::Reserve(next, count, capacity, maxRange, overflow);
    };
    for (int bad : {0, -1, INT_MIN, maxRange + 1, INT_MAX}) assert(reserve(bad) == -1);
    assert(next.load() == 0 && overflow.load() == 0);
    assert(VkActorShadowPolicy::Reserve(next, 1, 0, maxRange, overflow) == -1);
    assert(VkActorShadowPolicy::Reserve(next, 1, -1, maxRange, overflow) == -1);
    assert(VkActorShadowPolicy::Reserve(next, 1, capacity, 0, overflow) == -1);
    assert(next.load() == 0 && overflow.load() == 0);

    // Rejected multi-record requests cannot consume the final free slot.
    next.store(capacity - 1);
    assert(reserve(2) == -1 && next.load() == capacity - 1 && overflow.load() == 2);
    assert(reserve(1) == capacity - 1 && next.load() == capacity);
    for (int i = 1; i <= maxRange; ++i) assert(reserve(i) == -1);
    assert(next.load() == capacity && overflow.load() == 12);
    next.store(capacity - maxRange);
    assert(reserve(maxRange) == capacity - maxRange && next.load() == capacity);
    next.store(-1);
    assert(reserve(1) == -1 && next.load() == -1);
    next.store(INT_MAX);
    assert(reserve(1) == -1 && next.load() == INT_MAX);

    next.store(0);
    overflow.store(0);
    std::vector<std::atomic<int>> owner(static_cast<size_t>(capacity));
    for (auto& slot : owner) slot.store(0);
    // Heap allocation keeps this native fixture safe on Windows' 1-MiB stack.
    std::vector<FActorShadowCaster> records(static_cast<size_t>(capacity) + 2);
    records.front().alphaWords[0] = 0x13579bdfu;
    records.back().alphaWords[0] = 0xfdb97531u;
    std::atomic<bool> go{false};
    std::atomic<int> ready{0};
    std::array<std::thread, 8> workers;
    for (size_t worker = 0; worker < workers.size(); ++worker)
    {
        workers[worker] = std::thread([&, worker]() {
            ready.fetch_add(1, std::memory_order_release);
            while (!go.load(std::memory_order_acquire)) std::this_thread::yield();
            const int token = static_cast<int>(worker) + 1;
            const int count = token % maxRange + 1;
            for (;;)
            {
                const int start = reserve(count);
                if (start < 0) break;
                assert(start <= capacity - count);
                for (int at = start; at < start + count; ++at)
                {
                    int unowned = 0;
                    assert(owner[at].compare_exchange_strong(unowned, token));
                    records[at + 1].alphaWords[0] = static_cast<uint32_t>(token);
                }
                if ((start & 31) == 0) std::this_thread::yield();
            }
        });
    }
    while (ready.load(std::memory_order_acquire) != static_cast<int>(workers.size()))
        std::this_thread::yield();
    go.store(true, std::memory_order_release);
    for (auto& worker : workers) worker.join();
    assert(next.load() >= capacity - maxRange + 1 && next.load() <= capacity);
    // Different request sizes may leave fewer than four slots. Fill only those
    // remaining slots and prove all successfully reserved ranges are disjoint.
    for (int at = reserve(1); at >= 0; at = reserve(1))
    {
        int unowned = 0;
        assert(owner[at].compare_exchange_strong(unowned, 99));
        records[at + 1].alphaWords[0] = 99;
    }
    assert(next.load() == capacity);
    for (int at = 0; at < capacity; ++at)
    {
        assert(owner[at].load() != 0);
        assert(records[at + 1].alphaWords[0] == static_cast<uint32_t>(owner[at].load()));
    }
    const auto saved = records;
    for (int i = 0; i < 64; ++i) assert(reserve(maxRange) == -1);
    assert(next.load() == capacity);
    for (size_t at = 0; at < records.size(); ++at)
        assert(records[at].alphaWords[0] == saved[at].alphaWords[0]);
    assert(records.front().alphaWords[0] == 0x13579bdfu);
    assert(records.back().alphaWords[0] == 0xfdb97531u);
    std::cout << "{\"status\":\"PASS\",\"capacity\":" << capacity
        << ",\"record_stride_bytes\":" << sizeof(FActorShadowCaster)
        << ",\"buffer_bytes\":" << size_t(capacity) * sizeof(FActorShadowCaster)
        << ",\"concurrent_slots\":" << next.load() << "}\n";
}
