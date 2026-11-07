"""SDVK-161 notification determinism controls; no renderer or device execution.

Run the actual notification admission, trimming and CVar callback against CPU
services. The ordinary renderer logging and default four-line policy stay intact.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block
from tools.renderer_oracle import prepare, sdvk161_special_surfaces as gate
from tools.renderer_oracle.common import EvidenceError
from tools.renderer_oracle.tests.test_sdvk161_special_surfaces import native_recipe


ADAPTER = r'''
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
struct FString {
    std::string Value;
    FString(const char* value) : Value(value) {}
    bool IsEmpty() const { return Value.empty(); }
};
struct FFont {};
struct DObject {};
struct StatusBarType : DObject {};
struct VMValue { template<class T> VMValue(T) {} };
struct VMReturn { explicit VMReturn(int*) {} };
template<class... Args> void VMCall(Args...) {}
#define IFVIRTUALPTR(object, klass, method) if (void* func = nullptr; func != nullptr)
#define countof(value) (sizeof(value) / sizeof((value)[0]))
enum { GS_LEVEL, GS_FULLCONSOLE, GS_DEMOSCREEN, PRINT_TYPES = 255 };
static bool show_messages = true, generic_ui = false;
static int gamestate = GS_LEVEL, con_notifylines = 4, DisplayWidth = 640, twod = 0;
static float con_notifytime = 3.0f;
static StatusBarType* StatusBar = nullptr;
static FFont Font;
static FFont *NewSmallFont = &Font, *AlternativeSmallFont = &Font;
static int active_con_scaletext(int, bool) { return 1; }
struct TextStorage {
    std::vector<int> Values;
    unsigned Size() const { return unsigned(Values.size()); }
    void Delete(unsigned first, unsigned count) { Values.erase(Values.begin() + first, Values.begin() + first + count); }
    void Push(int value) { Values.push_back(value); }
};
struct FNotifyBufferBase {
    TextStorage Text;
    unsigned InsertionCalls = 0;
    virtual ~FNotifyBufferBase() = default;
    virtual void AddString(int, FString) = 0;
    void Shift(int maxlines);
    // The formatting/insertion boundary is an explicit CPU service. The real
    // FNotifyBuffer admission function must never reach it at zero lines.
    void AddString(int, FFont*, const FString&, int, float, int) { ++InsertionCalls; Text.Push(1); }
};
struct FNotifyBuffer : FNotifyBufferBase { void AddString(int, FString) override; };
static FNotifyBuffer NotifyStrings;
@SHIFT@
@ADD_STRING@
void NotifyLinesChanged(int self) @CALLBACK@
void require(bool value, const char* reason) { if (!value) throw std::runtime_error(reason); }
int main() {
    try {
        // Ordinary defaults still admit a normal message with notifications on.
        NotifyStrings.AddString(1, FString("Lightmaps invalidated\n"));
        require(NotifyStrings.InsertionCalls == 1 && NotifyStrings.Text.Size() == 1, "default-four-lines-did-not-admit-message");
        NotifyStrings.Text.Push(2); NotifyStrings.Text.Push(3);
        con_notifylines = 0;
        NotifyLinesChanged(con_notifylines);
        require(NotifyStrings.Text.Size() == 0, "prior-notifications-not-cleared");
        for (int i = 0; i < 128; ++i) NotifyStrings.AddString(1, FString("Lightmaps invalidated\n"));
        require(NotifyStrings.InsertionCalls == 1 && NotifyStrings.Text.Size() == 0, "normal-message-reached-insertion-at-zero-lines");
        con_notifylines = 4;
        NotifyLinesChanged(con_notifylines);
        NotifyStrings.AddString(1, FString("ordinary logging remains enabled\n"));
        require(NotifyStrings.InsertionCalls == 2 && NotifyStrings.Text.Size() == 1, "restored-four-lines-did-not-admit-message");
        std::cout << "PASS ordinary-four-lines / clear-at-zero / repeated-messages-blocked\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 11; }
}
'''


class SpecialSurfaceNotificationTests(unittest.TestCase):
    def test_actual_admission_shift_and_callback_block_repeated_normal_messages_at_zero(self):
        source = (ROOT / "src/console/c_notifybuffer.cpp").read_text()
        self.assertIn("CUSTOM_CVAR(Int, con_notifylines, 4,", source)
        add = block(source, "void FNotifyBuffer::AddString(")
        shift = block((ROOT / "src/common/console/c_notifybufferbase.cpp").read_text(),
                      "void FNotifyBufferBase::Shift(")
        callback = block(source, "CUSTOM_CVAR(Int, con_notifylines,")
        callback = callback[callback.index("{"):]
        self.assertIn("NotifyStrings.Shift(self)", callback)
        variants = (
            ("current", add, shift, None),
            ("missing-zero-admission", add.replace("con_notifylines == 0", "false"), shift,
             "normal-message-reached-insertion-at-zero-lines"),
            ("missing-zero-clear", add, shift.replace("maxlines >= 0", "maxlines > 0"),
             "prior-notifications-not-cleared"),
        )
        with tempfile.TemporaryDirectory(prefix="sdvk161-notify-") as directory:
            for name, admission, trimming, reason in variants:
                with self.subTest(variant=name):
                    path = Path(directory) / (name + ".cpp")
                    path.write_text(ADAPTER.replace("@ADD_STRING@", admission)
                                    .replace("@SHIFT@", trimming).replace("@CALLBACK@", callback))
                    binary = compile_fixture(path, output_dir=directory)
                    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
                    if reason is None:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn("repeated-messages-blocked", result.stdout)
                    else:
                        self.assertEqual(result.returncode, 11, result.stdout + result.stderr)
                        self.assertIn(reason, result.stderr)

    def test_recipe_requires_exact_integer_zero_and_rejects_late_overrides(self):
        for value in (None, 1, 4, -1, False, True, 0.0, "0"):
            native = native_recipe()
            if value is None:
                native["settings"].pop("con_notifylines")
            else:
                native["settings"]["con_notifylines"] = value
            with self.subTest(value=value), self.assertRaisesRegex(EvidenceError, "typed con_notifylines=0"):
                gate.validate_recipe({"id": gate.SCENE, "native": native})
        for command in ("con_notifylines 4", "CON_NOTIFYLINES 4", "echo later; CoN_NoTiFyLiNeS 4",
                        "echo later\ncon_notifylines 4", "set con_notifylines 4", "toggle con_notifylines",
                        'set "con_notifylines" 4', "con_notifylines 0"):
            native = native_recipe()
            native["console_commands"].append(command)
            with self.subTest(command=command), self.assertRaisesRegex(EvidenceError, "may not override con_notifylines"):
                gate.validate_recipe({"id": gate.SCENE, "native": native})
        gate.validate_recipe({"id": gate.SCENE, "native": native_recipe()})
        unrelated = native_recipe()
        unrelated["console_commands"] += ["show_messages true", "crosshair 0"]
        gate.validate_recipe({"id": gate.SCENE, "native": unrelated})

    def test_catalog_pins_source_setting_sorted_query_and_actual_checkpoint_guard(self):
        catalog = prepare.load_catalog()
        prepare.validate_catalog(catalog)
        scene = next(row for row in catalog["scenes"] if row["id"] == gate.SCENE)
        self.assertEqual(catalog["cvar_sources"]["con_notifylines"], ["src/console/c_notifybuffer.cpp"])
        self.assertIs(type(scene["native"]["settings"]["con_notifylines"]), int)
        self.assertEqual(scene["native"]["settings"]["con_notifylines"], 0)
        self.assertEqual(scene["native"]["console_queries"], sorted(scene["native"]["settings"]))
        self.assertIn(b"con_notifylines=0\n", prepare.configuration(scene))
        script = prepare.capture_script(scene)
        self.assertIn(b"con_notifylines 0;", script)
        self.assertIn(b"; con_notifylines;", script)
        source = (ROOT / "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text()
        self.assertIn("EXTERN_CVAR(Int, con_notifylines)", source)
        presentation = block(source, "void FramePresented()")
        guard = presentation.index("Require(int(con_notifylines) == 0,")
        writer = presentation.index("M_ScreenShot(")
        self.assertLess(presentation.index("Require(bool(screenshot_quiet)"), guard)
        self.assertLess(guard, writer)
        self.assertEqual(presentation[presentation.index(");", guard) + 2:writer].strip(), "")


if __name__ == "__main__":
    unittest.main()
