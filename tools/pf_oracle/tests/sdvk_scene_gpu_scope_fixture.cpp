// CPU execution of the production scope owner; no Vulkan/GPU is launched.
#include "hw_sdvkgpuscope.h"
#include <cassert>
#include <stdexcept>
#include <type_traits>

namespace SdvkDiagnostics
{
std::atomic<bool> EnabledFlag{false}, StateFlag{false}, GpuFlag{false};
int Starts = 0, Ends = 0;
bool CanStart = true;
bool BeginSceneGpuGroup() { ++Starts; return CanStart; }
void EndSceneGpuGroup() noexcept { ++Ends; }
}

int main()
{
    using namespace SdvkDiagnostics;
    static_assert(!std::is_copy_constructible<ScopedSceneGpuGroup>::value);
    static_assert(!std::is_move_constructible<ScopedSceneGpuGroup>::value);
    { ScopedSceneGpuGroup disabled(true); }
    assert(Starts == 0 && Ends == 0);
    GpuFlag.store(true);
    { ScopedSceneGpuGroup nonMain(false); }
    assert(Starts == 0 && Ends == 0);
    CanStart = false;
    { ScopedSceneGpuGroup unavailable(true); unavailable.End(); }
    assert(Starts == 1 && Ends == 0); // must not pop someone else's group
    CanStart = true;
    {
        ScopedSceneGpuGroup scene(true);
        assert(Starts == 2 && Ends == 0);
        scene.End();
        assert(Ends == 1); // explicit close precedes postprocess
        scene.End();
    }
    assert(Ends == 1);
    try
    {
        ScopedSceneGpuGroup scene(true);
        throw std::runtime_error("renderer failure");
    }
    catch (const std::runtime_error&) {}
    assert(Starts == 3 && Ends == 2);
}
