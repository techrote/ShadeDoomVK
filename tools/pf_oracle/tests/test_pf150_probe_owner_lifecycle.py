"""PF-150 semantic probe-builder owner lifecycle.

CPU-only exact-source fixture. No renderer or Vulkan device is created.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import compile_fixture

DATA = ROOT / "src/common/rendering/hwrenderer/data"
MASK = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)
POSITIVE = (
    "same-owner-terminal",
    "same-count-level",
    "same-count-revision",
    "same-count-via-empty",
    "count-change",
    "partial-transition",
    "invalid-owner",
    "full-owner-transition",
)


def block(text: str, signature: str) -> str:
    if text.count(signature) != 1:
        raise AssertionError(f"expected one source boundary: {signature}")
    start = text.index(signature)
    masked = MASK.sub(lambda m: " " * len(m.group()), text)
    opening = masked.index("{", start)
    depth = 0
    for pos in range(opening, len(masked)):
        if masked[pos] == "{":
            depth += 1
        elif masked[pos] == "}":
            depth -= 1
            if depth == 0:
                return text[start:pos + 1]
    raise AssertionError(f"unclosed source boundary: {signature}")


def current_methods() -> tuple[str, str]:
    src = (DATA / "hw_lightprobe.cpp").read_text()
    return (
        block(src, "void LightProbeIncrementalBuilder::Step("),
        block(src, "void LightProbeIncrementalBuilder::Full("),
    )


def ignore_owner_mutant(step: str) -> str:
    owner_block = block(step, "if (activeOwner != owner)")
    mutant = "if (activeOwner != owner)\n\t{\n\t\t// PF-150 negative control: ignore semantic owner replacement.\n\t}"
    return step.replace(owner_block, mutant, 1)


def fixture_source() -> str:
    return r'''
// SPDX-License-Identifier: GPL-3.0-or-later
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "tarray.h"
#include "hw_lightprobe.h"

void* M_Malloc(size_t n) { auto p = std::malloc(n); if (!p) throw std::bad_alloc(); return p; }
void* M_Realloc(void* p, size_t n) { auto q = std::realloc(p, n); if (!q) throw std::bad_alloc(); return q; }
void M_Free(void* p) { std::free(p); }
void* M_Calloc(size_t n, size_t m) { auto p = std::calloc(n, m); if (!p) throw std::bad_alloc(); return p; }

struct Screen
{
    int resets = 0;
    int passes = 0;
    void ResetLightProbes() { ++resets; }
    void EndLightProbePass() { ++passes; }
} screenObject;
Screen* screen = &screenObject;

#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable: 4018)
#else
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wsign-compare"
#endif
#include "pf150_probe_methods.cpp"
#ifdef _MSC_VER
#pragma warning(pop)
#else
#pragma GCC diagnostic pop
#endif

static void require(bool ok, const char* why)
{
    if (!ok) throw std::logic_error(why);
}

static TArray<LightProbe> authored(int count, int identity)
{
    TArray<LightProbe> probes;
    for (int i = 0; i < count; ++i)
        probes.Push(LightProbe{FVector3(float(identity * 1000 + i), 0, 0), i});
    return probes;
}

struct Route
{
    bool gl_lightprobe = true;
    LightProbeBuildOwner owner{1, 1};
    TArray<LightProbe> probes;
    LightProbeIncrementalBuilder builder;
    std::vector<int> captures;

    void frame()
    {
        if (!gl_lightprobe)
            return;
        if (probes.size() == 0)
            builder.Step(owner, probes, [](int, const LightProbe&) {});
        else
            builder.Step(owner, probes, [&](int, const LightProbe& p) { captures.push_back(int(p.position.X)); });
    }

    void frames(int count = 32)
    {
        for (int i = 0; i < count; ++i)
            frame();
    }

    void full()
    {
        builder.Full(owner, probes, [&](int, const LightProbe& p) { captures.push_back(int(p.position.X)); });
    }
};

static void prime(Route& r)
{
    r.owner = {1, 1};
    r.probes = authored(2, 1);
    r.frames();
    require(r.captures == std::vector<int>({1000,1001,1000,1001,1000,1001,1000,1001,1000,1001}), "initial-pass-identity");
    require(screen->resets == 1 && screen->passes == 5, "initial-publication-count");
    r.captures.clear();
}

static void run(const std::string& mode)
{
    Route r;

    if (mode == "partial-transition")
    {
        // Begin from a fresh builder so the negative mutant can establish a
        // real partial pass through the count path before owner replacement.
        r.owner = {2, 1};
        r.probes = authored(3, 2);
        r.frame(); // initial allocation/reset
        r.frame(); // first capture from owner 2
        require(r.captures == std::vector<int>({2000}), "partial-owner-setup");

        r.captures.clear();
        const int partialReset = screen->resets;
        const int partialPass = screen->passes;
        r.owner = {3, 1};
        r.probes = authored(3, 3);
        r.frames();
        require(r.captures.size() == 15 && r.captures.front() == 3000 && r.captures.back() == 3002, "partial-new-owner-not-rebuilt");
        require(screen->resets == partialReset + 1 && screen->passes == partialPass + 5, "partial-transition-publication");
        return;
    }

    prime(r);
    const int resetBefore = screen->resets;
    const int passBefore = screen->passes;

    if (mode == "same-owner-terminal")
    {
        r.frames();
        require(r.captures.empty(), "terminal-recaptured");
        require(screen->resets == resetBefore && screen->passes == passBefore, "terminal-republished");
    }
    else if (mode == "same-count-level")
    {
        r.owner = {2, 1};
        r.probes = authored(2, 2);
        r.frames();
        require(r.captures.size() == 10 && r.captures.front() == 2000, "new-owner-not-rebuilt");
        require(screen->resets == resetBefore + 1 && screen->passes == passBefore + 5, "new-owner-publication-count");
    }
    else if (mode == "same-count-revision")
    {
        r.owner = {1, 2};
        r.probes = authored(2, 2);
        r.frames();
        require(r.captures.size() == 10 && r.captures.front() == 2000, "new-revision-not-rebuilt");
        require(screen->resets == resetBefore + 1 && screen->passes == passBefore + 5, "new-revision-publication-count");
    }
    else if (mode == "same-count-via-empty")
    {
        r.owner = {2, 1};
        r.probes.Clear();
        r.frame();
        require(screen->resets == resetBefore + 1, "empty-owner-did-not-reset");

        r.owner = {3, 1};
        r.probes = authored(2, 3);
        r.frames();
        require(r.captures.size() == 10 && r.captures.front() == 3000, "post-empty-owner-not-rebuilt");
        require(screen->resets == resetBefore + 2 && screen->passes == passBefore + 5, "post-empty-publication-count");
    }
    else if (mode == "count-change")
    {
        r.probes = authored(3, 2);
        r.frames();
        require(r.captures.size() == 15 && r.captures.front() == 2000 && r.captures.back() == 2002, "changed-count-not-rebuilt");
        require(screen->resets == resetBefore + 1 && screen->passes == passBefore + 5, "changed-count-publication");
    }
    else if (mode == "invalid-owner")
    {
        r.owner = {};
        r.probes = authored(2, 9);
        r.frames(3);
        require(r.captures.empty(), "unset-owner-rendered");
        require(screen->resets == resetBefore + 1 && screen->passes == passBefore, "unset-owner-not-fail-closed");
    }
    else if (mode == "full-owner-transition")
    {
        Route fullRoute;
        fullRoute.owner = {10, 1};
        fullRoute.probes = authored(2, 10);
        for (int i = 0; i < 5; ++i)
            fullRoute.full();
        require(fullRoute.captures.size() == 10, "full-initial-incomplete");
        const int fullReset = screen->resets;
        const int fullPass = screen->passes;
        fullRoute.captures.clear();
        fullRoute.owner = {11, 1};
        fullRoute.probes = authored(2, 11);
        for (int i = 0; i < 5; ++i)
            fullRoute.full();
        require(fullRoute.captures.size() == 10 && fullRoute.captures.front() == 11000, "full-new-owner-not-rebuilt");
        require(screen->resets == fullReset + 1 && screen->passes == fullPass + 5, "full-new-owner-publication");
    }
    else
    {
        throw std::logic_error("unknown-case");
    }
}

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    try
    {
        run(argv[1]);
        std::cout << "PASS " << argv[1] << '\n';
        return 0;
    }
    catch (const std::logic_error& e)
    {
        std::cerr << "BLOCKED " << e.what() << '\n';
        return 11;
    }
}
'''


def build(directory: Path, *, mutant: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    step, full = current_methods()
    if mutant:
        step = ignore_owner_mutant(step)
    (directory / "pf150_probe_methods.cpp").write_text(step + "\n" + full + "\n")
    source = directory / "pf150_probe_owner.cpp"
    source.write_text(fixture_source())
    return compile_fixture(
        source,
        output_dir=directory,
        includes=[directory, DATA, ROOT / "src/common/utility", ROOT / "src/common/thirdparty"],
    )


class ProbeOwnerLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="pf150-probe-owner-")
        root = Path(cls.temp.name)
        cls.current = build(root / "current")
        cls.mutant = build(root / "ignore-owner", mutant=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_current_owner_lifecycle(self) -> None:
        for case in POSITIVE:
            with self.subTest(case=case):
                p = subprocess.run([str(self.current), case], text=True, capture_output=True, timeout=10)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                self.assertIn("PASS " + case, p.stdout)

    def test_ignore_owner_negative_control_fails_same_count(self) -> None:
        for case, reason in (
            ("same-count-level", "new-owner-not-rebuilt"),
            ("same-count-revision", "new-revision-not-rebuilt"),
            ("partial-transition", "partial-new-owner-not-rebuilt"),
        ):
            with self.subTest(case=case):
                p = subprocess.run([str(self.mutant), case], text=True, capture_output=True, timeout=10)
                self.assertEqual(p.returncode, 11, p.stdout + p.stderr)
                self.assertIn("BLOCKED " + reason, p.stderr)

    def test_production_route_observes_empty_owner(self) -> None:
        entry = (ROOT / "src/rendering/hwrenderer/hw_entrypoint.cpp").read_text()
        self.assertIn("const LightProbeBuildOwner probeOwner = level.GetLightProbeBuildOwner();", entry)
        self.assertIn("if (level.lightProbes.size() == 0)", entry)
        self.assertIn("lightProbeBuilder.Step(probeOwner, level.lightProbes, [](int, const LightProbe&) {});", entry)
        self.assertNotIn("if (gl_lightprobe && level.lightProbes.size() > 0)", entry)

    def test_level_and_runtime_mutations_advance_semantic_owner(self) -> None:
        setup = (ROOT / "src/p_setup.cpp").read_text()
        runtime = (ROOT / "src/rendering/hwrenderer/doom_lightprobes.cpp").read_text()
        levels = (ROOT / "src/g_levellocals.h").read_text()
        self.assertIn("BeginLightProbeBuildOwner(AllocateLightProbeLevelSerial())", setup)
        self.assertIn("level.InvalidateLightProbeBuildOwner();", runtime)
        self.assertIn("uint64_t LightProbeLevelSerial", levels)
        self.assertIn("uint64_t LightProbeSetRevision", levels)
        self.assertNotIn("reinterpret_cast", current_methods()[0])


if __name__ == "__main__":
    unittest.main()
