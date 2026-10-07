"""SDVK-001: production string allocation under a strict aligned allocator."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture


ROOT = Path(__file__).resolve().parents[3]


class StringAllocationTests(unittest.TestCase):
    def test_production_string_storage_accepts_small_sizes_and_rejects_failures(self):
        # Lift the actual storage declaration and allocation methods unchanged;
        # the rest of FString needs the complete engine. This also exercises
        # the POSIX branch on Windows with an allocator rejecting sub-pointer
        # alignment, rather than letting glibc's more permissive behavior hide it.
        header = (ROOT / "src/common/utility/zstring.h").read_text(encoding="utf-8")
        declaration = header[header.index("struct FStringData\n"):
                             header.index("struct FNullStringData\n")]
        source = (ROOT / "src/common/utility/zstring.cpp").read_text(encoding="utf-8")
        methods = source[source.index("FStringData *FStringData::Alloc ("):
                         source.index("FStringData *FStringData::MakeCopy (")]
        program = r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>
#undef _WIN32
static bool fail_allocation = false;
namespace std {
inline void* sdvk_malloc(size_t size) {
    return fail_allocation ? nullptr : std::malloc(size);
}
inline void* sdvk_strict_aligned_alloc(size_t alignment, size_t size) {
    if (alignment < sizeof(void*) || (alignment & (alignment - 1)) || size % alignment)
        return nullptr;
    return sdvk_malloc(size);
}
}
#define malloc sdvk_malloc
#define aligned_alloc sdvk_strict_aligned_alloc
''' + declaration + methods + r'''
#undef malloc
#undef aligned_alloc
int main() {
    assert(std::sdvk_strict_aligned_alloc(sizeof(void*) / 2, 16) == nullptr);
    for (size_t size : {0u, 1u, 2u, 7u, 15u, 16u, 31u, 64u, 255u, 1024u}) {
        FStringData* block;
        try { block = FStringData::Alloc(size); }
        catch (const std::bad_alloc&) {
            std::fprintf(stderr, "FStringData::Alloc(%zu) failed with strict alignment\n", size);
            return 1;
        }
        assert(reinterpret_cast<size_t>(block) % alignof(FStringData) == 0);
        assert(block->AllocLen >= size && block->Len == 0 && block->RefCount == 1);
        std::memset(block->Chars(), 'x', size);
        block->Chars()[size] = 0;
        block->Release();
    }
    auto block = FStringData::Alloc(7);
    block->Len = 7;
    std::memcpy(block->Chars(), "example", 8);
    block = block->Realloc(128);
    assert(block->Len == 7 && std::strcmp(block->Chars(), "example") == 0);
    block->Release();
    bool overflow_rejected = false;
    try { FStringData::Alloc(std::numeric_limits<size_t>::max()); }
    catch (const std::bad_alloc&) { overflow_rejected = true; }
    assert(overflow_rejected);
    fail_allocation = true;
    bool failure_rejected = false;
    try { FStringData::Alloc(1); }
    catch (const std::bad_alloc&) { failure_rejected = true; }
    assert(failure_rejected);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "string-allocation.cpp"
            fixture.write_text(program, encoding="utf-8")
            executable = compile_fixture(fixture, output_dir=Path(directory) / "build")
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
