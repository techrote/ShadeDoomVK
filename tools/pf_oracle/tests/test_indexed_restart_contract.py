"""Source-linked #110 restart guards; never builds or executes a renderer/GPU.

These tests protect the native diagnostic's ordering, actual engine symbols,
script/argv boundaries and value-only checkpoint. Native acceptance still
requires the separate one-process raw/state/validation receipts.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
DIAGNOSTIC = ROOT / "src/common/rendering/vulkan/textures/vk_indexedmaterialdiagnostics.cpp"


def body(source, marker):
    match = re.search(re.escape(marker) + r"[^;{}]*\{", source)
    if match is None:
        raise AssertionError(f"Missing source definition: {marker}")
    start = match.end() - 1
    # Ignore C++ comments and quoted literals so JSON/script braces do not
    # affect extraction of the production-linked function/structure body.
    tokens = re.finditer(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]', source[start:])
    depth = 0
    for token in tokens:
        value = token.group()
        if value == "{":
            depth += 1
        elif value == "}":
            depth -= 1
            if depth == 0:
                return source[start:start + token.end()]
    raise AssertionError(f"Unclosed source body: {marker}")


def take_pair(values, flag):
    """Bounded Python projection of TakeValue, not native FArgs execution."""
    if flag not in values[1:]:
        return ""
    index = values.index(flag, 1)
    if index < len(values) - 1 and not values[index + 1].startswith(("+", "-")):
        value = values[index + 1]
        del values[index:index + 2]
        return value
    del values[index]
    return ""


def collect_option_block(values, flag):
    """CollectFiles steps 2/3 for these no-bare-prefix, single-file inputs."""
    values = list(values)
    if len(values) > 1 and not values[1].startswith(("+", "-")):
        raise AssertionError("The minimized source projection forbids bare prefixes")
    work = []
    index = 1
    while flag in values[index:]:
        index = values.index(flag, index)
        del values[index]
        while index < len(values) and not values[index].startswith(("+", "-")):
            work.append(values.pop(index))
    if work:
        values.extend([flag, *work])
    return values


def inherited_remove(values, flag):
    """Bounded Python projection of the actual RemoveArgs do/while loop."""
    values = list(values)
    if flag not in values[1:]:
        return values
    index = values.index(flag, 1)
    if index < len(values) - 1:
        while True:
            values.pop(index)
            if values[index].startswith(("+", "-")) or index >= len(values) - 1:
                break
    return values


def launch_orderings():
    options = ["-stdout", "-noautoload", "-noautoexec", "-nosound", "-nojoy"]
    packages = ["-iwad", "C:/pinned/doom2.wad", "-file", "C:/pinned/pf110.pk3"]
    retained = ["-config", "C:/out/fixture-live.ini", "-width", "640", "-height", "480"]
    commands = ["+map", "PF110", "+exec", "C:/out/before/execute.cfg"]
    return (["exe", *options, *packages, *retained, *commands],
            ["exe", *packages, *options, *retained, *commands])


def startup_arguments(values):
    # D_DoomInit's actual call order. For these inputs only -file has a match;
    # +exec is distinct from -exec. Startup consumes +map via TakeValue while
    # -config/-width/-height use nonmutating CheckValue.
    for flag in ("-deh", "-bex", "-exec", "-playdemo", "-file"):
        values = collect_option_block(values, flag)
    if take_pair(values, "+map") != "PF110":
        raise AssertionError("Expected the actual startup +map consumption")
    return values


class IndexedRestartContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = DIAGNOSTIC.read_text()

    def test_real_counter_and_genuine_cleanup_arena_order_are_source_linked(self):
        main = (ROOT / "src/d_main.cpp").read_text()
        self.assertRegex(main, r"(?m)^int restart = 0;")
        self.assertIn("extern int restart;", self.source)
        cleanup = body(main, "void D_Cleanup()")
        self.assertLess(cleanup.index("TexMan.DeleteAll();"), cleanup.index("restart++;"))
        self.assertIn("D_Cleanup();", body(main, "int D_DoomMain_Game()"))
        initialize = body(main, "int D_InitGame")
        self.assertLess(initialize.index("if (!restart)"), initialize.index("V_Init2();"))
        self.assertIn("InitPalette();", initialize)
        palette = (ROOT / "src/r_data/v_palette.cpp").read_text()
        self.assertIn("GPalette.Init(NUM_TRANSLATION_TABLES, nullptr);", palette)
        container = (ROOT / "src/common/engine/palettecontainer.cpp").read_text()
        self.assertIn("Clear();", body(container, "void PaletteContainer::Init"))
        self.assertIn("remapArena.FreeAllBlocks();", body(container, "void PaletteContainer::Clear"))

    def test_unconditional_original_cleanup_is_a_pre_live_counterexample(self):
        execute = body(self.source, "void Execute(bool retainForRestart = false)")
        final = execute[execute.rindex("for (auto asset : { source, sourceA, sourceB })"):]
        self.assertIn("if (!retainForRestart || asset != sourceB)", final)
        self.assertIn("FIndexedMaterialDiagnosticAccess::ResetIndexedAsset(asset);", final)
        self.assertIn("WaitForCommands(false);", final)
        original = final.replace("if (!retainForRestart || asset != sourceB) ", "")
        self.assertNotIn("retainForRestart", original)
        # The old unconditional cleanup retires all three owners before the
        # before command can attest any live token; it cannot prove restart.
        def survivors(retain, protected):
            owners = {"source", "sourceA", "sourceB"}
            for owner in tuple(owners):
                if not protected or not retain or owner != "sourceB":
                    owners.remove(owner)
            return owners
        self.assertEqual(survivors(True, False), set())
        self.assertEqual(survivors(False, True), set())
        self.assertEqual(survivors(True, True), {"sourceB"})
        self.assertIn("run.Execute();", body(self.source, "CCMD(pf_indexedmaterial_validate)"))

    def test_two_actual_blocks_are_copied_only_after_raii_return(self):
        execute = body(self.source, "void Execute(bool retainForRestart = false)")
        self.assertIn('Draw("b-first", sourceB, idB.index())', execute)
        self.assertIn('Draw("a-after-b", sourceB, idA.index())', execute)
        self.assertIn("pairedRestartTokens = { bb0.token, aa0.token };", execute)
        before = body(self.source, "CCMD(pf_indexedmaterial_restart_before)")
        self.assertLess(before.index("run.Execute(true);"), before.index("const auto tokens = run.pairedRestartTokens;"))
        self.assertLess(before.index("run.Execute(true);"), before.index("ValidateBindlessIdentity(tokens[i])"))
        self.assertIn("tokens[0].Span == 2 && tokens[1].Span == 2", before)
        self.assertIn("tokens[0].Index != tokens[1].Index", before)
        self.assertIn("run.Check(live[0] && live[1]", before)
        self.assertLess(before.index("run.Check(live[0] && live[1]"), before.index("RestartPhase::Armed"))

    def test_checkpoint_carries_no_old_resource_or_arena_pointer(self):
        checkpoint = body(self.source, "struct RestartCheckpoint")
        self.assertNotRegex(checkpoint, r"\*|\b(?:FRemapTable|FGameTexture|FTexture|VkMaterial|VkHardwareTexture|VkTextureImage|CaseIdentity)\b")
        self.assertIn("std::array<FRendererResourceIdentity, 2> tokens", checkpoint)
        self.assertIn("uint64_t managerIdentity", checkpoint)
        after = body(self.source, "CCMD(pf_indexedmaterial_restart_after)")
        self.assertNotRegex(after, r"TranslationToTable|\.remap\b|reinterpret_cast|\.image\b|\.paletteImage\b")

    def test_after_stale_guard_precedes_any_new_producer_or_reset(self):
        after = body(self.source, "CCMD(pf_indexedmaterial_restart_after)")
        stale = after.index("ValidateBindlessIdentity(RestartState.tokens[i])")
        producer = after.index("run.Execute();")
        self.assertLess(after.index("restart == RestartState.counter + 1"), stale)
        self.assertLess(after.index("Handle(fb->GetDescriptorSetManager()) == RestartState.managerIdentity"), stale)
        self.assertLess(after.index("Handle(fb->GetDevice()->device) == RestartState.deviceIdentity"), stale)
        self.assertLess(stale, after.index("Require(!live[0] && !live[1]"))
        self.assertLess(after.index("Require(!live[0] && !live[1]"), producer)
        self.assertNotIn("ResetIndexedAsset(", after[:producer])
        self.assertNotIn("ValidateTexture(", after[:producer])
        self.assertNotIn("GetLayer(", after[:producer])
        self.assertIn("lifetime.Resets == RestartState.lifetime.Resets", after)
        self.assertIn("lifetime.InvalidRetires == RestartState.lifetime.InvalidRetires", after)

    def test_one_shot_same_prefix_schema_and_failed_phase_are_protected(self):
        before = body(self.source, "CCMD(pf_indexedmaterial_restart_before)")
        after = body(self.source, "CCMD(pf_indexedmaterial_restart_after)")
        self.assertIn("RestartState.phase == RestartPhase::Empty", before)
        self.assertIn("RestartState.phase == RestartPhase::Armed", after)
        self.assertIn("RestartState.schemaVersion == RestartSchemaVersion", after)
        self.assertIn("prefix == RestartState.afterPrefix", after)
        self.assertLess(after.index("RestartState.phase = RestartPhase::Consumed"), after.index("RestartFramebuffer()"))
        self.assertIn("RestartState.phase = RestartPhase::Complete", after)
        self.assertIn("RestartState.phase = RestartPhase::Failed", before)
        self.assertIn("RestartState.phase = RestartPhase::Failed", after)

    def test_argv_arity_duplicates_and_actual_pair_removal_are_guarded(self):
        arguments = body(self.source, "RestartArguments ReadRestartArguments()")
        self.assertIn("Args->NumArgs() <= 32", arguments)
        self.assertIn("std::find(seen.begin(), seen.end(), flag) == seen.end()", arguments)
        self.assertIn("i + 1 < Args->NumArgs()", arguments)
        self.assertIn("value[0] != '+' && value[0] != '-'", arguments)
        self.assertIn('flag == "-iwad" || flag == "-file"', arguments)
        self.assertIn('"unknown or unpinned restart fixture option"', arguments)
        before = body(self.source, "CCMD(pf_indexedmaterial_restart_before)")
        removal = body(self.source, "void TakeRestartPairs")
        self.assertEqual(re.findall(r'values\.TakeValue\("([^"]+)"\)', removal), ["-iwad", "-file", "+exec", "+map"])
        for field in ("iwad", "mod", "exec", "map"):
            self.assertIn("== pinned." + field, removal)
        self.assertIn('values.CheckParm("-iwad") == 0 && values.CheckParm("-file") == 0', removal)
        self.assertIn("values.GetArg(i)[0] != '+'", removal)
        self.assertNotIn("Args->RemoveArgs(", before)
        self.assertIn("const FArgs original(*Args);", before)
        self.assertIn("FArgs remaining(original);", before)
        self.assertLess(before.index("TakeRestartPairs(remaining, arguments);"), before.index("run.Execute(true);"))
        self.assertLess(before.index("Require(nativePass, nativeError.c_str());"), before.index("RequireSameRestartArgv(original, *Args);"))
        self.assertLess(before.index("RequireSameRestartArgv(original, *Args);"), before.index("TakeRestartPairs(*Args, arguments);"))
        self.assertLess(before.index("TakeRestartPairs(*Args, arguments);"), before.index("RequireSameRestartArgv(remaining, *Args);"))
        compare = body(self.source, "void RequireSameRestartArgv")
        self.assertIn("actual.NumArgs() == expected.NumArgs()", compare)
        self.assertIn("std::strcmp(actual.GetArg(i), expected.GetArg(i)) == 0", compare)
        argv = (ROOT / "src/common/utility/m_argv.cpp").read_text()
        take = body(argv, "FString FArgs::TakeValue")
        self.assertIn("Argv[i+1][0] != '+' && Argv[i+1][0] != '-'", take)
        self.assertIn("Argv.Delete(i, 2);", take)
        self.assertIn("Argv.Delete(i);", take)
        self.assertIn("i < (int)Argv.Size() - 1", body(argv, "void FArgs::RemoveArgs"))

    def test_terminal_package_orphan_is_the_original_negative(self):
        terminal = ["exe", "-stdout", "-file", "pinned.pk3"]
        self.assertEqual(inherited_remove(terminal, "-file"), ["exe", "-stdout", "pinned.pk3"])
        desired = ["exe", "-stdout"]
        self.assertNotEqual(inherited_remove(terminal, "-file"), desired)
        interior = ["exe", "-file", "pinned.pk3", "-stdout"]
        self.assertEqual(inherited_remove(interior, "-file"), desired)
        # TakeValue removes the exact terminal pair, without requiring a
        # following flag or changing any otherwise retained option.
        guarded = list(terminal)
        self.assertEqual(take_pair(guarded, "-file"), "pinned.pk3")
        self.assertEqual(guarded, desired)

    def test_collectfiles_defeats_both_launch_orderings_before_inherited_restart(self):
        main = (ROOT / "src/d_main.cpp").read_text()
        initialize = body(main, "static void D_DoomInit()")
        calls = re.findall(r'Args->CollectFiles\("([^"]+)",\s*("[^"]+"|NULL)\);', initialize)
        self.assertEqual(calls, [("-deh", '".deh"'), ("-bex", '".bex"'), ("-exec", '".cfg"'), ("-playdemo", '".lmp"'), ("-file", "NULL")])
        argv = (ROOT / "src/common/utility/m_argv.cpp").read_text()
        collect = body(argv, "void FArgs::CollectFiles(const char *finalname, const char **param, const char *extension)")
        self.assertIn("while ((i = CheckParm(param, i)) > 0)", collect)
        self.assertIn("while (i < Argv.Size() && Argv[i][0] != '-' && Argv[i][0] != '+')", collect)
        self.assertIn("work.Push(Argv[i]);", collect)
        self.assertIn("Argv.Delete(i);", collect)
        self.assertLess(collect.index("Argv.Push(finalname);"), collect.index("AppendArgs(work.Size(), &work[0]);"))
        self.assertIn('FString mapvalue = Args->TakeValue("+map");', main)
        for path, flags in (("src/gameconfigfile.cpp", ("-config",)), ("src/common/rendering/v_video.cpp", ("-width", "-height"))):
            source = (ROOT / path).read_text()
            for flag in flags:
                self.assertRegex(source, r'Args->CheckValue\s*\("' + re.escape(flag) + r'"\)')
                self.assertNotRegex(source, r'Args->TakeValue\s*\("' + re.escape(flag) + r'"\)')
        restart_command = body(main, "UNSAFE_CCMD(debug_restart)")
        self.assertIn('Args->RemoveArgs("-iwad");', restart_command)
        self.assertIn('Args->RemoveArgs("-file");', restart_command)
        self.assertIn("Args->AppendArg(argv[i]);", restart_command)
        self.assertIn("wantToRestart = true;", restart_command)
        for launch in launch_orderings():
            with self.subTest(launch=launch):
                startup = startup_arguments(launch)
                self.assertEqual(startup[-2:], ["-file", "C:/pinned/pf110.pk3"])
                old_before = list(startup)
                self.assertEqual(take_pair(old_before, "+exec"), "C:/out/before/execute.cfg")
                self.assertEqual(take_pair(old_before, "+map"), "")
                old_restart = inherited_remove(inherited_remove(old_before, "-iwad"), "-file")
                self.assertEqual(old_restart[-1], "C:/pinned/pf110.pk3")
                self.assertNotIn("-file", old_restart)

    def test_guarded_takevalue_pairs_preserve_options_after_collectfiles(self):
        pairs = (("-iwad", "C:/pinned/doom2.wad"), ("-file", "C:/pinned/pf110.pk3"), ("+exec", "C:/out/before/execute.cfg"), ("+map", ""))
        for launch in launch_orderings():
            with self.subTest(launch=launch):
                original = startup_arguments(launch)
                preflight = list(original)
                for flag, expected in pairs:
                    self.assertEqual(take_pair(preflight, flag), expected)
                self.assertEqual(original[-2:], ["-file", "C:/pinned/pf110.pk3"])
                retained = ["exe", "-stdout", "-noautoload", "-noautoexec", "-nosound", "-nojoy", "-config", "C:/out/fixture-live.ini", "-width", "640", "-height", "480"]
                self.assertEqual(preflight, retained)
                committed = list(original)
                for flag, expected in pairs:
                    self.assertEqual(take_pair(committed, flag), expected)
                self.assertEqual(committed, preflight)
                # The real debug_restart removals now have no old package
                # flags to find. It can append precisely the pinned new pairs.
                dispatched = inherited_remove(inherited_remove(committed, "-iwad"), "-file")
                self.assertEqual(dispatched, retained)
                dispatched.extend(["-iwad", "C:/pinned/doom2.wad", "-file", "C:/pinned/pf110.pk3", "+exec", "C:/out/after/execute.cfg"])
                for flag in ("-iwad", "-file", "+exec"):
                    self.assertEqual(dispatched.count(flag), 1)
                self.assertNotIn("C:/out/before/execute.cfg", dispatched)
                self.assertNotIn("+map", dispatched)
                self.assertEqual(dispatched[:len(retained)], retained)

    def test_before_atomic_restart_has_no_old_exec_or_clear_queue_hazard(self):
        scripts = body(self.source, "void GuardRestartScripts")
        self.assertIn("before.back() == terminal", scripts)
        self.assertIn("before.size() >= 2", scripts)
        self.assertIn('"BEFORE contains an extra exec, restart or uncontrolled command"', scripts)
        before = body(self.source, "CCMD(pf_indexedmaterial_restart_before)")
        self.assertLess(before.index("RequireSameRestartArgv(remaining, *Args);"), before.index('WriteRestartReceipt(prefix, "before", true'))
        self.assertLess(before.index('WriteRestartReceipt(prefix, "before", true'), before.index("RestartState.phase = RestartPhase::Armed;"))
        self.assertLess(before.index("RestartPhase::Armed"), before.index("AddCommandString(command.c_str());"))
        self.assertIn('"debug_restart -iwad " + RestartQuoted(arguments.iwad)', before)
        self.assertIn('" -file " + RestartQuoted(arguments.mod)', before)
        self.assertIn('" +exec " + RestartQuoted(afterExec)', before)
        self.assertNotIn("C_ClearDelayedCommands(", before)
        self.assertNotIn("D_Cleanup(", before)
        self.assertNotIn("InitPalette(", before)
        self.assertIn('AddCommandString("quit");', before)
        dispatch = (ROOT / "src/common/console/c_dispatch.cpp").read_text()
        self.assertLess(dispatch.index("delayedCommands[i]->Tick()"), dispatch.index("delete delayedCommands[i];"))

    def test_after_explicit_map_and_real_extent_guard_do_not_assume_autostart(self):
        scripts = body(self.source, "void GuardRestartScripts")
        self.assertIn('after[1] == "map PF110" && RestartWait(after[2], 105)', scripts)
        self.assertIn('after[3] == "vid_setsize 640 480" && RestartWait(after[4], 35)', scripts)
        self.assertIn('after.back() == "quit"', scripts)
        framebuffer = body(self.source, "VulkanRenderDevice* RestartFramebuffer()")
        self.assertIn('std::strcmp(primaryLevel->MapName.GetChars(), "PF110") == 0', framebuffer)
        self.assertIn("screen->GetWidth() == 640 && screen->GetHeight() == 480", framebuffer)
        main = (ROOT / "src/d_main.cpp").read_text()
        self.assertIn("D_StartTitle ();", main)
        level = (ROOT / "src/g_level.cpp").read_text()
        self.assertIn("G_SetMap(mapname, mode);", body(level, "CCMD (map)"))
        self.assertIn("G_DeferedInitNew(mapname);", body(level, "void G_SetMap"))

    def test_both_native_prefixes_are_frozen_fresh_and_use_existing_parents(self):
        before = body(self.source, "CCMD(pf_indexedmaterial_restart_before)")
        self.assertIn("argv.argc() == 4", before)
        self.assertIn("prefix != afterPrefix", before)
        self.assertIn("FreshRestartPrefix(prefix);", before)
        self.assertIn("FreshRestartPrefix(afterPrefix);", before)
        self.assertLess(before.index("FreshRestartPrefix(afterPrefix);"), before.index("run.Execute(true);"))
        self.assertLess(before.index("FreshRestartPrefix(afterPrefix);"), before.index("TakeRestartPairs(*Args, arguments);"))
        fresh = body(self.source, "void FreshRestartPrefix")
        self.assertIn("DirExists(", fresh)
        for suffix in (".json", ".restart-before.json", ".restart-after.json"):
            self.assertIn('"' + suffix + '"', fresh)
        self.assertIn("RestartState.beforePrefix = prefix; RestartState.afterPrefix = afterPrefix;", before)
        self.assertIn("DiagnosticRun run{ fb, prefix,", before)
        self.assertIn("DiagnosticRun run{ fb, prefix,", body(self.source, "CCMD(pf_indexedmaterial_restart_after)"))

    def test_native_execution_receipt_is_written_once_without_masking_io_failure(self):
        for phase in ("before", "after"):
            command = body(self.source, f"CCMD(pf_indexedmaterial_restart_{phase})")
            self.assertEqual(command.count("WriteNativeRestartReceipt(run, nativePass, nativeError);"), 1)
            self.assertIn("catch (const std::exception& e) { nativeError = e.what(); }", command)
            self.assertLess(command.index("WriteNativeRestartReceipt(run, nativePass, nativeError);"), command.index("Require(nativePass, nativeError.c_str());"))
        receipt = body(self.source, "void WriteRestartReceipt")
        self.assertIn("device ? Handle(device->device) : 0", receipt)
        self.assertIn("descriptors ? descriptors->GetBindlessLifetimeStats()", receipt)


if __name__ == "__main__":
    unittest.main()
