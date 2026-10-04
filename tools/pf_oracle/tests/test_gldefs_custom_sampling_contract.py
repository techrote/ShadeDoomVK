#!/usr/bin/env python3
"""PF-020: execute the production GLDEFS custom-texture property branches.

This is a source-extracted parser-state fixture, not a complete GLDEFS loader
or a Vulkan/image test. Only scanner, texture lookup, and container services are
stubbed. Allocation, property dispatch, filter assignment, and error branches
are copied unchanged from gldefs.cpp at test execution time. The exact inherited
two-line defect is retained as a separate negative producer.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import re
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.pf_oracle.fixture_runner import run_fixture  # noqa: E402


# SHA-256 of whitespace-normalized property bodies from the exact pre-repair
# master source. The negative producer must remain those original bodies,
# not merely any modified implementation which happens to fail a check.
ORIGINAL_SOURCE = "4df7dea1338f063c6417e024f967bfa4aa23edd4:src/r_data/gldefs.cpp"
ORIGINAL_BRANCH_SHA256 = {
    "Material": "81af8b539c665ba9f099bb18ba0325e92c6a1ba2da059c7273cbe375613e38c8",
    "Legacy": "42bd140910755a1bd271f975c5562c184f07481443250176d014b0b9024f84d0",
}


def braced_block(text: str, opening: int) -> str:
    """Read a C++ block while ignoring braces in strings/chars/comments."""
    if text[opening] != "{":
        raise ValueError("extraction anchor does not begin a C++ block")
    depth, i, state = 0, opening, "code"
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if state == "line":
            if ch == "\n":
                state = "code"
        elif state == "comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 1
        elif state in ("string", "char"):
            if ch == "\\":
                i += 1
            elif (state == "string" and ch == '"') or (state == "char" and ch == "'"):
                state = "code"
        elif ch == "/" and nxt == "/":
            state = "line"
            i += 1
        elif ch == "/" and nxt == "*":
            state = "comment"
            i += 1
        elif ch == '"':
            state = "string"
        elif ch == "'":
            state = "char"
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[opening : i + 1]
        i += 1
    raise ValueError("unterminated source block")


def extract_function(text: str, signature: str) -> str:
    start = text.index(signature)
    return braced_block(text, text.index("{", start))


def texture_branch(function: str) -> str:
    # ParseHardwareShader also has a postprocess texture property. Select the
    # one actual MaterialLayers allocator; do not accidentally test that route.
    bodies = []
    for marker in re.finditer(r'else\s+if\s*\(\s*sc\.Compare\("texture"\)\s*\)', function):
        body = braced_block(function, function.index("{", marker.end()))
        if "mlay.CustomShaderTextures" in body:
            bodies.append(body)
    if len(bodies) != 1:
        raise ValueError("production custom-texture allocation branch missing or ambiguous")
    body = bodies[0]
    if body.count("size_t texIndex = 0;") != 1 or body.count("texIndex = i;") != 1:
        raise ValueError("custom-texture allocation structure changed; review fixture")
    return body


def original_branch(body: str) -> str:
    """Restore only the exact original allocation-default statement.

    Do not replace the later explicit `filter default` assignment, whose
    texIndex is already established and correct.
    """
    # The repair may move the selected-slot assignment earlier (rather than
    # writing the default through i) so legacy texIndex remains meaningfully
    # consumed under strict warnings. Restore its exact inherited position.
    assignment = re.search(r"(?m)^([ \t]*)texIndex = i;[ \t]*\n", body)
    default_at = body.index("mlay.CustomShaderTextureSampling[")
    if assignment is None:
        raise ValueError("selected-slot assignment missing; review negative producer")
    if assignment.start() < default_at:
        body = body[:assignment.start()] + body[assignment.end():]
        after_index = re.search(r"(?m)^([ \t]*)texNameIndex\.Push\(\(int\)i\);[ \t]*\n", body)
        if after_index is None:
            raise ValueError("authoring index publication anchor changed")
        body = body[:after_index.end()] + after_index.group(1) + "texIndex = i;\n" + body[after_index.end():]
    before_lookup, after_lookup = body.split("mlay.CustomShaderTextures[i] = TexMan.FindGameTexture", 1)
    pattern = r"mlay\.CustomShaderTextureSampling\[(?:i|texIndex)\] = MaterialLayerSampling::Default;"
    original = "mlay.CustomShaderTextureSampling[texIndex] = MaterialLayerSampling::Default;"
    before_lookup, replacements = re.subn(pattern, original, before_lookup)
    if replacements != 1:
        raise ValueError("allocation-default anchor changed; review negative producer")
    return before_lookup + "mlay.CustomShaderTextures[i] = TexMan.FindGameTexture" + after_lookup


def generated_header() -> str:
    parser = (ROOT / "src/r_data/gldefs.cpp").read_text(encoding="utf-8")
    types = (ROOT / "src/common/textures/gametexture.h").read_text(encoding="utf-8")
    material = extract_function(parser, "void ParseMaterial(bool is_globalshader = false)")
    legacy = extract_function(parser, "void ParseHardwareShader()")
    branches = {"Material": texture_branch(material), "Legacy": texture_branch(legacy)}
    enum_at = types.index("enum class MaterialLayerSampling")
    enum_source = types[enum_at : types.index("{", enum_at)] + braced_block(types, types.index("{", enum_at)) + ";"
    layers_at = types.index("struct MaterialLayers")
    layers_source = types[layers_at : types.index("{", layers_at)] + braced_block(types, types.index("{", layers_at)) + ";"
    cap_match = re.search(r"^#define MAX_CUSTOM_HW_SHADER_TEXTURES (\d+)\s*$", types, re.MULTILINE)
    if cap_match is None or int(cap_match.group(1)) != 15:
        raise ValueError("supported custom-texture cap changed; review coverage")
    initializers = []
    for function in (material, legacy):
        match = re.search(r"MaterialLayers mlay\s*=\s*\{\s*-1000\s*,\s*-1000\s*\}\s*;", function)
        if match is None:
            raise ValueError("production MaterialLayers initialization changed; review defaults")
        initializers.append(match.group(0))
    output = ["// Generated unchanged from current source; do not commit this header.",
              "#define MAX_CUSTOM_HW_SHADER_TEXTURES 15", enum_source, layers_source,
              "#if defined(__GNUC__)\n#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored \"-Wmissing-field-initializers\"\n#endif"]
    for name, initializer in zip(("Material", "Legacy"), initializers):
        output.append(f"static MaterialLayers Initial{name}() {{ {initializer} return mlay; }}")
    output.append("#if defined(__GNUC__)\n#pragma GCC diagnostic pop\n#endif")
    for name, body in branches.items():
        original = original_branch(body)
        digest = hashlib.sha256(" ".join(original.split()).encode("utf-8")).hexdigest()
        if digest != ORIGINAL_BRANCH_SHA256[name]:
            raise ValueError(f"{name} original producer differs from pinned {ORIGINAL_SOURCE}; review regression fixture")
        for prefix, producer in (("Current", body), ("Original", original)):
            output.append(f"""static void {prefix}{name}(FScanner& sc, MaterialLayers& mlay,
    TArray<FString>& texNameList, TArray<int>& texNameIndex,
    [[maybe_unused]] bool is_globalshader, [[maybe_unused]] const FString& str_globaltargets)
{{
    [[maybe_unused]] bool isProperty = false;
    FGameTexture* tex = is_globalshader ? nullptr : &TexMan.Base;
    {producer}
}}
""")
    return "\n".join(output)


class GLDefsCustomSamplingTests(unittest.TestCase):
    def run_producer(self, mode: str) -> None:
        with tempfile.TemporaryDirectory(prefix="pf020-gldefs-") as directory:
            directory = Path(directory)
            (directory / "gldefs_extracted_sampling.h").write_text(generated_header(), encoding="utf-8")
            run_fixture("tools/pf_oracle/tests/gldefs_custom_sampling_fixture.cpp",
                        includes=(directory,), root=ROOT, args=(mode,),
                        name="gldefs-custom-sampling", timeout=30)

    def test_exact_inherited_producer_retains_the_counterexamples(self) -> None:
        self.run_producer("--original")

    def test_current_production_parser_preserves_slot_sampling_and_errors(self) -> None:
        self.run_producer("--current")


if __name__ == "__main__":
    unittest.main()
