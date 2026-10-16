"""Exact fixture input-driver/production-builder CPU replay; no native rendering.

ZScript services are bounded C++ doubles, not a VM or Vulkan implementation.
Only override/access syntax, static-call separators, one Name literal and the
unused RenderEvent parameter are adapted. The generated control-flow bodies
and production Step/Full are executed, not rewritten as a Python expectation.
"""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import block, current
from tools.renderer_oracle import prepare
from tools.renderer_oracle.common import EvidenceError
from tools.renderer_oracle.sdvk150_probe_owner import validate_lifecycle_records, validate_driver_log

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DATA = ROOT / 'src/common/rendering/hwrenderer/data'
RETAINED = ROOT / 'tools/pf_oracle/tests/fixtures/sdvk014_lightmap_pre_fix.json'
FAILURE = HERE / 'fixtures/sdvk150-tic-wait-failure.json'
FIXTURE = HERE / 'sdvk150_transition_schedule_fixture.cpp'


def definition(text: str, signature: str) -> str:
    # Mask only the named definition, not unrelated earlier C++ digit separators
    # or raw strings. Require the exact boundary to be unique before slicing.
    if text.count(signature) != 1:
        raise AssertionError("Expected unique route definition: " + signature)
    return block(text[text.index(signature):], signature)


def scene():
    return next(row for row in prepare.load_catalog()['scenes'] if row['id']=='probe-owner-transition')


def build(directory: Path, original=False, mutation=None):
    directory.mkdir(parents=True, exist_ok=True)
    retained = json.loads(RETAINED.read_text())['functions']
    methods = '\n'.join(retained[key]['content'] if original else current(key)
                        for key in ('probe_step','probe_full'))
    (directory/'sdvk150_probe_methods.cpp').write_text(methods)
    script = prepare._probe_owner_transition_script(scene()['native']['probe_owner_transition']).decode()
    if mutation is not None:
        script = mutation(script)
    # Adapt only syntax/services; no condition, limit or action is replaced.
    script = script.replace('class SDVKProbeOwnerTransition : EventHandler\n{',
                            'class SDVKProbeOwnerTransition : public EventHandler\n{\npublic:')
    script = script.replace('override void', 'void').replace('RenderEvent e', '[[maybe_unused]] RenderEvent e')
    for scope in ('CVar','Console','EventHandler'):
        script = script.replace(scope+'.', scope+'::')
    script = script.replace("'sdvk150_owner_frames'", '"sdvk150_owner_frames"')
    (directory/'sdvk150_generated_driver.hpp').write_text(script.rstrip()+';\n')
    cpp = FIXTURE.read_text()
    if original:
        (directory/'hw_lightprobe.h').write_text(retained['probe_header']['content'])
        cpp = '#define SDVK150_RETAINED 1\n'+cpp
    local = directory/'schedule.cpp'
    local.write_text(cpp)
    return compile_fixture(local, output_dir=directory,
                           includes=[directory,DATA,ROOT/'src/common/utility',ROOT/'src/common/thirdparty'])


class TransitionScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='sdvk150-schedule-')
        cls.directory = Path(cls.temp.name)
        cls.candidate = build(cls.directory/'current')
        cls.original = build(cls.directory/'retained', original=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def execute(self, exe, mode, ticks, expected=0, reason='PASS'):
        result = subprocess.run([str(exe),mode,str(ticks)],text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
        self.assertIn(reason,result.stdout+result.stderr)
        return result.stdout

    def test_adaptive_tic_bursts_cannot_shorten_main_view_budget(self):
        for ticks in (1,2,8,20,35,100,4096):
            with self.subTest(ticks=ticks):
                output = self.execute(self.candidate,'frame-driver',ticks)
                self.assertIn('A_passes=5 B_passes=5',output)
                self.assertIn('queue_count=1 apply_count=1 queue_at=32 apply_at=32',output)

    def test_old_tic_wait_only_passes_when_one_tic_happens_per_view(self):
        self.execute(self.candidate,'old-tic-wait',1)
        output = self.execute(self.candidate,'old-tic-wait',20,11,'A-incomplete-before-transition')
        self.assertIn('A_passes=0 B_passes=5',output)

    def test_frame_driver_does_not_hide_original_same_count_owner_defect(self):
        output = self.execute(self.original,'frame-driver',35,11,'B-incomplete-after-transition')
        self.assertIn('A_passes=5 B_passes=0',output)

    def test_shortened_frame_budget_mutant_is_rejected_by_pass_oracle(self):
        mutant = build(self.directory/'too-early',mutation=lambda text:text.replace('32','2'))
        self.execute(mutant,'frame-driver',35,11,'A-incomplete-before-transition')

    def test_invalid_manual_wrong_player_and_duplicate_input_events(self):
        self.execute(self.candidate,'forged-events',1)

    def test_retained_native_failure_is_still_rejected(self):
        failure = json.loads(FAILURE.read_text())
        self.assertEqual(failure['raw_observation_sha256'],
                         '60a24c47373e4e18f12f45360e0b768e5db11c498eb8700243bdb589675af73f')
        events = failure['records'][0]['data']['events']
        self.assertEqual([row['map'] for row in events if row['event']=='owner-reset'],['SDV15A','SDV15B'])
        self.assertEqual([row['map'] for row in events if row['event']=='pass-published'],['SDV15B']*5)
        spec = scene()['native']['state_assertions']['probe_owner_transition']
        with self.assertRaisesRegex(EvidenceError,'exactly five completed passes'):
            validate_lifecycle_records(failure['records'],spec)

    def test_driver_route_is_after_main_view_not_ticks_faces_or_wipes(self):
        main = (ROOT/'src/d_main.cpp').read_text()
        display = definition(main,'void D_Display ()')
        self.assertLess(display.index('viewsec = RenderView('),display.index('StatusBar->DrawTopStuff'))
        self.assertIn('TryRunTics ();', definition(main,'void D_DoomLoop ()\n{'))
        self.assertEqual(display.count('RenderView('),1)
        self.assertNotIn('StatusBar',definition(main,'static void DrawOverlays()'))
        self.assertIn('DrawOverlays);',display)  # wipe callback cannot tick the input driver
        statusbar = (ROOT/'src/g_statusbar/shared_sbar.cpp').read_text()
        self.assertIn('localEventManager->RenderOverlay(state);',definition(statusbar,'void DBaseStatusBar::DrawTopStuff '))
        entries = (ROOT/'src/rendering/hwrenderer/hw_entrypoint.cpp').read_text()
        self.assertNotIn('RenderOverlay(',entries)  # probe-face callbacks never count as main frames
        driver = prepare._probe_owner_transition_script(scene()['native']['probe_owner_transition']).decode()
        self.assertIn('override void RenderOverlay(RenderEvent e)',driver)
        self.assertNotIn('WorldTick',driver)
        for forbidden in ('SdvkDiagnostics','probeSetRevision','GetProbeSetRevision','PassPublished','iterations','singletics'):
            self.assertNotIn(forbidden,driver)
        events = (ROOT/'wadsrc/static/zscript/events.zs').read_text()
        self.assertIn('virtual ui void RenderOverlay(RenderEvent e)',events)
        self.assertIn('virtual void NetworkProcess(ConsoleEvent e)',events)
        engine = (ROOT/'src/events.cpp').read_text()
        self.assertIn('Net_WriteInt8(DEM_NETEVENT)',definition(engine,'bool EventManager::SendNetworkEvent('))
        declarations = (ROOT/'wadsrc/static/zscript/doombase.zs').read_text()
        self.assertIn('native void ChangeLevel(string levelname, int position = 0, int flags = 0, int skill = -1);',declarations)

    def test_catalog_rejects_tic_driver_short_budget_and_unknown_driver(self):
        for mutation in (
            lambda t:t.update(wait_tics=20),
            lambda t:t.update(main_view_frames=2),
            lambda t:t.update(main_view_frames=True),
            lambda t:t.update(driver='tic-wait'),
        ):
            catalog=prepare.load_catalog()
            recipe=next(row for row in catalog['scenes'] if row['id']=='probe-owner-transition')
            mutation(recipe['native']['probe_owner_transition'])
            with self.assertRaisesRegex(ValueError,'two bounded distinct map owners'):
                prepare.validate_catalog(catalog)

    def test_driver_receipt_requires_exact_order_once_and_full_frame_budget(self):
        recipe=scene()['native']['probe_owner_transition']
        queue='SDVK150_TRANSITION_QUEUED map=SDV15A main_view_frames=32'
        apply='SDVK150_TRANSITION_APPLIED from=SDV15A to=SDV15B main_view_frames=32'
        valid=queue+'\n'+apply+'\n'
        validate_driver_log(valid,recipe)
        for changed in (queue,apply,apply+'\n'+queue,valid+apply,valid.replace('32','2'),
                        valid.replace('SDV15A','SDV15B')):
            with self.subTest(log=changed), self.assertRaisesRegex(EvidenceError,'input-driver queue/apply'):
                validate_driver_log(changed,recipe)


if __name__=='__main__':
    unittest.main()
