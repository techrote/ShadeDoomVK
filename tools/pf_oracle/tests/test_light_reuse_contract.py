#!/usr/bin/env python3
"""PF-017 source-owned temporal light reuse lifecycle contract."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class LightReuseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reuse_h = source("src/common/rendering/hwrenderer/data/hw_lightreuse.h")
        cls.dyn_h = source("src/common/rendering/hwrenderer/data/hw_dynlightdata.h")
        cls.dyn_cpp = source("src/rendering/hwrenderer/hw_dynlightdata.cpp")
        cls.light_h = source("src/playsim/a_dynlight.h")
        cls.light_cpp = source("src/playsim/a_dynlight.cpp")
        cls.entrypoint = source("src/rendering/hwrenderer/hw_entrypoint.cpp")
        cls.rs_h = source("src/common/rendering/vulkan/buffers/vk_rsbuffers.h")
        cls.rs_cpp = source("src/common/rendering/vulkan/buffers/vk_rsbuffers.cpp")
        cls.renderstate = source("src/common/rendering/vulkan/vk_renderstate.cpp")

    def test_source_owned_snapshots_are_cleared_on_freelist_reincarnation(self) -> None:
        self.assertIn("FDynLightPackingSnapshot packingSnapshots[4]", self.light_h)
        get_light = self.light_cpp.split(
            "static FDynamicLight *GetLight", 1
        )[1].split("float LightCalcStrength", 1)[0]
        self.assertIn("FreeList.Pop(ret)", get_light)
        self.assertIn("memset(ret, 0, sizeof(*ret))", get_light)
        self.assertLess(
            get_light.index("FreeList.Pop(ret)"),
            get_light.index("memset(ret, 0, sizeof(*ret))"),
        )

    def test_context_begins_after_shadow_and_attenuation_finalization(self) -> None:
        body = self.entrypoint.split(
            "sector_t* RenderViewpoint", 1
        )[1].split("void DoWriteSavePic", 1)[0]
        shadow = body.index("screen->mShadowMap->PerformUpdate()")
        attenuation = body.index("FLightDefaults::SetAttenuationForLevel")
        scope = body.index("HWDynLightPackingContextScope lightPackingContext")
        eye_loop = body.index("for (int eye_ix = 0; eye_ix < eyeCount; ++eye_ix)")
        self.assertLess(shadow, scope)
        self.assertLess(attenuation, scope)
        self.assertLess(scope, eye_loop)

    def test_qualified_domain_excludes_ambiguous_mutation_spaces(self) -> None:
        for token in [
            "contextEpoch == 0 || light->IsSpot()",
            "RF2_LIGHTMULTALPHA",
            "!light->Sector || group != light->Sector->PortalGroup",
            "snapshotIndex = (forceAttenuate ? 1u : 0u) | (doTrace ? 2u : 0u)",
            "HWTryReuseLightPackingSnapshot",
            "HWCommitLightPackingSnapshot",
        ]:
            self.assertIn(token, self.dyn_cpp)

    def test_unqualified_and_sun_records_force_copy_path(self) -> None:
        self.assertIn("dld.revisions[lightClass].Push(revision)", self.dyn_cpp)
        self.assertIn("dld.revisions[LIGHTARRAY_NORMAL].Push(0)", self.dyn_cpp)
        self.assertIn("revisions[i].Clear()", self.dyn_h)
        self.assertIn("revisions[i] == 0", self.reuse_h)

    def test_mapped_reuse_requires_exact_revision_alignment(self) -> None:
        for token in [
            "RevisionShadow",
            "RangeShadow",
            "RangeShadowValid",
            "HWLightUploadClassCanReuse",
            "revisionsAligned",
            "previousRevisions[i] = revisionsAligned ? revisions[i] : 0",
        ]:
            self.assertIn(token, self.rs_h + self.rs_cpp + self.renderstate)

        begin_frame = self.renderstate.split(
            "void VkRenderState::BeginFrame()", 1
        )[1].split("void VkRenderState::EndRenderPass()", 1)[0]
        self.assertNotIn("RevisionShadow.clear", begin_frame)
        self.assertNotIn("RevisionShadow.assign", begin_frame)
        self.assertIn("Lightbuffer.UploadIndex = 0", begin_frame)
        self.assertIn("Lightbuffer.DataIndex = 0", begin_frame)

    def test_buffer_bounds_reject_range_index_equal_to_capacity(self) -> None:
        upload = self.renderstate.split(
            "int VkRenderState::UploadLights", 1
        )[1].split("int VkRenderState::UploadBones", 1)[0]
        self.assertIn("indexindex < lightbuffer.Count", upload)
        self.assertNotIn("indexindex <= lightbuffer.Count", upload)

    def test_revision_and_epoch_wrap_are_fail_closed(self) -> None:
        for token in [
            "mNextRevision == 0",
            "std::numeric_limits<uint64_t>::max()",
            "mDisabled = true",
            "epoch <= mLastEpoch",
            "mActiveEpoch = 0",
        ]:
            self.assertIn(token, self.reuse_h)

    def test_compiled_adversarial_lifecycle_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "light-reuse-fixture"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Isrc/common/rendering/hwrenderer/data",
                    "tools/pf_oracle/tests/light_reuse_fixture.cpp",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
