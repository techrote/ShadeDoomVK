"""CPU fixtures distinguish an actual immediate guard from unguarded sampling."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import cfx_lightmap_spirv_audit as audit


def instruction(op, *args):
    return [(len(args) + 1) << 16 | op, *args]


def name(identifier, text):
    data = text.encode() + b'\0'
    data += b'\0' * (-len(data) % 4)
    return instruction(5, identifier, *struct.unpack('<' + 'I' * (len(data) // 4), data))


def module(guard=True, false_block=False, minus_one=0xffffffff):
    # A minimized binary shape, not a complete module accepted by spirv-val.
    words = [0x07230203, 0x10400, 0, 100, 0]
    words += name(10, 'vLightmapIndex') + name(11, 'textures') + name(20, 'ProcessLightMode')
    words += instruction(15, 4, 20, 0)
    words += instruction(21, 1, 32, 1) + instruction(43, 1, 2, minus_one)
    words += instruction(54, 1, 20, 0, 1) + instruction(248, 21)
    words += instruction(61, 1, 30, 10)
    if guard:
        words += instruction(171, 1, 31, 30, 2)
        words += instruction(247, 23, 0) + instruction(250, 31, 22, 23)
        words += instruction(248, 23 if false_block else 22)
    words += instruction(61, 1, 32, 10) + instruction(83, 1, 33, 32)
    words += instruction(65, 1, 34, 11, 33) + instruction(61, 1, 35, 34)
    words += instruction(87, 1, 36, 35, 37)
    words += instruction(56)
    return struct.pack('<' + 'I' * len(words), *words)


def cache_bytes(keys=('key',), code=None):
    def text(value):
        data = value.encode()
        return struct.pack('<I', len(data)) + data
    code = module() if code is None else code
    data = b'shadercache' + struct.pack('<II', 2, len(keys))
    for key in keys:
        data += text(key) + struct.pack('<QI', 123, len(code) // 4) + code + struct.pack('<I', 0)
    return data


class OrdinaryGuardFixture(unittest.TestCase):
    def test_true_branch_contains_descriptor_and_sample(self):
        report = audit.audit_module(module())
        self.assertEqual(len(report['ordinary_sample_guards']), 1)
        self.assertEqual(report['unmatched_direct_accesses'], [])
        site = report['ordinary_sample_guards'][0]
        self.assertEqual(site['function_name'], 'ProcessLightMode')
        self.assertEqual(site['true_block_id'], 22)
        self.assertLess(site['branch']['byte_offset'], site['descriptor_access']['byte_offset'])
        self.assertLess(site['descriptor_load']['byte_offset'], site['image_sample']['byte_offset'])

    def test_unguarded_sample_is_not_reported_as_guarded(self):
        report = audit.audit_module(module(guard=False))
        self.assertEqual(report['ordinary_sample_guards'], [])
        self.assertEqual(len(report['unmatched_direct_accesses']), 1)

    def test_false_branch_sample_is_not_guarded(self):
        report = audit.audit_module(module(false_block=True))
        self.assertEqual(report['ordinary_sample_guards'], [])
        self.assertEqual(len(report['unmatched_direct_accesses']), 1)

    def test_comparison_against_zero_is_not_minus_one_guard(self):
        report = audit.audit_module(module(minus_one=0))
        self.assertEqual(report['ordinary_sample_guards'], [])
        self.assertEqual(len(report['unmatched_direct_accesses']), 1)

    def test_truncated_instruction_rejected(self):
        with self.assertRaisesRegex(ValueError, 'truncated'):
            audit.parse_spirv(module() + struct.pack('<I', 4 << 16 | 61))

    def test_unterminated_function_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unterminated'):
            audit.parse_spirv(module()[:-4])

    def test_zero_length_instruction_rejected(self):
        with self.assertRaisesRegex(ValueError, 'zero-length'):
            audit.parse_spirv(module() + struct.pack('<I', 87))


class CacheAndTimelineFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / 'cache.zdsc'
        self.cache.write_bytes(cache_bytes())
        self.timeline = self.root / 'timeline.tsv'
        self.timeline.write_text('# CFX-002 trace v1 run=fixture\n' + '\t'.join(audit.TIMELINE_FIELDS)
                                 + '\n1\t2\t3\t4\t5\tworld\tshader-cache-hit\tkey\t0\n', encoding='utf-8')

    def test_actual_recorded_key_selects_exact_cached_bytes(self):
        report = audit.audit(self.cache, self.timeline, 'a' * 40)
        self.assertEqual(report['run_id'], 'fixture')
        self.assertEqual(report['summary']['recognized_ordinary_sample_guards'], 1)
        self.assertEqual(report['modules'][0]['cache_keys'], ['key'])
        self.assertIn('not executed shader', report['evidence_kind'])

    def test_duplicate_cache_key_rejected(self):
        self.cache.write_bytes(cache_bytes(('key', 'key')))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            audit.read_cache(self.cache)

    def test_trailing_and_truncated_cache_rejected(self):
        for data in (cache_bytes() + b'x', cache_bytes()[:-1]):
            self.cache.write_bytes(data)
            with self.assertRaises(ValueError):
                audit.read_cache(self.cache)

    def test_missing_recorded_module_rejected(self):
        self.cache.write_bytes(cache_bytes(('another',)))
        with self.assertRaisesRegex(ValueError, 'absent'):
            audit.audit(self.cache, self.timeline, 'a' * 40)

    def test_rotated_or_incomplete_timeline_rejected(self):
        original = self.timeline.read_text()
        for data in (original.replace('run=fixture', 'run=fixture (rotated tail)'), original.rstrip('\n')):
            self.timeline.write_text(data)
            with self.assertRaises(ValueError):
                audit.read_timeline(self.timeline)


if __name__ == '__main__':
    unittest.main()
