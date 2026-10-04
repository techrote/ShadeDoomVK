"""Bounded CPU/source-linked tests; never dispatch a renderer or GPU probe."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import zlib

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("pf020_dense_runner", ROOT / "tools/pf_oracle/run_freeze_dense_runtime.py")
dense = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dense)


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)


def png(width=11, height=7, blank=False, filters=(0, 1, 2, 3, 4)):
    pixels = bytes(0 if blank else (x * 23 + y * 41 + c * 67) % 256
                   for y in range(height) for x in range(width) for c in range(3))
    stride = width * 3; previous = bytes(stride); filtered = bytearray()
    for y in range(height):
        row = pixels[y * stride:(y + 1) * stride]; mode = filters[y % len(filters)]; filtered.append(mode)
        for x, value in enumerate(row):
            left, above, corner = (row[x - 3] if x >= 3 else 0), previous[x], (previous[x - 3] if x >= 3 else 0)
            if mode == 4:
                p = left + above - corner; distances = (abs(p - left), abs(p - above), abs(p - corner))
                prediction = (left, above, corner)[distances.index(min(distances))]
            else:
                prediction = (0, left, above, (left + above) // 2)[mode]
            filtered.append((value - prediction) & 255)
        previous = row
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(filtered)) + chunk(b"IEND", b"")), pixels


def bench_block(all_ms="18.167", sprite_setup="3.854"):
    return ('Map PF16TST: "PF-016 Dense Dynamic-Light Stress",\n'
            'x = -1850.0000, y = 0.0000, z = 41.0000, angle = 0.0000, pitch = 0.0000\n49 fps\n\n'
            'Walls: 5 (0 splits, 0 t-splits, 20 vertices)\n'
            'Flats: 2 (2 primitives, 24 vertices)\n'
            'Sprites: 832, Decals=0, Portals: 0, Command buffers: 5\n'
            'BSP = .112, Clip=.100\nW: Render=.222, Setup=.111\nF: Render=.012, Setup=.013\n'
            f'S: Render=.342, Setup={sprite_setup}\n'
            '2D: .013 Finish3D: .012\n'
            'Main thread total=1.00, Main thread waiting=.01 Worker thread total=2.00, Worker thread waiting=.01\n'
            f'All={all_ms}, Render=.508, Setup=3.922, Portal=.000, Drawcalls=.178, Postprocess=.113, Finish=13.542\n'
            'DLight - Walls: 257 processed, 253 rendered - Flats: 432 processed, 432 rendered\n\n\n\n')


def seed_ini():
    values = dict(dense.GLOBAL)
    values.update(use_mouse="true", m_use_mouse="1", vid_activeinbackground="false", vid_lowerinbackground="true", show_messages="true")
    game = {**dense.GAME, "con_notifytime": "3"}
    return ('[IWADSearch.Directories]\nPath=old\nPath=older\n[GlobalSettings]\n'
            + "\n".join(k + "=" + v for k, v in values.items())
            + '\n[Doom.ConsoleVariables]\n' + "\n".join(k + "=" + v for k, v in game.items())
            + '\n[Doom.Bindings]\nw=+forward\n[Doom.DoubleBindings]\nmouse1=+attack\n'
            '[Doom.ConsoleAliases]\nbench=quit\n[Doom.AutoExec]\nPath=unsafe.cfg\n'
            '[Global.Autoload]\nPath=unknown.wad\n')


class DenseRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)

    def write_png(self, data):
        path = self.out / "image.png"; path.write_bytes(data); return path

    def test_rgb_png_real_filters_roundtrip(self):
        data, wanted = png()
        pixels, result = dense.decode_png(self.write_png(data), (11, 7))
        self.assertEqual(pixels, wanted)
        self.assertEqual(result["rowFiltersObserved"], [0, 1, 2, 3, 4])
        self.assertEqual(result["decodedRgbSha256"], dense.sha(wanted))

    def test_png_corrupt_crc_rejected(self):
        data, _ = png(); changed = bytearray(data); changed[47] ^= 1
        with self.assertRaisesRegex(ValueError, "CRC"):
            dense.decode_png(self.write_png(changed), (11, 7))

    def test_png_header_only_rejected(self):
        data, _ = png()
        with self.assertRaises(ValueError):
            dense.decode_png(self.write_png(data[:33]), (11, 7))

    def test_png_wrong_extent_rejected(self):
        data, _ = png()
        with self.assertRaisesRegex(ValueError, "extent"):
            dense.decode_png(self.write_png(data), (12, 7))

    def test_png_trailing_bytes_rejected(self):
        data, _ = png()
        with self.assertRaisesRegex(ValueError, "trailing"):
            dense.decode_png(self.write_png(data + b"extra"), (11, 7))

    def test_png_extra_zlib_stream_rejected(self):
        data, _ = png(); length = struct.unpack_from(">I", data, 33)[0]
        body = data[41:41 + length] + zlib.compress(b"extra")
        mutated = data[:33] + chunk(b"IDAT", body) + chunk(b"IEND", b"")
        with self.assertRaisesRegex(ValueError, "boundary"):
            dense.decode_png(self.write_png(mutated), (11, 7))

    def test_png_invalid_filter_rejected(self):
        data, _ = png(); length = struct.unpack_from(">I", data, 33)[0]
        body = bytearray(zlib.decompress(data[41:41 + length])); body[0] = 5
        with self.assertRaisesRegex(ValueError, "filter"):
            dense.decode_png(self.write_png(data[:33] + chunk(b"IDAT", zlib.compress(body)) + chunk(b"IEND", b"")), (11, 7))

    def test_png_noncontiguous_idat_rejected(self):
        data, _ = png(); length = struct.unpack_from(">I", data, 33)[0]; payload = data[41:41 + length]
        changed = data[:33] + chunk(b"IDAT", payload[:4]) + chunk(b"tEXt", b"x\0y") + chunk(b"IDAT", payload[4:]) + chunk(b"IEND", b"")
        with self.assertRaisesRegex(ValueError, "noncontiguous"):
            dense.decode_png(self.write_png(changed), (11, 7))

    def test_nonblank_gate_rejects_actual_decoded_blank(self):
        data, _ = png(32, 32, blank=True)
        with mock.patch.object(dense, "EXTENT", (32, 32)):
            with self.assertRaisesRegex(ValueError, "blank"):
                dense.image_evidence(self.write_png(data))

    def test_nonblank_gate_records_decoded_hash(self):
        data, wanted = png(96, 96)
        with mock.patch.object(dense, "EXTENT", (96, 96)):
            result = dense.image_evidence(self.write_png(data))
        self.assertEqual(result["decodedRgbSha256"], dense.sha(wanted))

    def test_five_cpu_snapshots_first_excluded(self):
        result = dense.parse_benchmarks(bench_block("999") + bench_block() * 4)
        self.assertEqual(result["retainedIndices"], [1, 2, 3, 4])
        self.assertTrue(result["snapshots"][0]["excludedWarmSnapshot"])
        self.assertFalse(result["gpuTimestampClaimed"])
        self.assertEqual(result["snapshots"][1]["counts"]["sprites"], 832)
        self.assertEqual(result["snapshots"][1]["cpuMilliseconds"]["allIncludingFinish"], 18.167)

    def test_snapshot_missing_extra_rejected(self):
        for count in (0, 4, 6):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "snapshot"):
                dense.parse_benchmarks(bench_block() * count)

    def test_camera_movement_rejected(self):
        with self.assertRaisesRegex(ValueError, "camera"):
            dense.parse_benchmarks((bench_block() * 5).replace("x = -1850.0000", "x = -1849.0000", 1))

    def test_population_or_light_reduction_rejected(self):
        for old, new in (("Sprites: 832", "Sprites: 831"), ("253 rendered", "252 rendered"), ("Command buffers: 5", "Command buffers: 4")):
            with self.subTest(old=old), self.assertRaisesRegex(ValueError, "counters"):
                dense.parse_benchmarks((bench_block() * 5).replace(old, new, 1))

    def test_cpu_nan_negative_rejected(self):
        for value in ("nan", "inf", "-1"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "timing"):
                dense.parse_benchmarks(bench_block(value) * 5)

    def test_duplicate_camera_or_counter_rejected(self):
        changed = bench_block().replace("Walls: 5", "Walls: 5 (0 splits, 0 t-splits, 20 vertices)\nWalls: 5")
        with self.assertRaisesRegex(ValueError, "duplicated"):
            dense.parse_benchmarks(changed + bench_block() * 4)

    def test_config_preserves_quality_locks_input_clears_untrusted_dispatch(self):
        result = dense.ini_sections(dense.configuration(seed_ini()))
        self.assertEqual(dense.section_values(result, "GlobalSettings", dense.GLOBAL), dense.GLOBAL)
        self.assertEqual(dense.section_values(result, "Doom.ConsoleVariables", dense.GAME), dense.GAME)
        for section in ("Doom.Bindings", "Doom.DoubleBindings", "Doom.ConsoleAliases", "Doom.AutoExec", "Global.Autoload", "IWADSearch.Directories"):
            self.assertEqual(result[section], [])

    def test_saved_ini_repeated_path_allowed_duplicate_critical_rejected(self):
        sections = dense.ini_sections(seed_ini())
        self.assertEqual(len(sections["IWADSearch.Directories"]), 2)
        sections["GlobalSettings"].append(("VID_RENDERMODE", "0"))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            dense.section_values(sections, "GlobalSettings", dense.GLOBAL)

    def test_seed_quality_change_rejected(self):
        with self.assertRaisesRegex(ValueError, "quality"):
            dense.configuration(seed_ini().replace("gl_texture_filter=6", "gl_texture_filter=0"))

    def test_notifications_are_explicit_ui_overrides_without_renderer_quality_change(self):
        source = dense.ini_sections(seed_ini())
        result = dense.ini_sections(dense.configuration(seed_ini()))
        self.assertEqual(dense.section_values(source, "GlobalSettings", dense.UI_GLOBAL), {"show_messages": "true"})
        self.assertEqual(dense.section_values(source, "Doom.ConsoleVariables", dense.UI_GAME), {"con_notifytime": "3"})
        self.assertEqual(dense.section_values(result, "GlobalSettings", dense.UI_GLOBAL), {"show_messages": "false"})
        self.assertEqual(dense.section_values(result, "Doom.ConsoleVariables", dense.UI_GAME), {"con_notifytime": "0"})
        self.assertEqual(dense.section_values(result, "GlobalSettings", {"gl_texture_filter": "6", "gl_spritelight": "2"}),
                         {"gl_texture_filter": "6", "gl_spritelight": "2"})
        # Captured absence is paired with actual runtime queries and saved state,
        # not inferred from requested commands or a seed alone.
        self.assertEqual(dense.QUERIES["show_messages"], "false")
        self.assertEqual(dense.QUERIES["con_notifytime"], "0")
        script = dense.execution_script(self.out)
        self.assertTrue(script.startswith("show_messages false; con_notifytime 0; "))
        self.assertLess(script.index("show_messages false"), script.index("; show_messages;"))

    def test_source_linked_notification_gate_preserves_stdout_query_proof(self):
        notify = (ROOT / "src/console/c_notifybuffer.cpp").read_text()
        start = notify.index("void FNotifyBuffer::AddString")
        guard = notify[start:notify.index("// [MK]", start)]
        self.assertRegex(guard, r"(?s)\{\s*if \(!show_messages \|\|.*?\)\s*return;")
        self.assertIn("CVAR(Float, con_notifytime, 3.f, CVAR_ARCHIVE)", notify)
        commands = (ROOT / "src/console/c_cmds.cpp").read_text()
        self.assertIn("CVARD(Bool, show_messages, true, CVAR_ARCHIVE | CVAR_GLOBALCONFIG", commands)
        console = (ROOT / "src/common/console/c_console.cpp").read_text()
        print_body = console[console.index("int PrintString ("):]
        self.assertLess(print_body.index("I_PrintStr(outline);"), print_body.index("NotifyStrings->AddString"))
        self.assertNotIn("show_messages", print_body[:print_body.index("I_PrintStr(outline);")])

    def test_runtime_queries_all_required_and_unique(self):
        text = "\n".join(f'"{k}" is "{v}" (default: "other")' for k, v in dense.QUERIES.items()) + "\n"
        self.assertEqual(dense.query_evidence(text), dense.QUERIES)
        for changed in (text.replace('"gl_levelmesh" is "false"', '"gl_levelmesh" is "true"'), text + text, text.replace('"gl_levelmesh"', '"other"')):
            with self.assertRaises(ValueError):
                dense.query_evidence(changed)

    def test_single_physical_exec_chain_and_bounded_snapshot_windows(self):
        script = dense.execution_script(self.out)
        self.assertEqual(script.count("\n"), 1)
        commands = script.strip().split("; ")
        self.assertEqual(commands.count("bench"), 5)
        self.assertEqual(commands.count("wait 190"), 4)
        self.assertIn("bench; wait 350; pause; wait 60", script)
        self.assertIn("stat rendertimes; vid_fps false", script)
        self.assertIn('wait 35; screenshot "', script)
        self.assertTrue(script.endswith("wait 35; echo PF020_DENSE_COMPLETE; quit\n"))
        self.assertNotRegex(script.lower(), r"pf_indexed|pf_pbr|debug_restart|cfx")

    def test_command_exact_map_seed_no_old_runner(self):
        args = dense.execution_command(self.out / "vkdoom.exe", self.out / "doom2.wad", self.out / "dense.wad", self.out)
        self.assertEqual(args[args.index("-rngseed") + 1], "12345")
        self.assertEqual(args[args.index("+map") + 1], "PF16TST")
        self.assertEqual(args[-2:], ["+exec", str((self.out / "execute.cfg").resolve())])
        self.assertNotIn("-warp", args)
        self.assertIn("-noautoexec", args)

    def test_console_path_injection_rejected(self):
        for name in ('x;quit', 'x"', 'x\nquit'):
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                dense.console_path(self.out / name)

    def test_environment_removes_diagnostics_validation_retains_normal(self):
        env, removed = dense.clean_environment({"Path": "path", "pf16_diag": "1", "PF17_DUMP": "x", "CFX_CRASH": "x",
                                              "VK_INSTANCE_LAYERS": "Khronos", "VULKAN_SDK": "sdk", "HOME": "home"})
        self.assertEqual(env, {"Path": "path", "HOME": "home"})
        self.assertEqual(len(removed), 5)

    def packages(self):
        expected = {}
        rows = []
        for index in range(7):
            path = self.out / f"package{index}.wad"; path.write_bytes(bytes([index]))
            pin = dense.identity(path); expected[pin["path"]] = {**pin, "lumps": index + 1}
            rows.append(f'adding {path}, {index + 1} lumps')
        return expected, "W_Init: Init WADfiles.\n" + "\n".join(rows) + "\n"

    def test_actual_packages_exact_once_hash_counts(self):
        expected, text = self.packages()
        self.assertEqual(len(dense.package_evidence(text, expected)), 7)
        (self.out / "package2.wad").write_bytes(b"wrong")
        with self.assertRaisesRegex(ValueError, "Immutable"):
            dense.package_evidence(text, expected)

    def test_packages_missing_extra_duplicate_multiple_startup_rejected(self):
        expected, text = self.packages()
        lines = text.splitlines()
        for changed in ("\n".join(lines[:-1]), text + lines[-1] + "\n", text.replace(lines[-1], lines[-2]), text + "W_Init: Init WADfiles.\n"):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                dense.package_evidence(changed, expected)

    def test_native_device_actual_not_requested_only(self):
        text = "Vulkan device: NVIDIA GeForce GTX 1650 SUPER\nVulkan device type: discrete gpu\nVulkan version: 1.4.351 (api) 616.368.0 (driver)\n"
        self.assertEqual(dense.native_device(text)["encodedDriver"], "616.368.0")
        for changed in (text * 2, text.replace("NVIDIA GeForce GTX 1650 SUPER", "software")):
            with self.assertRaises(ValueError):
                dense.native_device(changed)

    def test_committed_source_attestation_actual_blob_protocol(self):
        names = [f"src/test{i:03}.cpp" for i in range(100)]
        data = b"line\n"; closure = {name: {"raw_sha256": dense.sha(b"line\r\n"), "normalized_lf_sha256": dense.sha(data)} for name in names}
        response = (b"a" * 40 + b" blob 5\n" + data + b"\n") * 100
        runner = mock.Mock(return_value=types.SimpleNamespace(returncode=0, stdout=response))
        result = dense.attest_sources(closure, "b" * 40, runner=runner)
        self.assertEqual(result["files"], 100)
        self.assertEqual(result["crlfProjections"], 100)
        self.assertEqual(runner.call_args.args[0], ["git", "--no-optional-locks", "cat-file", "--batch"])
        closure[names[0]]["normalized_lf_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Committed LF"):
            dense.attest_sources(closure, "b" * 40, runner=runner)

    def test_source_query_path_injection_rejected(self):
        for name in ("../src.cpp", "src/a\nb", "C:/outside.cpp", "/src.cpp"):
            with self.assertRaises(ValueError):
                dense.source_name(name)

    def test_own_child_watchdog_kills_only_owned_handle_and_retains_running_receipt(self):
        class Child:
            pid = 441
            returncode = None
            killed = False
            def poll(self): return -9 if self.killed else None
            def kill(self): self.killed = True
            def wait(self, timeout): self.returncode = -9; return -9
        child = Child(); spawn = mock.Mock(return_value=child); receipt = {}
        with self.assertRaisesRegex(ValueError, "watchdog"):
            dense.run_child(["fake-child"], self.out, {}, receipt, popen=spawn, clock=iter((0., 91.)).__next__)
        self.assertTrue(child.killed)
        self.assertEqual(receipt["watchdog"]["killedOwnPid"], 441)
        self.assertEqual(receipt["childCount"], 1)
        self.assertFalse(spawn.call_args.kwargs["shell"])
        self.assertEqual(json.loads((self.out / "receipt.json").read_text())["status"], "RUNNING")

    def test_output_mutation_changes_closure(self):
        file = self.out / "proof.bin"; file.write_bytes(b"one")
        before = dense.output_inventory(self.out); file.write_bytes(b"two")
        self.assertNotEqual(before, dense.output_inventory(self.out))

    def test_running_receipt_write_failure_still_kills_owned_child(self):
        child = mock.Mock(pid=881, returncode=-9)
        child.poll.side_effect = [None]
        receipt = {}
        with mock.patch.object(dense, "save", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                dense.run_child(["fake-child"], self.out, {}, receipt, popen=mock.Mock(return_value=child))
        child.kill.assert_called_once_with()
        child.wait.assert_called_once_with(timeout=10)
        self.assertEqual(receipt["abortedOwnPid"], 881)

    def test_duplicate_json_key_rejected(self):
        file = self.out / "bad.json"; file.write_text('{"status":"PASS","status":"FAIL"}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            dense.read_json(file)

    def test_real_stock_sprite_lump_names_allowed_directory_truncation_rejected(self):
        file = self.out / "stock.wad"
        payload = b"IWAD" + struct.pack("<ii", 2, 14) + b"ab"
        payload += struct.pack("<ii8s", 12, 1, b"VILE[1\0\0") + struct.pack("<ii8s", 13, 1, b"VILE\\1\0\0")
        file.write_bytes(payload)
        self.assertEqual([n for n, _ in dense.wad_members(file, b"IWAD")], ["VILE[1", "VILE\\1"])
        file.write_bytes(payload[:-1])
        with self.assertRaisesRegex(ValueError, "directory"):
            dense.wad_members(file, b"IWAD")

    def test_completed_receipt_cannot_retry_or_be_rewritten(self):
        (self.out / "receipt.json").write_text('{"schema":"' + dense.SCHEMA + '","status":"PASS"}')
        before = (self.out / "receipt.json").read_bytes()
        with mock.patch.object(dense, "health", side_effect=AssertionError("must not launch")):
            result = dense.main(["--launch", "--variant", "candidate", "--out", str(self.out)])
        self.assertEqual(result, 1)
        self.assertEqual((self.out / "receipt.json").read_bytes(), before)

    def test_source_linked_timer_waits_and_cpu_units(self):
        source = (ROOT / "src/common/rendering/hwrenderer/data/hw_clock.cpp").read_text()
        self.assertIn("I_msTime() - waitstart < 5000", source)
        self.assertIn('fopen("benchmarks.txt", "at")', source)
        self.assertIn("All.TimeMS() + Finish.TimeMS()", source)
        self.assertIn("SetupSprite.TimeMS()", source)
        self.assertIn("printstats && ConsoleState == c_up", source)
        self.assertGreater(190 / 35, 5)

    def test_source_linked_native_size_camera_and_unarchived_levelmesh(self):
        self.assertIn("CCMD(vid_setsize)", (ROOT / "src/common/rendering/v_video.cpp").read_text())
        main = (ROOT / "src/d_main.cpp").read_text()
        self.assertIn("System_GetLocationDescription", main)
        self.assertIn('"Map %s:', main)
        self.assertTrue('CheckParm("-noautoexec")' in main)
        bsp = (ROOT / "src/rendering/hwrenderer/scene/hw_drawinfo.cpp").read_text()
        self.assertIn("CVAR(Bool, gl_levelmesh, false, 0", bsp)

    def test_source_linked_default_material_does_not_select_pbr_without_authored_layers(self):
        material = (ROOT / "src/common/textures/hw_material.cpp").read_text()
        constructor = material[material.index("FMaterial::FMaterial"):material.index("mShaderIndex = SHADER_PBR;") + 32]
        self.assertIn("mShaderIndex = SHADER_Default;", constructor)
        self.assertIn("tx->Layers && tx->Layers->Normal.get() && tx->Layers->Metallic.get() && tx->Layers->Roughness.get() && tx->Layers->AmbientOcclusion.get()", constructor)
        shader = (ROOT / "src/common/rendering/vulkan/shaders/vk_shader.cpp").read_text()
        default = shader[shader.index('{"Default",'):shader.index('{"Warp 1",')]
        self.assertIn("shaders/scene/lightmodel_normal.glsl", default)
        self.assertNotIn("lightmodel_pbr.glsl", default)


if __name__ == "__main__":
    unittest.main()
