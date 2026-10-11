#!/usr/bin/env python3
"""Validate opt-in collision snapshots and replay production collision code on CPU.

Snapshots are reconstructed runtime evidence or explicitly synthetic test inputs.
They cannot establish the unrecorded state of either failed physical experiment.
No renderer, Vulkan loader, device, or GPU is used by this tool.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MAGIC = b"SDVKCL01"
HEADER_NAMES = ("version event object_id phase vertex_stride vertex_extent index_extent "
                "index_count indexes_per_blas instance_count slot_extent tlas_count "
                "tlas_root node_backing_extent root section_count").split()
STRIDES = {b"VERT": 16, b"INDX": 4, b"VFRE": 8, b"IFRE": 8,
           b"VDIR": 8, b"IDIR": 8, b"NDIR": 8, b"TLAS": 60,
           b"SLOT": 20, b"BLAS": 60, b"NODE": 36}
MAX_BYTES = 128 * 1024 * 1024
MAX_ELEMENTS = 1_000_000
MAX_STACK = 64
MAX_SEQUENCE_BYTES = 256 * 1024 * 1024
MAX_EVENTS = 4096


class EvidenceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


@dataclass
class Snapshot:
    header: dict
    sections: dict
    sha256: str = ""
    path: str = ""

    def rows(self, tag, fmt):
        return list(struct.iter_unpack(fmt, self.sections[tag]))

    def encode(self):
        result = MAGIC + struct.pack("<16I", *(self.header[key] & 0xffffffff for key in HEADER_NAMES))
        for tag, stride in STRIDES.items():
            raw = self.sections[tag]
            result += tag + struct.pack("<II", len(raw) // stride, stride) + raw
        return result


def parse_snapshot(path):
    path = Path(path)
    require(path.stat().st_size <= MAX_BYTES, "snapshot exceeds bounded file size")
    raw = path.read_bytes()
    require(len(raw) >= 72 and raw[:8] == MAGIC, "invalid collision snapshot magic/header")
    h = dict(zip(HEADER_NAMES, struct.unpack_from("<16I", raw, 8)))
    for key in ("tlas_root", "root"):
        if h[key] >= 0x80000000:
            h[key] -= 0x100000000
    require(h["version"] == 1 and h["vertex_stride"] == 32, "unsupported collision layout")
    require(h["phase"] in (0, 1, 2) and h["event"] > 0 and h["object_id"] > 0, "invalid event identity/phase")
    require(h["section_count"] == len(STRIDES), "section count mismatch")
    for key in ("vertex_extent", "index_extent", "index_count", "slot_extent", "tlas_count", "node_backing_extent"):
        require(h[key] <= MAX_ELEMENTS, f"{key} exceeds bounded element count")
    sections = {}
    offset = 72
    for _ in range(h["section_count"]):
        require(offset + 12 <= len(raw), "truncated section header")
        tag, count, stride = struct.unpack_from("<4sII", raw, offset)
        offset += 12
        require(tag in STRIDES and tag not in sections, "unknown or duplicate section")
        require(stride == STRIDES[tag] and count <= MAX_ELEMENTS, "invalid section stride/count")
        size = count * stride
        require(offset + size <= len(raw), "truncated section payload")
        sections[tag] = raw[offset:offset + size]
        offset += size
    require(offset == len(raw) and set(sections) == set(STRIDES), "trailing bytes or missing sections")
    return Snapshot(h, sections, hashlib.sha256(raw).hexdigest(), str(path.resolve()))


def _ranges(snapshot, tag, extent):
    rows = snapshot.rows(tag, "<ii")
    previous = -1
    for start, end in rows:
        require(0 <= start < end <= extent and start > previous, f"{tag.decode()} invalid/overlapping range")
        previous = end - 1
    return rows


def _contains_range(ranges, index):
    return any(start <= index < end for start, end in ranges)


def _close(a, b):
    return abs(a - b) <= max(1e-4, max(abs(a), abs(b)) * 2e-6)


def _bbox_record(record):
    require(all(math.isfinite(v) for v in record[:12]), "non-finite tree bounds")
    lo, hi, center, extents = record[:3], record[3:6], record[6:9], record[9:12]
    require(all(a <= b for a, b in zip(lo, hi)) and all(v >= 0 for v in extents), "inverted tree bounds")
    require(all(_close(c, a * 0.5 + b * 0.5) and _close(e, b * 0.5 - a * 0.5)
                for a, b, c, e in zip(lo, hi, center, extents)), "inconsistent tree bbox fields")
    return lo, hi


def _walk(nodes, root, leaf_identity, bbox, *, all_nodes=False, stack_limit=None):
    if root == -1:
        require(not nodes or not all_nodes, "empty root with live tree nodes")
        return [], 0
    pending = [(root, None)]
    seen, leaves = set(), []
    peak = 1
    while pending:
        index, parent = pending.pop()
        require(0 <= index < len(nodes), "tree child/root out of bounds")
        require(index not in seen, "tree cycle or aliased child")
        seen.add(index)
        node = nodes[index]
        lo, hi = bbox(node)
        if parent is not None:
            plo, phi = parent
            require(all(a >= pa or _close(a, pa) for a, pa in zip(lo, plo)) and
                    all(b <= pb or _close(b, pb) for b, pb in zip(hi, phi)), "child bbox escapes parent")
        left, right, identity = node[-3:]
        if identity != -1:
            require(left == right == -1, "leaf has child references")
            leaves.append((leaf_identity(identity), lo, hi))
        else:
            require(left >= 0 and right >= 0, "internal node has invalid child")
            # Exact software shader order: push right, then left.
            pending.extend(((right, (lo, hi)), (left, (lo, hi))))
            peak = max(peak, len(pending))
            if stack_limit is not None:
                require(peak <= stack_limit, "software traversal exceeds 64-entry stack")
    if all_nodes:
        require(len(seen) == len(nodes), "unreachable CPU tree nodes")
    return leaves, peak


def validate_snapshot(snapshot):
    h = snapshot.header
    require(0 <= h["index_count"] <= h["index_extent"] and h["index_count"] % 3 == 0, "invalid occupied index extent")
    require(h["indexes_per_blas"] > 0 and h["indexes_per_blas"] % 3 == 0, "invalid BLAS partition")
    require(h["instance_count"] == (h["index_count"] + h["indexes_per_blas"] - 1) // h["indexes_per_blas"], "instance count differs from occupied extent")
    require(h["instance_count"] <= h["slot_extent"] and h["slot_extent"] == 32, "invalid original BLAS slot extent")
    indexes = [row[0] for row in snapshot.rows(b"INDX", "<I")]
    require(len(indexes) == h["index_count"], "INDX count mismatch")
    vertices = {}
    for index, x, z, y in snapshot.rows(b"VERT", "<Ifff"):
        require(index < h["vertex_extent"] and index not in vertices, "invalid/duplicate original vertex identity")
        require(all(math.isfinite(v) for v in (x, z, y)), "non-finite referenced vertex")
        vertices[index] = (x, z, y)
    vfree = _ranges(snapshot, b"VFRE", h["vertex_extent"])
    ifree = _ranges(snapshot, b"IFRE", h["index_extent"])
    _ranges(snapshot, b"VDIR", h["vertex_extent"])
    idir = _ranges(snapshot, b"IDIR", h["index_extent"])
    ndir = _ranges(snapshot, b"NDIR", h["node_backing_extent"])
    require(h["phase"] != 1 or idir, "dirty update lacks index dirty range")
    require(h["phase"] != 2 or not idir, "unchanged update has index dirty range")
    for start, end in ifree:
        require(all(v == 0 for v in indexes[start:min(end, len(indexes))]), "freed occupied index hole is not zero")
    triangles, references = {}, set()
    for offset in range(0, len(indexes), 3):
        a, b, c = indexes[offset:offset + 3]
        if a == b:  # Exact production degeneracy policy; c is not consumed.
            continue
        require(not any(_contains_range(ifree, i) for i in range(offset, offset + 3)), "active triangle occupies free range")
        require(all(i in vertices and not _contains_range(vfree, i) for i in (a, b, c)), "triangle references missing/free vertex")
        triangles[offset] = tuple(vertices[i] for i in (a, b, c))
        references.update((a, b, c))
    require(set(vertices) == references, "VERT does not exactly describe consumed original identities")
    tlas = snapshot.rows(b"TLAS", "<12f3i")
    blas = snapshot.rows(b"BLAS", "<12f3i")
    slots = snapshot.rows(b"SLOT", "<IiIII")
    require(len(tlas) == h["tlas_count"] and len(slots) == h["slot_extent"], "tree/slot count mismatch")
    cursor, live_slots = 0, []
    for expected_slot, (slot, root, start, count, index_start) in enumerate(slots):
        require(slot == expected_slot and start == cursor and start + count <= len(blas), "compressed or overlapping BLAS slot identity")
        require(index_start == slot * h["indexes_per_blas"], "BLAS original triangle offset mismatch")
        require((root == -1) == (count == 0), "BLAS root/membership mismatch")
        local = blas[start:start + count]
        leaves, _ = _walk(local, root, lambda value: index_start + value, _bbox_record, all_nodes=True)
        if count and slot < h["instance_count"]:
            live_slots.append(slot)
            expected = {offset for offset in triangles if index_start <= offset < index_start + h["indexes_per_blas"]}
            require({value for value, _, _ in leaves} == expected and len(leaves) == len(expected), "BLAS triangle membership mismatch")
            for value, lo, hi in leaves:
                require(value % 3 == 0 and value in triangles, "BLAS leaf original triangle out of bounds")
                for x, z, y in triangles[value]:
                    require(all(a >= low or _close(a, low) for a, low in zip((x, y, z), lo)) and
                            all(a <= high or _close(a, high) for a, high in zip((x, y, z), hi)), "BLAS bbox does not contain triangle")
        cursor += count
    require(cursor == len(blas), "unowned BLAS node records")
    tlas_leaves, _ = _walk(tlas, h["tlas_root"], lambda value: value, _bbox_record, all_nodes=True)
    require(sorted(value for value, _, _ in tlas_leaves) == live_slots, "TLAS live original slot membership mismatch")
    for slot, lo, hi in tlas_leaves:
        _, root, start, count, _ = slots[slot]
        blo, bhi = _bbox_record(blas[start + root])
        require(all(a >= low or _close(a, low) for a, low in zip(blo, lo)) and
                all(a <= high or _close(a, high) for a, high in zip(bhi, hi)), "TLAS bbox does not contain BLAS")
    nodes = snapshot.rows(b"NODE", "<6f3i")
    require(len(nodes) == max(1, len(tlas) + len(blas)) and len(nodes) <= h["node_backing_extent"], "export node count/backing mismatch")

    def exported_bbox(node):
        require(all(math.isfinite(v) for v in node[:6]) and all(v >= 0 for v in node[3:6]), "invalid exported bbox")
        return tuple(c - e for c, e in zip(node[:3], node[3:6])), tuple(c + e for c, e in zip(node[:3], node[3:6]))

    leaves, peak = _walk(nodes, h["root"], lambda value: value, exported_bbox, stack_limit=MAX_STACK)
    require({value for value, _, _ in leaves} == set(triangles) and len(leaves) == len(triangles), "export original triangle membership mismatch")
    for value, lo, hi in leaves:
        require(value in triangles and value % 3 == 0, "export triangle index out of bounds")
        for point in triangles[value]:
            require(all(a >= low or _close(a, low) for a, low in zip(point, lo)) and
                    all(a <= high or _close(a, high) for a, high in zip(point, hi)), "export bbox does not contain triangle")
    if not triangles:
        require(h["root"] == -1 and nodes[0] == (0., 0., 0., 0., 0., 0., -1, -1, -1), "empty export sentinel/storage mismatch")
    require(h["phase"] == 2 or any(start == 0 and end >= len(nodes) for start, end in ndir), "changed graph lacks complete node/header publication range")
    return {"event": h["event"], "object_id": h["object_id"], "phase": h["phase"],
            "active_triangles": len(triangles), "live_blas_slots": live_slots,
            "vertex_backing_extent": h["vertex_extent"], "index_backing_extent": h["index_extent"],
            "occupied_index_extent": h["index_count"], "exported_semantic_nodes": len(nodes),
            "shader_stack_peak_all_bounds_overlap": peak,
            "publication_storage_beyond_semantic_export": sum(max(0, end - max(start, len(nodes))) for start, end in ndir)}


def validate_sequence(snapshots):
    require(len(snapshots) <= MAX_EVENTS, "event sequence exceeds bounded event count")
    require(sum(sum(len(raw) for raw in s.sections.values()) for s in snapshots) <= MAX_SEQUENCE_BYTES,
            "event sequence exceeds bounded captured bytes")
    summaries, objects, last_event = [], {}, 0
    for snapshot in snapshots:
        h = snapshot.header
        require(h["event"] == last_event + 1, "missing/reordered collision event; complete history required")
        if h["phase"] == 0:
            require(h["object_id"] not in objects, "duplicate constructor identity")
        else:
            require(h["object_id"] in objects, "update lacks constructor/predecessor state")
            previous = objects[h["object_id"]]
            before = previous.rows(b"INDX", "<I")
            after = snapshot.rows(b"INDX", "<I")
            dirty = snapshot.rows(b"IDIR", "<ii")
            require(len(after) >= len(before), "occupied extent shrank without a new collision constructor")
            for i, value in enumerate(after):
                if i >= len(before) or before[i] != value:
                    require(_contains_range(dirty, i), "changed index lacks GPU/collision dirty publication")
            old_vertices = {row[0]: row[1:] for row in previous.rows(b"VERT", "<I3I")}
            changed = {row[0] for row in snapshot.rows(b"VERT", "<I3I") if old_vertices.get(row[0]) != row[1:]}
            if changed:
                vertex_dirty = snapshot.rows(b"VDIR", "<ii")
                require(all(_contains_range(vertex_dirty, index) for index in changed),
                        "changed referenced vertex lacks GPU vertex dirty publication")
                partition = h["indexes_per_blas"]
                for offset in range(0, len(after), 3):
                    if after[offset][0] == after[offset + 1][0]:
                        continue  # Production does not read vertices of a skipped hole.
                    if any(after[i][0] in changed for i in range(offset, offset + 3)):
                        start = (offset // partition) * partition
                        require(any(a < start + partition and b > start for a, b in dirty), "changed referenced vertex lacks BLAS rebuild dirty range")
        summaries.append(validate_snapshot(snapshot))
        objects[h["object_id"]] = snapshot
        require(sum(s.header["vertex_extent"] * 32 + s.header["index_extent"] * 4 +
                    s.header["node_backing_extent"] * 48 for s in objects.values()) <= MAX_SEQUENCE_BYTES,
                "replay object backing exceeds bounded memory")
        last_event = h["event"]
    require(snapshots, "no snapshots supplied")
    return summaries


def _function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    for end in range(opening + 1, len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return source[start:end + 1]
    raise EvidenceError("unterminated production function")


def compile_replay(output_dir, *, source_root=ROOT, compiler=None):
    from tools.pf_oracle.fixture_runner import compile_fixture
    output_dir, source_root = Path(output_dir), Path(source_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    support = ROOT / "tools/pf_oracle/tests/fixtures"
    collision = source_root / "src/common/rendering/hwrenderer/data"
    pin_paths = (collision / "hw_collision.cpp", collision / "hw_collision.h", collision / "hw_levelmesh.cpp",
                 collision / "flatvertices.h", collision / "hw_levelmesh_contract.h", collision / "hw_resourcegeneration.h",
                 source_root / "src/common/utility/vectors.h", source_root / "src/common/thirdparty/xs_Float.h",
                 source_root / "src/common/thirdparty/math/cmath.h", support / "collision_replay_driver.cpp",
                 support / "collision_replay_mesh.h")
    captured = {path: path.read_bytes() for path in pin_paths}
    for name in ("hw_collision.cpp", "hw_collision.h"):
        (output_dir / name).write_bytes(captured[collision / name])
    for name in ("collision_replay_driver.cpp", "collision_replay_mesh.h"):
        (output_dir / name).write_bytes(captured[support / name])
    (output_dir / "hw_levelmesh.h").write_text('#include "collision_replay_mesh.h"\n')
    (output_dir / "v_video.h").write_text("#pragma once\nstruct ReplayScreen { bool IsRayQueryEnabled() const { return false; } };\ninline ReplayScreen replayScreen; inline ReplayScreen* screen = &replayScreen;\n")
    (output_dir / "printf.h").write_text("#pragma once\n#include <cstdio>\n#define Printf std::printf\nstruct cycle_t { void ResetAndClock() {} void Unclock() {} double TimeMS() const { return 0; } };\ninline cycle_t DynamicBLASTime;\n")
    mesh_source = captured[collision / "hw_levelmesh.cpp"].decode().replace("\r\n", "\n")
    (output_dir / "collision_replay_ranges.inc").write_text("\n".join(_function(mesh_source, f"void MeshBufferUploads::{name}(") for name in ("Clear", "Add")))
    includes = [output_dir, source_root / "src", source_root / "src/common/utility",
                source_root / "src/common/thirdparty", collision]
    exe = compile_fixture(output_dir / "collision_replay_driver.cpp", output_dir=output_dir,
                          includes=includes, root=source_root, name="collision-replay-cpu", compiler=compiler)
    pins = []
    for path in pin_paths:
        require(path.read_bytes() == captured[path], "production replay input changed during compilation")
        pins.append({"path": str(path), "sha256": hashlib.sha256(captured[path]).hexdigest()})
    source = captured[collision / "hw_collision.cpp"].decode().replace("\r\n", "\n")
    for signature in ("CPUAccelStruct::CPUAccelStruct(", "void CPUAccelStruct::Update()",
                      "void CPUAccelStruct::Upload()", "void CPUAccelStruct::CreateTLAS()",
                      "int CPUAccelStruct::Subdivide(", "CPUBottomLevelAccelStruct::CPUBottomLevelAccelStruct(",
                      "int CPUBottomLevelAccelStruct::Subdivide(", "int CPUBottomLevelAccelStruct::SubdivideLeaf("):
        offset, occurrence = 0, 0
        while (start := source.find(signature, offset)) != -1:
            occurrence += 1
            function = _function(source[start:], signature)
            pins.append({"path": str(collision / "hw_collision.cpp"), "function": signature,
                         "occurrence": occurrence, "normalization": "UTF-8 read_text universal newlines",
                         "sha256": hashlib.sha256(function.encode()).hexdigest()})
            offset = start + len(function)
    return exe, pins


def run_driver(executable, paths, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [str(executable), str(output_dir), *(str(Path(p).resolve()) for p in paths)]
    result = subprocess.run(command, check=False, timeout=90, capture_output=True, text=True)
    (output_dir / "execution.json").write_text(json.dumps({"argv": command, "returncode": result.returncode,
                                                         "stdout": result.stdout, "stderr": result.stderr}, indent=2) + "\n")
    result.check_returncode()
    return [parse_snapshot(output_dir / f"replayed-{i}.bin") for i in range(len(paths))]


def compare_replayed(expected, actual):
    for key in ("indexes_per_blas", "instance_count", "slot_extent", "tlas_count", "tlas_root", "root"):
        require(expected.header[key] == actual.header[key], f"production replay {key} mismatch")
    for tag in (b"SLOT", b"NDIR"):
        require(expected.sections[tag] == actual.sections[tag], f"production replay {tag.decode()} identity/range mismatch")
    for tag, fmt, floats in ((b"TLAS", "<12f3i", 12), (b"BLAS", "<12f3i", 12), (b"NODE", "<6f3i", 6)):
        want, got = expected.rows(tag, fmt), actual.rows(tag, fmt)
        require(len(want) == len(got), f"production replay {tag.decode()} node count mismatch")
        for first, second in zip(want, got):
            require(first[floats:] == second[floats:] and all(_close(a, b) for a, b in zip(first[:floats], second[:floats])),
                    f"production replay {tag.decode()} semantic node mismatch")


def qualify(paths, *, evidence_class, output_dir=None, source_root=ROOT, compiler=None):
    require(evidence_class in ("synthetic", "reconstructed-hosted-production"), "exact failed physical runtime claim is unsupported")
    snapshots = [parse_snapshot(path) for path in paths]
    summaries = validate_sequence(snapshots)
    with tempfile.TemporaryDirectory(prefix="sdvk-collision-replay-") as temporary:
        directory = Path(output_dir) if output_dir else Path(temporary)
        executable, pins = compile_replay(directory / "build", source_root=source_root, compiler=compiler)
        actual = run_driver(executable, paths, directory / "replayed")
        for expected, got in zip(snapshots, actual):
            validate_snapshot(got)
            compare_replayed(expected, got)
        return {"schema": "sdvk-collision-cpu-replay/v1", "status": "PASS", "evidence_class": evidence_class,
                "actual_failed_runtime_equivalence": False, "gpu_execution_or_submission_proved": False,
                "physical_stop_lifted": False, "snapshots": [{"path": s.path, "sha256": s.sha256} for s in snapshots],
                "events": summaries, "production_source_pins": pins,
                "limits": ["Unused backing tail and live-node padding were not captured or compared.",
                           "CPU adapters replace mesh containers, screen capability and timing; map/allocator creation is not replayed.",
                           "Whole collision source and actual production vector/layout/range headers are compiled.",
                           "No retained failed runtime graph exists; reconstructed hosted state cannot establish physical causality."]}


def _review(options, result):
    require(bool(options.snapshots) != bool(options.snapshot_root), "supply explicit snapshots or one snapshot root")
    paths = list(options.snapshot_root.rglob("collision-*.bin")) if options.snapshot_root else options.snapshots
    require(paths, "no collision snapshots found")
    require(len(paths) <= MAX_EVENTS, "snapshot root exceeds bounded event count")
    require(sum(path.stat().st_size for path in paths) <= MAX_SEQUENCE_BYTES, "snapshot root exceeds bounded bytes")
    groups = {}
    for path in paths:
        groups.setdefault(path.parent.resolve(), []).append(path)
    for group in groups.values():
        group.sort(key=lambda path: parse_snapshot(path).header["event"])
    with tempfile.TemporaryDirectory(prefix="sdvk-collision-review-") as temporary:
        directory = options.retain or Path(temporary)
        executable, pins = compile_replay(directory / "build", source_root=options.source_root) if options.replay else (None, [])
        result["production_source_pins"] = pins
        for number, (process, group) in enumerate(sorted(groups.items())):
            snapshots = [parse_snapshot(path) for path in group]
            record = {"path": str(process), "snapshots": [{"path": s.path, "sha256": s.sha256} for s in snapshots]}
            result["processes"].append(record)
            summaries = validate_sequence(snapshots)
            record["events"] = summaries
            if executable:
                result["production_replay_executed"] = True
                replayed = run_driver(executable, group, directory / f"process-{number}")
                for expected, actual in zip(snapshots, replayed):
                    validate_snapshot(actual)
                    compare_replayed(expected, actual)
    result["limits"] = ["Unused backing tail and live-node padding are explicitly UNKNOWN and are not compared.",
                       "CPU mesh-container/screen/timing adapters do not replay map creation or allocator events.",
                       "Complete per-process constructor/Update event sequences replay whole production collision source.",
                       "64-entry shader-stack proof assumes every AABB overlaps; no GLSL execution is implied.",
                       "Software-hosted reconstruction cannot recover failed physical state or establish causality."]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshots", nargs="*", type=Path)
    parser.add_argument("--snapshot-root", type=Path)
    parser.add_argument("--classification", "--evidence-class", dest="evidence_class", required=True,
                        choices=("synthetic", "reconstructed-hosted-production"))
    parser.add_argument("--replay", action="store_true", help="Compile and execute whole production collision source on CPU")
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--retain", type=Path)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args(argv)
    result = {"schema": "sdvk-collision-cpu-review/v1", "status": "PASS", "classification": options.evidence_class,
              "actual_failed_runtime_equivalence": False, "physical_stop_lifted": False,
              "gpu_execution_or_submission_proved": False, "production_replay_requested": options.replay,
              "production_replay_executed": False, "source_root": str(options.source_root.resolve()), "processes": []}
    try:
        _review(options, result)
        result["production_replay_executed"] = options.replay
    except (EvidenceError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        result.update(status="FAIL", error_type=type(error).__name__, error=str(error))
    text = json.dumps(result, indent=2) + "\n"
    if options.output:
        options.output.write_text(text)
    print(text, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
