"""SDVK-014 3D-floor side lightmap ownership contract; source-only, no Vulkan."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools.pf_oracle.tests.sdvk014_source import current


def contract_errors(build_ffblock: str, create_wall: str, add_tile: str, visible: str) -> list[str]:
    errors: list[str] = []

    if "LevelMeshInfo.ControlSector = rover->model;" not in build_ffblock:
        errors.append("missing-3dfloor-control-owner")
    if "info.ControlSector = wallpart.LevelMeshInfo.ControlSector;" not in create_wall:
        errors.append("lost-wall-control-owner")
    if "binding.ControlSector = info.ControlSector ? info.ControlSector->Index()" not in add_tile:
        errors.append("lost-tile-control-identity")

    side_start = visible.index("if (tile->Binding.Type == ST_MIDDLESIDE")
    flat_start = visible.index("else if (tile->Binding.Type == ST_CEILING")
    side = visible[side_start:flat_start]
    flat = visible[flat_start:]

    owner_line = "uint32_t controlSector = sinfo.ControlSector ? (uint32_t)sinfo.ControlSector->Index() : (uint32_t)0xffffffffUL;"
    side_match = "sinfo.Type == tile->Binding.Type && controlSector == tile->Binding.ControlSector"
    flat_match = "sinfo.Type == (DoomLevelMeshSurfaceType)tile->Binding.Type && controlSector == tile->Binding.ControlSector"
    if owner_line not in side or side_match not in side:
        errors.append("side-control-sector-alias")
    if owner_line not in flat or flat_match not in flat:
        errors.append("flat-control-sector-alias")
    return errors


class SpecialSurfaceLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ffblock = current("build_ffblock")
        cls.wall = current("create_wall_surface")
        cls.add = current("add_surface_to_tile")
        cls.visible = current("get_visible_surfaces")

    def test_3dfloor_control_sector_survives_producer_to_bake_consumer(self) -> None:
        self.assertEqual(contract_errors(self.ffblock, self.wall, self.add, self.visible), [])

    def test_side_control_sector_alias_negative_fails_for_intended_reason(self) -> None:
        side_start = self.visible.index("if (tile->Binding.Type == ST_MIDDLESIDE")
        flat_start = self.visible.index("else if (tile->Binding.Type == ST_CEILING")
        side = self.visible[side_start:flat_start]
        needle = " && controlSector == tile->Binding.ControlSector"
        self.assertEqual(side.count(needle), 1)
        mutant = self.visible[:side_start] + side.replace(needle, "", 1) + self.visible[flat_start:]
        self.assertIn(
            "side-control-sector-alias",
            contract_errors(self.ffblock, self.wall, self.add, mutant),
        )

    def test_flat_control_sector_alias_negative_remains_sensitive(self) -> None:
        flat_start = self.visible.index("else if (tile->Binding.Type == ST_CEILING")
        flat = self.visible[flat_start:]
        needle = " && controlSector == tile->Binding.ControlSector"
        self.assertEqual(flat.count(needle), 1)
        mutant = self.visible[:flat_start] + flat.replace(needle, "", 1)
        self.assertIn(
            "flat-control-sector-alias",
            contract_errors(self.ffblock, self.wall, self.add, mutant),
        )


if __name__ == "__main__":
    unittest.main()
