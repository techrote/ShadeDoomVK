#!/usr/bin/env python3
"""PF-016 dynamic-light query correctness and fast-path boundaries."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class LightQueryCorrectnessContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sprite_light = source("src/rendering/hwrenderer/scene/hw_spritelight.cpp")
        cls.draw_context = source("src/rendering/hwrenderer/scene/hw_drawcontext.h")
        cls.dyn_data = source("src/common/rendering/hwrenderer/data/hw_dynlightdata.h")
        cls.query_h = source("src/common/rendering/hwrenderer/data/hw_lightquery.h")

    def test_generation_membership_replaces_sorted_per_query_duplicate_list(self) -> None:
        self.assertIn("HWGenerationSet<FDynamicLight*> lightQuerySeen", self.draw_context)
        self.assertIn("lightQuerySeen.BeginQuery()", self.sprite_light)
        self.assertIn("lightQuerySeen", self.sprite_light)
        self.assertIn("seen.MarkFirst(light)", self.sprite_light)
        self.assertNotIn("addedLights.SortedFind", self.sprite_light)
        self.assertNotIn("addedLights.Insert", self.sprite_light)
        self.assertIn("std::unordered_map", self.query_h)

    def test_baseline_and_local_candidate_sources_share_one_filter_pipeline(self) -> None:
        self.assertIn("auto processLightList", self.sprite_light)
        self.assertIn("light->ShouldLightActor(self)", self.sprite_light)
        self.assertIn("light->PosRelative(group)", self.sprite_light)
        self.assertIn("staticLight.TraceLightVisbility", self.sprite_light)
        self.assertIn("AddLightToList(*output, group, light, true", self.sprite_light)
        self.assertIn("processLightList(self->section->lighthead, actorPortalGroup", self.sprite_light)
        self.assertIn("processLightList(section->lighthead, group", self.sprite_light)

    def test_fast_path_requires_side_by_side_selected_identity_class_order_equivalence(self) -> None:
        for token in [
            "LocalQueryKnown",
            "LocalQueryExact",
            "LocalQueryPos",
            "LocalQuerySection",
            "LocalQueryRadius",
            "LocalQueryPortalGroup",
            "section != self->section",
            "group != actorPortalGroup",
            "BSPWalkCircle",
            "std::vector<LightQuerySelection> baselineSelections",
            "std::vector<LightQuerySelection> localSelections",
            "baselineSelections == localSelections",
            "LightQueryClass(light)",
            "LocalQueryExact = localSelectionExact",
        ]:
            self.assertIn(token, self.sprite_light + self.dyn_data)
        # Qualification must not use PF-010 pass identity as a semantic key.
        self.assertNotIn("RenderContext.identity", self.sprite_light)
        self.assertNotIn("RenderContext.epoch", self.sprite_light)

    def test_diagnostics_cover_candidate_source_filter_and_qualification_work(self) -> None:
        for token in [
            "LightQueryBaselineQueries",
            "LightQueryLocalQueries",
            "LightQueryQualificationPasses",
            "LightQueryQualificationFallbacks",
            "LightQueryVisitedSections",
            "LightQueryCandidates",
            "LightQueryDuplicates",
            "LightQueryFiltered",
            "LightQueryTraces",
            "LightQueryBaselineNanos",
            "LightQueryLocalNanos",
            "LightQueryQualificationNanos",
            "ADD_STAT(actorlightquery)",
        ]:
            self.assertIn(token, self.sprite_light)

    def test_compiled_adversarial_boundary_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "light-query-correctness-fixture"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Isrc/common/rendering/hwrenderer/data",
                    "tools/pf_oracle/tests/light_query_correctness_fixture.cpp",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
