"""CPU-only fixture-isolation gate for SDVK-161's explicitly revised startup policy.

The production renderer and comparator are unchanged. The old argv is a
deliberately failing pre-fix fixture, not a new source/renderer regression.
"""
from __future__ import annotations

import copy
from pathlib import Path
import unittest

from tools.renderer_oracle import prepare, sdvk161_fixtures
from tools.renderer_oracle.common import EvidenceError

FIXTURE = "special-surface-lifecycle"
EXPECTED = [
    "{exe}", "-stdout", "-nostartup", "-noautoload", "-noautoexec",
    "-nosound", "-nojoy", "-rngseed", "161", "-iwad", "{iwad}",
    "-file", "{pk3}", "-config", "{config}", "-width", "640",
    "-height", "480", "-window", "+map", "SDV161A", "+exec",
    "{capture_script}",
]
ORIGINAL = [value for value in EXPECTED if value != "-nostartup"]


def scene():
    return copy.deepcopy(next(row for row in prepare.load_catalog()["scenes"]
                              if row["id"] == FIXTURE))


class StartupIsolation(unittest.TestCase):
    def test_exact_and_only_authored_startup_change(self):
        target = scene()
        self.assertEqual(target["native"]["argv"], EXPECTED)
        self.assertEqual([x for x in target["native"]["argv"]
                          if x != "-nostartup"], ORIGINAL)
        sdvk161_fixtures.validate_recipe(target)
        self.assertEqual(target["native"]["recommended_warmup_frames"], 32)
        self.assertEqual(target["native"]["surface_witness_frames"],
                         list(range(8, 97, 8)))
        self.assertEqual(len(target["native"]["special_surface_schedule"]), 12)
        self.assertEqual(target["native"]["map_sequence"],
                         ["SDV161A", "SDV161A", "SDV161B", "SDV161B"])

    def test_original_argv_fails_for_explicit_missing_startup_isolation(self):
        pre_fix = scene()
        pre_fix["native"]["argv"] = ORIGINAL
        with self.assertRaisesRegex(ValueError, "isolated startup argv"):
            sdvk161_fixtures.validate_recipe(pre_fix)

    def test_wrong_flag_position_or_unrelated_bootstrap_edit_rejects(self):
        mutations = (
            lambda argv: argv.insert(0, "-nostartup"),
            lambda argv: argv.append("-nostartup"),
            lambda argv: argv.remove("-noautoexec"),
            lambda argv: argv.__setitem__(argv.index("-rngseed"), "-rngsead"),
            lambda argv: argv.insert(5, "-skipshadercache"),
        )
        for operation in mutations:
            candidate = scene()
            operation(candidate["native"]["argv"])
            with self.subTest(candidate=candidate["native"]["argv"]), \
                    self.assertRaisesRegex(ValueError, "isolated startup argv"):
                sdvk161_fixtures.validate_recipe(candidate)

    def test_engine_existing_startup_gate_is_real(self):
        root = Path(__file__).resolve().parents[3]
        source = (root / "src/common/startscreen/startscreen.cpp").read_text()
        segment = source[source.index("FStartScreen* GetGameStartScreen("):]
        segment = segment[:segment.index("FStartScreen::~FStartScreen()")]
        self.assertIn('if (!Args->CheckParm("-nostartup"))', segment)
        self.assertIn("return nullptr;", segment)

    def test_controlled_plane_scene_is_not_changed_by_this_revision(self):
        other = next(row for row in prepare.load_catalog()["scenes"]
                     if row["id"] == "controlled-plane-lifecycle")
        self.assertNotIn("-nostartup", other["native"]["argv"])
        self.assertEqual(other["native"]["argv"][:5],
                         ["{exe}", "-stdout", "-noautoload", "-noautoexec",
                          "-nosound"])

    def test_manifest_preparation_rejects_mutated_startup_flag(self):
        selected = scene()
        variants = (ORIGINAL, EXPECTED + ["-nostartup"])
        for argv in variants:
            altered = copy.deepcopy(selected)
            altered["native"]["argv"] = argv
            with self.subTest(argv=argv), self.assertRaisesRegex(
                    ValueError, "isolated startup argv"):
                prepare.special_surface_module(altered)


if __name__ == "__main__":
    unittest.main()
