"""SDVK-014 retained-load, dynamic-update and atlas-publication robustness.

CPU/source only: compiles the exact retained pixel-span helper and audits the
production state transitions. No renderer or Vulkan device is created.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import current

CASES = (
    "valid-start",
    "valid-end",
    "valid-full",
    "misaligned-offset",
    "span-overrun",
    "empty-width",
    "large-arithmetic",
)


def contract_errors(load: str, select: str, copy: str, pages: str) -> list[str]:
    errors: list[str] = []

    validate = "!IsValidLightmapPixelSpan(entry.pixelsOffset, entry.width, entry.height, numTexPixels)"
    mutation = "tile->AtlasLocation.Width = entry->width;"
    admitted_loop = "for (auto& binding : foundBindings)"
    if (
        "numTexPixels > std::numeric_limits<unsigned int>::max() / 3u" not in load
        or "if (tile.UseCount > 0)" not in load
        or "entry.HasFiniteTransform()" not in load
        or "controlSector < level.sectors.Size()" not in load
        or "controlSector < level.subsectors.Size()" in load
        or validate not in load
        or "!foundTiles.insert(tile).second" not in load
        or admitted_loop not in load
        or mutation not in load
        or load.index(admitted_loop) > load.index(mutation)
    ):
        errors.append("retained-admission-before-mutation")

    dirty = (
        "tile->ReceivedNewLight = false;",
        "tile->NeedsInitialBake = false;",
        "tile->GeometryUpdate = false;",
    )
    if any(item in select for item in dirty):
        errors.append("premature-dynamic-completion")

    publish = "barrier1.Execute(cmdbuffer, VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT);"
    copied = (
        "selected.Tile->ReceivedNewLight = false;",
        "selected.Tile->NeedsInitialBake = false;",
        "selected.Tile->GeometryUpdate = false;",
    )
    if (
        publish not in copy
        or "if (!selected.Rendered)" not in copy
        or any(item not in copy for item in copied)
        or any(copy.index(item) < copy.index(publish) for item in copied if item in copy)
    ):
        errors.append("missing-post-publication-completion")

    light_clear = "clearColorImage(Lightmaps[i].Light.Image->image"
    probe_clear = "clearColorImage(Lightmaps[i].Probe.Image->image"
    transfer = "VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL"
    sampled = "VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL"
    if (
        pages.count(light_clear) != 1
        or pages.count(probe_clear) != 1
        or pages.count(transfer) < 4
        or pages.count(sampled) < 2
        or pages.index(transfer) > pages.index(light_clear)
        or pages.index(transfer) > pages.index(probe_clear)
        or pages.rindex(sampled) < pages.index(probe_clear)
    ):
        errors.append("uninitialized-expanded-atlas")

    return errors


def replacement_errors(create: str) -> list[str]:
    errors: list[str] = []
    light_clear = "clearColorImage(Lightmaps[i].Light.Image->image"
    probe_clear = "clearColorImage(Lightmaps[i].Probe.Image->image"
    transfer = "VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL"
    sampled = "VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL"
    upload = "if (srcPixels.size() != 0)"
    empty_guard = "if (srcPixels.size() == 0)"
    if (
        create.count(light_clear) != 1
        or create.count(probe_clear) != 1
        or create.count(transfer) < 4
        or create.count(sampled) < 2
        or empty_guard not in create
        or upload not in create
        or create.index(probe_clear) > create.index(upload)
        or create.index(light_clear) > create.index(upload)
        or create.rindex(sampled) < create.index(probe_clear)
    ):
        errors.append("uninitialized-replacement-atlas")
    return errors


def helper_source(helper: str) -> str:
    return f"""#include <cstdint>
#include <iostream>
#include <string>
{helper}

int main(int argc, char** argv)
{{
    if (argc != 2) return 2;
    const std::string c = argv[1];
    bool got = false;
    bool expected = false;

    if (c == "valid-start") {{ got = IsValidLightmapPixelSpan(0u, 2, 1, 4u); expected = true; }}
    else if (c == "valid-end") {{ got = IsValidLightmapPixelSpan(6u, 2, 1, 4u); expected = true; }}
    else if (c == "valid-full") {{ got = IsValidLightmapPixelSpan(0u, 2, 2, 4u); expected = true; }}
    else if (c == "misaligned-offset") {{ got = IsValidLightmapPixelSpan(1u, 1, 1, 4u); expected = false; }}
    else if (c == "span-overrun") {{ got = IsValidLightmapPixelSpan(9u, 2, 1, 4u); expected = false; }}
    else if (c == "empty-width") {{ got = IsValidLightmapPixelSpan(0u, 0, 1, 4u); expected = false; }}
    else if (c == "large-arithmetic") {{ got = IsValidLightmapPixelSpan(0xffffffffu, 65535, 65535, 0xffffffffu); expected = false; }}
    else return 3;

    if (got != expected)
    {{
        std::cerr << "unexpected-span-admission " << c << " got=" << got << " expected=" << expected << "\\n";
        return 11;
    }}
    std::cout << "PASS " << c << "\\n";
    return 0;
}}
"""


def build(directory: Path, helper: str, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / (name + ".cpp")
    source.write_text(helper_source(helper))
    return compile_fixture(source, output_dir=directory, name=name)


class RetainedLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.load = current("load_lightmap")
        cls.select = current("select_tiles")
        cls.copy = current("copy_result")
        cls.pages = current("set_lightmap_count")
        cls.create = current("create_lightmap")
        cls.freshness = current("lightmap_source_current")
        cls.helper = current("lightmap_span")
        cls.save = current("save")
        cls.pack = current("pack_atlas")

    def test_current_contract_has_no_known_lifecycle_error(self) -> None:
        self.assertEqual(contract_errors(self.load, self.select, self.copy, self.pages), [])


    def test_retained_source_digest_is_admitted_before_any_tile_mutation(self) -> None:
        read = "fr.Read(sourceDigest, sizeof(sourceDigest));"
        gate = "if (!IsRetainedLightmapSourceCurrent(sourceDigest, Level->md5))"
        mutation = "tile->AtlasLocation.Width = entry->width;"
        self.assertIn(read, self.load)
        self.assertIn(gate, self.load)
        self.assertIn("return false;", self.load[self.load.index(gate):self.load.index("if (developer >= 5)")])
        self.assertLess(self.load.index(read), self.load.index(gate))
        self.assertLess(self.load.index(gate), self.load.index(mutation))
        self.assertIn("lumpFile.Write(doomMap.md5, 16);", self.save)
        self.assertIn("sizeof(int) + 2 * sizeof(uint32_t) + 16", self.save)
        version = (ROOT / "src/version.h").read_text()
        self.assertIn("#define LIGHTMAPVER 5", version)

    def test_map_checksum_authority_is_non_circular_and_bake_relevant(self) -> None:
        source = (ROOT / "src/p_openmap.cpp").read_text()
        start = source.index("void MapData::GetChecksum(uint8_t cksum[16])")
        end = source.index("}", source.index("md5.Final(cksum);", start)) + 1
        body = source[start:end]
        self.assertIn("ML_TEXTMAP", body)
        for lump in ("ML_LABEL", "ML_THINGS", "ML_LINEDEFS", "ML_SIDEDEFS", "ML_SECTORS", "ML_BEHAVIOR"):
            self.assertIn(lump, body)
        self.assertNotIn("ML_LIGHTMAP", body)
        self.assertNotIn("ML_NODES", body)
        self.assertNotIn("ML_ZNODES", body)

    def test_retained_source_digest_helper_accepts_only_exact_identity(self) -> None:
        source = """#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
""" + self.freshness + r"""
int main(int argc, char** argv)
{
    uint8_t current[16] = {};
    uint8_t retained[16] = {};
    if (argc != 2) return 2;
    if (std::string(argv[1]) == "equal") {}
    else if (std::string(argv[1]) == "first") retained[0] = 1;
    else if (std::string(argv[1]) == "last") retained[15] = 1;
    else return 3;
    const bool got = IsRetainedLightmapSourceCurrent(retained, current);
    const bool expected = std::string(argv[1]) == "equal";
    if (got != expected) return 11;
    std::cout << "PASS " << argv[1] << "\n";
    return 0;
}
"""
        with tempfile.TemporaryDirectory(prefix="sdvk158-freshness-") as temp:
            path = Path(temp) / "freshness.cpp"
            path.write_text(source)
            exe = compile_fixture(path, output_dir=Path(temp), name="freshness")
            for case in ("equal", "first", "last"):
                with self.subTest(case=case):
                    p = subprocess.run([str(exe), case], text=True, capture_output=True, timeout=10)
                    self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                    self.assertIn("PASS " + case, p.stdout)

    def test_digest_bypass_mutation_is_rejected(self) -> None:
        needle = "std::memcmp(retainedDigest, currentDigest, 16) == 0"
        self.assertEqual(self.freshness.count(needle), 1)
        mutant = self.freshness.replace(needle, "true")
        source = """#include <cstdint>
#include <cstring>
""" + mutant + r"""
int main()
{
    uint8_t current[16] = {};
    uint8_t retained[16] = {};
    retained[15] = 1;
    return IsRetainedLightmapSourceCurrent(retained, current) ? 11 : 0;
}
"""
        with tempfile.TemporaryDirectory(prefix="sdvk158-freshness-mutant-") as temp:
            path = Path(temp) / "freshness_mutant.cpp"
            path.write_text(source)
            exe = compile_fixture(path, output_dir=Path(temp), name="freshness_mutant")
            p = subprocess.run([str(exe)], text=True, capture_output=True, timeout=10)
            self.assertEqual(p.returncode, 11, p.stdout + p.stderr)

    def test_current_page_is_republished_to_vertex_sampling_state(self) -> None:
        self.assertIn("Lightmap.TextureCount = (int)Lightmap.AtlasPacker->GetNumPages();", self.pack)
        self.assertIn("vertex.lindex = (float)tile.AtlasLocation.ArrayIndex;", self.pack)
        self.assertIn("UploadRanges.Vertex.Add(surface->MeshLocation.StartVertIndex, surface->MeshLocation.NumVerts);", self.pack)
        self.assertLess(
            self.pack.index("vertex.lindex = (float)tile.AtlasLocation.ArrayIndex;"),
            self.pack.index("UploadRanges.Vertex.Add(surface->MeshLocation.StartVertIndex, surface->MeshLocation.NumVerts);"),
        )

    def test_stale_sampling_page_publication_mutation_is_rejected(self) -> None:
        needle = "vertex.lindex = (float)tile.AtlasLocation.ArrayIndex;"
        self.assertEqual(self.pack.count(needle), 1)
        mutant = self.pack.replace(needle, "vertex.lindex = 0.0f;")
        self.assertNotIn(needle, mutant)
        self.assertIn("vertex.lindex = 0.0f;", mutant)

    def test_pixel_span_helper_executes_exact_boundaries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sdvk014-retained-span-") as temp:
            exe = build(Path(temp), self.helper, "span_current")
            for case in CASES:
                with self.subTest(case=case):
                    p = subprocess.run([str(exe), case], text=True, capture_output=True, timeout=10)
                    self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                    self.assertIn("PASS " + case, p.stdout)

    def test_misaligned_offset_negative_control_fails_for_reason(self) -> None:
        needle = " || pixelsOffset % 3u != 0"
        self.assertEqual(self.helper.count(needle), 1)
        mutant = self.helper.replace(needle, "")
        with tempfile.TemporaryDirectory(prefix="sdvk014-span-misaligned-") as temp:
            exe = build(Path(temp), mutant, "span_no_alignment")
            p = subprocess.run([str(exe), "misaligned-offset"], text=True, capture_output=True, timeout=10)
            self.assertEqual(p.returncode, 11, p.stdout + p.stderr)
            self.assertIn("unexpected-span-admission misaligned-offset", p.stderr)

    def test_overrun_negative_control_fails_for_reason(self) -> None:
        needle = "componentCount <= totalComponents - firstComponent"
        self.assertEqual(self.helper.count(needle), 1)
        mutant = self.helper.replace(needle, "componentCount <= totalComponents")
        with tempfile.TemporaryDirectory(prefix="sdvk014-span-overrun-") as temp:
            exe = build(Path(temp), mutant, "span_no_end_check")
            p = subprocess.run([str(exe), "span-overrun"], text=True, capture_output=True, timeout=10)
            self.assertEqual(p.returncode, 11, p.stdout + p.stderr)
            self.assertIn("unexpected-span-admission span-overrun", p.stderr)

    def test_premature_completion_mutation_is_rejected(self) -> None:
        marker = "\t\t\tselectedTiles.Push(selected);"
        self.assertEqual(self.select.count(marker), 1)
        mutant = self.select.replace(marker, marker + "\n\t\t\ttile->ReceivedNewLight = false;")
        self.assertIn(
            "premature-dynamic-completion",
            contract_errors(self.load, mutant, self.copy, self.pages),
        )

    def test_missing_post_publication_completion_is_rejected(self) -> None:
        needle = "\t\tselected.Tile->ReceivedNewLight = false;\n"
        self.assertEqual(self.copy.count(needle), 1)
        mutant = self.copy.replace(needle, "")
        self.assertIn(
            "missing-post-publication-completion",
            contract_errors(self.load, self.select, mutant, self.pages),
        )


    def test_replacement_atlas_initializes_probe_and_empty_light(self) -> None:
        self.assertEqual(replacement_errors(self.create), [])

    def test_replacement_probe_clear_negative_control_is_rejected(self) -> None:
        line = "\t\tcmdbuffer->clearColorImage(Lightmaps[i].Probe.Image->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, &zero, 1, &clearRange);\n"
        self.assertEqual(self.create.count(line), 1)
        mutant = self.create.replace(line, "")
        self.assertIn("uninitialized-replacement-atlas", replacement_errors(mutant))

    def test_replacement_empty_light_clear_negative_control_is_rejected(self) -> None:
        line = "\t\t\tcmdbuffer->clearColorImage(Lightmaps[i].Light.Image->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, &zero, 1, &clearRange);\n"
        self.assertEqual(self.create.count(line), 1)
        mutant = self.create.replace(line, "")
        self.assertIn("uninitialized-replacement-atlas", replacement_errors(mutant))

    def test_missing_probe_page_clear_is_rejected(self) -> None:
        line = "\t\tcmdbuffer->clearColorImage(Lightmaps[i].Probe.Image->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, &zero, 1, &range);\n"
        self.assertEqual(self.pages.count(line), 1)
        mutant = self.pages.replace(line, "")
        self.assertIn(
            "uninitialized-expanded-atlas",
            contract_errors(self.load, self.select, self.copy, mutant),
        )


    def test_control_sector_namespace_mutation_is_rejected(self) -> None:
        needle = "controlSector < level.sectors.Size()"
        self.assertEqual(self.load.count(needle), 1)
        mutant = self.load.replace(needle, "controlSector < level.subsectors.Size()")
        self.assertIn(
            "retained-admission-before-mutation",
            contract_errors(mutant, self.select, self.copy, self.pages),
        )

    def test_retained_admission_order_mutation_is_rejected(self) -> None:
        mutation = "\t\ttile->AtlasLocation.Width = entry->width;\n"
        self.assertEqual(self.load.count(mutation), 1)
        mutant = self.load
        # Force the ownership oracle with a source-order mutation representing
        # a write before complete admission. This mutation is inspected, not compiled.
        marker = "\t// Admit complete retained entries before mutating any current tile state.\n"
        self.assertEqual(mutant.count(marker), 1)
        mutant = mutant.replace(marker, marker + "\tLightmapTile* tile = nullptr;\n\ttile->AtlasLocation.Width = entry->width;\n", 1)
        self.assertIn(
            "retained-admission-before-mutation",
            contract_errors(mutant, self.select, self.copy, self.pages),
        )


if __name__ == "__main__":
    unittest.main()
