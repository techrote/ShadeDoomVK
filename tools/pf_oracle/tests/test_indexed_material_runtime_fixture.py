"""Deterministic asset/container/API tests; these are not runtime/GPU evidence."""
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
import re
import unittest
import zipfile

GENERATOR = Path(__file__).resolve().parents[1] / "prepare_indexed_material_runtime.py"
spec = importlib.util.spec_from_file_location("pf110_runtime_inputs", GENERATOR)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def decode_patch(data):
    width, height, left, top = struct.unpack_from("<HHhh", data)
    rows = [[None] * width for _ in range(height)]
    for x in range(width):
        offset, = struct.unpack_from("<I", data, 8+x*4)
        while data[offset] != 255:
            first, count = data[offset], data[offset+1]
            for y, index in enumerate(data[offset+3:offset+3+count], first):
                rows[y][x] = index
            offset += count+4
    return rows, (left, top)


class IndexedMaterialRuntimeInputs(unittest.TestCase):
    def test_real_doom_patch_posts_and_independent_first_use_owners(self):
        files = fixture.members()
        expected = [list(fixture.INDEX_ROW)] * fixture.HEIGHT
        for name in ("PF110SRC", "PF110SA", "PF110SB"):
            rows, origin = decode_patch(files[f"patches/{name}.lmp"])
            self.assertEqual(rows, expected)
            self.assertEqual(origin, (0, 0))
        self.assertEqual(len(files["flats/PF110FL.lmp"]), 4096)
        self.assertEqual(files["flats/PF110FL.lmp"][:64], bytes(fixture.INDEX_ROW * 4))

    def test_inverse_reference_rejects_translation_after_shader_order(self):
        files = fixture.members()
        old = [255-fixture.REMAP_A.get(n, n) for n in fixture.INDEX_ROW]
        wrong = [fixture.REMAP_A.get(255-n, 255-n) for n in fixture.INDEX_ROW]
        self.assertEqual(decode_patch(files["patches/PF110IA.lmp"])[0][0], old)
        self.assertEqual(decode_patch(files["patches/PF110WR.lmp"])[0][0], wrong)
        self.assertEqual((old[0], wrong[0]), (245, 20))
        self.assertNotEqual(old, wrong)

    def test_inverse_literal_indexed_reference_preserves_ordinary_filter_controls(self):
        overlay = fixture.zscript()
        self.assertIn('Panel("PF110SA", 120, 204, true, a, 0x12030201);', overlay)
        self.assertIn('Panel("PF110IA", 284, 204, true, 0);', overlay)
        self.assertNotIn('Panel("PF110IA", 284, 204, false, 0);', overlay)
        # The literal inverse reference alone changes route. These controls
        # must continue to exercise ordinary truecolour/global filtering.
        for control in (
            'Panel("PF110SRC", 284, 54, false, 0);',
            'Panel("PF110WR", 448, 204, false, 0);',
            'Panel("PF110RA", 284.25, 304, false, 0, 0x02030201, 0xffffffff, 127.5);',
            'Panel("PF110SRC", 120, 354, false, a);',
            'DTA_TranslationIndex, 0, DTA_Indexed, false);',
        ):
            self.assertIn(control, overlay)
        draw = (fixture.ROOT/"src/common/rendering/hwrenderer/hw_draw2d.cpp").read_text()
        self.assertIn("auto scaleflags = cmd.mFlags & F2DDrawer::DTF_Indexed ? CTF_Indexed : 0;", draw)
        material = (fixture.ROOT/"src/common/rendering/vulkan/textures/vk_hwtexture.cpp").read_text()
        descriptor = material[material.index("VkMaterial::DescriptorEntry& VkMaterial::GetDescriptorEntry"):]
        discrete = descriptor[descriptor.index("if (state.mPaletteMode || indexedMaterial)"):descriptor.index("for (auto& set : mDescriptorSets)")]
        self.assertIn("if (clampmode == CLAMP_XY_NOMIP) clampmode = CLAMP_NOFILTER_XY;", discrete)
        samplers = (fixture.ROOT/"src/common/rendering/vulkan/samplers/vk_samplers.cpp").read_text()
        ordinary = samplers[samplers.index("mSamplers[CLAMP_XY_NOMIP]"):samplers.index("for (int i = CLAMP_NOFILTER;")]
        discrete = samplers[samplers.index("for (int i = CLAMP_NOFILTER;"):samplers.index("// CAMTEX")]
        self.assertIn(".MagFilter(TexFilter[filter].magFilter)", ordinary)
        self.assertIn(".MinFilter(TexFilter[filter].magFilter)", ordinary)
        self.assertIn(".MagFilter(VK_FILTER_NEAREST)", discrete)
        self.assertIn(".MinFilter(VK_FILTER_NEAREST)", discrete)
        self.assertIn("gl_texture_filter;", samplers)
        self.assertIn("src/common/rendering/vulkan/samplers/vk_samplers.cpp", fixture.SOURCE_FILES)

    def test_archive_reproducible_no_original_game_data(self):
        first = fixture.archive_bytes(fixture.members())
        second = fixture.archive_bytes(fixture.members())
        self.assertEqual(first, second)
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            self.assertNotIn("PLAYPAL", archive.namelist())
            self.assertNotIn("doom2.wad", archive.namelist())
            self.assertIn("maps/PF110.wad", archive.namelist())
            self.assertTrue(all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in archive.infolist()))

    def test_color_tag_reference_keeps_actual_indexed_route_without_object_tint_claim(self):
        files = fixture.members()
        translated = [fixture.REMAP_A.get(n, n) for n in fixture.INDEX_ROW]
        self.assertEqual(decode_patch(files["patches/PF110RA.lmp"])[0][0], translated)
        overlay = files["ZSCRIPT"].decode()
        self.assertIn('Panel("PF110SA", 120, 254, true, a, 0x02030201, 0xff80c0ff);', overlay)
        self.assertIn('Panel("PF110RA", 284, 254, true, 0, 0x02030201, 0xff80c0ff);', overlay)
        parser = (fixture.ROOT/"src/common/2d/v_draw.cpp").read_text()
        self.assertIn("case DTA_Color:\n\t\t\tparms->color = ListGetInt(tags);", parser)
        drawer = (fixture.ROOT/"src/common/2d/v_2ddrawer.cpp").read_text()
        producer = drawer[drawer.index("dg.mTranslationId = NO_TRANSLATION;"):]
        self.assertLess(producer.index("SetStyle(img, parms, vertexcolor, dg);"), producer.index("if (parms.indexed)"))
        self.assertIn("dg.mLightLevel = vertexcolor.Luminance();\n\t\tvertexcolor = 0xffffffff;", producer)
        consumer = (fixture.ROOT/"src/common/rendering/hwrenderer/hw_draw2d.cpp").read_text()
        self.assertIn("if (cmd.mFlags & F2DDrawer::DTF_Indexed) state.SetSoftLightLevel(cmd.mLightLevel);", consumer)
        lightmode = (fixture.ROOT/"wadsrc/static/shaders/scene/lightmode.glsl").read_text()
        self.assertIn("if (SIMPLE2D)", lightmode)
        self.assertIn("vec4 frag = material.Base * vColor;", lightmode)
        for name in ("vert_main.glsl", "frag_main.glsl", "lightmode.glsl"):
            self.assertIn("wadsrc/static/shaders/scene/" + name, fixture.SOURCE_FILES)

    def test_room_and_public_api_are_real_source_contracts(self):
        source = fixture.ROOT
        overlay = fixture.zscript()
        self.assertEqual(overlay.splitlines()[0], 'version "4.5"')
        engine_script = (source/"wadsrc/static/zscript.txt").read_text()
        self.assertTrue(engine_script.startswith('version "4.15.1"\n'))
        self.assertIn('#include "zscript/doombase.zs"', engine_script)
        doom_base = (source/"wadsrc/static/zscript/doombase.zs").read_text()
        self.assertIn("extend struct CVar", doom_base)
        self.assertIn("native static CVar GetCVar(Name name, PlayerInfo player = null);", doom_base)
        self.assertIn("CVar.GetCVar('pf110_overlay').GetBool()", overlay)
        self.assertIn("virtual ui void RenderOverlay(RenderEvent e)", (source/"wadsrc/static/zscript/events.zs").read_text())
        base = (source/"wadsrc/static/zscript/engine/base.zs").read_text()
        for token in ("DTA_Indexed", "DTA_TranslationIndex", "native static TranslationID GetID(Name transname)",
                      "native static vararg void DrawTexture", "native static TextureID CheckForTexture"):
            self.assertIn(token, base)
        parser = (source/"src/r_data/r_translate.cpp").read_text()
        self.assertIn('fileSystem.FindLump("TRNSLATE"', parser)
        self.assertIn("GPalette.StoreTranslation(TRANSLATION_Custom, &NewTranslation)", parser)
        draw = (source/"src/common/2d/v_draw.cpp").read_text()
        self.assertIn("parms->style.AsDWORD = ListGetInt(tags)", draw)
        style = (source/"src/common/engine/renderstyle.h").read_text()
        self.assertIn("STYLEF_InvertSource = 16", style)
        self.assertIn("STYLEF_Alpha1 = 2", style)
        self.assertLess(style.index("uint8_t BlendOp"), style.index("uint8_t SrcAlpha"))
        self.assertLess(style.index("uint8_t SrcAlpha"), style.index("uint8_t DestAlpha"))
        self.assertLess(style.index("uint8_t DestAlpha"), style.index("uint8_t Flags"))
        self.assertEqual(struct.pack("<I", fixture.INVERSE_STYLE), bytes((1,2,3,18)))
        textmap = fixture.textmap()
        self.assertEqual(textmap.count("sector {"), 1)
        self.assertEqual(textmap.count("linedef {"), 4)
        self.assertEqual(textmap.count("thing {"), 1)
        self.assertIn("type = 1;", textmap)

    def test_missing_or_indistinguishable_input_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="pf110-input-") as folder:
            path = Path(folder)/"test.wad"
            path.write_bytes(b"not an iwad")
            with self.assertRaises(ValueError):
                fixture.iwad_identity(path)
            palette = bytes(768)
            image = bytearray(fixture.wad([("PLAYPAL", palette)]))
            image[:4] = b"IWAD"
            path.write_bytes(image)
            with self.assertRaisesRegex(ValueError, "cannot distinguish"):
                fixture.iwad_identity(path)

    def test_capture_rois_stay_in_reserved_overlay_and_modes_are_separate(self):
        self.assertEqual(len(fixture.roi_metadata()), 21)
        for roi in fixture.roi_metadata():
            x,y,w,h = roi["rect"]
            self.assertTrue(0 <= x < x+w <= 640)
            self.assertTrue(0 <= y < y+h <= 404)
            for px,py in roi["interiorSamples"]:
                self.assertTrue(x <= px < x+w and y <= py < y+h)
        for mode in (4,2,0):
            for filtering in (0,2):
                config = fixture.configuration(mode, filtering)
                self.assertIn(f"vid_rendermode={mode}", config)
                self.assertIn(f"gl_texture_filter={filtering}", config)

    def test_waits_retain_one_real_exec_command_continuation(self):
        script = fixture.capture_script(Path("C:/acceptance folder/presentation.png"))
        self.assertEqual(len(script.splitlines()), 1)
        self.assertEqual(script, 'wait 105; vid_setsize 640 480; wait 5; pf110_overlay true; '
                                'wait 35; screenshot "C:/acceptance folder/presentation.png"; wait 5; quit\n')
        dispatch = (fixture.ROOT/"src/common/console/c_dispatch.cpp").read_text()
        execute = dispatch[dispatch.index("void FExecList::ExecCommands()"):]
        self.assertIn("AddCommandString(Commands[i].GetChars());", execute)
        parse = dispatch[dispatch.index("void AddCommandString ("):dispatch.index("void AddCommandString (")+4000]
        self.assertIn("while (*brkpt != ';' && *brkpt != '\\0')", parse)
        self.assertIn("if (more)\n\t\t\t\t\t\t{ // The remainder of the command will be executed later", parse)
        self.assertIn("new FWaitingCommand(brkpt, tics, UnsafeExecutionContext)", parse)
        self.assertIn("src/common/console/c_dispatch.cpp", fixture.SOURCE_FILES)

    def test_render_acknowledgement_is_bounded_ui_only_and_mod_cvar_write_is_permitted(self):
        files = fixture.members()
        self.assertIn(b'nosave int pf110_overlay_frames = 0;', files["CVARINFO"])
        overlay = files["ZSCRIPT"].decode()
        callback = overlay[overlay.index("override void RenderOverlay(RenderEvent e)"):]
        increment = callback.index("frameCounter.SetInt(enabledFrames);")
        for guard in ("if (!CVar.GetCVar('pf110_overlay').GetBool()) return;",
                      "if (Screen.GetWidth() != 640 || Screen.GetHeight() != 480)", "if (a == -1 || b == -1)"):
            self.assertLess(callback.index(guard), increment)
        self.assertIn("if (enabledFrames < 2)", callback)
        self.assertIn("if (enabledFrames == 2)", callback)
        self.assertEqual(overlay.count("frameCounter.SetInt(enabledFrames);"), 1)
        self.assertEqual(overlay.count("PF110_OVERLAY_READY mode=%d filter=%d extent=640x480 frames=2"), 1)
        native = (fixture.ROOT/"src/common/scripting/interface/vmnatives.cpp").read_text()
        setter = native[native.index("DEFINE_ACTION_FUNCTION(_CVar, SetInt)"):native.index("DEFINE_ACTION_FUNCTION(_CVar, SetFloat)")]
        self.assertIn("if (!(self->GetFlags() & CVAR_MOD))", setter)
        self.assertLess(setter.index("if (!(self->GetFlags() & CVAR_MOD))"), setter.index("if (DMenu::InMenu == 0)"))
        self.assertIn("self->SetGenericRep(v, CVAR_Int);", setter)
        console = native[native.index("DEFINE_ACTION_FUNCTION(_Console, Printf)"):native.index("DEFINE_ACTION_FUNCTION(_Console, PrintfEx)")]
        self.assertIn('Printf("%s\\n", s.GetChars());', console)
        parser = (fixture.ROOT/"src/d_main.cpp").read_text()
        declaration = parser[parser.index("void ParseCVarInfo()"):parser.index("void ParseCVarInfo()")+6000]
        self.assertIn("int cvarflags = CVAR_MOD|CVAR_ARCHIVE;", declaration)
        self.assertIn('else if (stricmp(sc.String, "nosave") == 0)', declaration)
        self.assertIn("cvarflags |= CVAR_CONFIG_ONLY;", declaration)
        self.assertIn("cvarflags &= ~CVAR_SERVERINFO;", declaration)
        self.assertIn("cvarflags &= ~CVAR_USERINFO;", declaration)

    def test_five_tick_capture_has_a_real_pre_display_catchup_counterexample(self):
        source = fixture.ROOT
        constants = (source/"src/common/engine/i_net.h").read_text()
        backup = int(re.search(r"\bBACKUPTICS\s*=\s*(\d+)", constants)[1])
        batch = backup // 2 - 1
        self.assertEqual(batch, 17)
        net = (source/"src/d_net.cpp").read_text()
        self.assertIn("(maketic - gametic) / ticdup >= BACKUPTICS/2-1", net)
        self.assertIn("while (counts--)", net)
        game = (source/"src/g_game.cpp").read_text()
        self.assertIn("C_RunDelayedCommands();", game)
        main = (source/"src/d_main.cpp").read_text()
        loop = main[main.index("void D_DoomLoop ()"):]
        self.assertLess(loop.index("TryRunTics ();"), loop.index("D_Display ();"))

        def capture_state(after_raw, after_enabled):
            # Source-linked scheduling witness, not an engine/native test:
            # run the allowed17 ticks, then one D_Display callback batch.
            callbacks, enabled, captured = 0, False, None
            screenshot_at = after_raw + after_enabled
            for tick in range(screenshot_at + 1):
                if tick == after_raw:
                    enabled = True
                if tick == screenshot_at:
                    captured = callbacks
                if (tick + 1) % batch == 0 and enabled:
                    callbacks = min(callbacks + 1, 2)
            return captured

        self.assertEqual(capture_state(5, 5), 0)
        self.assertEqual(capture_state(35, 35), 2)
        self.assertEqual(capture_state(5, 35), 2)
        commands = fixture.capture_script(Path("presentation.png")).split("; ")
        enabled_at = commands.index("pf110_overlay true")
        self.assertEqual(commands[enabled_at+1], "wait 35")
        for name in ("src/common/engine/i_net.h", "src/d_net.cpp", "src/g_game.cpp", "src/events.cpp",
                     "src/g_statusbar/shared_sbar.cpp", "src/common/scripting/interface/vmnatives.cpp"):
            self.assertIn(name, fixture.SOURCE_FILES)


if __name__ == "__main__":
    unittest.main()
