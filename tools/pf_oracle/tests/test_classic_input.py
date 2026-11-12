from pathlib import Path
import hashlib
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture


class ClassicInputTests(unittest.TestCase):
    def test_actual_cpp_decoder_boundaries_and_mapping(self):
        run_fixture('tools/pf_oracle/tests/classic_input_fixture.cpp', includes=('src',), root=ROOT)

    def test_native_form_parser_tic_reader_and_recorder_preserved(self):
        game = (ROOT / 'src/g_game.cpp').read_text(encoding='utf-8')
        parts = [
            game.split('bool G_ProcessIFFDemo (FString &mapname)', 1)[1].split('\nvoid G_DoPlayDemo', 1)[0],
            game.split('void G_ReadDemoTiccmd (ticcmd_t *cmd, int player)', 1)[1].split('\n\tint id = DEM_BAD;', 1)[1].split('\nbool stoprecording;', 1)[0],
            game.split('void G_WriteDemoTiccmd (ticcmd_t *cmd, int player, int buf)', 1)[1].split('\nvoid G_RecordDemo', 1)[0],
        ]
        # These exact native-protocol bodies are retained from accepted master90415699e.
        self.assertEqual([hashlib.sha256(part.encode()).hexdigest() for part in parts], ['9af2e0eb48335bbb47b0c0ff42c246574ea0009ffe610fc2fe4278a9197c34ed', '2d7fa86a52929e3de14b0f6c9ad621835cf075240d32a9cfb458a914ae7cadf3', '2759c20de3085f94f65076e0592f4fcb14d64f0de7b6e3fd1844fafd77e7ef1d'])

    def test_classic_to_native_timedemo_cleanup_precedes_new_flags(self):
        import tempfile
        game = (ROOT / 'src/g_game.cpp').read_text(encoding='utf-8')
        cleanup = game.split('void G_StopClassicInputPlayback()\n{', 1)[1].split('\n}\n', 1)[0]
        current = game.split('void G_TimeDemo (const char* name)\n{', 1)[1].split('\n}\n', 1)[0]
        # Exact pre-fix function body from 88a1eb351, retained as a failing control.
        legacy = '\n\tclassicInputRequested = false;\n\tnodrawers = !!Args->CheckParm ("-nodraw");\n\tnoblit = !!Args->CheckParm ("-noblit");\n\ttimingdemo = true;\n\tsingletics = true;\n\n\tdefdemoname = name;\n\tgameaction = (gameaction == ga_loadgame) ? ga_loadgameplaydemo : ga_playdemo;'
        self.assertEqual(hashlib.sha256(legacy.encode()).hexdigest(), 'e63337f8f63cc8f0bcc7bd1c5bbaae8af64bbadf80f01bacd9f9ae1dfc0dc439')
        harness = r"""
#include <cassert>
#include <stdexcept>
#include <string>
bool classicInputActive, demoplayback, timingdemo, singletics, nodrawers, noblit, classicInputRequested;
enum Action { ga_nothing, ga_loadgame, ga_loadgameplaydemo, ga_playdemo };
Action gameaction;
unsigned cleanups;
std::string defdemoname;
struct Arguments { bool CheckParm(const char*) { return false; } } arguments;
Arguments* Args = &arguments;
bool G_CheckDemoStatus() {
    ++cleanups;
    // The native cleanup's existing timedemo branch fatally reports a benchmark.
    if (timingdemo) throw std::runtime_error("timed old imported stream");
    classicInputActive = demoplayback = timingdemo = singletics = false;
    gameaction = ga_nothing;
    return false;
}
"""
        harness += 'void G_StopClassicInputPlayback() {\n' + cleanup + '\n}\n'
        harness += 'void LegacyTimeDemo(const char* name) {\n' + legacy + '\n}\n'
        harness += 'void G_TimeDemo(const char* name) {\n' + current + '\n}\n'
        harness += r"""
void Reset(bool active) {
    classicInputActive = demoplayback = active;
    timingdemo = singletics = nodrawers = noblit = false;
    classicInputRequested = true;
    gameaction = ga_nothing; cleanups = 0; defdemoname.clear();
}
int main() {
    Reset(true);
    LegacyTimeDemo("native.lmp");
    bool failed = false;
    try { G_StopClassicInputPlayback(); } catch (const std::runtime_error&) { failed = true; }
    assert(failed && cleanups == 1);
    Reset(true);
    G_TimeDemo("native.lmp");
    assert(cleanups == 1 && !classicInputActive && !demoplayback);
    assert(timingdemo && singletics && !classicInputRequested && defdemoname == "native.lmp");
    assert(gameaction == ga_playdemo);
    G_StopClassicInputPlayback();
    assert(cleanups == 1 && timingdemo && singletics);
    Reset(false);
    G_TimeDemo("normal.lmp");
    assert(cleanups == 0 && timingdemo && singletics && gameaction == ga_playdemo);
    Reset(true); gameaction = ga_loadgame;
    G_TimeDemo("with-save.lmp");
    assert(cleanups == 1 && timingdemo && singletics && gameaction == ga_loadgameplaydemo);
}
"""
        with tempfile.TemporaryDirectory(prefix='classic-timedemo-control-') as directory:
            fixture = Path(directory) / 'transition.cpp'
            fixture.write_text(harness, encoding='utf-8')
            run_fixture(fixture, root=ROOT)

    def test_explicit_interface_and_visible_warning(self):
        main = (ROOT / 'src/d_main.cpp').read_text(encoding='utf-8')
        self.assertIn('Args->CheckValue("-playclassicinput")', main)
        self.assertIn('G_DeferedPlayDemo (v, classicInputFile != nullptr);', main)
        game = (ROOT / 'src/g_game.cpp').read_text(encoding='utf-8')
        self.assertIn('UNSAFE_CCMD(playclassicinput)', game)
        start = game.split('if (importClassic)', 1)[1].split('C_BackupCVars();', 1)[0]
        self.assertIn('ClassicInput::Parse', start)
        self.assertIn('P_CheckMapData', start)
        self.assertIn('mo->FindInventory("Chainsaw")', game)
        self.assertIn('if (ClassicInput::OwnsInventory(mo, selected)) mo->UseInventory(selected);', game)
        hud = (ROOT / 'src/g_statusbar/shared_sbar.cpp').read_text(encoding='utf-8')
        self.assertIn('Classic Doom INPUT imported under CURRENT game rules', hud)
        self.assertIn('Original vanilla/Crispy/DSDA demo sync is NOT supported.', hud)

    def test_importer_does_not_override_physics_or_rng(self):
        game = (ROOT / 'src/g_game.cpp').read_text(encoding='utf-8')
        start = game.split('if (importClassic)', 1)[1].split('\n\tC_BackupCVars ();', 1)[0]
        for prohibited in ('rngseed =', 'compatflags =', 'compatmode =', 'singletics =', 'r_NoInterpolate =', 'StaticClearRandom'):
            self.assertNotIn(prohibited, start)
        self.assertIn('C_RestoreCVars();', start)
        self.assertIn('G_InitNew(mapname.GetChars(), false);', start)


if __name__ == '__main__':
    unittest.main()
