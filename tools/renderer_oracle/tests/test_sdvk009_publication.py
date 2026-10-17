"""CPU-only publication evidence falsification; all native data is synthetic.

No renderer, Vulkan loader, device or release download is executed by this test.
The fixture represents one triangle over121 distinct observed frames solely to
exercise evidence joins, mutation rejection, orchestration and content pins.
"""
from argparse import Namespace
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import collision_replay
from tools.renderer_oracle import sdvk009_publication as publication
from tools.renderer_oracle.common import EvidenceError, pin, read_json


def synthetic_snapshot(event):
    h = dict(version=1, event=event, object_id=1, phase=0 if event == 1 else 2,
             vertex_stride=32, vertex_extent=3, index_extent=3, index_count=3,
             indexes_per_blas=3, instance_count=1, slot_extent=32, tlas_count=1,
             tlas_root=0, node_backing_extent=2, root=1, section_count=11)
    sections = {key: b"" for key in collision_replay.STRIDES}
    sections[b"VERT"] = b"".join(struct.pack("<Ifff", i, *point) for i, point in enumerate(
        ((0., 0., 0.), (1., 0., 0.), (0., 0., 1.))))
    sections[b"INDX"] = struct.pack("<3I", 0, 1, 2)
    if event == 1:
        sections[b"VDIR"] = sections[b"IDIR"] = struct.pack("<2i", 0, 3)
        sections[b"NDIR"] = struct.pack("<2i", 0, 2)
    bbox = (0., 0., 0., 1., 1., 0., .5, .5, 0., .5, .5, 0.)
    sections[b"TLAS"] = sections[b"BLAS"] = struct.pack("<12f3i", *bbox, -1, -1, 0)
    sections[b"SLOT"] = struct.pack("<IiIII", 0, 0, 0, 1, 0) + b"".join(
        struct.pack("<IiIII", i, -1, 1, 0, i * 3) for i in range(1, 32))
    sections[b"NODE"] = b"".join(struct.pack("<6f3i", .5, 0., .5, .5, 0., .5, -1, -1, element)
                                  for element in (-1, 0))
    snapshot = collision_replay.Snapshot(h, sections)
    collision_replay.validate_snapshot(snapshot)
    return snapshot


def synthetic_spirv():
    # Structurally parsed synthetic module, not executable SPIR-V qualification.
    words = [0x07230203, 0x00010000, 0, 8, 0,
             (5 << 16) | 15, 4, 1, 0x6e69616d, 0]
    for identity, binding in ((2, 2), (3, 3), (4, 4)):
        words.extend(((4 << 16) | 71, identity, 34, 0,
                      (4 << 16) | 71, identity, 33, binding))
    return struct.pack("<" + "I" * len(words), *words)


def synthetic_packet(root):
    directory = root / "publication"
    directory.mkdir()
    (directory / "cfx-trace.tsv").write_text("# SYNTHETIC CPU TEST TRACE; no Vulkan or native process\n")
    rows = []

    def add(event, **fields):
        rows.append({"seq": len(rows) + 1, "event": event,
                     "fields": {key: str(value) for key, value in fields.items()}})

    def create(identity, kind, size=0):
        add("resource-create", kind=kind, id=identity, handle=hex(identity), bytes=size)

    sizes = (112, 96, 12)
    for identity, size in enumerate(sizes, 1):
        create(identity, "buffer", size)
    create(4, "buffer", sum(sizes))
    create(5, "descriptor-set")
    create(6, "pipeline-layout")
    create(7, "shader")
    spirv = synthetic_spirv()
    (directory / "shader-7.spv").write_bytes(spirv)
    add("shader-bytes", shader_id=7, bytes=len(spirv), coverage="complete",
        fnv1a64=hex(publication.fnv1a64(spirv)), file="shader-7.spv")
    specialization = struct.pack("<I", 3)

    def stage(pipeline, source):
        add("pipeline-stage", pipeline_id=pipeline, ordinal=0, source_pipeline_id=source, stage=16, shader_id=7,
            entry="main", specialization_entries=1, specialization_bytes=4,
            specialization_file=f"pipeline-{source}-stage-0.spec",
            specialization_fnv1a64=hex(publication.fnv1a64(specialization)), coverage="complete")
        add("pipeline-specialization", pipeline_id=pipeline, stage_ordinal=0, ordinal=0,
            constant_id=1, offset=0, bytes=4)

    # A genuine linked-library closure and an unrelated library with otherwise
    # identical stage bytes make provenance substitution falsifiable.
    for library in (500, 502):
        create(library, "pipeline")
        add("pipeline-created", pipeline_id=library, kind="graphics-library", layout_id=6,
            flags=2048, library_flags=4, stages=1, libraries=0, coverage="complete")
        (directory / f"pipeline-{library}-stage-0.spec").write_bytes(specialization)
        stage(library, library)
    add("resource-destroy", kind="shader", id=7, handle=hex(7), bytes=0)
    create(501, "pipeline")
    add("pipeline-created", pipeline_id=501, kind="graphics-library", layout_id=6,
        flags=2048, library_flags=4, stages=1, libraries=1, coverage="complete")
    stage(501, 500)
    add("pipeline-library", pipeline_id=501, ordinal=0, library_id=500)
    create(504, "pipeline")
    add("pipeline-created", pipeline_id=504, kind="graphics-library", layout_id=0,
        flags=2048, library_flags=1, stages=0, libraries=0, coverage="complete")
    create(8, "pipeline")
    add("pipeline-created", pipeline_id=8, kind="graphics", layout_id=6, flags=0,
        library_flags=0, stages=1, libraries=1, coverage="complete")
    stage(8, 500)
    add("pipeline-library", pipeline_id=8, ordinal=0, library_id=501)
    for identity, binding, size in zip((1, 2, 3), (2, 3, 4), sizes):
        add("descriptor-buffer-published", set_id=5, generation=1, binding=binding, array=0,
            type=7, buffer_id=identity, offset=0, range=size)
    add("descriptor-published", set_id=5, generation=1, write_count=3, api="void")
    create(506, "command")
    add("command-begin", cmd_id=506, recording=1, frame=0)
    add("bind-pipeline", cmd_id=506, recording=1, ordinal=1, bind_point=0, pipeline_id=8, coverage="complete")
    add("bind-set", cmd_id=506, recording=1, ordinal=2, bind_point=0, layout_id=6, set_index=0,
        set_id=5, generation=1, dynamic_count=0, coverage="complete")
    add("consume", cmd_id=506, recording=1, ordinal=3, frame=0, bind_point=0,
        kind="draw-indexed", pipeline_id=8, pipeline_bind_ordinal=1, pipeline_alive=1, coverage="complete")
    add("consume-set", cmd_id=506, recording=1, ordinal=3, bind_point=0, set_index=0,
        set_id=5, layout_id=6, bind_ordinal=2, bound_generation=1, publication_generation=1,
        set_alive=1, dynamic_count=0, coverage="complete")
    add("command-end", cmd_id=506, recording=1, ordinal=3)
    create(9, "command")
    add("command-begin", cmd_id=9, recording=1, frame=1)
    offset = 0
    for identity, size in enumerate(sizes, 1):
        add("upload-packed", src_id=4, dst_id=identity, src_offset=offset, dst_offset=0, bytes=size,
            coverage="complete", fnv1a64=hex(publication.fnv1a64(bytes(size))))
        add("buffer-copy-recorded", cmd_id=9, recording=1, src_id=4, dst_id=identity,
            src_offset=offset, dst_offset=0, bytes=size)
        offset += size
    add("command-end", cmd_id=9, recording=1, ordinal=0)
    for frame in range(1, 122):
        snapshot = synthetic_snapshot(frame)
        (root / f"collision-{frame}.bin").write_bytes(snapshot.encode())
        raw, regions, counts = publication._semantic_readback(snapshot, (1, 2, 3))
        metadata = dict(frame=frame, ordinal=frame, phase="warmup" if frame <= 120 else "retained",
                        warmup=120, requested=1, map="SDVSHDW")
        add("observer-frame", **metadata)
        draw, readback, staging = 10 + (frame - 1) * 3, 11 + (frame - 1) * 3, 12 + (frame - 1) * 3
        create(draw, "command")
        add("command-begin", cmd_id=draw, recording=1, frame=frame)
        add("bind-pipeline", cmd_id=draw, recording=1, ordinal=1, bind_point=0, pipeline_id=8, coverage="complete")
        add("bind-set", cmd_id=draw, recording=1, ordinal=2, bind_point=0, layout_id=6, set_index=0,
            set_id=5, generation=1, dynamic_count=0, coverage="complete")
        add("consume", cmd_id=draw, recording=1, ordinal=3, frame=frame, bind_point=0,
            kind="draw-indexed", pipeline_id=8, pipeline_bind_ordinal=1, pipeline_alive=1,
            coverage="complete", indices=3, instances=1, first_index=0, vertex_offset=0, first_instance=0)
        add("consume-set", cmd_id=draw, recording=1, ordinal=3, bind_point=0, set_index=0,
            set_id=5, layout_id=6, bind_ordinal=2, bound_generation=1, publication_generation=1,
            set_alive=1, dynamic_count=0, coverage="complete")
        add("observer-frame-end", **metadata)
        add("consume", cmd_id=draw, recording=1, ordinal=4, frame=frame, bind_point=0,
            kind="draw-indexed", pipeline_id=8, pipeline_bind_ordinal=1, pipeline_alive=1, coverage="complete")
        add("consume-set", cmd_id=draw, recording=1, ordinal=4, bind_point=0, set_index=0,
            set_id=5, layout_id=6, bind_ordinal=2, bound_generation=1, publication_generation=1,
            set_alive=1, dynamic_count=0, coverage="complete")
        add("command-end", cmd_id=draw, recording=1, ordinal=4)
        create(staging, "buffer", len(raw))
        create(readback, "command")
        add("command-begin", cmd_id=readback, recording=1, frame=frame)
        add("postuse-plan", readback_id=frame, snapshot_object=1, snapshot_event=frame, root=1,
            node_id=1, vertex_id=2, index_id=3, staging_id=staging, cmd_id=readback, recording=1,
            bytes=len(raw), ranges=len(regions), **counts)
        for region in regions:
            add("postuse-range", readback_id=frame, **region)
            add("buffer-copy-recorded", cmd_id=readback, recording=1, src_id=region["src_id"],
                dst_id=staging, src_offset=region["src_offset"], dst_offset=region["dst_offset"], bytes=region["bytes"])
        add("command-end", cmd_id=readback, recording=1, ordinal=0)
        commands = [9, 506, draw, readback] if frame == 1 else [draw, readback]
        fence = dict(submission=frame, fence_slot=0, fence="0xf001")
        for index, command in enumerate(commands):
            add("submit-command", cmd_id=command, recording=1, index=index, buffers=len(commands), **fence)
        add("postuse-submit", readback_id=frame, cmd_id=readback, recording=1, **fence)
        if frame in (1, 121):
            targets = (4,) if frame == 1 else (1, 2, 3, 5, 5, 6, 8, draw, readback, staging)
            for identity in targets:
                source = next(row for row in rows if row["event"] == "resource-create" and row["fields"]["id"] == str(identity))
                add("resource-name", **source["fields"])
        add("fence-complete", wait="frame", result=0, **fence)
        add("postuse-fence", readback_id=frame, **fence)
        add("resource-name", kind="buffer", id=staging, handle=hex(staging), bytes=len(raw))
        (directory / f"readback-{frame}.bin").write_bytes(raw)
        add("postuse-readback", readback_id=frame, bytes=len(raw), fnv1a64=hex(publication.fnv1a64(raw)),
            file=f"readback-{frame}.bin")
        add("observer-frame-presented", **metadata)
    create(510, "shader")
    postprocess = struct.pack("<10I", 0x07230203, 0x00010000, 0, 2, 0,
                              (5 << 16) | 15, 4, 1, 0x6e69616d, 0)
    (directory / "shader-510.spv").write_bytes(postprocess)
    add("shader-bytes", shader_id=510, bytes=len(postprocess), coverage="complete",
        fnv1a64=hex(publication.fnv1a64(postprocess)), file="shader-510.spv")
    create(511, "pipeline")
    add("pipeline-created", pipeline_id=511, kind="graphics", layout_id=6, flags=0,
        library_flags=0, stages=1, libraries=0, coverage="complete")
    add("pipeline-stage", pipeline_id=511, ordinal=0, source_pipeline_id=511, stage=16, shader_id=510,
        entry="main", specialization_entries=0, specialization_bytes=0, specialization_file="none",
        specialization_fnv1a64=hex(publication.fnv1a64(b"")), coverage="complete")
    create(507, "command")
    add("command-begin", cmd_id=507, recording=1, frame=121)
    add("bind-pipeline", cmd_id=507, recording=1, ordinal=1, bind_point=0, pipeline_id=511, coverage="complete")
    add("consume", cmd_id=507, recording=1, ordinal=2, frame=121, bind_point=0,
        kind="draw", pipeline_id=511, pipeline_bind_ordinal=1, pipeline_alive=1, coverage="complete")
    add("command-end", cmd_id=507, recording=1, ordinal=2)
    add("submit-command", cmd_id=507, recording=1, index=0, buffers=1, submission=122, fence_slot=0, fence="0xf001")
    add("fence-complete", wait="frame", result=0, submission=122, fence_slot=0, fence="0xf001")
    add("observer-complete", complete=1, failure=0, seen=121, collected=1, warmup=120, requested=1)
    add("witness-summary", records=len(rows), failures=0, closed=1)
    text = "# cfx-publication-v1\nseq\tevent\tdetail\n" + "".join(
        str(row["seq"]) + "\t" + row["event"] + "\t" + " ".join(k + "=" + v for k, v in row["fields"].items()) + "\n"
        for row in rows)
    (directory / "publication-witness.tsv").write_text(text)
    completion = "schema=cfx-publication-complete-v1\nrecords=" + str(len(rows)) + "\nfailures=0\n"
    for leaf in ("publication-witness.complete", "publication-witness.complete.pending"):
        (directory / leaf).write_text(completion)
    return rows


class PublicationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="sdvk009-publication-synthetic-")
        cls.root = Path(cls.temporary.name)
        cls.rows = synthetic_packet(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def mutate(self, event, changes, predicate=lambda row: True):
        rows = list(self.rows)
        index = next(i for i, row in enumerate(rows) if row["event"] == event and predicate(row))
        rows[index] = {**rows[index], "fields": {**rows[index]["fields"], **changes}}
        return rows

    def test_synthetic_complete_chain_and_all_derived_negative_controls(self):
        result = publication.validate_witness(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual((result["warmup_frames"], result["retained_frames"], result["qualified_collision_consumes"]), (120, 1, 121))
        self.assertEqual(result["joined_staging_uploads"], 3)
        self.assertFalse(result["physical_gpu_qualified"])
        self.assertEqual(result["outside_observer_consumes"], 123)
        before = pin(self.root / "publication/publication-witness.tsv")
        negative = publication.negative_controls(self.root)
        self.assertEqual(len(negative["controls"]), 9)
        self.assertTrue(all(item["status"] == "PASS" for item in negative["controls"]))
        targeted = next(item for item in negative["controls"] if item["name"] == "unknown-bound-pipeline-coverage")
        self.assertEqual(targeted["mutation"]["seq"], result["negative_control_target"]["consume_seq"])
        self.assertNotEqual(targeted["mutation"]["seq"], next(row["seq"] for row in self.rows if row["event"] == "consume"))
        self.assertEqual(before, pin(self.root / "publication/publication-witness.tsv"))

    def test_ranges_descriptor_stride_generation_and_missing_staging_fail_closed(self):
        variants = [self.mutate("descriptor-buffer-published", {"buffer_id": "2"}),
                    self.mutate("descriptor-buffer-published", {"range": "16"}),
                    self.mutate("postuse-range", {"src_offset": "32"}, lambda row: row["fields"]["kind"] == "node_center"),
                    self.mutate("upload-packed", {"coverage": "omitted-budget"}),
                    self.mutate("buffer-copy-recorded", {"src_id": "2"}),
                    self.mutate("command-end", {"ordinal": "5"}, lambda row: row["fields"]["ordinal"] == "4"),
                    self.mutate("descriptor-published", {"write_count": "2"}),
                    self.mutate("consume-set", {"publication_generation": "2"}),
                    self.mutate("postuse-submit", {"fence": "0xf002"})]
        for rows in variants:
            with self.subTest(mutation=next(row for a, row in zip(self.rows, rows) if a != row)), self.assertRaises(EvidenceError):
                publication.validate_witness(self.root, records=rows)

    def test_linked_stage_provenance_and_specialization_are_exact(self):
        for event, changes, predicate, message in (
                ("pipeline-stage", {"source_pipeline_id": "502"}, lambda row: row["fields"]["pipeline_id"] == "8", "library closure"),
                ("pipeline-stage", {"specialization_file": "pipeline-502-stage-0.spec"}, lambda row: row["fields"]["pipeline_id"] == "8", "originating library"),
                ("pipeline-specialization", {"constant_id": "2"}, lambda row: row["fields"]["pipeline_id"] == "8", "originating library"),
                ("pipeline-library", {"library_id": "502"}, lambda row: row["fields"]["pipeline_id"] == "8", "library closure")):
            with self.subTest(event=event, changes=changes), self.assertRaisesRegex(EvidenceError, message):
                publication.validate_witness(self.root, records=self.mutate(event, changes, predicate))

    def test_allocation_lifetimes_and_descriptor_generation_reach_exact_fence(self):
        for identity in (1, 2, 3, 4, 5, 6, 8, 370, 371, 372):
            rows = list(self.rows)
            index = next(i for i, row in enumerate(rows) if row["event"] == "resource-name" and row["fields"]["id"] == str(identity))
            rows[index] = {**rows[index], "event": "resource-destroy"}
            # Drop later informational names for this allocation without removing
            # a sequence: retirement-list receipts have no resource lifetime.
            for later in range(index + 1, len(rows)):
                if rows[later]["event"] == "resource-name" and rows[later]["fields"]["id"] == str(identity):
                    rows[later] = {**rows[later], "event": "retirement-list-release",
                                   "fields": {"kind": "draw-list", "id": "9000", "handle": "0x0", "bytes": "0"}}
            with self.subTest(allocation=identity), self.assertRaisesRegex(EvidenceError, "lifetime"):
                publication.validate_witness(self.root, records=rows)
        rows = list(self.rows)
        placeholders = [i for i, row in enumerate(rows) if row["event"] == "resource-name" and row["fields"]["id"] == "5"]
        rows[placeholders[0]] = {**rows[placeholders[0]], "event": "descriptor-other-published",
                                "fields": {"set_id": "5", "generation": "2", "binding": "90", "array": "0",
                                           "type": "0", "scope": "outside-collision-buffers"}}
        rows[placeholders[1]] = {**rows[placeholders[1]], "event": "descriptor-published",
                                "fields": {"set_id": "5", "generation": "2", "write_count": "1", "api": "void"}}
        with self.assertRaisesRegex(EvidenceError, "generation is stale"):
            publication.validate_witness(self.root, records=rows)
        rows = list(self.rows)
        index = max(i for i, row in enumerate(rows) if row["event"] == "resource-name" and row["fields"]["id"] == "372")
        rows[index] = {**rows[index], "event": "resource-destroy"}
        with self.assertRaisesRegex(EvidenceError, "lifetime"):
            publication.validate_witness(self.root, records=rows)

    def test_consume_layout_and_frame_interval_cannot_be_relabelled(self):
        rows = list(self.rows)
        for index, row in enumerate(rows):
            if row["event"] in ("bind-set", "consume-set") and row["fields"]["cmd_id"] == "10":
                rows[index] = {**row, "fields": {**row["fields"], "layout_id": "505"}}
        with self.assertRaisesRegex(EvidenceError, "layout identity"):
            publication.validate_witness(self.root, records=rows)
        with self.assertRaisesRegex(EvidenceError, "authenticated frame interval"):
            publication.validate_witness(self.root, records=self.mutate("consume", {"frame": "2"}, lambda row: row["fields"]["frame"] == "1"))
        rows = list(self.rows)
        end = next(i for i, row in enumerate(rows) if row["event"] == "observer-frame-end")
        present = next(i for i, row in enumerate(rows) if row["event"] == "observer-frame-presented")
        rows[end] = {**rows[end], "event": "observer-frame-presented"}
        rows[present] = {**rows[present], "event": "observer-frame-end"}
        with self.assertRaisesRegex(EvidenceError, "reordered or overlapping"):
            publication.validate_witness(self.root, records=rows)
        with self.assertRaisesRegex(EvidenceError, "stale previous-frame"):
            publication.validate_witness(self.root, records=self.mutate("postuse-plan", {"snapshot_event": "1"},
                                        lambda row: row["fields"]["readback_id"] == "2"))

    def test_fence_slot_cannot_be_reused_before_previous_completion(self):
        rows = list(self.rows)
        index = next(i for i, row in enumerate(rows) if row["event"] == "fence-complete")
        fence = rows.pop(index)
        before_second_fence = next(i for i, row in enumerate(rows) if row["event"] == "fence-complete")
        rows.insert(before_second_fence, fence)
        rows = [{**row, "seq": i + 1} for i, row in enumerate(rows)]
        with self.assertRaisesRegex(EvidenceError, "Fence slot reused"):
            publication.validate_witness(self.root, records=rows)

    def test_parser_and_blob_tampering_without_receipt_trust(self):
        with tempfile.TemporaryDirectory(prefix="sdvk009-publication-parser-") as temporary:
            path = Path(temporary) / "input.tsv"
            for payload in ("# cfx-publication-v1\nseq\tevent\tdetail\n1\tevent\tk=1 k=2\n",
                            "# cfx-publication-v1\nseq\tevent\tdetail\n2\tevent\tk=1\n",
                            "# cfx-publication-v1\nseq\tevent\tdetail\n1\tevent\tk=1"):
                path.write_text(payload)
                with self.assertRaises(EvidenceError):
                    publication.parse_witness(path)
        target = self.root / "publication/readback-1.bin"
        original = target.read_bytes()
        try:
            target.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            altered = self.mutate("postuse-readback", {"fnv1a64": hex(publication.fnv1a64(target.read_bytes()))})
            with self.assertRaisesRegex(EvidenceError, "defined destination bytes"):
                publication.validate_witness(self.root, records=altered)
        finally:
            target.write_bytes(original)

    def test_disturbed_dynamic_offsets_are_unknown_not_invented(self):
        complete = {"binds": {1: {}}, "sets": {1: {"dynamic_count": "2", "coverage": "complete"}},
                    "offsets": {1: {0: 64, 1: 128}}}
        publication._validate_consumed_dynamic_offsets(complete)
        disturbed = {"binds": {1: {}}, "sets": {1: {"dynamic_count": "5", "coverage": "unknown"}},
                     "offsets": {1: {}}}
        publication._validate_consumed_dynamic_offsets(disturbed)
        missing = copy.deepcopy(complete)
        missing["offsets"][1].pop(1)
        with self.assertRaisesRegex(EvidenceError, "incomplete coverage"):
            publication._validate_consumed_dynamic_offsets(missing)
        partial_unknown = copy.deepcopy(disturbed)
        partial_unknown["offsets"][1][0] = 64
        with self.assertRaisesRegex(EvidenceError, "partial dynamic offsets"):
            publication._validate_consumed_dynamic_offsets(partial_unknown)

    def test_exclusive_completion_and_full_frame_coverage(self):
        target = self.root / "publication/publication-witness.complete"
        before = target.read_bytes()
        try:
            target.unlink()
            with self.assertRaisesRegex(EvidenceError, "exclusive witness close"):
                publication.validate_witness(self.root)
        finally:
            target.write_bytes(before)
        rows = self.mutate("consume", {"frame": "0"}, lambda row: row["fields"]["frame"] == "65")
        with self.assertRaisesRegex(EvidenceError, "authenticated frame interval"):
            publication.validate_witness(self.root, records=rows)

    def test_diagnostic_environment_is_owned_and_ordinary_capture_unchanged(self):
        with tempfile.TemporaryDirectory(prefix="sdvk009-publication-env-") as temporary:
            root = Path(temporary)
            args = Namespace(mode="state", gpu=False, publication_witness=False, collision_snapshot=False)
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(publication.capture_diagnostics(args, root), (None, None))
                args.publication_witness = args.collision_snapshot = True
                diagnostic, environment = publication.capture_diagnostics(args, root)
                self.assertEqual(diagnostic["witness_directory"], "publication")
                self.assertEqual(environment["CFX_RESOURCE_TRACE"], "1")
                self.assertNotIn("CFX_WITNESS_DIR", os.environ)
                with self.assertRaises(FileExistsError):
                    publication.capture_diagnostics(args, root)
            with patch.dict(os.environ, {"CFX_WITNESS_DIR": "inherited"}, clear=True), self.assertRaises(EvidenceError):
                publication.capture_diagnostics(args, root)

    def test_four_process_fixed_preregistration_and_fail_stop(self):
        for fail_at, expected, status in ((None, 4, "PASS"), (2, 2, "FAIL")):
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory(prefix="sdvk009-publication-plan-") as temporary:
                args = Namespace(exe=Path("unused-engine"), iwad=Path("unused.wad"), iwad_license=Path("unused-license"),
                                 expected_commit="a" * 40, out=Path(temporary) / "out")
                calls = []

                def capture(call):
                    calls.append(call)
                    self.assertTrue((args.out / "preregistration.json").is_file())
                    if len(calls) == fail_at:
                        raise EvidenceError("Synthetic process failure")
                    return {"status": "COLLECTED", "synthetic_only": True}

                with ExitStack() as stack, redirect_stdout(io.StringIO()):
                    manifest = Path(temporary) / "lvp_icd.x86_64.json"
                    manifest.write_text(json.dumps({"ICD": {"library_path": "/usr/lib/x86_64-linux-gnu/libvulkan_lvp.so"}}))
                    stack.enter_context(patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                        "VK_DRIVER_FILES": str(manifest), "VK_ICD_FILENAMES": str(manifest)}, clear=True))
                    stack.enter_context(patch.object(publication.sys, "platform", "linux"))
                    stack.enter_context(patch.object(publication.native_ci, "preflight", return_value={"status": "PASS"}))
                    stack.enter_context(patch.object(publication.prepare, "prepare"))
                    stack.enter_context(patch.object(publication, "verify_historical_content", return_value={"synthetic_only": True}))
                    stack.enter_context(patch.object(publication.run, "capture", side_effect=capture))
                    for name in ("validate_witness", "negative_controls", "compare_control"):
                        stack.enter_context(patch.object(publication, name, return_value={"status": "PASS", "synthetic_only": True}))
                    stack.enter_context(patch.object(publication.run, "compare_runs", return_value={"status": "PASS"}))
                    result = publication.qualify(args)
                self.assertEqual((result["status"], len(calls)), (status, expected))
                for call in calls:
                    self.assertEqual((call.warmup, call.frames, call.timeout, call.gpu, call.image_policy), (120, 1, 1800, False, "exact"))
                self.assertEqual([call.publication_witness for call in calls[:2]], [False, False])
                self.assertEqual([call.publication_witness for call in calls[2:]], [True] * max(0, expected - 2))
                self.assertFalse(result["physical_gpu_qualified"])
                self.assertEqual(read_json(args.out / "preregistration.json")["automatic_retries"], 0)

    def test_unhosted_or_inherited_cfx_prevents_any_preflight_or_renderer(self):
        for environment in ({}, {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "self-hosted"},
                            {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted", "CFX_RESOURCE_TRACE": "1"}):
            with self.subTest(environment=environment), tempfile.TemporaryDirectory(prefix="sdvk009-publication-block-") as temporary:
                args = Namespace(expected_commit="a" * 40, out=Path(temporary) / "out")
                with patch.dict(os.environ, environment, clear=True), patch.object(publication.native_ci, "preflight") as preflight:
                    result = publication.qualify(args)
                self.assertEqual(result["status"], "FAIL")
                preflight.assert_not_called()

    def test_nonlinux_or_nonisolated_icd_rejected_before_device_enumeration(self):
        with tempfile.TemporaryDirectory(prefix="sdvk009-publication-icd-") as temporary:
            root = Path(temporary)
            manifest = root / "lvp_icd.x86_64.json"
            manifest.write_text(json.dumps({"ICD": {"library_path": "libvulkan_lvp.so"}}))
            alternate = root / "lvp_icd.other.json"
            alternate.write_bytes(manifest.read_bytes())
            normal = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                      "VK_DRIVER_FILES": str(manifest), "VK_ICD_FILENAMES": str(manifest)}
            variants = [("darwin", {}), ("linux", {"VK_DRIVER_FILES": ""}),
                        ("linux", {"VK_DRIVER_FILES": str(manifest) + ":" + str(alternate)}),
                        ("linux", {"VK_ICD_FILENAMES": str(alternate)}),
                        ("linux", {"VK_ADD_DRIVER_FILES": str(alternate)}),
                        ("linux", {"VK_LOADER_DRIVERS_SELECT": "*"}),
                        ("linux", {"MESA_LOADER_DRIVER_OVERRIDE": "iris"})]
            for index, (platform, changed) in enumerate(variants):
                with self.subTest(platform=platform, changed=changed), patch.dict(os.environ, {**normal, **changed}, clear=True), \
                        patch.object(publication.sys, "platform", platform), patch.object(publication.native_ci, "preflight") as preflight:
                    result = publication.qualify(Namespace(expected_commit="a" * 40, out=root / str(index)))
                    self.assertEqual(result["status"], "FAIL")
                    preflight.assert_not_called()
            manifest.write_text(json.dumps({"ICD": {"library_path": "libvulkan_intel.so"}}))
            with patch.dict(os.environ, normal, clear=True), patch.object(publication.sys, "platform", "linux"), \
                    patch.object(publication.native_ci, "preflight") as preflight:
                self.assertEqual(publication.qualify(Namespace(expected_commit="a" * 40, out=root / "hardware-library"))["status"], "FAIL")
                preflight.assert_not_called()


if __name__ == "__main__":
    unittest.main()
