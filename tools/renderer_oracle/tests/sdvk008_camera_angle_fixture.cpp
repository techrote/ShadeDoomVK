// CPU-only execution of the production angle header; no renderer or GPU.
#include <iomanip>
#include <iostream>
// The inherited xs_ToInt header has an unused fallback parameter. Keep the
// fixture warning-clean without changing the production header or /WX policy.
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable: 4100)
#else
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"
#endif
#include "vectors.h"
#ifdef _MSC_VER
#pragma warning(pop)
#else
#pragma GCC diagnostic pop
#endif

int main()
{
    std::cout << std::setprecision(17);
    for (int degrees = -180; degrees <= 180; ++degrees)
    {
        std::cout << degrees << ' '
            << DAngle::fromDeg(degrees).Normalized180().Degrees() << '\n';
    }
}
