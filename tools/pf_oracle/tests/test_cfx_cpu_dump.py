"""Synthetic legal CPU/minidump fixtures: no WAD, shaders, Vulkan or GPU."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("cfx_cpu_dump", ROOT / "tools/cfx_cpu_dump.py")
cfx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfx)


def node(left=-1, right=-1, element=0, extent=1.0):
    return struct.pack("<8f4i", 0, 0, 0, 0, extent, 1, 1, 0, left, right, element, 0)


def geometry():
    return struct.pack("<3I", 0, 1, 2), bytes(3 * 32)


def make_dump(path, guid=cfx.PDB_GUID, age=cfx.PDB_AGE, split=False, hole=False):
    # One module and one logical memory region (optionally split at an adjacent boundary).
    base, start = 0x10000000, 0x10000000 + cfx.LEVEL_RVA
    memory = bytearray(0x1000)
    struct.pack_into("<Q", memory, 0x290, start + 0x300)
    mesh = 0x300 + 0x38
    for offset, pointer, count in ((0, 0x800, 3), (0x90, 0x900, 3), (0xb8, 0xa00, 2)):
        struct.pack_into("<QII", memory, mesh + offset, start + pointer, count, count)
    struct.pack_into("<i", memory, mesh + 0xb0, 3)
    struct.pack_into("<i", memory, mesh + 0xc8, 0)
    indexes, vertices = geometry()
    memory[0x800:0x860] = vertices
    memory[0x900:0x90c] = indexes
    memory[0xa00:0xa30] = node()
    struct.pack_into("<Q", memory, 0x300 + 0x7b0, start + 0xc00)
    struct.pack_into("<Q", memory, 0xc00, start + 0x300)
    struct.pack_into("<QQQ", memory, 0xc08, start + 0xe20, start + 0xe60, start + 0xe60)
    struct.pack_into("<QQQ", memory, 0xc28, start + 0xe00, start + 0xe08, start + 0xe08)
    struct.pack_into("<ii", memory, 0xc40, 3, 1)
    struct.pack_into("<Q", memory, 0xe00, start + 0xd00)
    struct.pack_into("<QQQ", memory, 0xd20, start + 0xe60, start + 0xea0, start + 0xea0)
    name = "C:\\test\\vkdoom.exe".encode("utf-16-le")
    cv = b"RSDS" + uuid.UUID(guid).bytes_le + struct.pack("<I", age) + b"vkdoom.pdb\0"
    module_rva, name_rva = 56, 168
    cv_rva = name_rva + 4 + len(name)
    mem_rva = cv_rva + len(cv)
    ranges = [(start, len(memory))]
    if split:
        # Split inside the levelMesh pointer read, exercising adjacent range reads.
        ranges = [(start, 0x294), (start + 0x294 + int(hole), len(memory) - 0x294)]
    data_rva = mem_rva + 16 + len(ranges) * 16
    header = struct.pack("<6IQ", 0x504d444d, 0xa793, 2, 32, 0, 0, 2)
    directory = struct.pack("<6I", 4, 112, module_rva, 9, 16 + 16 * len(ranges), mem_rva)
    module = bytearray(108)
    struct.pack_into("<Q", module, 0, base)
    struct.pack_into("<I", module, 20, name_rva)
    struct.pack_into("<II", module, 76, len(cv), cv_rva)
    payload = header + directory + struct.pack("<I", 1) + module
    payload += struct.pack("<I", len(name)) + name + cv
    payload += struct.pack("<QQ", len(ranges), data_rva)
    payload += b"".join(struct.pack("<QQ", *r) for r in ranges) + memory
    path.write_bytes(payload)


class TreeChecks(unittest.TestCase):
    def check(self, nodes, indexes=None, vertices=None, logical=3):
        defaults = geometry()
        return cfx.validate_tree(nodes, defaults[0] if indexes is None else indexes,
                                 defaults[1] if vertices is None else vertices, 0, logical)

    def test_valid_leaf_ignores_uninitialized_backing_tail(self):
        report = self.check(node() + bytes([255]) * 48,
                            geometry()[0] + struct.pack("<I", 999999))
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["reachable_nodes"], 1)
        self.assertEqual(report["peak_pending_stack"], 1)

    def test_cycle_and_missing_child_terminate(self):
        report = self.check(node(0, -1, -1))
        codes = {e["code"] for e in report["errors_first_32"]}
        self.assertIn("cycle-or-shared-child", codes)
        self.assertIn("node-index-bounds", codes)

    def test_shared_child(self):
        self.assertEqual(self.check(node(1, 1, -1) + node())["error_count"], 1)

    def test_leaf_must_fit_logical_extent_not_backing_array(self):
        report = self.check(node(element=3), geometry()[0] * 2)
        self.assertEqual(report["errors_first_32"][0]["code"], "leaf-index-range")

    def test_unaligned_and_negative_leaf(self):
        for element in (1, -2):
            self.assertGreater(self.check(node(element=element))["error_count"], 0)

    def test_all_logical_indices_checked(self):
        report = self.check(node(), geometry()[0] + struct.pack("<3I", 0, 999, 0), logical=6)
        self.assertEqual(report["errors_first_32"][0]["code"], "vertex-index-bounds")

    def test_nonfinite_and_negative_bounds(self):
        for extent in (float("nan"), float("inf"), -1):
            self.assertEqual(self.check(node(extent=extent))["errors_first_32"][0]["code"], "invalid-bbox")
        vertices = bytearray(geometry()[1])
        struct.pack_into("<f", vertices, 0, float("inf"))
        self.assertEqual(self.check(node(), vertices=vertices)["errors_first_32"][0]["code"], "nonfinite-position")

    def test_stack_boundary_uses_pending_count_not_tree_node_count(self):
        for pending_peak in (64, 65):
            depth = pending_peak - 1
            nodes = b"".join(node(i + 1, depth + 1 + i, -1) for i in range(depth))
            nodes += node() * (depth + 1)
            report = self.check(nodes)
            self.assertEqual(report["peak_pending_stack"], pending_peak)
            self.assertEqual(report["error_count"], int(pending_peak > 64))

    def test_live_extent_excludes_valid_looking_unuploaded_tail(self):
        indexes, vertices = geometry()
        report = cfx.validate_tree(node(1, 2, -1) + node() * 2, indexes, vertices, 0, 3, 2)
        self.assertEqual(report["errors_first_32"][0]["code"], "node-index-bounds")
        with self.assertRaises(cfx.EvidenceError):
            cfx.validate_tree(node(), indexes, vertices, 0, 3, 2)

    def test_bad_logical_count_and_stride(self):
        for logical in (-1, 1, 6):
            with self.assertRaises(cfx.EvidenceError):
                self.check(node(), logical=logical)
        with self.assertRaises(cfx.EvidenceError):
            self.check(node() + b"x")

    def test_error_output_bounded(self):
        report = self.check(node(), struct.pack("<300I", *([999] * 300)), logical=300)
        self.assertEqual(report["error_count"], 300)
        self.assertEqual(len(report["errors_first_32"]), 32)


class DumpChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "process.dmp"
        self.manifest = Path(self.temp.name) / "manifest.json"
        self.manifest.write_text(json.dumps({"schema": "cfx-002-run-v1", "run_id": "synthetic",
            "source": {"exe": {"sha256": cfx.EXE_SHA}, "pdb": {"sha256": cfx.PDB_SHA}}}), encoding="utf-8")

    def test_extract_and_validate_split_memory(self):
        make_dump(self.path, split=True)
        report = cfx.inspect(self.path, self.manifest)
        self.assertEqual(report["checks"]["error_count"], 0)
        self.assertEqual(report["root"], 0)
        self.assertEqual(report["arrays"]["nodes"]["stride"], 48)
        self.assertEqual(report["dump"]["sha256"], cfx.sha256_file(self.path))

    def test_empty_memory_descriptor_is_not_readable_memory(self):
        make_dump(self.path, split=True)
        data = bytearray(self.path.read_bytes())
        mem_rva, = struct.unpack_from("<I", data, 52)
        struct.pack_into("<Q", data, mem_rva + 24, 0)
        self.path.write_bytes(data)
        dump = cfx.Dump(self.path)
        self.addCleanup(dump.close)
        with self.assertRaises(cfx.EvidenceError):
            dump.memory(dump.base + cfx.LEVEL_RVA, 1)

    def test_guid_and_age_must_both_match(self):
        for kwargs in ({"age": 14}, {"guid": "00000000-0000-0000-0000-000000000000"}):
            make_dump(self.path, **kwargs)
            with self.assertRaises(cfx.EvidenceError):
                cfx.inspect(self.path, self.manifest)

    def test_manifest_identity_gate(self):
        make_dump(self.path)
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["source"]["exe"]["sha256"] = "wrong"
        self.manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(cfx.EvidenceError):
            cfx.inspect(self.path, self.manifest)

    def test_truncation_and_hole_fail_closed(self):
        make_dump(self.path)
        self.path.write_bytes(self.path.read_bytes()[:-1])
        with self.assertRaises(cfx.EvidenceError):
            cfx.Dump(self.path)
        make_dump(self.path, split=True, hole=True)
        with self.assertRaises(cfx.EvidenceError):
            cfx.inspect(self.path, self.manifest)

    def test_overlap_and_huge_range_fail_closed(self):
        for corrupt_size in (0xffffffffffffffff,):
            make_dump(self.path)
            data = bytearray(self.path.read_bytes())
            mem_rva, = struct.unpack_from("<I", data, 52)
            struct.pack_into("<Q", data, mem_rva + 24, corrupt_size)
            self.path.write_bytes(data)
            with self.assertRaises(cfx.EvidenceError):
                cfx.Dump(self.path)
        make_dump(self.path, split=True)
        data = bytearray(self.path.read_bytes())
        mem_rva, = struct.unpack_from("<I", data, 52)
        start, = struct.unpack_from("<Q", data, mem_rva + 16)
        struct.pack_into("<Q", data, mem_rva + 32, start)
        self.path.write_bytes(data)
        with self.assertRaises(cfx.EvidenceError):
            cfx.Dump(self.path)


if __name__ == "__main__":
    unittest.main()
