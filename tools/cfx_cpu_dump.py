#!/usr/bin/env python3
"""Read-only CFX-004 CPU collision snapshot check for one pinned Windows build.

No engine/Vulkan initialization. Not a GPU-memory validator or a general debugger.
See docs/shadedoomvk/CFX-004-OFFLINE-DISPOSITION.md for the evidence boundary.
"""
import argparse
import bisect
import hashlib
import json
import math
from pathlib import Path
import struct
import uuid

EXE_SHA = "15bf5c71d955308fb331e320a8b872b4ee573d16cb1ea5b3cfbd8e069d08b7fd"
PDB_SHA = "b9b0b4c141318eed46ff73a5af60babd6155965ce9c0fbc422deb5da9f8b6394"
PDB_GUID = "43bfc543-3656-4d78-ac05-9b180ce4da2a"
PDB_AGE = 28
LEVEL_RVA = 0xc052b0
MAX_ARRAY_BYTES = 96 * 1024 * 1024  # parser bound, never a renderer limit
MAX_RECORDS = 2_000_000


class EvidenceError(ValueError):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class Dump:
    """Only ModuleList and Memory64List; reject missing/truncated/ambiguous data."""
    def __init__(self, path):
        self.file = Path(path).open("rb")
        try:
            self.size = Path(path).stat().st_size
            header = self.at(0, 32)
            signature, version, count, directory = struct.unpack_from("<4I", header)
            if signature != 0x504d444d or version & 0xffff != 0xa793 or count > 4096:
                raise EvidenceError("unsupported minidump header")
            streams = {}
            for kind, size, rva in struct.iter_unpack("<III", self.at(directory, count * 12)):
                if kind not in (4, 9):
                    continue
                if kind in streams:
                    raise EvidenceError("duplicate required stream")
                streams[kind] = (rva, size)
            if set(streams) != {4, 9}:
                raise EvidenceError("ModuleList and full Memory64List required")
            rva, size = streams[9]
            if size < 16:
                raise EvidenceError("short Memory64List")
            count, data = struct.unpack("<QQ", self.at(rva, 16))
            if count > MAX_RECORDS or size != 16 + 16 * count:
                raise EvidenceError("invalid Memory64List size")
            ranges = []
            for address, length in struct.iter_unpack("<QQ", self.at(rva + 16, count * 16)):
                if address + length > 2**64 or data + length > self.size:
                    raise EvidenceError("invalid/truncated memory range")
                if length:  # DbgHelp can include empty descriptors; they provide no bytes.
                    ranges.append((address, address + length, data))
                data += length
            self.ranges = sorted(ranges)
            if any(a[1] > b[0] for a, b in zip(self.ranges, self.ranges[1:])):
                raise EvidenceError("overlapping virtual memory ranges")
            self.starts = [r[0] for r in self.ranges]
            rva, size = streams[4]
            if size < 4:
                raise EvidenceError("short ModuleList")
            count, = struct.unpack("<I", self.at(rva, 4))
            if count > 4096 or size != 4 + count * 108:
                raise EvidenceError("invalid ModuleList size")
            matches = []
            for i in range(count):
                module = self.at(rva + 4 + i * 108, 108)
                base, = struct.unpack_from("<Q", module)
                name_rva, = struct.unpack_from("<I", module, 20)
                name_len, = struct.unpack("<I", self.at(name_rva, 4))
                if name_len > 65536 or name_len % 2:
                    raise EvidenceError("invalid module name")
                name = self.at(name_rva + 4, name_len).decode("utf-16-le")
                if name.replace("\\", "/").rsplit("/", 1)[-1].lower() != "vkdoom.exe":
                    continue
                cv_size, cv_rva = struct.unpack_from("<II", module, 76)
                if cv_size < 24 or cv_size > 65536:
                    raise EvidenceError("invalid CodeView record")
                cv = self.at(cv_rva, cv_size)
                if cv[:4] != b"RSDS":
                    raise EvidenceError("RSDS required")
                guid = str(uuid.UUID(bytes_le=cv[4:20]))
                age, = struct.unpack_from("<I", cv, 20)
                if (guid, age) != (PDB_GUID, PDB_AGE):
                    raise EvidenceError("dump does not match pinned PDB GUID/age")
                matches.append(base)
            if len(matches) != 1:
                raise EvidenceError("one pinned vkdoom.exe module required")
            self.base = matches[0]
        except Exception:
            self.file.close()
            raise

    def close(self):
        self.file.close()

    def at(self, offset, size):
        if offset < 0 or size < 0 or offset + size > self.size or size > MAX_ARRAY_BYTES:
            raise EvidenceError("file range outside dump/parser bound")
        self.file.seek(offset)
        data = self.file.read(size)
        if len(data) != size:
            raise EvidenceError("short read")
        return data

    def memory(self, address, size):
        if size < 0 or size > MAX_ARRAY_BYTES or address + size > 2**64:
            raise EvidenceError("virtual read outside parser bound")
        chunks = []
        while size:
            i = bisect.bisect_right(self.starts, address) - 1
            if i < 0 or address >= self.ranges[i][1]:
                raise EvidenceError("required memory absent from dump")
            start, end, offset = self.ranges[i]
            length = min(size, end - address)
            chunks.append(self.at(offset + address - start, length))
            address += length
            size -= length
        return b"".join(chunks)


def validate_tree(nodes, indexes, vertices, root, index_count, live_node_count=None):
    """Worst-case overlap traversal, right then left as GLSL pushes; no ray culling.

    Nodes backing tail is intentionally not visited. IndexCount is the logical
    initialized index extent, not the larger Indexes TArray backing allocation.
    Errors are bounded; corrupt cycles cannot make the checker loop forever.
    """
    if len(nodes) % 48 or len(indexes) % 4 or len(vertices) % 32:
        raise EvidenceError("array byte size does not match pinned stride")
    nc, ic, vc = len(nodes) // 48, len(indexes) // 4, len(vertices) // 32
    if not (0 <= index_count <= ic) or index_count % 3:
        raise EvidenceError("invalid logical IndexCount")
    if live_node_count is not None:
        if not 0 <= live_node_count <= nc:
            raise EvidenceError("live node extent exceeds backing array")
        nc = live_node_count
    errors, error_count = [], 0
    def fail(code, value):
        nonlocal error_count
        error_count += 1
        if len(errors) < 32:
            errors.append({"code": code, "value": value})
    # Check every logical index, even ones not referenced by a reachable leaf.
    referenced = set()
    for i in range(index_count):
        vertex, = struct.unpack_from("<I", indexes, i * 4)
        if vertex >= vc:
            fail("vertex-index-bounds", i)
        else:
            referenced.add(vertex)
    for vertex in sorted(referenced):
        if not all(math.isfinite(x) for x in struct.unpack_from("<3f", vertices, vertex * 32)):
            fail("nonfinite-position", vertex)
    pending, seen, leaves, peak, max_element = [root], set(), 0, 1, -1
    semantic_hash = hashlib.sha256()
    while pending:
        node = pending.pop()
        if not 0 <= node < nc:
            fail("node-index-bounds", node)
            continue
        if node in seen:
            fail("cycle-or-shared-child", node)
            continue
        seen.add(node)
        n = struct.unpack_from("<8f4i", nodes, node * 48)
        # Exclude padding, which is neither initialized nor shader-consumed.
        semantic_hash.update(struct.pack("<I6f3i", node, *n[:3], *n[4:7], *n[8:11]))
        if not all(math.isfinite(x) for x in (*n[:3], *n[4:7])) or any(x < 0 for x in n[4:7]):
            fail("invalid-bbox", node)
        left, right, element = n[8:11]
        if element != -1:
            leaves += 1
            max_element = max(max_element, element)
            if element < 0 or element % 3 or element + 3 > index_count:
                fail("leaf-index-range", node)
        else:
            pending.extend((right, left))
            peak = max(peak, len(pending))
    if peak > 64:
        fail("glsl-stack-capacity", peak)
    return {"reachable_nodes": len(seen), "leaves": leaves,
            "max_reachable_node": max(seen, default=-1), "peak_pending_stack": peak,
            "glsl_stack_capacity": 64, "max_leaf_element": max_element,
            "referenced_vertices": len(referenced), "max_referenced_vertex": max(referenced, default=-1),
            "reachable_semantic_sha256": semantic_hash.hexdigest(),
            "logical_indexes_sha256": hashlib.sha256(indexes[:index_count * 4]).hexdigest(),
            "error_count": error_count, "errors_first_32": errors}


def vector_count(dump, address, stride):
    first, last, end = struct.unpack("<QQQ", dump.memory(address, 24))
    if not first <= last <= end or (last - first) % stride or (end - first) % stride:
        raise EvidenceError("invalid pinned MSVC vector extent")
    count = (last - first) // stride
    if count > MAX_RECORDS:
        raise EvidenceError("vector exceeds parser bound")
    return first, count


def collision_extent(dump, mesh):
    # Matching PDB: CPUAccelStruct at LevelMesh+0x7b0; MSVC release vectors
    # are three pointers; both CPU node types are 64 bytes, unlike GPU's 48.
    collision, = struct.unpack("<Q", dump.memory(mesh + 0x7b0, 8))
    if not collision:
        raise EvidenceError("CPU collision object absent")
    owner, = struct.unpack("<Q", dump.memory(collision, 8))
    if owner != mesh:
        raise EvidenceError("collision owner does not match LevelMesh")
    _, tlas_count = vector_count(dump, collision + 8, 64)
    first, slot_count = vector_count(dump, collision + 0x28, 8)
    if slot_count > 4096:
        raise EvidenceError("BLAS slot list exceeds parser bound")
    per_blas, instance_count = struct.unpack("<ii", dump.memory(collision + 0x40, 8))
    slots, live_count = [], tlas_count
    for i in range(slot_count):
        blas, = struct.unpack("<Q", dump.memory(first + i * 8, 8))
        if blas:
            _, count = vector_count(dump, blas + 0x20, 64)
            slots.append({"slot": i, "node_count": count})
            live_count += count
    return {"tlas_nodes": tlas_count, "blas_slots": slot_count,
            "nonnull_blas": slots, "indexes_per_blas": per_blas, "instance_count": instance_count,
            "recomputed_upload_node_count": live_count,
            "nonnull_slots_contiguous_from_zero": [s["slot"] for s in slots] == list(range(len(slots)))}


def inspect(dump_path, manifest_path):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    if manifest.get("schema") != "cfx-002-run-v1":
        raise EvidenceError("CFX run manifest required")
    source = manifest["source"]
    if source["exe"]["sha256"] != EXE_SHA or source["pdb"]["sha256"] != PDB_SHA:
        raise EvidenceError("manifest does not match pinned EXE/PDB")
    dump = Dump(dump_path)
    try:
        level = dump.base + LEVEL_RVA
        mesh, = struct.unpack("<Q", dump.memory(level + 0x290, 8))
        if not mesh:
            raise EvidenceError("null levelMesh")
        metadata, arrays = {}, {}
        for name, offset, stride in (("vertices", 0, 32), ("indexes", 0x90, 4), ("nodes", 0xb8, 48)):
            pointer, count, capacity = struct.unpack("<QII", dump.memory(mesh + 0x38 + offset, 16))
            if count > capacity or count > MAX_RECORDS or count * stride > MAX_ARRAY_BYTES:
                raise EvidenceError("invalid/beyond-bound TArray: " + name)
            data = dump.memory(pointer, count * stride)
            arrays[name] = data
            metadata[name] = {"address": hex(pointer), "count": count, "capacity": capacity,
                              "stride": stride, "sha256": hashlib.sha256(data).hexdigest()}
        index_count, = struct.unpack("<i", dump.memory(mesh + 0x38 + 0xb0, 4))
        root, = struct.unpack("<i", dump.memory(mesh + 0x38 + 0xc8, 4))
        extent = collision_extent(dump, mesh)
        checks = validate_tree(arrays["nodes"], arrays["indexes"], arrays["vertices"], root, index_count,
                               extent["recomputed_upload_node_count"])
        return {"schema": "cfx-004-cpu-snapshot-v1", "run_id": manifest["run_id"],
                "dump": {"path": str(Path(dump_path).resolve()), "size": dump.size,
                         "sha256": sha256_file(dump_path)},
                "manifest_sha256": sha256_file(manifest_path),
                "pinned_layout": {"exe_sha256": EXE_SHA, "pdb_sha256": PDB_SHA,
                                  "pdb_guid": PDB_GUID, "pdb_age": PDB_AGE, "level_rva": hex(LEVEL_RVA)},
                "level_address": hex(level), "mesh_address": hex(mesh),
                "root": root, "index_count": index_count, "arrays": metadata,
                "post_error_collision_extent": extent, "checks": checks,
                "boundary": "Post-error CPU data; not proof of submitted GPU bytes, uploaded extent, descriptors, shader execution or causal mechanism"}
    finally:
        dump.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        inputs = (args.dump, args.manifest)
        if (args.output.resolve() in tuple(p.resolve() for p in inputs) or
                (args.output.exists() and any(args.output.samefile(p) for p in inputs))):
            raise EvidenceError("output must not overwrite input evidence")
        report = inspect(args.dump, args.manifest)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"run_id": report["run_id"], "checks": report["checks"]}))
        return 1 if report["checks"]["error_count"] else 0
    except (EvidenceError, OSError, KeyError, ValueError) as exc:
        print("INCOMPLETE EVIDENCE: " + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
