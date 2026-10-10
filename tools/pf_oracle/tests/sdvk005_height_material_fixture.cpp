#include "material_layer_semantics.h"
#include <cassert>
#include <cstddef>
#include <vector>

static int AppendHeightAfterExisting(int fixed, int custom, bool present)
{
    return present ? fixed + custom : -1;
}

int main()
{
    using S = MaterialLayerSemantic;
    static_assert(static_cast<unsigned>(S::Albedo) == 0);
    static_assert(static_cast<unsigned>(S::Custom) == 9);
    static_assert(static_cast<unsigned>(S::Height) == 10);

    // Historical custom bindings are invariant; height is always after them.
    assert(AppendHeightAfterExisting(4, 0, true) == 4); // default
    assert(AppendHeightAfterExisting(6, 0, true) == 6); // specular
    assert(AppendHeightAfterExisting(8, 0, true) == 8); // PBR
    assert(AppendHeightAfterExisting(8, 1, true) == 9); // PBR + custom texture
    assert(AppendHeightAfterExisting(8, 15, true) == 23); // inherited custom cap
    assert(AppendHeightAfterExisting(8, 1, false) == -1);
    return 0;
}
