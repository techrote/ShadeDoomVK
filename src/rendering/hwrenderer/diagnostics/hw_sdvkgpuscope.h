#pragma once
#include "hw_sdvkdiagnostics.h"

namespace SdvkDiagnostics
{
bool BeginSceneGpuGroup();
void EndSceneGpuGroup() noexcept;

// Own only a successfully opened group. Explicit End closes before postprocess;
// the destructor closes on exceptions without replacing the original failure.
class ScopedSceneGpuGroup
{
public:
    explicit ScopedSceneGpuGroup(bool eligible)
        : Active(eligible && GpuTimingRequested() && BeginSceneGpuGroup()) {}
    ~ScopedSceneGpuGroup() noexcept { End(); }
    ScopedSceneGpuGroup(const ScopedSceneGpuGroup&) = delete;
    ScopedSceneGpuGroup& operator=(const ScopedSceneGpuGroup&) = delete;
    void End() noexcept
    {
        if (!Active) return;
        Active = false;
        EndSceneGpuGroup();
    }
private:
    bool Active;
};
}
