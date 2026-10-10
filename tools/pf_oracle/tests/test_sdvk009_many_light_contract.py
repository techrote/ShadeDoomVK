#!/usr/bin/env python3
"""SDVK-009 active/dormant many-light contracts and pure boundary fixture."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class Sdvk009ManyLightTests(unittest.TestCase):
    def test_compiled_capacity_and_indexed_representation_fixture(self) -> None:
        run_fixture(
            "tools/pf_oracle/tests/sdvk009_many_light_fixture.cpp",
            includes=("src/common/rendering",), root=ROOT,
        )

    def test_active_upload_guard_rejects_one_past_index_table(self) -> None:
        renderstate = source("src/common/rendering/vulkan/vk_renderstate.cpp")
        policy = source("src/common/rendering/vulkan/vk_lightuploadpolicy.h")
        self.assertIn("uploadIndex < count", policy)
        body = renderstate.split("int VkRenderState::UploadLights", 1)[1].split("int VkRenderState::UploadBones", 1)[0]
        self.assertIn("VkLightUploadPolicy::Fits", body)
        self.assertNotIn("indexindex <= mRSBuffers->Lightbuffer.Count", body)
        self.assertIn("IndexCapacityFailures", body)
        self.assertIn("DataCapacityFailures", body)
        self.assertIn("if (size0) memcpy(dataptr, data.arrays[0].Data()", body)
        self.assertIn("if (size1) memcpy(dataptr + size0, data.arrays[1].Data()", body)
        self.assertIn("if (size2) memcpy(dataptr + (size0 + size1), data.arrays[2].Data()", body)

    def test_empty_levelmesh_classes_do_not_form_out_of_bounds_array_references(self) -> None:
        levelmesh = source("src/rendering/hwrenderer/doom_levelmesh.cpp")
        body = levelmesh.split("void DoomLevelMesh::UploadDynLights", 1)[1].split("TArray<HWWall>& DoomLevelMesh::GetSidePortals", 1)[0]
        self.assertIn("if (size0) memcpy(dataptr, lightdata.arrays[0].Data()", body)
        self.assertIn("if (size1) memcpy(dataptr + size0, lightdata.arrays[1].Data()", body)
        self.assertIn("if (size2) memcpy(dataptr + (size0 + size1), lightdata.arrays[2].Data()", body)

    def test_dormant_tile_consumer_cannot_preserve_dense_equivalence(self) -> None:
        shader = source("wadsrc/static/shaders/scene/comp_lighttiles.glsl")
        frag = source("wadsrc/static/shaders/scene/frag_main.glsl")
        self.assertIn("const int maxLights = 16;", shader)
        self.assertIn("DynLightInfo lights[16];", shader)
        self.assertIn("if(count == maxLights) break;", shader)
        self.assertIn("uLightIndex = -1;", frag)
        self.assertIn("//uLightIndex = int(uint(gl_FragCoord.x)", frag)

    def test_dormant_levelmesh_producer_has_unresolved_portal_semantics(self) -> None:
        levelmesh = source("src/rendering/hwrenderer/doom_levelmesh.cpp")
        self.assertIn("int portalGroup = 0; // What value should this have?", levelmesh)
        self.assertIn("AddLightToList(lightdata, portalGroup, light, false, false);", levelmesh)
        self.assertIn("return 0;", levelmesh.split("int DoomLevelMesh::GetLightIndex", 1)[1].split("void DoomLevelMesh::UpdateLight", 1)[0])
        header = source("src/playsim/a_dynlight.h")
        self.assertIn("max_levelmesh_entries", header)

    def test_pf017_rejected_temporal_record_reuse_is_not_resurrected(self) -> None:
        report = source("docs/shadedoomvk/PF-017-FINAL-ACCEPTANCE.md")
        self.assertIn("LIGHT-PATH NO-GO", report)
        self.assertIn("+10.79%", report)
        self.assertIn("No reuse, hash/indirection", source("docs/shadedoomvk/rag/10-KNOWN-TRAPS-DORMANT-PATHS.md"))

    def test_reusable_state_diagnostics_expose_light_scaling_and_fallback(self) -> None:
        observer = source("src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp")
        vulkan = source("src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp")
        for field in (
            "authored_lights", "active_lights", "spot_lights", "subtractive_lights", "additive_lights",
            "actor_light_queries", "actor_light_candidates", "actor_light_selected", "actor_light_filtered",
            "actor_light_duplicates", "actor_light_traces",
        ):
            self.assertIn(f'"{field}"', observer)
        for field in (
            "range_entries_used", "records_used", "attempts", "successful", "failed",
            "index_capacity_failures", "data_capacity_failures", "normal_records",
            "subtractive_records", "additive_records", "uploaded_bytes", "peak_records_per_upload",
            "range_capacity_bytes", "record_capacity_bytes", "records_per_upload_histogram",
        ):
            self.assertIn(f'"{field}"', vulkan)
        self.assertIn("StateEnabled() ?", vulkan)


if __name__ == "__main__":
    unittest.main()
