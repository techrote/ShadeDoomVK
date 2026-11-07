"""Execute exact production flat publication with CPU storage-only adapters.

No renderer/Vulkan device: supplied HWFlat input is already selected and oriented
by the real Process contract, pinned separately below. Retained pre-fix function
mutations must fail the same independent triangle/plane ownership oracle.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block


SIGNATURE = "void DoomLevelMesh::CreateFlatSurface("
OLD_PLANE = """auto plane = info.ControlSector ? info.ControlSector->GetSecPlane(!flatpart.ceiling) : flatpart.sector->GetSecPlane(flatpart.ceiling);
        surf.Plane = FVector4((float)plane.Normal().X, (float)plane.Normal().Y, (float)plane.Normal().Z, -(float)plane.D);
        if (info.ControlSector) surf.Plane = -surf.Plane;"""
NEW_PLANE = """auto plane = flatpart.plane.plane;
		surf.Plane = FVector4((float)plane.Normal().X, (float)plane.Normal().Y, (float)plane.Normal().Z, -(float)plane.D);"""
OLD_OVERWRITE = """for (int i = ginfo.IndexStart / 3, end = (ginfo.IndexStart + ginfo.IndexCount) / 3; i < end; i++)
                Mesh.SurfaceIndexes[i] = sinfo.Index;
            """


class FlatSurfaceOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory(prefix="sdvk014-flat-")
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        doom = (ROOT / "src/rendering/hwrenderer/doom_levelmesh.cpp").read_text()
        cls.function = block(doom, SIGNATURE)
        cls.flats = (ROOT / "src/rendering/hwrenderer/scene/hw_flats.cpp").read_text()
        template = (Path(__file__).with_name("sdvk014_flat_surface_fixture.cpp")).read_text()
        tile = (ROOT / "src/common/rendering/hwrenderer/data/hw_lightmaptile.h").read_text()
        binding = block(tile, "struct LightmapTileBinding\n") + ";"
        allocate = block(doom, "int DoomLevelMesh::AddSurfaceToTile(")
        publish = block(doom, "void DoomLevelMesh::SetSubsectorLightmap(")
        # The existing producer currently ignores alwaysUpdate. Silence only
        # that inherited warning in the storage-only adapter, not production.
        allocate = allocate.replace("uint8_t alwaysUpdate)", "uint8_t /*alwaysUpdate*/)")
        template = template.replace("// @PRODUCTION_LIGHTMAP_BINDING@", binding)
        template = template.replace("// @PRODUCTION_ADD_SURFACE_TO_TILE@", allocate)
        template = template.replace("// @PRODUCTION_SET_SUBSECTOR_LIGHTMAP@", publish)
        header = (ROOT / "src/common/rendering/hwrenderer/data/hw_levelmesh.h").read_text()
        methods = "\n".join(block(header, signature) for signature in
            ("inline int LevelMesh::AllocTile(", "inline void LevelMesh::FreeTile("))
        template = template.replace("// @PRODUCTION_TILE_POOL_METHODS@", methods.replace("LevelMesh::", "DoomLevelMesh::"))
        template = template.replace("// @PRODUCTION_RELEASE_TILES@", block(doom, "void DoomLevelMesh::ReleaseTiles("))

        def build(name: str, function: str) -> Path:
            path = root / (name + ".cpp")
            path.write_text(template.replace("// @PRODUCTION_CREATE_FLAT_SURFACE@", function))
            return compile_fixture(path, output_dir=root, name=name)

        cls.current = build("current", cls.function)
        cls.old_mapping = build("old-mapping", cls.function.replace(
            "SetSubsectorLightmap(sinfo.Index);", OLD_OVERWRITE + "SetSubsectorLightmap(sinfo.Index);"))
        if NEW_PLANE not in cls.function:
            raise AssertionError("exact selected-plane production boundary missing")
        cls.old_plane = build("old-plane", cls.function.replace(NEW_PLANE, OLD_PLANE))
        portal = "drawType == LevelMeshDrawType::Portal ? sectorPortals[flatpart.ceiling][flatpart.sector->Index()] : 0"
        if portal not in cls.function:
            raise AssertionError("exact portal ownership production boundary missing")
        cls.old_portal = build("old-portal", cls.function.replace(portal,
            "sectorPortals[flatpart.ceiling][flatpart.sector->Index()]"))
        alias_start = "\t\tif (tile.UseXYAxis &&"
        if alias_start not in allocate:
            raise AssertionError("flat plane-alias admission boundary changed")
        alias_guard = block(allocate, alias_start)
        old_allocate = allocate.replace(alias_guard, "")
        old_template = template.replace(allocate, old_allocate)
        path = root / "ambiguous-unchecked.cpp"
        path.write_text(old_template.replace("// @PRODUCTION_CREATE_FLAT_SURFACE@", cls.function))
        cls.unchecked_alias = compile_fixture(path, output_dir=root, name="ambiguous-unchecked")
        axis = "int index = surface->LightmapPlane;"
        if axis not in publish:
            raise AssertionError("3D-floor table source-plane boundary changed")
        old_template = template.replace(axis, "int index = surface->Type == ST_CEILING ? 0 : 1;")
        path = root / "old-source-axis.cpp"
        path.write_text(old_template.replace("// @PRODUCTION_CREATE_FLAT_SURFACE@", cls.function))
        cls.old_source_axis = compile_fixture(path, output_dir=root, name="old-source-axis")

    def execute(self, executable: Path, case: str, error: str | None = None) -> None:
        result = subprocess.run([str(executable), case], text=True, capture_output=True, timeout=10)
        if error is None:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), "PASS " + case)
        else:
            self.assertEqual(result.returncode, 11, result.stdout + result.stderr)
            self.assertEqual(result.stderr.strip(), error)

    def test_current_flat_publication(self) -> None:
        for case in ("floor", "ceiling", "3dfloor-top", "3dfloor-bottom", "inverted-selected-plane",
                     "sky-no-tile", "one-subsector", "repeated", "both-planes-ambiguous"):
            with self.subTest(case=case):
                self.execute(self.current, case)

    def test_pre_fix_whole_allocation_overwrite_fails(self) -> None:
        for case in ("floor", "ceiling", "3dfloor-top", "3dfloor-bottom", "repeated"):
            with self.subTest(case=case):
                self.execute(self.old_mapping, case, "triangle-surface-owner")
        self.execute(self.old_mapping, "one-subsector")

    def test_pre_fix_reconstructed_plane_fails_selected_input(self) -> None:
        self.execute(self.old_plane, "inverted-selected-plane", "selected-plane-height")
        # Ordinary supported 3D-floor top/bottom preserve old output.
        self.execute(self.old_plane, "3dfloor-top")
        self.execute(self.old_plane, "3dfloor-bottom")

    def test_actual_process_owns_plane_selection_and_orientation(self) -> None:
        process = block(self.flats, "void HWFlat::Process(")
        self.assertIn("plane.GetFromSector(model, whichplane);", process)
        self.assertIn("lightmapPlane = whichplane;", process)
        self.assertIn("if (whichplane != int(ceiling))", process)
        self.assertIn("plane.plane.FlipVert();", process)
        sector = block(self.flats, "void HWFlat::ProcessSector(")
        self.assertIn("Process(di, state, rover->top.model, rover->top.isceiling,", sector)
        self.assertIn("Process(di, state, rover->bottom.model, rover->bottom.isceiling,", sector)
        self.assertIn("FF_INVERTPLANES | FF_BOTHPLANES", sector)

    def test_pre_fix_sector_portal_leaks_into_internal_flat(self) -> None:
        for case in ("3dfloor-top", "3dfloor-bottom"):
            with self.subTest(case=case):
                self.execute(self.old_portal, case, "portal-owner")
        self.execute(self.old_portal, "sky-no-tile")

    def test_ambiguous_both_plane_binding_cannot_merge(self) -> None:
        self.execute(self.unchecked_alias, "both-planes-ambiguous", "plane-binding-alias")

    def test_source_plane_table_is_distinct_from_emitted_facing(self) -> None:
        self.execute(self.old_source_axis, "inverted-selected-plane", "source-plane-table-owner")
        self.execute(self.old_source_axis, "3dfloor-top")
        self.execute(self.old_source_axis, "3dfloor-bottom")
        vertex = (ROOT / "src/rendering/hwrenderer/hw_vertexbuilder.cpp").read_text()
        producer = block(vertex, "static int CreateIndexedVertices(")
        self.assertIn("ffloor->top.isceiling == h", producer)
        self.assertIn("ffloor->bottom.isceiling == h", producer)
        self.assertIn("h, ffloorIndex + 1", producer)
        consumer = block(vertex, "static void UpdatePlaneLightmap(")
        self.assertIn("origin->sub->LightmapTiles[origin->plane][origin->lightmapSlot]", consumer)

    def test_control_height_reconstruction_reuses_current_ranges_and_tiles(self) -> None:
        for case in ("control-top-rebuild", "control-bottom-rebuild", "inverted-rebuild"):
            with self.subTest(case=case):
                self.execute(self.current, case)
        self.execute(self.old_source_axis, "inverted-rebuild", "source-plane-table-owner")

    def test_supported_height_callback_reaches_current_reconstruction(self) -> None:
        helper = (ROOT / "src/levelmeshhelper.cpp").read_text()
        doom = (ROOT / "src/rendering/hwrenderer/doom_levelmesh.cpp").read_text()
        for height in ("Floor", "Ceiling"):
            wrapper = block(helper, "void UpdateLevelMesh::" + height + "HeightChanged(")
            self.assertIn("PropagateCorrelations(this, &UpdateLevelMesh::On" + height + "HeightChanged, sector);", wrapper)
            callback = block(doom, "void DoomLevelMesh::On" + height + "HeightChanged(")
            self.assertIn("UpdateFlat(sector->Index(), SurfaceUpdateType::Full);", callback)
        propagation = block(helper, "void PropagateCorrelations(")
        self.assertIn("sector->Level->SecCorrelations.CheckKey(sector->Index())", propagation)
        self.assertIn("&sector->Level->sectors[index]", propagation)
        begin = block(doom, "void DoomLevelMesh::BeginFrame(")
        self.assertLess(begin.index("TileBindings.clear();"), begin.index("CreateFlat(doomMap, flatIndex);"))
        create = block(doom, "void DoomLevelMesh::CreateFlat(")
        self.assertLess(create.index("FreeFlat(doomMap, sectorIndex);"), create.index("flat.ProcessSector(&disp, state, sector);"))
        free = block(doom, "void DoomLevelMesh::FreeFlat(")
        self.assertIn("ReleaseTiles(Flats[sectorIndex].FirstSurface);", free)
        self.assertIn("FreeGeometry(geo.VertexStart, geo.VertexCount, geo.IndexStart, geo.IndexCount);", free)
        self.assertNotIn("UpdateFlat(", block(doom, "void DoomLevelMesh::OnMidTex3DHeightChanged(").split("//")[0])


if __name__ == "__main__":
    unittest.main()
