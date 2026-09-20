#!/usr/bin/env python3
"""PF-015 dense-shadow and visibility-cache correctness coverage."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class ShadowVisibilityCorrectnessContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entry = source("src/rendering/hwrenderer/hw_entrypoint.cpp")
        cls.sprite_light = source("src/rendering/hwrenderer/scene/hw_spritelight.cpp")
        cls.dyn_data = source("src/common/rendering/hwrenderer/data/hw_dynlightdata.h")
        cls.shadow_h = source("src/common/rendering/hwrenderer/data/hw_shadowmap.h")

    def test_shadow_overflow_uses_view_relevance_only_after_cap(self) -> None:
        self.assertIn("HWSelectShadowCandidates", self.entry)
        self.assertIn("HWShadowMapLightCapacity", self.entry)
        self.assertIn("viewPosition", self.entry)
        self.assertIn("DistanceSquared", self.entry)
        self.assertIn("LightsCandidates", self.entry)
        self.assertIn("LightsDropped", self.entry)
        self.assertNotIn("closer lights are preferred", self.entry)
        self.assertNotIn("lightindex < 1024", self.entry)

    def test_visibility_cache_keys_world_query_and_stable_portal_context(self) -> None:
        for token in [
            "GetMutationEpochs().Query",
            "HWCheckVisibilityCacheValidity",
            "WorldQueryChanged",
            "PortalContextChanged",
            "CachePortalGroup",
            "TraceCacheHits",
            "TraceCacheMisses",
        ]:
            self.assertIn(token, self.sprite_light)
        self.assertIn("uint64_t QueryEpoch", self.dyn_data)
        self.assertIn("int PortalGroup", self.dyn_data)
        # PF-010 epoch/identity change per pass and must not become a global
        # cross-frame cache flush. Stable portal-group displacement is the key.
        self.assertNotIn("RenderContext.identity", self.sprite_light)
        self.assertNotIn("RenderContext.epoch", self.sprite_light)

    def test_shadow_diagnostics_expose_candidate_selected_and_drop_counts(self) -> None:
        for token in ["LightsProcessed", "LightsCandidates", "LightsShadowmapped", "LightsDropped"]:
            self.assertIn(token, self.shadow_h)

    def test_compiled_adversarial_boundary_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "shadow-visibility-correctness-fixture"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Isrc/common/rendering/hwrenderer/data",
                    "tools/pf_oracle/tests/shadow_visibility_correctness_fixture.cpp",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
