"""Injected address callbacks only; never loads Vulkan or launches the renderer."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class AddressCallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.exe = cls.directory / ('fixture.exe' if os.name == 'nt' else 'fixture')
        compiler = os.environ.get('CFX_CXX') or shutil.which('cl' if os.name == 'nt' else 'c++')
        if not compiler:
            raise RuntimeError('Address fixture needs a VS developer shell or c++')
        source = str(ROOT / 'tools/pf_oracle/tests/cfx_address_fixture.cpp')
        include = str(ROOT / 'libraries/ZVulkan/include')
        if Path(compiler).name.lower() in ('cl', 'cl.exe'):
            cmd = [compiler, '/nologo', '/std:c++17', '/EHsc', '/W4', '/UNDEBUG',
                   *(['/fsanitize=address'] if os.environ.get('CFX_TEST_ASAN') == '1' else []),
                   source, '/I' + include, '/Fe:' + str(cls.exe), '/Fo:' + str(cls.directory / 'fixture.obj')]
        else:
            cmd = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread',
                   '-Wno-missing-field-initializers', '-UNDEBUG', source, '-I' + include, '-o', str(cls.exe)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def fixture(self, mode, active=True, resources=True):
        trace, bindings = self.directory / (mode + '.tsv'), self.directory / (mode + '-bindings.tsv')
        if mode == 'unavailable':
            bindings = self.directory / 'missing-parent' / 'bindings.tsv'
        env = os.environ.copy()
        for key in ('CFX_RUN_ID', 'CFX_TRACE_FILE', 'CFX_RESOURCE_TRACE', 'CFX_ADDRESS_TRACE', 'CFX_ADDRESS_FILE'):
            env.pop(key, None)
        env.update(CFX_RUN_ID='synthetic-address', CFX_TRACE_FILE=str(trace),
                   CFX_RESOURCE_TRACE='1' if resources else '0', CFX_ADDRESS_FILE=str(bindings),
                   CFX_ADDRESS_TRACE='1' if active else '0')
        subprocess.run([str(self.exe), mode], env=env, check=True, timeout=10)
        return trace.read_text(), bindings.read_text() if bindings.exists() else ''

    def test_binding_payload_and_names_survive_callback(self):
        trace, bindings = self.fixture('content')
        self.assertIn('run=synthetic-address', bindings)
        self.assertIn('\tbind\t0x1da00000\t4096\t1\t9\t0xab\t0\t1\ttemporary name ', bindings)
        self.assertIn('\tunbind\t', bindings)
        self.assertIn('persistent-name', bindings)
        self.assertNotIn('vulkan warning', trace)
        self.assertIn('records=4 omitted=0 contended=0 writer_ok=1', trace)
        self.assertTrue(all(len(row.split('\t')) == 15 for row in bindings.splitlines()[2:]))

    def test_caps_and_concurrent_callback_never_deadlock(self):
        trace, bindings = self.fixture('bounded')
        self.assertEqual(len(bindings.splitlines()[2:]), 16)
        self.assertIn('records=32768 omitted=36 contended=0 writer_ok=1', trace)
        self.assertIn('flushed=16 cutoff=0', trace)

    def test_concurrent_producers_preserve_every_copied_payload(self):
        trace, bindings = self.fixture('concurrent')
        rows = bindings.splitlines()[2:]
        self.assertEqual(len(rows), 8001)
        self.assertEqual([int(r.split('\t')[0]) for r in rows], list(range(1, 8002)))
        self.assertEqual(sum('temporary name ' in r for r in rows), 8000)
        self.assertIn('records=8001 omitted=0 contended=0 writer_ok=1 limit=32768 flushed=8001 cutoff=8001', trace)

    def test_unpublished_producer_does_not_block_callback_or_claim_flushed(self):
        trace, bindings = self.fixture('unpublished')
        self.assertIn('flushed=0 cutoff=3', trace)
        self.assertIn('flushed=4 cutoff=4', trace)
        self.assertEqual(len(bindings.splitlines()[2:]), 4)
        self.assertIn('owned-before-callback', bindings)
        self.assertNotIn('XXXXXXXXXXXXXXXXXXXXX', bindings)

    def test_malformed_chain_is_bounded_and_missing_object_is_explicit(self):
        trace, bindings = self.fixture('malformed')
        self.assertIn('binding-payload-missing', bindings)
        self.assertIn('binding-no-object', bindings)
        self.assertIn('omitted=1', trace)

    def test_disabled_callback_does_not_dereference_payload(self):
        self.assertEqual(self.fixture('disabled', active=False)[1], '')
        self.assertEqual(self.fixture('disabled', resources=False)[1], '')

    def test_unavailable_writer_disables_capture_and_preserves_cpu_summary(self):
        trace, bindings = self.fixture('unavailable')
        self.assertEqual(bindings, '')
        self.assertIn('records=0 omitted=0 contended=0 writer_ok=0', trace)

    def test_parent_environment_cannot_enable_off_or_plain_capture(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('capture', ROOT / 'tools/cfx_capture.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        base = {'CFX_ADDRESS_TRACE': '1', 'CFX_ADDRESS_FILE': 'untrusted-parent-path'}
        for mode in ('off', 'capture'):
            env = module.capture_environment(base, mode, 'id', Path('trace'), Path('fault'), True)
            self.assertNotIn('CFX_ADDRESS_FILE', env)
            self.assertNotIn('CFX_ADDRESS_TRACE', env)
        self.assertEqual(module.capture_environment(base, 'capture', 'id', Path('trace'), Path('fault'), True,
                                                   Path('address'))['CFX_ADDRESS_FILE'], 'address')


class AddressOverlapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location('address_correlate', ROOT / 'tools/cfx_address_correlate.py')
        cls.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.module)

    def files(self, directory, omissions=0):
        path = directory / 'bindings.tsv'
        rows = []
        for seq, event, base, size, obj in ((1, 'bind', 0x1DA00000, 4096, '0xab'),
                                          (2, 'bind', 0x1DA00000, 8192, '0xcd'),
                                          (3, 'unbind', 0x1DA00800, 2048, '0xab'),
                                          (4, 'snapshot', 0, 0, '0x0')):
            rows.append(f'{seq}\t1\t2\t7\t18\t11\t{event}\t{hex(base)}\t{size}\t0\t9\t{obj}\t0\t1\t' +
                        ('device-lost' if seq == 4 else 'mesh-name'))
        path.write_text('# CFX address bindings v1 run=fixture\n' + '\t'.join(self.module.FIELDS) + '\n' + '\n'.join(rows) + '\n')
        trace = directory / 'timeline.tsv'
        trace.write_text('# CFX-002 trace v1 run=fixture\nheader\n'
                         '1\t2\t7\t18\t11\tworld\tresource-create\tkind=buffer id=3 handle=0xab bytes=4096\t0\n'
                         f'2\t2\t7\t18\t11\tworld\taddress-binding-summary\treason=device-lost records=4 omitted={omissions} contended=0 writer_ok=1 limit=32768\t0\n')
        return path, trace

    def test_precision_alias_and_partial_unbind_preserve_all_history(self):
        with tempfile.TemporaryDirectory() as temp:
            bindings, trace = self.files(Path(temp))
            result = self.module.correlate(bindings, trace, 0x1DA00888, 4096)
            self.assertTrue(result['reported_binding_capture_complete_to_cutoff'])
            self.assertEqual(result['fault']['lower_inclusive'], '0x1da00000')
            self.assertEqual(result['fault']['upper_inclusive'], '0x1da00fff')
            self.assertEqual([r['event'] for r in result['overlapping_event_history']], ['bind', 'bind', 'unbind'])
            self.assertEqual(len(result['related_buffer_identity_history']['0xab']), 1)
            self.assertIn('No unique', result['interpretation'])

    def test_omission_and_missing_loss_cutoff_do_not_clear_address(self):
        with tempfile.TemporaryDirectory() as temp:
            bindings, trace = self.files(Path(temp), omissions=1)
            result = self.module.correlate(bindings, trace, 0xFFFF0000, 4096)
            self.assertFalse(result['reported_binding_capture_complete_to_cutoff'])
            self.assertEqual(result['overlapping_event_history'], [])
            bindings.write_text(bindings.read_text().replace('device-lost', 'safe-stop'))
            self.assertIn('no device-loss callback-stream cutoff', self.module.correlate(bindings, trace, 0, 1)['capture_gaps'])

    def test_invalid_precision_corruption_and_wrong_run_rejected(self):
        for precision in (0, 3, -1):
            with self.assertRaises(ValueError): self.module.fault_interval(1, precision)
        self.assertEqual(self.module.fault_interval((1 << 64) - 1, 1), ((1 << 64) - 1,) * 2)
        with tempfile.TemporaryDirectory() as temp:
            bindings, trace = self.files(Path(temp))
            trace.write_text(trace.read_text().replace('run=fixture', 'run=other'))
            with self.assertRaises(ValueError): self.module.correlate(bindings, trace, 0, 1)
            bindings.write_text(bindings.read_text().rstrip())
            with self.assertRaises(ValueError): self.module.read_bindings(bindings)

    def test_queued_loss_cutoff_requires_confirmed_flush(self):
        with tempfile.TemporaryDirectory() as temp:
            bindings, trace = self.files(Path(temp))
            original = trace.read_text()
            trace.write_text(original.replace('limit=32768', 'limit=32768 flushed=3 cutoff=4'))
            result = self.module.correlate(bindings, trace, 0x1DA00000, 4096)
            self.assertIn('queued binding records not flushed through loss cutoff', result['capture_gaps'])
            trace.write_text(original.replace('limit=32768', 'limit=32768 flushed=4 cutoff=4'))
            self.assertTrue(self.module.correlate(bindings, trace, 0x1DA00000, 4096)['reported_binding_capture_complete_to_cutoff'])
