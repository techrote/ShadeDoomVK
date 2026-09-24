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

    def test_local_membership_elision_requires_unique_section_ownership(self) -> None:
        # AddLightNode must reuse an existing target link before allocating:
        # a single section traversal therefore cannot encounter one light twice.
        links = source("src/playsim/a_dynlight.cpp")
        add = links.split("FLightNode * AddLightNode(", 1)[1].split("static FLightNode * DeleteLightNode", 1)[0]
        self.assertLess(add.index("if (node->targ==linkto)"), add.index("node = new FLightNode"))
        reuse = add.split("if (node->targ==linkto)", 1)[1].split("node = node->nextTarget", 1)[0]
        self.assertIn("return(nextnode)", reuse)
        self.assertIn("bool deduplicate = true", self.sprite_light)
        self.assertIn("deduplicate && !seen.MarkFirst(light)", self.sprite_light)
        local = self.sprite_light.split("if (useLocalSection)", 1)[1].split("\n\telse", 1)[0]
        self.assertIn("&modellightdata, nullptr, true, false)", local)
        self.assertEqual(self.sprite_light.count("&modellightdata, nullptr, true, false)"), 1)
        # The BSP source and independent qualification comparison keep the default.
        baseline = self.sprite_light.split("processLightList(section->lighthead", 1)[1].split("});", 1)[0]
        self.assertNotIn("true, false)", baseline)
        self.assertIn("nullptr, &localSelections, false)", self.sprite_light)

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
