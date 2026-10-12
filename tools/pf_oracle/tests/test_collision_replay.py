"""CPU-only exact-source replay plus independent graph/format negative controls.

All authored geometry in this file is explicitly synthetic. It does not model
or substitute for either unrecorded failed SDVSHDW runtime graph.
"""
import copy
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.collision_replay import (EvidenceError, HEADER_NAMES, STRIDES, Snapshot,
    _walk, compare_replayed, compile_replay, parse_snapshot, run_driver,
    validate_sequence, validate_snapshot)


def synthetic_seed(*, holes=(), event=1, phase=0, extent=128, triangles=6):
    """Synthetic original slots with deliberate holes; no map triangulation."""
    count = triangles * 3
    header = dict.fromkeys(HEADER_NAMES, 0)
    header.update(version=1, event=event, object_id=1, phase=phase,
                  vertex_stride=32, vertex_extent=count, index_extent=extent,
                  index_count=count, indexes_per_blas=((extent + 2) // 3 // 32 + 1) * 3,
                  slot_extent=32, tlas_root=-1, root=-1, section_count=11,
                  node_backing_extent=0 if phase == 0 else 10000)
    header["instance_count"] = (count + header["indexes_per_blas"] - 1) // header["indexes_per_blas"]
    sections = {tag: b"" for tag in STRIDES}
    vertices, indexes = bytearray(), []
    for triangle in range(triangles):
        base = triangle * 3
        if triangle in holes:
            indexes.extend((0, 0, 0))
            continue
        indexes.extend((base, base + 1, base + 2))
        # VERT disk order is original index, x, z, y.
        for i, point in enumerate(((triangle * 4., 0., 0.), (triangle * 4. + 1., 0., 0.), (triangle * 4., 1., 0.))):
            vertices += struct.pack("<Ifff", base + i, *point)
    sections[b"VERT"] = bytes(vertices)
    sections[b"INDX"] = struct.pack(f"<{count}I", *indexes)
    ranges = []
    for triangle in sorted(holes):
        start, end = triangle * 3, triangle * 3 + 3
        if ranges and ranges[-1][1] == start:
            ranges[-1] = (ranges[-1][0], end)
        else:
            ranges.append((start, end))
    sections[b"VFRE"] = b"".join(struct.pack("<ii", *r) for r in ranges)
    index_free = list(ranges)
    if count < extent:
        if index_free and index_free[-1][1] == count:
            index_free[-1] = (index_free[-1][0], extent)
        else:
            index_free.append((count, extent))
    sections[b"IFRE"] = b"".join(struct.pack("<ii", *r) for r in index_free)
    sections[b"VDIR"] = struct.pack("<ii", 0, count) if phase != 2 and count else b""
    sections[b"IDIR"] = struct.pack("<ii", 0, count) if phase != 2 and count else b""
    return Snapshot(header, sections)


def edit_word(snapshot, tag, word, value, fmt="I"):
    raw = bytearray(snapshot.sections[tag])
    struct.pack_into("<" + fmt, raw, word * 4, value)
    snapshot.sections[tag] = bytes(raw)


class CollisionReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="sdvk-collision-replay-tests-")
        cls.directory = Path(cls.temporary.name)
        cls.executable, cls.source_pins = compile_replay(cls.directory / "build")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def generate(self, seeds, name):
        directory = self.directory / name
        directory.mkdir(exist_ok=True)
        paths = []
        for number, seed in enumerate(seeds):
            path = directory / f"seed-{number}.bin"
            path.write_bytes(seed.encode())
            paths.append(path)
        return run_driver(self.executable, paths, directory / "generated")

    def test_production_constructor_sparse_and_unchanged_controls(self):
        for name, holes, live in (("no-hole", (), [0, 1, 2]),
                                  ("leading", (0, 1), [1, 2]),
                                  ("interior", (2, 3), [0, 2]),
                                  ("empty", tuple(range(6)), [])):
            with self.subTest(name=name):
                snapshots = self.generate([synthetic_seed(holes=holes)], name)
                summary = validate_sequence(snapshots)[0]
                self.assertEqual(summary["live_blas_slots"], live)
                self.assertEqual(summary["active_triangles"], 6 - len(holes))
                replayed = run_driver(self.executable, [snapshots[0].path], self.directory / (name + "-replay"))
                compare_replayed(snapshots[0], replayed[0])

    def test_single_leaf_and_zero_occupied_extent_controls(self):
        for count in (0, 1):
            snapshots = self.generate([synthetic_seed(triangles=count)], f"occupied-{count}")
            summary = validate_sequence(snapshots)[0]
            self.assertEqual(summary["active_triangles"], count)
            self.assertEqual(summary["live_blas_slots"], [0] if count else [])

    def test_production_dirty_and_unchanged_updates_retain_original_ids(self):
        snapshots = self.generate([synthetic_seed(),
            synthetic_seed(holes=(2, 3), event=2, phase=1),
            synthetic_seed(holes=(2, 3), event=3, phase=2),
            synthetic_seed(holes=tuple(range(6)), event=4, phase=1)], "lifecycle")
        summaries = validate_sequence(snapshots)
        self.assertEqual([row["active_triangles"] for row in summaries], [6, 4, 4, 0])
        self.assertEqual(summaries[1]["live_blas_slots"], [0, 2])
        self.assertEqual(snapshots[1].sections[b"NODE"], snapshots[2].sections[b"NODE"])
        self.assertEqual(snapshots[3].header["root"], -1)
        actual = run_driver(self.executable, [s.path for s in snapshots], self.directory / "lifecycle-replay")
        for first, second in zip(snapshots, actual):
            validate_snapshot(second)
            compare_replayed(first, second)

    def test_parser_rejects_truncation_duplicate_section_and_oversize(self):
        original = self.generate([synthetic_seed()], "parse")[0].encode()
        for name, raw in (("truncated", original[:-1]), ("oversize", original[:28] + struct.pack("<I", 1_000_001) + original[32:]),
                          ("duplicate", original[:72] + b"NODE" + original[76:])):
            with self.subTest(name=name):
                path = self.directory / f"bad-{name}.bin"
                path.write_bytes(raw)
                with self.assertRaises(EvidenceError):
                    parse_snapshot(path)

    def test_rejects_original_identity_bounds_cycles_and_bbox_corruption(self):
        original = self.generate([synthetic_seed()], "corrupt")[0]
        negatives = []
        snapshot = copy.deepcopy(original)
        edit_word(snapshot, b"SLOT", 10, 1)
        negatives.append(("slot identity", snapshot))
        snapshot = copy.deepcopy(original)
        edit_word(snapshot, b"VERT", 0, 999)
        negatives.append(("vertex bounds", snapshot))
        snapshot = copy.deepcopy(original)
        edit_word(snapshot, b"VERT", 1, float("nan"), "f")
        negatives.append(("nonfinite vertex", snapshot))
        snapshot = copy.deepcopy(original)
        snapshot.header["root"] = len(snapshot.sections[b"NODE"]) // 36
        negatives.append(("root bounds", snapshot))
        snapshot = copy.deepcopy(original)
        root = snapshot.header["root"]
        edit_word(snapshot, b"NODE", root * 9 + 6, root, "i")
        negatives.append(("cycle", snapshot))
        snapshot = copy.deepcopy(original)
        # Every CPU BLAS has at least one leaf; deliberately duplicate its global identity.
        rows = snapshot.rows(b"NODE", "<6f3i")
        leaves = [i for i, row in enumerate(rows) if row[-1] != -1]
        edit_word(snapshot, b"NODE", leaves[1] * 9 + 8, rows[leaves[0]][-1], "i")
        negatives.append(("triangle identity", snapshot))
        snapshot = copy.deepcopy(original)
        edit_word(snapshot, b"NODE", leaves[0] * 9, 9999., "f")
        negatives.append(("bbox", snapshot))
        for name, snapshot in negatives:
            with self.subTest(name=name), self.assertRaises(EvidenceError):
                validate_snapshot(snapshot)

    def test_free_holes_and_missing_publication_are_rejected(self):
        original = self.generate([synthetic_seed(holes=(2, 3))], "hole-corrupt")[0]
        hole = copy.deepcopy(original)
        edit_word(hole, b"INDX", 7, 99)
        with self.assertRaisesRegex(EvidenceError, "hole is not zero"):
            validate_snapshot(hole)
        publication = copy.deepcopy(original)
        publication.sections[b"NDIR"] = b""
        with self.assertRaisesRegex(EvidenceError, "publication"):
            validate_snapshot(publication)

    def test_missing_history_and_replay_mutation_fail(self):
        original = self.generate([synthetic_seed()], "history")[0]
        missing = copy.deepcopy(original)
        missing.header.update(event=1, phase=2)
        missing.sections[b"IDIR"] = b""
        with self.assertRaisesRegex(EvidenceError, "predecessor"):
            validate_sequence([missing])
        bad = copy.deepcopy(original)
        bad.header["indexes_per_blas"] += 3
        with self.assertRaisesRegex(EvidenceError, "replay"):
            compare_replayed(original, bad)

    def test_vertex_move_requires_both_cpu_rebuild_and_gpu_publication(self):
        moved = synthetic_seed(event=2, phase=1)
        edit_word(moved, b"VERT", 1, 0.25, "f")
        snapshots = self.generate([synthetic_seed(), moved], "vertex-move")
        validate_sequence(snapshots)
        missing_vertex = copy.deepcopy(snapshots[1])
        missing_vertex.sections[b"VDIR"] = b""
        with self.assertRaisesRegex(EvidenceError, "GPU vertex dirty"):
            validate_sequence([snapshots[0], missing_vertex])
        missing_rebuild = copy.deepcopy(snapshots[1])
        missing_rebuild.header["phase"] = 2
        missing_rebuild.sections[b"IDIR"] = b""
        with self.assertRaisesRegex(EvidenceError, "BLAS rebuild"):
            validate_sequence([snapshots[0], missing_rebuild])

    def test_vertex_zero_move_does_not_rebuild_degenerate_hole_partition(self):
        moved = synthetic_seed(holes=(2, 3), event=2, phase=1)
        edit_word(moved, b"VERT", 1, 0.25, "f")
        moved.sections[b"VDIR"] = struct.pack("<ii", 0, 1)
        moved.sections[b"IDIR"] = struct.pack("<ii", 0, 6)
        snapshots = self.generate([synthetic_seed(holes=(2, 3)), moved], "vertex-zero-with-holes")
        summaries = validate_sequence(snapshots)
        self.assertEqual(summaries[1]["live_blas_slots"], [0, 2])
        actual = run_driver(self.executable, [s.path for s in snapshots], self.directory / "vertex-zero-with-holes-replay")
        for expected, replayed in zip(snapshots, actual):
            compare_replayed(expected, replayed)

    def test_shader_stack_64_bound_has_deliberate_overflow_control(self):
        # Synthetic deep tree used solely to test the independent DFS checker.
        # Each internal left child continues; its right sibling remains pending.
        def tree(depth):
            result = []
            for i in range(depth):
                result.append((i + 1 if i + 1 < depth else depth, depth + 1 + i, -1))
            result.append((-1, -1, 1000))
            result.extend((-1, -1, i) for i in range(depth))
            return result
        bbox = lambda node: ((0., 0., 0.), (1., 1., 1.))
        leaves, peak = _walk(tree(63), 0, lambda value: value, bbox, stack_limit=64)
        self.assertEqual((len(leaves), peak), (64, 64))
        with self.assertRaisesRegex(EvidenceError, "64-entry"):
            _walk(tree(64), 0, lambda value: value, bbox, stack_limit=64)

    def test_direct_cli_replays_without_pythonpath(self):
        original = self.generate([synthetic_seed()], "cli-input")[0]
        directory = self.directory / "direct-cli" / "process-1"
        directory.mkdir(parents=True)
        (directory / "collision-1.bin").write_bytes(original.encode())
        report = self.directory / "direct-cli-report.json"
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        completed = subprocess.run([sys.executable, "-B", str(ROOT / "tools/collision_replay.py"),
            "--snapshot-root", str(directory.parent), "--classification", "synthetic", "--replay", "--output", str(report)],
            cwd=self.directory, env=environment, capture_output=True, text=True, timeout=120)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(report.read_text())
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["production_replay_executed"])
        self.assertFalse(result["actual_failed_runtime_equivalence"])
        bad = copy.deepcopy(original)
        bad.header["root"] = 999999
        (directory / "collision-1.bin").write_bytes(bad.encode())
        completed = subprocess.run([sys.executable, "-B", str(ROOT / "tools/collision_replay.py"),
            "--snapshot-root", str(directory.parent), "--classification", "synthetic", "--output", str(report)],
            cwd=self.directory, env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 1)
        result = json.loads(report.read_text())
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("out of bounds", result["error"])


if __name__ == "__main__":
    unittest.main()
