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

    def test_latched_startup_restore_uses_actual_generic_backup_and_preserves_queue(self):
        import tempfile
        cvars = (ROOT / 'src/common/console/c_cvars.cpp').read_text(encoding='utf-8')
        game = (ROOT / 'src/g_game.cpp').read_text(encoding='utf-8')
        def function(source, signature):
            return signature + '\n{' + source.split(signature + '\n{', 1)[1].split('\n}\n', 1)[0] + '\n}\n'
        harness = r"""
#include "g_classicinput.h"
#include <cassert>
#include <cstdint>
#include <string>
#include <vector>
enum { CVAR_SERVERINFO = 1<<2, CVAR_LATCH = 1<<4, CVAR_DEMOSAVE = 1<<6, CVAR_Int, CVAR_String };
struct UCVarValue { int Int = 0; const char* String = nullptr; };
struct FString {
    std::string text;
    FString& operator=(const char* s) { text = s; return *this; }
    const char* GetChars() const { return text.c_str(); }
};
struct FBaseCVar {
    const char* Name; uint32_t Flags; int Current; mutable std::string formatted;
    const char* GetName() const { return Name; }
    UCVarValue GetGenericRep(int) const { formatted = std::to_string(Current); UCVarValue v; v.String = formatted.c_str(); return v; }
    void ForceSet(UCVarValue v, int) { Current = v.Int; }
};
struct Ref { FBaseCVar* variable; FBaseCVar* operator->() { return variable; } };
struct FCVarBackup { FString Name, String; };
struct Backups : std::vector<FCVarBackup> {
    unsigned int Size() const { return static_cast<unsigned int>(size()); }
    void Clear() { clear(); }
    void Push(const FCVarBackup& v) { push_back(v); }
} CVarBackups;
struct CVarMap {
    struct Pair { FBaseCVar* Value; };
    std::vector<Pair> values;
    struct Iterator {
        CVarMap& map; size_t index = 0;
        explicit Iterator(CVarMap& m) : map(m) {}
        bool NextPair(Pair*& pair) { if(index == map.values.size()) return false; pair = &map.values[index++]; return true; }
    };
} cvarMap;
struct Latched { FBaseCVar* Variable; int Value; };
std::vector<Latched> LatchedValues;
void cvar_set(const char* name, const char* value) {
    for (auto& pair : cvarMap.values) if (std::string(pair.Value->Name) == name) pair.Value->Current = std::stoi(value);
}
ClassicInput::StartupValues classicInputStartupValues;
FBaseCVar skillVar{"skill", CVAR_SERVERINFO|CVAR_LATCH, 1, ""};
FBaseCVar deathmatchVar{"deathmatch", CVAR_SERVERINFO|CVAR_LATCH, 2, ""};
FBaseCVar dmflagsVar{"dmflags", CVAR_SERVERINFO, 7, ""};
Ref gameskill{&skillVar}, deathmatch{&deathmatchVar};
void C_ForgetCVars();
"""
        for sig in ('void C_BackupCVars (void)', 'void C_RestoreCVars (void)', 'void C_ForgetCVars (void)',
                    'bool C_HasPendingLatchedChange(const FBaseCVar* variable)'):
            harness += function(cvars, sig)
        harness += function(game, 'static void RestoreClassicInputStartupValues()')
        harness += r"""
void Reset() {
    skillVar.Current = 1; deathmatchVar.Current = 2; dmflagsVar.Current = 7;
    CVarBackups.clear(); LatchedValues.clear(); classicInputStartupValues = {};
    cvarMap.values = {{&skillVar},{&deathmatchVar},{&dmflagsVar}};
}
void ApplyInputHeader() { skillVar.Current = 3; deathmatchVar.Current = 0; dmflagsVar.Current = 0; }
int main() {
    // Exact existing generic backup omits both latched vars: original failure/native behavior.
    Reset(); C_BackupCVars(); assert(CVarBackups.size() == 1);
    ApplyInputHeader(); C_RestoreCVars(); RestoreClassicInputStartupValues();
    assert(skillVar.Current == 3 && deathmatchVar.Current == 0 && dmflagsVar.Current == 7);
    // Importer privately owns only the two latched startup values.
    Reset(); C_BackupCVars(); classicInputStartupValues.Capture(skillVar.Current, deathmatchVar.Current);
    ApplyInputHeader(); C_RestoreCVars();
    assert(skillVar.Current == 3 && deathmatchVar.Current == 0);
    RestoreClassicInputStartupValues();
    assert(skillVar.Current == 1 && deathmatchVar.Current == 2 && dmflagsVar.Current == 7);
    assert(!classicInputStartupValues.captured);
    // Already queued user intent is detected read-only, so preflight can reject without consuming it.
    Reset(); LatchedValues.push_back({&skillVar,4});
    assert(C_HasPendingLatchedChange(&skillVar));
    assert(!C_HasPendingLatchedChange(&deathmatchVar));
    assert(LatchedValues.size() == 1 && LatchedValues[0].Value == 4 && skillVar.Current == 1);
    // New user requests during import survive ForceSet restoration for the next normal new game.
    Reset(); C_BackupCVars(); classicInputStartupValues.Capture(skillVar.Current, deathmatchVar.Current);
    ApplyInputHeader(); LatchedValues = {{&skillVar,4},{&deathmatchVar,1}};
    C_RestoreCVars(); RestoreClassicInputStartupValues();
    assert(skillVar.Current == 1 && deathmatchVar.Current == 2 && LatchedValues.size() == 2);
    assert(LatchedValues[0].Value == 4 && LatchedValues[1].Value == 1);
    for (const auto& request : LatchedValues) { UCVarValue value; value.Int = request.Value; request.Variable->ForceSet(value,CVAR_Int); }
    LatchedValues.clear(); RestoreClassicInputStartupValues();
    assert(skillVar.Current == 4 && deathmatchVar.Current == 1);
}
"""
        with tempfile.TemporaryDirectory(prefix='classic-cvar-latch-control-') as directory:
            fixture = Path(directory) / 'latch.cpp'
            fixture.write_text(harness, encoding='utf-8')
            run_fixture(fixture, includes=('src',), root=ROOT)
        imported = game.split('if (importClassic)', 1)[1].split('\n\tC_BackupCVars ();', 1)[0]
        self.assertLess(imported.index('C_HasPendingLatchedChange'), imported.index('C_BackupCVars();'))
        self.assertLess(imported.index('classicInputStartupValues.Capture'), imported.index('ForceSet'))
        self.assertIn('RestoreClassicInputStartupValues();', imported.split('catch (...)',1)[1])

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
