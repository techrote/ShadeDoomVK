"""CPU/source checks for authored inputs; no shader/compiler/engine execution."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib

PATH = Path(__file__).resolve().parents[1] / "prepare_pbr_probe_runtime.py"
SPEC = importlib.util.spec_from_file_location("pf113_prepare_inputs", PATH)
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class ProbeInputs(unittest.TestCase):
    def test_deterministic_archive_and_only_authored_map_lumps(self):
        members = fixture.members()
        raw = fixture.archive_bytes(members)
        self.assertEqual(raw, fixture.archive_bytes(fixture.members()))
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertEqual(archive.namelist(), sorted(members))
            for entry in archive.infolist():
                self.assertEqual(entry.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(archive.read(entry), members[entry.filename])
        wad = members["maps/PF113.wad"]
        magic, count, start = struct.unpack_from("<4sII", wad)
        self.assertEqual(magic, b"PWAD")
        names = [struct.unpack_from("<II8s", wad, start+16*i)[2].rstrip(b"\0") for i in range(count)]
        self.assertEqual(names, [b"PF113", b"TEXTMAP", b"ENDMAP"])
        self.assertFalse(any("lightmap" in name.lower() or "probe" in name.lower() for name in members))

    def test_probe_ordinals_and_selected_target_geometry(self):
        source = fixture.textmap()
        self.assertEqual(source.count("type = 9892"), 2)
        self.assertLess(source.index("x = -112; y = -112"), source.index("x = 64; y = 0; height = 64"))
        def nearest(point):
            return min(range(2), key=lambda i: sum((a-b)**2 for a, b in zip(point, fixture.PROBES[i])))
        self.assertEqual(nearest([0, 0, 64]), 1)
        self.assertEqual(nearest([128, 0, 64]), 1)
        self.assertEqual(nearest([-128, 0, 64]), 0)
        parser = (fixture.ROOT/"src/maploader/udmf.cpp").read_text()
        selector = (fixture.ROOT/"src/g_levellocals.h").read_text()
        self.assertIn("th->EdNum == 9892", parser)
        self.assertIn("Level->lightProbes.Push(probe)", parser)
        self.assertIn("FindClosestProbe(origin)", selector)
        self.assertIn("floorplane.ZatPoint", selector)
        self.assertIn("+ 64", selector)

    def test_real_material_channel_inputs_and_source_parser(self):
        members = fixture.members()
        declarations = fixture.gldefs()
        self.assertIn("material texture PF113W", declarations)
        self.assertIn("material flat PF113FL", declarations)
        for keyword, name in (("normal", "PF113N"), ("metallic", "PF113M"), ("roughness", "PF113R"), ("ao", "PF113A")):
            self.assertEqual(declarations.count(f'{keyword} "{name}"'), 2)
            self.assertIn(f"textures/{name}.png", members)
        parser = (fixture.ROOT/"src/r_data/gldefs.cpp").read_text()
        self.assertIn('"normal", "specular", "metallic", "roughness", "ao"', parser)
        self.assertIn("textures[i] = TexMan.FindGameTexture", parser)
        material = (fixture.ROOT/"src/common/textures/hw_material.cpp").read_text()
        self.assertIn("mShaderIndex = SHADER_PBR;", material)
        for channel in ("Normal", "Metallic", "Roughness", "AmbientOcclusion"):
            self.assertIn(f"tx->Layers->{channel}.get()", material)

    def test_png_channel_bytes_are_bounded_and_deterministic(self):
        for name, wanted in (("N", [128, 128, 255, 255]), ("M", [64]*3+[255]), ("R", [128]*3+[255]), ("A", [192]*3+[255])):
            raw = fixture.members()[f"textures/PF113{name}.png"]
            width, height, depth, kind, *_ = struct.unpack_from(">IIBBBBB", raw, 16)
            self.assertEqual((width, height, depth, kind), (64, 64, 8, 6))
            position, compressed = 8, b""
            while position < len(raw):
                size, chunk = struct.unpack_from(">I4s", raw, position)
                body = raw[position+8:position+8+size]
                crc = struct.unpack_from(">I", raw, position+8+size)[0]
                self.assertEqual(crc, zlib.crc32(chunk+body) & 0xffffffff)
                if chunk == b"IDAT":
                    compressed += body
                position += size+12
            rows = zlib.decompress(compressed)
            self.assertEqual(len(rows), 64*(64*4+1))
            for y in range(64):
                row = rows[y*257:(y+1)*257]
                self.assertEqual(row[0], 0)
                self.assertEqual(row[1:], bytes(wanted)*64)
        with self.assertRaises(ValueError):
            fixture.png_rgba(1024, 1, b"")

    def test_actual_immediate_controls_no_invented_switch(self):
        command = fixture.command(None, Path("a.wad"), Path("b.pk3"), Path("c.ini"), Path("d.cfg"), Path("early"))
        for key, value in (("+gl_lightprobe", "true"), ("+gl_levelmesh", "false"), ("+gl_ubershaders", "false"), ("+gl_light_shadows", "0")):
            self.assertEqual(command[command.index(key)+1], value)
            self.assertLess(command.index(key), command.index("+map"))
        self.assertNotIn("+gl_render_method", command)
        self.assertIn("CVAR(Bool, gl_levelmesh, false", (fixture.ROOT/"src/rendering/hwrenderer/scene/hw_drawinfo.cpp").read_text())
        self.assertIn("uselevelmesh = gl_levelmesh && !outer", (fixture.ROOT/"src/rendering/hwrenderer/scene/hw_bsp.cpp").read_text())
        pipeline = (fixture.ROOT/"src/common/rendering/vulkan/pipelines/vk_renderpass.cpp").read_text()
        self.assertIn("if (!gl_ubershaders)", pipeline)
        self.assertIn("CVAR(Bool, gl_ubershaders", pipeline)
        self.assertIn("gl_light_shadows=0", fixture.configuration())

    def test_wait_chain_and_native_extent_source(self):
        script = fixture.capture_script(Path("native"), Path("presentation.png"))
        self.assertEqual(len(script.splitlines()), 1)
        commands = [item.strip() for item in script.strip().split(";")]
        self.assertEqual(commands[0:3], ["wait 105", "vid_setsize 640 480", "wait 35"])
        self.assertEqual(commands[4], "wait 35")
        self.assertEqual(commands[-2:], ["wait 5", "quit"])
        self.assertGreater(int(commands[2].split()[1]), 17)
        dispatch = (fixture.ROOT/"src/common/console/c_dispatch.cpp").read_text()
        self.assertIn("AddCommandString", dispatch)
        self.assertIn("ExecCommands", dispatch)
        self.assertIn("CCMD(vid_setsize)", (fixture.ROOT/"src/common/rendering/v_video.cpp").read_text())
        self.assertIn("AdjustWindowRectEx", (fixture.ROOT/"src/common/platform/win32/base_sysfb.cpp").read_text())

    def test_console_injection_rejected(self):
        for path in ('bad;quit', 'bad"path', "bad\npath"):
            with self.assertRaises(ValueError):
                fixture.safe_path(Path(path))

    def test_fresh_manifest_pins_and_unexecuted_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            iwad_dir = directory/"isolated"
            iwad_dir.mkdir()
            iwad = iwad_dir/"doom2.wad"
            iwad.write_bytes(b"authored test identity, never native launched")
            out = directory/"prepared"
            with patch.object(fixture, "IWAD_SHA256", hashlib.sha256(iwad.read_bytes()).hexdigest()), patch.object(fixture, "source_identity", return_value={"test": "0"*64}):
                manifest = fixture.prepare(out, iwad)
                self.assertFalse(manifest["gpuExecuted"])
                self.assertEqual(manifest["status"], "prepared-unaccepted")
                self.assertFalse(manifest["scene"]["prebakedProbeOrLightmapLumps"])
                self.assertEqual(json.loads((out/"manifest.json").read_text()), manifest)
                self.assertEqual(manifest["mod"]["sha256"], hashlib.sha256(Path(manifest["mod"]["path"]).read_bytes()).hexdigest())
                with self.assertRaisesRegex(ValueError, "fresh"):
                    fixture.prepare(out, iwad)
                (iwad_dir/"extras.wad").write_bytes(b"unowned extra")
                with self.assertRaisesRegex(ValueError, "adjacent"):
                    fixture.prepare(directory/"extra-case", iwad)

    def test_wrong_iwad_and_missing_required_source_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            iwad = directory/"doom2.wad"
            iwad.write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError, "IWAD differs"):
                fixture.prepare(directory/"prepared", iwad)
            with self.assertRaises(FileNotFoundError):
                fixture.source_identity(directory)


if __name__ == "__main__":
    unittest.main()
