#!/usr/bin/env python3
"""Bounded SDVK-009 publication evidence on explicitly hosted software Vulkan.

The read-only validator and negative controls never create a Vulkan device. The
four-process collector is restricted to GitHub-hosted llvmpipe, retains exact
historical authored content, and cannot grant physical or architecture acceptance.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
import copy
import os
from pathlib import Path
import re
import struct
import sys
import urllib.request
import uuid
import zipfile

try:
    from . import images, native_ci, prepare, run, validate
    from .common import (EvidenceError, ROOT, artifact_path, canonical, checked,
                         integer, pin, read_json, require, sha256, write_json)
except ImportError:
    import images
    import native_ci
    import prepare
    import run
    import validate
    from common import (EvidenceError, ROOT, artifact_path, canonical, checked,
                        integer, pin, read_json, require, sha256, write_json)

sys.path.insert(0, str(ROOT))
from tools import collision_replay

SCHEMA = "sdvk009-publication-qualification/v1"
WITNESS_SCHEMA = "sdvk009-publication-witness-validation/v1"
HISTORICAL_MANIFEST = ROOT / "docs/shadedoomvk/evidence/sdvk009-physical-20261011/raw-artifact-manifest.json"
IWAD_SHA256 = "a8772e088847032510d97ba2312406a6998f21cbab44d4ff10696faa9c0ecd4b"
IWAD_BYTES = 28787748
RELEASE_URL = "https://github.com/freedoom/freedoom/releases/download/v0.13.0/freedoom-0.13.0.zip"
RELEASE_ASSET_ID = 148625434
RELEASE_BYTES = 24143781
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_WITNESS_BYTES = 128 * 1024 * 1024
MAX_WITNESS_ROWS = 262144
MAX_STAGE_BYTES = 16 * 1024 * 1024
MAX_STAGE_TOTAL = 128 * 1024 * 1024
DIAGNOSTIC_KEYS = ("CFX_TRACE_FILE", "CFX_RUN_ID", "CFX_RESOURCE_TRACE", "CFX_WITNESS_DIR")
PLAN = (("compositing-control", "compositing", False),
        ("shadow-control", "shadow-boundary", False),
        ("shadow-witness-1", "shadow-boundary", True),
        ("shadow-witness-2", "shadow-boundary", True))


def fnv1a64(raw):
    value = 14695981039346656037
    for byte in raw:
        value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
    return value


def fetch_content(destination):
    """Fetch one official release once and require the sealed historical IWAD."""
    out = run.fresh_directory(destination)
    result = {"schema": "sdvk009-matching-content/v1", "status": "FAIL",
              "release_url": RELEASE_URL, "release_asset_id": RELEASE_ASSET_ID,
              "automatic_retries": 0, "started_utc": run.utc()}
    archive = out / "freedoom-0.13.0.zip"
    try:
        request = urllib.request.Request(RELEASE_URL, headers={"User-Agent": "ShadeDoomVK-publication-qualification"})
        with urllib.request.urlopen(request, timeout=60) as response, archive.open("xb") as output:
            total = 0
            for block in iter(lambda: response.read(1024 * 1024), b""):
                total += len(block)
                require(total <= MAX_ARCHIVE_BYTES, "Freedoom release archive exceeds the preregistered bound")
                output.write(block)
        require(archive.stat().st_size == RELEASE_BYTES, "Official release archive size changed")
        with zipfile.ZipFile(archive) as bundle:
            require(len(bundle.infolist()) <= 100, "Unexpected release archive member count")
            names = [entry.filename for entry in bundle.infolist()]
            require(len(names) == len(set(names)), "Duplicate release archive members")
            for member, leaf, maximum in (
                    ("freedoom-0.13.0/freedoom2.wad", "freedoom2.wad", IWAD_BYTES),
                    ("freedoom-0.13.0/COPYING.txt", "COPYING.txt", 65536)):
                info = bundle.getinfo(member)
                require(0 < info.file_size <= maximum and not info.is_dir(), "Unexpected release member extent")
                raw = bundle.read(member)
                if leaf == "freedoom2.wad":
                    require(len(raw) == IWAD_BYTES and sha256(raw) == IWAD_SHA256,
                            "Freedoom 0.13.0 IWAD does not match the sealed historical identity")
                else:
                    text = raw.decode("utf-8")
                    require("Redistribution and use" in text and "Freedoom" in text and "THIS SOFTWARE" in text,
                            "Freedoom release license notice is missing")
                with (out / leaf).open("xb") as output:
                    output.write(raw)
        result.update(status="PASS", archive=pin(archive, relative_to=out),
                      iwad=pin(out / "freedoom2.wad", relative_to=out),
                      license=pin(out / "COPYING.txt", relative_to=out),
                      publisher_signature_verified=False,
                      identity_basis="Official release URL and exact sealed historical IWAD SHA-256/size")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        result["error"] = str(error)
        raise
    finally:
        result["finished_utc"] = run.utc()
        write_json(out / "content.json", result)
    return result


def verify_historical_content(iwad, prepared):
    identity = pin(iwad)
    require(identity["bytes"] == IWAD_BYTES and identity["sha256"] == IWAD_SHA256,
            "Matching-content qualification requires the historical Freedoom 0.13.0 bytes")
    historical = read_json(HISTORICAL_MANIFEST)["files"]
    result = {"iwad": identity, "historical_manifest": pin(HISTORICAL_MANIFEST), "inputs": {}}
    for scene in ("compositing", "shadow-boundary"):
        for name, historical_name in (("scene.pk3", "input/scene.pk3"),
                                      ("fixture.ini", "input/fixture.ini"),
                                      ("capture.cfg", "capture.cfg")):
            key = f"campaign-01/reference-state/{scene}/1/{historical_name}"
            current = pin(Path(prepared) / "scenes" / scene / name, relative_to=prepared)
            require({k: current[k] for k in ("bytes", "sha256")} == historical[key],
                    "Prepared authored input differs from the sealed historical content: " + key)
            result["inputs"][f"{scene}/{name}"] = current
    return result


def capture_diagnostics(args, out):
    """Set diagnostics only on the owned renderer child; never change the caller."""
    if not getattr(args, "publication_witness", False):
        return None, None
    require(args.mode == "state" and not args.gpu and getattr(args, "collision_snapshot", False),
            "Publication witness requires a state-only production collision snapshot")
    require(not any(os.environ.get(key) for key in DIAGNOSTIC_KEYS), "Inherited CFX diagnostics are not isolated")
    directory = Path(out) / "publication"
    directory.mkdir(exist_ok=False)
    run_id = "sdvk009-publication-" + uuid.uuid4().hex
    environment = dict(os.environ)
    environment.update(CFX_TRACE_FILE=str(directory / "cfx-trace.tsv"), CFX_RUN_ID=run_id,
                       CFX_RESOURCE_TRACE="1", CFX_WITNESS_DIR=str(directory))
    return {"schema": "sdvk009-publication-request/v1", "run_id": run_id,
            "witness_directory": "publication", "trace": "publication/cfx-trace.tsv",
            "scope": "typed recorded commands and post-use defined fields; no executed-instruction attribution"}, environment


def validate_capture_diagnostics(root, request, artifacts=None):
    root = Path(root)
    diagnostic = request.get("diagnostics")
    require(isinstance(diagnostic, dict) and diagnostic.get("schema") == "sdvk009-publication-request/v1",
            "Unknown or incomplete publication diagnostic request")
    require(set(diagnostic) == {"schema", "run_id", "witness_directory", "trace", "scope"}
            and diagnostic["witness_directory"] == "publication"
            and diagnostic["trace"] == "publication/cfx-trace.tsv"
            and re.fullmatch(r"sdvk009-publication-[0-9a-f]{32}", diagnostic["run_id"]),
            "Publication diagnostic provenance changed")
    require(request["mode"] == "state" and request["reproduction"]["gpu_timestamps_requested"] is False
            and request["argv"].count("-sdvkcollisionsnapshot") == 1,
            "Publication request lacks the state-only CPU snapshot")
    expected = {"CFX_TRACE_FILE": str(Path(request["cwd"]) / diagnostic["trace"]),
                "CFX_RUN_ID": diagnostic["run_id"], "CFX_RESOURCE_TRACE": "1",
                "CFX_WITNESS_DIR": str(Path(request["cwd"]) / "publication")}
    require(all(request["environment"].get(key) == value for key, value in expected.items()),
            "Publication environment differs from the preregistered run")
    if artifacts is not None:
        required = {path.relative_to(root).as_posix() for path in (root / "publication").rglob("*")
                    if path.is_file()}
        required |= {path.relative_to(root).as_posix() for path in root.glob("collision-*.bin")}
        require(required and required <= set(artifacts), "Publication/snapshot artifact missing from the run inventory")
    return validate_witness(root)


def parse_witness(path):
    path = Path(path)
    require(path.is_file() and 0 < path.stat().st_size <= MAX_WITNESS_BYTES,
            "Missing or oversized publication witness")
    text = path.read_text(encoding="utf-8")
    require(text.endswith("\n"), "Publication witness is truncated")
    lines = text.splitlines()
    require(lines[:2] == ["# cfx-publication-v1", "seq\tevent\tdetail"], "Unknown publication witness header")
    require(2 < len(lines) <= MAX_WITNESS_ROWS + 2, "Publication witness row bound exceeded")
    result = []
    for expected_sequence, line in enumerate(lines[2:], 1):
        cells = line.split("\t")
        require(len(cells) == 3 and cells[0] == str(expected_sequence)
                and re.fullmatch(r"[a-z][a-z0-9-]*", cells[1]),
                "Publication witness sequence/row malformed or omitted")
        fields = {}
        for field in cells[2].split(" "):
            require(field.count("=") == 1, "Publication field is not one token-safe key=value")
            key, value = field.split("=", 1)
            require(re.fullmatch(r"[a-z][a-z0-9_]*", key) and value and key not in fields,
                    "Publication field missing, duplicated or malformed")
            fields[key] = value
        result.append({"seq": expected_sequence, "event": cells[1], "fields": fields})
    return result


def _number(fields, name, *, positive=False):
    value = fields.get(name, "")
    require(re.fullmatch(r"(?:0|[1-9][0-9]*)", value) is not None,
            "Missing or malformed witness integer: " + name)
    result = int(value)
    require(result <= 0xffffffffffffffff and (not positive or result > 0),
            "Witness integer out of bounds: " + name)
    return result


def _signed(fields, name):
    value = fields.get(name, "")
    require(re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value) is not None,
            "Missing or malformed signed witness integer: " + name)
    result = int(value)
    require(-(2**31) <= result < 2**31, "Signed witness integer out of bounds: " + name)
    return result


def _hex(fields, name):
    value = fields.get(name, "")
    require(re.fullmatch(r"0x[0-9a-f]{1,16}", value) is not None,
            "Missing or malformed witness hexadecimal: " + name)
    return int(value, 16)


def _key(fields):
    return (_number(fields, "cmd_id", positive=True), _number(fields, "recording", positive=True))


def _spirv(raw):
    """Read exact module interface/entry identities; this is not execution proof."""
    require(20 <= len(raw) <= MAX_STAGE_BYTES and len(raw) % 4 == 0, "Invalid SPIR-V byte extent")
    words = struct.unpack("<" + "I" * (len(raw) // 4), raw)
    require(words[0] == 0x07230203 and words[4] == 0 and 0 < words[3] <= 4_000_000,
            "Invalid SPIR-V module header")
    entries, decorations = set(), {}
    cursor = 5
    while cursor < len(words):
        length, opcode = words[cursor] >> 16, words[cursor] & 0xffff
        require(length > 0 and cursor + length <= len(words), "Truncated or malformed SPIR-V instruction")
        operands = words[cursor + 1:cursor + length]
        if opcode == 15:  # OpEntryPoint
            require(len(operands) >= 3, "Malformed SPIR-V entry point")
            name = struct.pack("<" + "I" * (len(operands) - 2), *operands[2:]).split(b"\0", 1)[0]
            try:
                name = name.decode("utf-8")
            except UnicodeError as error:
                raise EvidenceError("Invalid SPIR-V entry-point name") from error
            entries.add((operands[0], name))
        elif opcode == 71 and len(operands) >= 3 and operands[1] in (33, 34):  # Binding / DescriptorSet
            key = (operands[0], operands[1])
            require(key not in decorations, "Repeated SPIR-V descriptor decoration")
            decorations[key] = operands[2]
        cursor += length
    bindings = {(value, decorations[(identity, 33)]) for (identity, kind), value in decorations.items()
                if kind == 34 and (identity, 33) in decorations}
    require(entries, "SPIR-V module has no entry point")
    return {"entry_points": entries, "bindings": bindings}


def _blob(root, fields, *, filename="file", size="bytes", fingerprint="fnv1a64", maximum=MAX_STAGE_BYTES):
    name = fields.get(filename, "")
    count = _number(fields, size)
    require(count <= maximum, "Publication blob exceeds its declared byte bound")
    expected_hash = _hex(fields, fingerprint)
    if count == 0:
        require(name == "none" and expected_hash == fnv1a64(b""), "Invalid empty specialization identity")
        return b"", None
    require(re.fullmatch(r"[a-zA-Z0-9_-]+\.(?:spv|spec|bin)", name) is not None,
            "Publication blob filename is not a bounded leaf")
    path = artifact_path(root / "publication", name)
    require(path.is_file() and path.stat().st_size == count, "Publication blob missing or extent changed: " + name)
    raw = path.read_bytes()
    require(fnv1a64(raw) == expected_hash, "Publication blob fingerprint changed: " + name)
    return raw, pin(path, relative_to=root)


def _semantic_readback(snapshot, sources):
    """Build the compact expected defined fields without inventing padding/tails."""
    nodes = snapshot.sections[b"NODE"]
    count = len(nodes) // 36
    pending = [snapshot.header["root"]] if snapshot.header["root"] >= 0 else []
    reachable = set()
    while pending:
        identity = pending.pop()
        require(0 <= identity < count and identity not in reachable, "Readback graph has invalid/repeated reachable node")
        reachable.add(identity)
        left, right, element = struct.unpack_from("<3i", nodes, identity * 36 + 24)
        if element == -1:
            pending.extend((right, left))
    output = bytearray()
    ranges = []

    def append(kind, identity, source, offset, raw):
        ranges.append({"kind": kind, "identity": str(identity), "src_id": str(source),
                       "src_offset": str(offset), "dst_offset": str(len(output)), "bytes": str(len(raw))})
        output.extend(raw)

    append("root", 0, sources[0], 0, struct.pack("<I", snapshot.header["root"] & 0xffffffff))
    for identity in sorted(reachable):
        for ordinal, kind in enumerate(("node_center", "node_extents", "node_links")):
            append(kind, identity, sources[0], 16 + identity * 48 + ordinal * 16,
                   nodes[identity * 36 + ordinal * 12:identity * 36 + ordinal * 12 + 12])
    if snapshot.sections[b"INDX"]:
        append("index", 0, sources[2], 0, snapshot.sections[b"INDX"])
    vertices = sorted(snapshot.rows(b"VERT", "<4I"))
    for identity, x, z, y in vertices:
        append("vertex", identity, sources[1], identity * 32, struct.pack("<3I", x, z, y))
    require(len(output) <= 4 * 1024 * 1024 and len(ranges) <= 16384,
            "Defined-field readback exceeds its predeclared bound")
    return bytes(output), ranges, {"exported_count": count, "reachable_count": len(reachable),
                                  "occupied_count": snapshot.header["index_count"], "referenced_count": len(vertices)}


def validate_witness(root, *, records=None):
    """Validate the full publication chain; mutated records are CPU-only controls."""
    root = Path(root)
    records = parse_witness(root / "publication/publication-witness.tsv") if records is None else records
    return _validate_records(root, records)


def _validate_records(root, records):
    require(records and len(records) <= MAX_WITNESS_ROWS, "Missing or over-budget witness records")
    allowed = {"resource-create", "resource-name", "resource-destroy", "shader-bytes", "pipeline-created",
               "pipeline-stage", "pipeline-specialization", "pipeline-library", "descriptor-buffer-published",
               "descriptor-other-published", "descriptor-published", "command-begin", "command-end",
               "bind-pipeline", "bind-set", "consume", "consume-set", "consume-offset", "upload-packed",
               "buffer-copy-recorded", "submit-command", "fence-complete", "postuse-plan", "postuse-range",
               "postuse-submit", "postuse-fence", "postuse-readback", "observer-frame", "observer-frame-end",
               "observer-frame-presented", "observer-complete", "witness-summary", "retirement-list-release"}
    groups = {event: [] for event in allowed}
    for sequence, row in enumerate(records, 1):
        require(row.get("seq") == sequence and row.get("event") in allowed,
                "Witness contains missing, failed, unknown or reordered records")
        require(isinstance(row.get("fields"), dict) and all(isinstance(k, str) and isinstance(v, str)
                for k, v in row["fields"].items()), "Malformed witness fields")
        groups[row["event"]].append(row)
    require(len(groups["witness-summary"]) == 1 and records[-1]["event"] == "witness-summary",
            "Witness closure is missing, duplicated or not final")
    summary = records[-1]["fields"]
    require(summary == {"records": str(len(records) - 1), "failures": "0", "closed": "1"},
            "Witness summary reports omitted/failed/incomplete coverage")
    completion = ("schema=cfx-publication-complete-v1\nrecords=" + str(len(records)) + "\nfailures=0\n").encode()
    for leaf in ("publication-witness.complete", "publication-witness.complete.pending"):
        path = artifact_path(root / "publication", leaf)
        require(path.is_file() and path.read_bytes() == completion, "Successful exclusive witness close is not authenticated")
    trace = artifact_path(root / "publication", "cfx-trace.tsv")
    require(trace.is_file() and trace.stat().st_size <= 64 * 1024 * 1024, "Missing or oversized diagnostic trace")
    require("publication-witness-failed" not in trace.read_text(encoding="utf-8"), "Witness writer reported a failure")

    objects = {}
    for row in records:
        event, f, seq = row["event"], row["fields"], row["seq"]
        if event == "resource-create":
            identity = _number(f, "id", positive=True)
            require(identity not in objects and f.get("kind") in
                    {"buffer", "command", "descriptor-set", "shader", "pipeline", "pipeline-layout"},
                    "Allocation generation reused or unknown resource kind")
            require(_hex(f, "handle") > 0, "Resource has a null handle")
            objects[identity] = {"fields": f, "create": seq, "destroy": None}
        elif event in ("resource-destroy", "resource-name"):
            identity = _number(f, "id", positive=True)
            require(identity in objects and objects[identity]["fields"] == f and objects[identity]["destroy"] is None,
                    "Resource lifecycle/name has an unknown or stale allocation generation")
            if event == "resource-destroy":
                objects[identity]["destroy"] = seq
        elif event == "retirement-list-release":
            require(f.get("kind") in ("transfer-list", "draw-list") and _hex(f, "handle") == 0,
                    "Unknown retirement-list diagnostic scope")
            _number(f, "id", positive=True); _number(f, "bytes")

    def live(identity, kind, sequence):
        require(identity in objects, "Unknown allocation generation")
        obj = objects[identity]
        require(obj["fields"]["kind"] == kind and obj["create"] < sequence
                and (obj["destroy"] is None or sequence < obj["destroy"]), "Stale allocation generation/lifetime")
        return obj["fields"]

    def extent(identity, offset, count, sequence):
        obj = live(identity, "buffer", sequence)
        size = _number(obj, "bytes", positive=True)
        require(0 <= offset <= size and 0 < count <= size - offset, "Published/copied buffer range exceeds allocation")

    shaders, blobs, total_blob = {}, {}, 0
    for row in groups["shader-bytes"]:
        f = row["fields"]
        identity = _number(f, "shader_id", positive=True)
        live(identity, "shader", row["seq"])
        require(identity not in shaders and f.get("coverage") == "complete"
                and f.get("file") == f"shader-{identity}.spv", "Missing/duplicate/unknown shader-byte identity")
        raw, identity_pin = _blob(root, f)
        shaders[identity] = _spirv(raw)
        shaders[identity]["seq"] = row["seq"]
        blobs[identity_pin["path"]] = identity_pin
        total_blob += len(raw)
    pipelines = {}
    for row in groups["pipeline-created"]:
        f, seq = row["fields"], row["seq"]
        identity = _number(f, "pipeline_id", positive=True)
        live(identity, "pipeline", seq)
        layout_id = _number(f, "layout_id")
        if layout_id:
            live(layout_id, "pipeline-layout", seq)
        else:
            require(f.get("kind") == "graphics-library" and _number(f, "library_flags") & 6 == 0
                    and _number(f, "stages") == 0, "Shader-bearing pipeline has no layout identity")
        require(identity not in pipelines and f.get("kind") in ("graphics", "graphics-library", "compute")
                and f.get("coverage") == "complete" and _number(f, "stages") <= 8 and _number(f, "libraries") <= 8,
                "Pipeline creation has duplicate/unknown/bounded coverage")
        pipelines[identity] = {"fields": f, "seq": seq, "stages": {}, "stage_sequences": {},
                               "libraries": {}, "specializations": {}}
    stage_models = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4, 32: 5}
    for row in groups["pipeline-stage"]:
        f = row["fields"]
        pipeline = pipelines.get(_number(f, "pipeline_id", positive=True))
        ordinal, shader, stage = _number(f, "ordinal"), _number(f, "shader_id", positive=True), _number(f, "stage")
        require(pipeline is not None and pipeline["seq"] < row["seq"] and ordinal not in pipeline["stages"]
                and shader in shaders and shaders[shader]["seq"] < row["seq"] and stage in stage_models
                and (stage_models[stage], f.get("entry")) in shaders[shader]["entry_points"]
                and f.get("coverage") == "complete" and _number(f, "specialization_entries") <= 64,
                "Bound pipeline stage bytes/entry/coverage are missing or inconsistent")
        source = _number(f, "source_pipeline_id", positive=True)
        require(source in pipelines and pipelines[source]["seq"] <= pipeline["seq"], "Pipeline stage source identity is unknown")
        raw, identity_pin = _blob(root, f, filename="specialization_file", size="specialization_bytes",
                                  fingerprint="specialization_fnv1a64")
        if identity_pin and identity_pin["path"] not in blobs:
            blobs[identity_pin["path"]] = identity_pin
            total_blob += len(raw)
        pipeline["stages"][ordinal] = f
        pipeline["stage_sequences"][ordinal] = row["seq"]
        pipeline["specializations"][ordinal] = {}
    require(total_blob <= MAX_STAGE_TOTAL, "SPIR-V/specialization evidence exceeds the fixed run budget")
    for row in groups["pipeline-specialization"]:
        f = row["fields"]
        pipeline = pipelines.get(_number(f, "pipeline_id", positive=True))
        ordinal = _number(f, "stage_ordinal")
        require(pipeline is not None and ordinal in pipeline["stages"]
                and pipeline["stage_sequences"][ordinal] < row["seq"], "Specialization has no preceding pipeline stage")
        index = _number(f, "ordinal")
        entries = pipeline["specializations"][ordinal]
        size, offset = _number(f, "bytes", positive=True), _number(f, "offset")
        require(index not in entries and offset + size <= _number(pipeline["stages"][ordinal], "specialization_bytes"),
                "Specialization entry is duplicated or out of bounds")
        _number(f, "constant_id")
        entries[index] = f
    for row in groups["pipeline-library"]:
        f = row["fields"]
        pipeline = pipelines.get(_number(f, "pipeline_id", positive=True))
        identity, ordinal = _number(f, "library_id", positive=True), _number(f, "ordinal")
        require(pipeline is not None and identity in pipelines and pipelines[identity]["seq"] < pipeline["seq"]
                and pipeline["seq"] < row["seq"] and ordinal not in pipeline["libraries"]
                and pipelines[identity]["fields"].get("kind") == "graphics-library",
                "Pipeline library identity is missing, cyclic or duplicated")
        live(identity, "pipeline", pipeline["seq"])
        pipeline["libraries"][ordinal] = identity
    for pipeline in pipelines.values():
        require(set(pipeline["stages"]) == set(range(_number(pipeline["fields"], "stages")))
                and set(pipeline["libraries"]) == set(range(_number(pipeline["fields"], "libraries"))),
                "Pipeline stage/library records were omitted")
        for ordinal, f in pipeline["stages"].items():
            entries = pipeline["specializations"][ordinal]
            require(set(entries) == set(range(_number(f, "specialization_entries")))
                    and len({_number(entry, "constant_id") for entry in entries.values()}) == len(entries),
                    "Pipeline specialization records omitted/duplicated")

    def stage_identity(pipeline, ordinal):
        stage = pipeline["stages"][ordinal]
        identity = tuple(stage[key] for key in ("source_pipeline_id", "stage", "shader_id", "entry",
                         "specialization_entries", "specialization_bytes", "specialization_file",
                         "specialization_fnv1a64", "coverage"))
        entries = pipeline["specializations"][ordinal]
        return identity, tuple(tuple(entries[index][key] for key in ("constant_id", "offset", "bytes"))
                               for index in sorted(entries))

    library_closures = {}
    for identity, pipeline in sorted(pipelines.items(), key=lambda item: item[1]["seq"]):
        closure = set()
        expected_inherited = []
        for index in sorted(pipeline["libraries"]):
            library = pipeline["libraries"][index]
            closure.add(library)
            closure.update(library_closures[library])
            expected_inherited.extend(stage_identity(pipelines[library], ordinal)
                                      for ordinal in sorted(pipelines[library]["stages"]))
        actual_inherited = []
        for ordinal, stage in sorted(pipeline["stages"].items()):
            source = _number(stage, "source_pipeline_id", positive=True)
            if source == identity:
                require(not actual_inherited, "Direct pipeline stage follows inherited library stages")
                shader = _number(stage, "shader_id", positive=True)
                require(shaders[shader]["seq"] < pipeline["seq"], "Pipeline predates its shader-byte identity")
                live(shader, "shader", pipeline["seq"])
            else:
                require(source in closure, "Inherited stage source is outside the linked library closure")
                provenance = stage_identity(pipeline, ordinal)
                require(any(provenance == stage_identity(pipelines[source], origin)
                            and pipelines[source]["stage_sequences"][origin] < pipeline["seq"]
                            for origin in pipelines[source]["stages"]),
                        "Inherited stage differs from its originating library shader/entry/specialization")
                actual_inherited.append(provenance)
        require(actual_inherited == expected_inherited, "Linked library stage coverage was substituted or omitted")
        library_closures[identity] = closure

    descriptor_history, pending = {}, {}
    for row in records:
        event, f, sequence = row["event"], row["fields"], row["seq"]
        if event not in {"descriptor-buffer-published", "descriptor-other-published", "descriptor-published"}:
            continue
        identity, generation = _number(f, "set_id", positive=True), _number(f, "generation", positive=True)
        live(identity, "descriptor-set", sequence)
        history = descriptor_history.setdefault(identity, [])
        require(generation == len(history) + 1, "Descriptor publication generation is stale or omitted")
        if event == "descriptor-published":
            writes = pending.pop((identity, generation), [])
            require(writes and len(writes) == _number(f, "write_count", positive=True) and f.get("api") == "void",
                    "Descriptor publication return or complete write coverage missing")
            slots = dict(history[-1]["slots"]) if history else {}
            for write in writes:
                slots[(_number(write, "binding"), _number(write, "array"))] = write
            history.append({"seq": sequence, "slots": slots, "generation": generation})
        else:
            _number(f, "binding"); _number(f, "array"); _number(f, "type")
            if event == "descriptor-buffer-published":
                buffer, offset = _number(f, "buffer_id", positive=True), _number(f, "offset")
                size = _number(f, "range", positive=True)
                allocation = live(buffer, "buffer", sequence)
                if size == 0xffffffffffffffff:
                    size = _number(allocation, "bytes") - offset
                extent(buffer, offset, size, sequence)
            else:
                require(f.get("scope") == "outside-collision-buffers", "Unknown descriptor evidence scope")
            pending.setdefault((identity, generation), []).append(f)
    require(not pending, "Descriptor writes have no successful publication marker")

    def descriptor(identity, generation, sequence):
        live(identity, "descriptor-set", sequence)
        history = descriptor_history.get(identity, [])
        require(0 < generation <= len(history) and history[generation - 1]["seq"] < sequence,
                "Bound descriptor publication is missing")
        require(generation == len([item for item in history if item["seq"] < sequence]),
                "Bound descriptor generation is stale")
        return history[generation - 1]["slots"]

    commands, latest_recording, consumes, copies = {}, {}, {}, []
    for row in records:
        event, f, seq = row["event"], row["fields"], row["seq"]
        if event not in {"command-begin", "command-end", "bind-pipeline", "bind-set", "consume",
                         "consume-set", "consume-offset", "buffer-copy-recorded"}:
            continue
        key = _key(f)
        live(key[0], "command", seq)
        if event == "command-begin":
            require(key not in commands and key[1] == latest_recording.get(key[0], 0) + 1,
                    "Command recording generation reused or omitted")
            latest_recording[key[0]] = key[1]
            commands[key] = {"begin": seq, "end": None, "ordinal": 0, "frame": _number(f, "frame"),
                             "binds": {}, "pipeline_binds": {}, "consumes": [], "copies": []}
            continue
        require(key in commands and commands[key]["end"] is None, "Command recording missing, ended or stale")
        command = commands[key]
        if event == "command-end":
            require(_number(f, "ordinal") == command["ordinal"], "Command bind/consume coverage was omitted")
            command["end"] = seq
        elif event == "buffer-copy-recorded":
            size = _number(f, "bytes", positive=True)
            for prefix in ("src", "dst"):
                extent(_number(f, prefix + "_id", positive=True), _number(f, prefix + "_offset"), size, seq)
            entry = {"fields": f, "seq": seq, "command": key}
            copies.append(entry); command["copies"].append(entry)
        elif event in ("bind-pipeline", "bind-set", "consume"):
            ordinal, point = _number(f, "ordinal", positive=True), _number(f, "bind_point")
            require(ordinal == command["ordinal"] + 1 and point in (0, 1), "Command ordinal/bind-point omitted or unknown")
            command["ordinal"] = ordinal
            if event == "bind-pipeline":
                command["pipeline_binds"][point] = f
            elif event == "bind-set":
                index = _number(f, "set_index")
                require(index < 8 and _number(f, "dynamic_count") <= 16, "Descriptor bind exceeds fixed evidence bounds")
                command["binds"][(point, index)] = f
            else:
                pipeline = command["pipeline_binds"].get(point)
                require(pipeline is not None and f.get("pipeline_bind_ordinal") == pipeline["ordinal"]
                        and f.get("pipeline_id") == pipeline["pipeline_id"], "Consume lost its actual recorded pipeline bind")
                entry = {"fields": f, "seq": seq, "command": key, "pipeline_bind": pipeline,
                         "binds": {index: bind for (p, index), bind in command["binds"].items() if p == point},
                         "sets": {}, "set_sequences": {}, "offsets": {}}
                consumes[(key, ordinal)] = entry
                command["consumes"].append(entry)
        else:
            ordinal, index = _number(f, "ordinal", positive=True), _number(f, "set_index")
            entry = consumes.get((key, ordinal))
            require(entry is not None and f.get("bind_point") == entry["fields"]["bind_point"],
                    "Consumed descriptor/offset has no consuming command")
            if event == "consume-set":
                bind = entry["binds"].get(index)
                require(bind is not None and index not in entry["sets"] and f.get("set_id") == bind["set_id"]
                        and f.get("bind_ordinal") == bind["ordinal"] and f.get("bound_generation") == bind["generation"]
                        and f.get("layout_id") == bind["layout_id"] and f.get("dynamic_count") == bind["dynamic_count"],
                        "Consumed descriptor differs from its typed recorded bind")
                entry["sets"][index] = f
                entry["set_sequences"][index] = seq
                entry["offsets"][index] = {}
            else:
                offset = _number(f, "offset_index")
                require(index in entry["sets"] and offset not in entry["offsets"][index],
                        "Consume dynamic-offset record missing or repeated")
                entry["offsets"][index][offset] = _number(f, "offset")
    for command in commands.values():
        require(command["end"] is not None, "Unended recorded command leaves evidence incomplete")
    for entry in consumes.values():
        require(set(entry["sets"]) == set(entry["binds"]), "A bound descriptor was omitted from a consume snapshot")
        for index, f in entry["sets"].items():
            require(set(entry["offsets"][index]) == set(range(_number(f, "dynamic_count"))),
                    "Consumed dynamic offsets have incomplete coverage")

    submissions, membership, fences = {}, {}, {}
    for row in groups["submit-command"]:
        f, seq = row["fields"], row["seq"]
        key, identity = _key(f), _number(f, "submission", positive=True)
        index, count = _number(f, "index"), _number(f, "buffers", positive=True)
        require(key in commands and commands[key]["end"] < seq and key not in membership and index < count,
                "Submission has unknown, unfinished or repeated command recording")
        live(key[0], "command", seq)
        sub = submissions.setdefault(identity, {"commands": {}, "count": count, "fence": f.get("fence"),
                                               "slot": _number(f, "fence_slot"), "seq": seq})
        require(sub["count"] == count and sub["fence"] == f.get("fence") and sub["slot"] == _number(f, "fence_slot")
                and _hex(f, "fence") > 0 and index not in sub["commands"], "Submission membership/fence identity inconsistent")
        sub["commands"][index] = key
        membership[key] = (identity, index)
    for identity, sub in submissions.items():
        require(set(sub["commands"]) == set(range(sub["count"])), "Submission command coverage omitted")
    for row in groups["fence-complete"]:
        f = row["fields"]
        identity = _number(f, "submission", positive=True)
        sub = submissions.get(identity)
        require(sub is not None and sub["seq"] < row["seq"] and identity not in fences
                and f.get("fence") == sub["fence"] and _number(f, "fence_slot") == sub["slot"]
                and f.get("wait") in ("frame", "recycle") and f.get("result") == "0",
                "Fence completion missing its exact successful submission")
        fences[identity] = row
    require(set(membership) == set(commands) and set(fences) == set(submissions),
            "Recorded commands/submissions do not have complete submission/fence coverage")
    require(set(submissions) == set(range(1, len(submissions) + 1)), "A real submission identity was omitted")
    slot_last, slot_handles = {}, {}
    for identity, sub in sorted(submissions.items()):
        slot = sub["slot"]
        require(slot not in slot_handles or slot_handles[slot] == sub["fence"], "Fence slot changed its object identity")
        require(slot not in slot_last or fences[slot_last[slot]]["seq"] < sub["seq"],
                "Fence slot reused before its exact prior submission completed")
        slot_handles[slot], slot_last[slot] = sub["fence"], identity
        for key in sub["commands"].values():
            live(key[0], "command", fences[identity]["seq"])
            previous = (key[0], key[1] - 1)
            if previous in commands:
                require(fences[membership[previous][0]]["seq"] < commands[key]["begin"],
                        "Command recording generation reused before its previous fence completed")

    uploads = []
    for row in groups["upload-packed"]:
        f, seq = row["fields"], row["seq"]
        require(f.get("coverage") == "complete", "Packed staging upload coverage is omitted or unavailable")
        _hex(f, "fnv1a64")
        size = _number(f, "bytes", positive=True)
        for prefix in ("src", "dst"):
            extent(_number(f, prefix + "_id", positive=True), _number(f, prefix + "_offset"), size, seq)
        uploads.append(row)
    by_destination = {}
    for entry in copies:
        f = entry["fields"]
        sub, index = membership[entry["command"]]
        entry["order"] = (sub, index, entry["seq"])
        extent(_number(f, "src_id"), _number(f, "src_offset"), _number(f, "bytes"), submissions[sub]["seq"])
        extent(_number(f, "dst_id"), _number(f, "dst_offset"), _number(f, "bytes"), submissions[sub]["seq"])
        extent(_number(f, "src_id"), _number(f, "src_offset"), _number(f, "bytes"), fences[sub]["seq"])
        extent(_number(f, "dst_id"), _number(f, "dst_offset"), _number(f, "bytes"), fences[sub]["seq"])
        entry["packed"] = [row for row in uploads if row["seq"] < entry["seq"] and
                           all(row["fields"].get(key) == f[key] for key in
                               ("src_id", "dst_id", "src_offset", "dst_offset", "bytes"))]
        by_destination.setdefault(_number(f, "dst_id"), []).append(entry)

    def published(identity, offset, size, before, depth=0):
        require(depth <= 32, "Copy publication lineage exceeds its bounded depth")
        candidates = [row for row in by_destination.get(identity, []) if row["order"] < before
                      and _number(row["fields"], "dst_offset") < offset + size
                      and _number(row["fields"], "dst_offset") + _number(row["fields"], "bytes") > offset]
        boundaries = {offset, offset + size}
        for row in candidates:
            f = row["fields"]
            boundaries.update((max(offset, _number(f, "dst_offset")),
                               min(offset + size, _number(f, "dst_offset") + _number(f, "bytes"))))
        boundaries = sorted(boundaries)
        leaves = set()
        for start, end in zip(boundaries, boundaries[1:]):
            covering = [row for row in candidates if _number(row["fields"], "dst_offset") <= start
                        and end <= _number(row["fields"], "dst_offset") + _number(row["fields"], "bytes")]
            require(covering, "Defined source bytes have missing staging/copy publication")
            last = max(covering, key=lambda row: row["order"])
            if last["packed"]:
                leaves.add(last["packed"][-1]["seq"])
            else:
                f = last["fields"]
                leaves.update(published(_number(f, "src_id"), _number(f, "src_offset") + start - _number(f, "dst_offset"),
                                        end - start, last["order"], depth + 1))
        return leaves

    snapshots = {}
    snapshot_paths = sorted(root.glob("collision-*.bin"))
    require(0 < len(snapshot_paths) <= 4096, "Production snapshot history missing or over bound")
    parsed = []
    for path in snapshot_paths:
        snapshot = collision_replay.parse_snapshot(path)
        collision_replay.validate_snapshot(snapshot)
        identity = (snapshot.header["object_id"], snapshot.header["event"])
        require(identity not in snapshots and path.name == f"collision-{identity[1]}.bin", "Snapshot object/event aliased")
        snapshots[identity] = snapshot
        parsed.append(snapshot)
    parsed.sort(key=lambda snapshot: snapshot.header["event"])
    collision_replay.validate_sequence(parsed)

    plans = {}
    for row in groups["postuse-plan"]:
        f = row["fields"]
        identity = _number(f, "readback_id", positive=True)
        require(identity == len(plans) + 1 and identity <= 4096, "Readback plan identity missing or duplicated")
        snapshot = snapshots.get((_number(f, "snapshot_object", positive=True), _number(f, "snapshot_event", positive=True)))
        require(snapshot is not None and _signed(f, "root") == snapshot.header["root"], "Readback uses an unknown/stale snapshot identity")
        sources = tuple(_number(f, name, positive=True) for name in ("node_id", "vertex_id", "index_id"))
        require(len(set(sources)) == 3, "Readback source allocation identities alias")
        raw, expected_ranges, counts = _semantic_readback(snapshot, sources)
        require(_number(f, "bytes", positive=True) == len(raw) and _number(f, "ranges", positive=True) == len(expected_ranges)
                and all(_number(f, key) == value for key, value in counts.items()), "Readback semantic counts/extent changed")
        key = _key(f)
        require(key in commands and commands[key]["begin"] < row["seq"] < commands[key]["end"],
                "Readback plan is not inside its actual command recording")
        extent(_number(f, "staging_id", positive=True), 0, len(raw), row["seq"])
        plans[identity] = {"fields": f, "seq": row["seq"], "command": key, "sources": sources,
                           "raw": raw, "expected_ranges": expected_ranges, "ranges": [], "snapshot": snapshot,
                           "submit": None, "fence": None, "readback": None}
    require(plans and sum(len(plan["raw"]) for plan in plans.values()) <= 256 * 1024 * 1024,
            "Readbacks missing or exceed the fixed run staging budget")
    for event in ("postuse-range", "postuse-submit", "postuse-fence", "postuse-readback"):
        for row in groups[event]:
            f = row["fields"]
            identity = _number(f, "readback_id", positive=True)
            require(identity in plans and plans[identity]["seq"] < row["seq"], "Readback event has no preceding plan")
            plan = plans[identity]
            if event == "postuse-range":
                plan["ranges"].append({k: v for k, v in f.items() if k != "readback_id"})
            else:
                key = event.split("-", 1)[1]
                require(plan[key] is None, "Readback lifecycle event repeated")
                plan[key] = row
    qualified_submissions = {}
    publication_leaves = set()
    for identity, plan in plans.items():
        f = plan["fields"]
        require(plan["ranges"] == plan["expected_ranges"], "Readback range coverage, original identity or field mask differs")
        require(all(plan[key] is not None for key in ("submit", "fence", "readback")), "Readback lifecycle completion missing")
        submission, index = membership[plan["command"]]
        sub = submissions[submission]
        require(index == sub["count"] - 1 and submission not in qualified_submissions,
                "Post-use readback is not the final command after ordinary consumers")
        expected_fence = {"submission": str(submission), "fence_slot": str(sub["slot"]), "fence": sub["fence"]}
        require(_key(plan["submit"]["fields"]) == plan["command"]
                and all(plan[event]["fields"].get(key) == value for event in ("submit", "fence") for key, value in expected_fence.items())
                and sub["seq"] <= plan["submit"]["seq"] < fences[submission]["seq"]
                <= plan["fence"]["seq"] < plan["readback"]["seq"], "Readback submission/fence completion identity or order differs")
        current_copies = commands[plan["command"]]["copies"]
        expected_copies = [{"cmd_id": f["cmd_id"], "recording": f["recording"], "src_id": region["src_id"],
                            "dst_id": f["staging_id"], "src_offset": region["src_offset"],
                            "dst_offset": region["dst_offset"], "bytes": region["bytes"]} for region in plan["ranges"]]
        require([row["fields"] for row in current_copies] == expected_copies,
                "Readback plan does not match its actual recorded copies")
        for region, copied in zip(plan["ranges"], current_copies):
            publication_leaves.update(published(_number(region, "src_id"), _number(region, "src_offset"),
                                                _number(region, "bytes"), copied["order"]))
        readback = plan["readback"]["fields"]
        live(_number(f, "staging_id", positive=True), "buffer", plan["readback"]["seq"])
        require(readback.get("file") == f"readback-{identity}.bin", "Readback artifact identity aliased")
        raw, identity_pin = _blob(root, readback, maximum=4 * 1024 * 1024)
        require(raw == plan["raw"], "Post-use defined destination bytes differ from the exact CPU snapshot")
        blobs[identity_pin["path"]] = identity_pin
        qualified_submissions[submission] = plan

    observer = groups["observer-frame"]
    require(len(observer) == 121 and len(groups["observer-complete"]) == 1,
            "The complete declared 120-warmup/one-retained observation is missing")
    observed_frames = {}
    for ordinal, row in enumerate(observer, 1):
        f = row["fields"]
        phase = "warmup" if ordinal <= 120 else "retained"
        frame = _number(f, "frame", positive=True)
        require(frame not in observed_frames and f.get("ordinal") == str(ordinal)
                and f.get("phase") == phase and f.get("warmup") == "120"
                and f.get("requested") == "1" and f.get("map") == "SDVSHDW", "Observed warmup/frame policy changed or omitted")
        observed_frames[frame] = row
    frame_intervals = {}
    for event in ("observer-frame-end", "observer-frame-presented"):
        require(len(groups[event]) == 121, "Observed frame completion/presentation omitted")
        for start, end in zip(observer, groups[event]):
            require(end["fields"] == start["fields"] and start["seq"] < end["seq"],
                    "Observer frame completion identity/order differs")
    for index, (start, end, presented) in enumerate(zip(observer, groups["observer-frame-end"], groups["observer-frame-presented"])):
        require(start["seq"] < end["seq"] < presented["seq"]
                and (index == 120 or presented["seq"] < observer[index + 1]["seq"]),
                "Observer begin/end/presentation sequence is reordered or overlapping")
        frame_intervals[_number(start["fields"], "frame")] = (start["seq"], end["seq"])
    done = groups["observer-complete"][0]
    require(all(done["fields"].get(key) == value for key, value in
                {"complete": "1", "failure": "0", "seen": "121", "collected": "1", "warmup": "120", "requested": "1"}.items())
            and max(row["seq"] for row in groups["observer-frame-presented"]) < done["seq"] < records[-1]["seq"],
            "Observer did not complete its exact declared interval")
    frame_consumes = {frame: [] for frame in observed_frames}
    interval_starts = [row["seq"] for row in observer]
    outside_interval, outside_unknown = 0, 0
    for entry in consumes.values():
        f, seq = entry["fields"], entry["seq"]
        frame = _number(f, "frame")
        submission, index = membership[entry["command"]]
        # Startup, 2D/present and screenshot work can share a CFX frame number
        # while falling outside the ordinary observer's begin/end interval.
        # Retain lifetime checks for every known typed identity in that work.
        if entry["pipeline_bind"].get("coverage") == "complete":
            pipeline_id = _number(f, "pipeline_id", positive=True)
            require(pipeline_id in pipelines and pipelines[pipeline_id]["seq"] < seq,
                    "Typed consume has no preceding pipeline identity")
            live(pipeline_id, "pipeline", seq)
            live(pipeline_id, "pipeline", fences[submission]["seq"])
        for bound in entry["sets"].values():
            if bound.get("coverage") == "complete":
                bound_id = _number(bound, "set_id", positive=True)
                live(bound_id, "descriptor-set", seq)
                live(bound_id, "descriptor-set", fences[submission]["seq"])
                observed_generation = len([item for item in descriptor_history.get(bound_id, []) if item["seq"] < seq])
                require(bound.get("set_alive") == "1" and _number(bound, "publication_generation") == observed_generation,
                        "Typed consume descriptor publication generation/liveness differs from its recorded history")
        interval = bisect_right(interval_starts, seq) - 1
        inside = interval >= 0 and seq < groups["observer-frame-end"][interval]["seq"]
        if not inside:
            outside_interval += 1
            outside_unknown += f.get("coverage") != "complete" or entry["pipeline_bind"].get("coverage") != "complete"
            continue
        require(frame == _number(observer[interval]["fields"], "frame"),
                "Observed consume frame differs from its authenticated frame interval")
        require(f.get("coverage") == "complete" and f.get("pipeline_alive") == "1"
                and entry["pipeline_bind"].get("coverage") == "complete", "Observed consume has unknown or stale pipeline identity")
        pipeline_id = _number(f, "pipeline_id", positive=True)
        pipeline = pipelines.get(pipeline_id)
        require(pipeline is not None and pipeline["seq"] < seq, "Observed consume has no pipeline creation identity")
        live(pipeline_id, "pipeline", seq)
        fragment = [stage for stage in pipeline["stages"].values() if stage["stage"] == "16"
                    and {(0, 2), (0, 3), (0, 4)} <= shaders[_number(stage, "shader_id")]["bindings"]]
        if not fragment:
            continue
        require(f.get("bind_point") == "0" and f.get("kind") in ("draw", "draw-indexed"),
                "Collision-capable fragment consumption uses an unqualified draw kind")
        fixed = entry["sets"].get(0)
        require(fixed is not None and fixed.get("coverage") == "complete" and fixed.get("set_alive") == "1"
                and fixed.get("bound_generation") == fixed.get("publication_generation")
                and fixed.get("dynamic_count") == "0", "Collision fixed descriptor is missing, stale or dynamically aliased")
        require(all(bound.get("layout_id") == pipeline["fields"]["layout_id"] for bound in entry["sets"].values()),
                "Collision consume has a mismatched descriptor/pipeline layout identity")
        set_id, generation = _number(fixed, "set_id", positive=True), _number(fixed, "bound_generation", positive=True)
        slots = descriptor(set_id, generation, seq)
        require(submission in qualified_submissions, "Observed collision consume has no same-submission post-use readback")
        plan = qualified_submissions[submission]
        require(index < membership[plan["command"]][1], "Readback was ordered before its consuming command")
        descriptor(set_id, generation, submissions[submission]["seq"])
        descriptor(set_id, generation, fences[submission]["seq"])
        live(pipeline_id, "pipeline", submissions[submission]["seq"])
        live(pipeline_id, "pipeline", fences[submission]["seq"])
        live(_number(pipeline["fields"], "layout_id", positive=True), "pipeline-layout", fences[submission]["seq"])
        for binding, expected in zip((2, 3, 4), plan["sources"]):
            slot = slots.get((binding, 0))
            require(slot is not None and slot.get("type") == "7" and _number(slot, "buffer_id", positive=True) == expected
                    and _number(slot, "offset") == 0, "Bound collision descriptor differs from post-use allocation generation")
            live(expected, "buffer", seq)
            capacity = _number(objects[expected]["fields"], "bytes")
            bound_range = _number(slot, "range", positive=True)
            if bound_range == 0xffffffffffffffff:
                bound_range = capacity
            require(all(_number(region, "src_offset") + _number(region, "bytes") <= bound_range
                        for region in plan["ranges"] if _number(region, "src_id") == expected),
                    "Bound descriptor range omits required collision semantics")
        frame_consumes[frame].append(entry)
    require(all(frame_consumes.values()), "An observed warmup/retained frame lacks qualified collision consumption/readback")
    previous_snapshot = 0
    for frame in observed_frames:
        frame_events = {_number(qualified_submissions[membership[entry["command"]][0]]["fields"], "snapshot_event")
                        for entry in frame_consumes[frame]}
        require(min(frame_events) > previous_snapshot, "Observed frame reused a stale previous-frame collision snapshot")
        previous_snapshot = max(frame_events)
    required_files = {"publication/publication-witness.tsv", "publication/cfx-trace.tsv",
                      "publication/publication-witness.complete", "publication/publication-witness.complete.pending"} | set(blobs)
    actual_files = {path.relative_to(root).as_posix() for path in (root / "publication").rglob("*") if path.is_file()}
    require(actual_files == required_files, "Publication artifact inventory contains missing or unaccounted files")
    control_target = next(entry for entries in frame_consumes.values() for entry in entries)
    return {"schema": WITNESS_SCHEMA, "status": "PASS", "records": len(records),
            "observer_frames": 121, "warmup_frames": 120, "retained_frames": 1,
            "qualified_collision_consumes": sum(len(entries) for entries in frame_consumes.values()),
            "qualified_frames": len(frame_consumes), "readbacks": len(plans), "snapshots": len(snapshots),
            "shader_modules": len(shaders), "pipelines": len(pipelines), "submitted_commands": len(membership),
            "completed_submissions": len(fences), "joined_staging_uploads": len(publication_leaves),
            "outside_observer_consumes": outside_interval, "outside_observer_unknown_consumes": outside_unknown,
            "outside_observer_scope": "Startup/2D/present/screenshot commands retain submission/fence and known-object lifetime checks; do not satisfy observed collision-frame coverage",
            "negative_control_target": {"consume_seq": control_target["seq"], "fixed_set_seq": control_target["set_sequences"][0]},
            "readback_semantics": "root; reachable original node center/extents/links; occupied indices; referenced original XYZ",
            "semantic_readback_bytes": sum(len(plan["raw"]) for plan in plans.values()),
            "artifacts": {name: pin(root / name, relative_to=root) for name in sorted(required_files)},
            "limits": ["Recorded bind and queue ordering identify CPU-submitted work, not an executed shader instruction.",
                       "Readback appends copies/barriers after ordinary consumers and may perturb later frame scheduling.",
                       "Exact historical authored input is not the unrecorded failed physical runtime or node-cache history."],
            "physical_gpu_qualified": False, "performance_accepted": False, "root_cause": "UNDETERMINED"}


def compare_control(control, witness):
    """Use the established exact state/RGB oracle with one explicit diagnostic delta."""
    left_root, left, left_raw, _ = run.validate_run(control)
    right_root, right, right_raw, _ = run.validate_run(witness)
    left_request = read_json(left_root / "request.json")
    right_request = read_json(right_root / "request.json")
    require(left_root != right_root and left_request["cwd"] != right_request["cwd"],
            "Control/witness comparison needs distinct native processes")
    require("diagnostics" not in left_request and "diagnostics" in right_request,
            "Control/witness instrumentation roles are not explicit")
    require(not any(key.startswith("CFX_") for key in left_request["environment"])
            and "-sdvkcollisionsnapshot" not in left_request["argv"],
            "Uninstrumented control inherited collision/publication diagnostics")
    control_profile, witness_profile = copy.deepcopy(left["reproduction"]), copy.deepcopy(right["reproduction"])
    require("collision_snapshot" not in control_profile and witness_profile.pop("collision_snapshot", None)
            == "production-cpu-state; no submitted-GPU-byte claim", "Unexpected diagnostic profile delta")
    require(control_profile == witness_profile, "Control/witness production profiles differ")
    require(left["mode"] == right["mode"] == "state"
            and left["build"]["working_tree"] == right["build"]["working_tree"] == "clean",
            "Control/witness captures are not clean correctness runs")
    require(run.comparable_build(left["build"]) == run.comparable_build(right["build"])
            and left["executable"]["sha256"] == right["executable"]["sha256"]
            and run.package_identity(left) == run.package_identity(right),
            "Control/witness source, executable, device or loaded content differs")
    static = control_profile["clock"] == "static_after_initialization"
    x = validate.state_projection(left_raw, static_scene=static)
    y = validate.state_projection(right_raw, static_scene=static)
    image = images.compare(left_root / "native.png", right_root / "native.png", control_profile["image_policy"])
    return {"schema": "sdvk009-publication-control-comparison/v1",
            "status": "PASS" if x == y and image["passed"] else "FAIL",
            "control": pin(left_root / "run.json"), "witness": pin(right_root / "run.json"),
            "state_equal": x == y, "state_sha256": {"control": sha256(canonical(x)), "witness": sha256(canonical(y))},
            "first_state_differences": run.differences(x, y), "image": image,
            "diagnostic_delta": "Only opt-in CPU snapshot and publication witness; original production state/RGB oracle",
            "physical_gpu_qualified": False, "performance_accepted": False}


def negative_controls(root):
    """Retain falsification receipts; never mutate a real captured artifact."""
    records = parse_witness(Path(root) / "publication/publication-witness.tsv")
    proof = validate_witness(root, records=records)
    return _negative_records(root, records, proof["negative_control_target"])


def _negative_records(root, records, target):
    mutations = []

    def change(name, event, field, value, sequence=None):
        original = records[sequence - 1] if sequence is not None else next(row for row in records if row["event"] == event)
        require(original["event"] == event, "Negative control does not target the authenticated event")
        altered = {**original, "fields": {**original["fields"], field: value(original["fields"].get(field))}}
        changed = list(records)
        changed[original["seq"] - 1] = altered
        mutations.append((name, changed, {"seq": original["seq"], "event": event, "field": field,
                                         "original": original["fields"].get(field), "altered": altered["fields"][field]}))

    change("stale-bound-descriptor-generation", "consume-set", "bound_generation", lambda value: str(int(value) + 1), target["fixed_set_seq"])
    change("unknown-bound-pipeline-coverage", "consume", "coverage", lambda _: "unknown", target["consume_seq"])
    change("missing-bound-stage-bytes", "shader-bytes", "file", lambda _: "missing-shader.spv")
    change("wrong-postuse-source-allocation", "postuse-plan", "node_id", lambda value: str(int(value) + 1))
    change("missing-postuse-field-coverage", "postuse-plan", "ranges", lambda value: str(int(value) + 1))
    change("wrong-completed-fence-generation", "postuse-fence", "submission", lambda value: str(int(value) + 1))
    change("altered-readback-defined-bytes", "postuse-readback", "fnv1a64", lambda value: hex(int(value, 16) ^ 1))
    change("missing-observed-warmup-frame", "observer-frame", "ordinal", lambda value: str(int(value) + 1))
    mutations.append(("truncated-completion-evidence", records[:-1], {"removed_seq": records[-1]["seq"], "event": "witness-summary"}))
    results = []
    for name, altered, mutation in mutations:
        try:
            _validate_records(Path(root), altered)
        except (OSError, ValueError) as error:
            results.append({"name": name, "status": "PASS", "expected": "REJECTED", "error": str(error), "mutation": mutation})
        else:
            raise EvidenceError("Deliberately invalid publication evidence was accepted: " + name)
    return {"schema": "sdvk009-publication-negative-controls/v1", "status": "PASS", "controls": results,
            "source_witness": pin(Path(root) / "publication/publication-witness.tsv"),
            "classification": "Deliberately mutated in-memory copies of captured records; original files unchanged",
            "native_negative_resources_submitted": False, "physical_gpu_qualified": False}


def hosted_software_guard():
    """Reject an unsafe execution surface before any device-enumerating process."""
    require(sys.platform == "linux" and os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Native publication qualification requires an explicitly GitHub-hosted Linux runner")
    names = ("VK_DRIVER_FILES", "VK_ICD_FILENAMES")
    selected = []
    for name in names:
        value = os.environ.get(name, "")
        require(value and len(value.split(os.pathsep)) == 1, "Select one lavapipe ICD explicitly with " + name)
        path = Path(value)
        require(path.is_absolute(), "Software ICD selection must use an absolute manifest path")
        selected.append(path.resolve(strict=True))
    require(selected[0] == selected[1], "Vulkan driver manifest selectors differ")
    path = selected[0]
    require(re.fullmatch(r"lvp_icd(?:\.[A-Za-z0-9_-]+)?\.json", path.name) is not None,
            "Selected manifest is not the lavapipe ICD")
    manifest = read_json(path, maximum=65536)
    require(isinstance(manifest, dict) and isinstance(manifest.get("ICD"), dict), "Malformed software ICD manifest")
    library = manifest["ICD"].get("library_path", "")
    require(isinstance(library, str) and re.fullmatch(r"libvulkan_lvp\.so(?:\.[0-9]+)*", Path(library).name),
            "Selected ICD does not name the lavapipe shared library")
    overrides = {key: value for key, value in os.environ.items() if value and
                 ((key.startswith("VK_") and key not in names) or key in
                  ("MESA_LOADER_DRIVER_OVERRIDE", "MESA_VK_DEVICE_SELECT", "MESA_VK_DEVICE_SELECT_FORCE_DEFAULT_DEVICE", "DRI_PRIME"))}
    require(not overrides, "Additional Vulkan driver/layer/device overrides are not isolated")
    return {"platform": sys.platform, "icd": pin(path), "library_path": library,
            "selectors": {key: os.environ[key] for key in names}, "additional_overrides": {}}


def qualify(args):
    out = run.fresh_directory(args.out)
    result = {"schema": SCHEMA, "status": "FAIL", "started_utc": run.utc(), "steps": [],
              "physical_stop_active": True, "physical_gpu_qualified": False, "performance_accepted": False,
              "root_cause": "UNDETERMINED", "automatic_retries": 0,
              "plan": [{"name": name, "scene": scene, "publication_witness": witness,
                        "extent": [640, 480], "warmup_frames": 120, "frames": 1,
                        "timeout_seconds": 600, "mode": "state", "gpu_timestamps": False}
                       for name, scene, witness in PLAN],
              "budget_scope": "Prospective hosted software-only 600s/process budget; not the held physical 180s protocol",
              "evidence_scope": "Matching authored inputs and software publication; not failed physical runtime reconstruction"}
    steps = result["steps"]
    try:
        result["software_execution_guard"] = hosted_software_guard()
        require(not any(key.startswith("CFX_") and value for key, value in os.environ.items()),
                "Publication qualification forbids inherited diagnostic environment")
        require(re.fullmatch(r"[0-9a-f]{40}", args.expected_commit), "Expected clean source commit is required")
        result["hosted_run"] = {key: os.environ.get(key) for key in
                              ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "RUNNER_NAME", "RUNNER_ENVIRONMENT")}
        result["expected_commit"] = args.expected_commit
        # Durable prospective plan exists before the first provenance or renderer process.
        write_json(out / "preregistration.json", copy.deepcopy(result))
        steps.append(native_ci.attempt(out, "preflight", lambda: native_ci.preflight(args, out)))
        require(steps[-1]["status"] == "PASS", "Software-only preflight failed; no renderer may launch")
        prepared = out / "prepared"
        prepare.prepare(prepared, ["compositing", "shadow-boundary"])
        result["matching_content"] = verify_historical_content(args.iwad, prepared)
        write_json(out / "matching-content.json", result["matching_content"])
        for name, scene, instrumented in PLAN:
            capture_args = argparse.Namespace(exe=args.exe, iwad=args.iwad, prepared=prepared,
                out=out / "captures" / name, scene=scene, mode="state", frames=1, warmup=120,
                timeout=600, gpu=False, include_stress=True, image_policy="exact",
                collision_snapshot=instrumented, publication_witness=instrumented,
                expected_commit=args.expected_commit, require_clean=True)
            steps.append(native_ci.attempt(out, name, lambda a=capture_args: run.capture(a), ("COLLECTED",)))
            require(steps[-1]["status"] == "PASS", "Publication process failed; subsequent dependent launches suppressed")
            if instrumented:
                proof = validate_witness(capture_args.out)
                write_json(out / (name + "-publication.json"), proof)
                controls = negative_controls(capture_args.out)
                write_json(out / (name + "-negative-controls.json"), controls)
                comparison = compare_control(out / "captures/shadow-control", capture_args.out)
                write_json(out / (name + "-control-comparison.json"), comparison)
                require(comparison["status"] == "PASS", "Instrumented witness changed protected state or exact RGB")
        comparison = run.compare_runs(out / "captures/shadow-witness-1", out / "captures/shadow-witness-2")
        write_json(out / "witness-repeat-comparison.json", comparison)
        require(comparison["status"] == "PASS", "Independent publication witnesses are not repeatable")
        result["status"] = "PASS"
    except (OSError, ValueError) as error:
        result["error"] = str(error)
    finally:
        result["finished_utc"] = run.utc()
        write_json(out / "qualification.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch-content", help="download and authenticate the public historical Freedoom release once")
    fetch.add_argument("--out", type=Path, required=True)
    collect = sub.add_parser("qualify", help="four fixed correctness processes on GitHub-hosted llvmpipe only")
    for name in ("exe", "iwad", "iwad-license", "out"):
        collect.add_argument("--" + name, type=Path, required=True)
    collect.add_argument("--expected-commit", required=True)
    check = sub.add_parser("validate", help="read-only CPU validation of a retained publication run")
    check.add_argument("run", type=Path)
    check.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch-content":
            result = fetch_content(args.out)
        elif args.command == "qualify":
            result = qualify(args)
        else:
            root, _, _, _ = run.validate_run(args.run)
            result = validate_witness(root)
            write_json(args.out, result)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(result["status"], flush=True)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
