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
        self.assertIn('if (selected) mo->UseInventory(selected);', game)
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
