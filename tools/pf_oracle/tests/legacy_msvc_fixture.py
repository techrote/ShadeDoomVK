"""Scope inherited MSVC warnings to exact legacy headers/extracted bodies only.

The regular fixture compiler retains /W4 /WX and assertions. This adapter does
not edit production functions or pinned historical inputs. Header diagnostics
are the legacy CRT spelling, TArray's size_t facade and xs_Float's unused dummy
parameter; fixture and generated producer diagnostics remain errors by default.
"""
from pathlib import Path

from tools.pf_oracle.fixture_runner import compile_fixture, is_msvc, select_compiler

ROOT = Path(__file__).resolve().parents[3]


def extracted_legacy_scope(text: str, warnings: tuple[int, ...]) -> str:
    if not warnings or set(warnings) - {4018, 4267, 4456}:
        raise ValueError("Only documented inherited producer diagnostics are allowed")
    return ('#ifdef _MSC_VER\n#pragma warning(push)\n#pragma warning(disable: ' +
            ' '.join(map(str, warnings)) + ')\n#endif\n' + text +
            '\n#ifdef _MSC_VER\n#pragma warning(pop)\n#endif\n')


def compile_legacy_fixture(source, *, output_dir, includes):
    compiler = select_compiler()
    if not is_msvc(compiler):
        return compile_fixture(source, output_dir=output_dir, includes=includes, compiler=compiler)
    directory = Path(output_dir)
    wrapper = directory / (Path(source).stem + '_msvc_adapter.cpp')
    # Preinclude only the legacy headers inside the warning scope. Their include
    # guards let the unchanged current/retained fixture follow under full /WX.
    header_names = ('src/common/utility/tarray.h', 'src/common/utility/engineerrors.h',
                    'src/common/thirdparty/xs_Float.h')
    prelude = ('#include <algorithm>\n#include <cstdint>\n#include <cstdlib>\n'
               '#include <cstring>\n#include <memory>\n#include <stdexcept>\n'
               '#ifdef _MSC_VER\n#pragma warning(push)\n'
               '#pragma warning(disable: 4996 4267 4100)\n#endif\n')
    prelude += ''.join('#include "' + (ROOT / name).as_posix() + '"\n' for name in header_names)
    prelude += '#ifdef _MSC_VER\n#pragma warning(pop)\n#endif\n'
    wrapper.write_text(prelude + '#include "' + Path(source).resolve().as_posix() + '"\n',
                       encoding='utf-8', newline='\n')
    return compile_fixture(wrapper, output_dir=directory, includes=includes, compiler=compiler)
