"""Actual typed wrappers/builders with CPU callbacks; no loader or device."""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class PublicationWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.exe = cls.directory / ("publication.exe" if os.name == "nt" else "publication")
        source = (ROOT / "libraries/ZVulkan/src/vulkanbuilders.cpp").read_text(encoding="utf-8")
        # Compile these complete implementation sections verbatim, omitting the
        # independent GLSL compiler/device builders and their external libraries.
        sections = [
            ("static std::unique_ptr<VulkanShader> CreateShaderModule(", "DescriptorSetLayoutBuilder::DescriptorSetLayoutBuilder()"),
            ("ColorBlendAttachmentBuilder::ColorBlendAttachmentBuilder()", "PipelineLayoutBuilder::PipelineLayoutBuilder()"),
            ("WriteDescriptors& WriteDescriptors::AddBuffer(", "VulkanInstanceBuilder::VulkanInstanceBuilder()"),
        ]
        (cls.directory / "cfx_witness_production.inc").write_text("\n".join(source[source.index(a):source.index(b)] for a, b in sections), encoding="utf-8")
        compiler = os.environ.get("CFX_CXX") or shutil.which("cl" if os.name == "nt" else "c++")
        if not compiler:
            raise RuntimeError("Publication witness CPU fixture needs a C++17 compiler")
        fixture = str(ROOT / "tools/pf_oracle/tests/cfx_publication_fixture.cpp")
        includes = [ROOT / "libraries/ZVulkan/include", cls.directory]
        if Path(compiler).name.lower() in ("cl", "cl.exe"):
            command = [compiler, "/nologo", "/std:c++17", "/EHsc", "/W4", "/UNDEBUG", fixture,
                       *["/I" + str(p) for p in includes], "/Fe:" + str(cls.exe), "/Fo:" + str(cls.directory / "publication.obj")]
        else:
            command = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-missing-field-initializers", "-Wno-unused-parameter",
                       "-UNDEBUG", fixture, *["-I" + str(p) for p in includes], "-o", str(cls.exe)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_fixture(self, scenario="positive", *, enabled=True, resources=True, prepare=None):
        directory = self.directory / self._testMethodName
        directory.mkdir(exist_ok=True)
        env = os.environ.copy()
        for key in ("CFX_TRACE_FILE", "CFX_RUN_ID", "CFX_RESOURCE_TRACE", "CFX_ADDRESS_TRACE", "CFX_ADDRESS_FILE", "CFX_WITNESS_DIR"):
            env.pop(key, None)
        env["CFX_WITNESS_DIR"] = str(directory)
        if enabled:
            env.update(CFX_TRACE_FILE=str(directory / "legacy.tsv"), CFX_RUN_ID="synthetic-publication", CFX_RESOURCE_TRACE="1" if resources else "0")
        if prepare:
            prepare(directory)
        result = subprocess.run([str(self.exe), scenario], env=env, capture_output=True, text=True, check=True, timeout=10)
        path = directory / "publication-witness.tsv"
        text = path.read_text() if path.exists() else ""
        rows = []
        if text.startswith("# cfx-publication-v1\nseq\tevent\tdetail\n"):
            for line in text.splitlines()[2:]:
                seq, event, detail = line.split("\t")
                rows.append((int(seq), event, dict(part.split("=", 1) for part in detail.split())))
        return directory, result.stdout, text, rows

    def test_exact_shader_specialization_and_actual_bind_consumption(self):
        directory, _, _, rows = self.run_fixture()
        self.assertEqual([seq for seq, _, _ in rows], list(range(1, len(rows) + 1)))
        code = [row for _, event, row in rows if event == "shader-bytes"]
        self.assertEqual(len(code), 2)
        self.assertEqual(len({row["shader_id"] for row in code}), 2)
        self.assertEqual((directory / code[0]["file"]).read_bytes(), struct.pack("<6I", 0x07230203, 0x00010000, 11, 3, 0, 0x12345678))
        self.assertEqual((directory / code[1]["file"]).read_bytes(), struct.pack("<6I", 0x07230203, 0x00010300, 22, 4, 0, 0xabcdef00))
        stages = [row for _, event, row in rows if event == "pipeline-stage"]
        self.assertEqual((directory / stages[0]["specialization_file"]).read_bytes(), struct.pack("<I", 0x13572468))
        self.assertEqual(stages[0]["specialization_entries"], "1")
        self.assertEqual(stages[1]["specialization_file"], "none")
        pubs = [(seq, row) for seq, event, row in rows if event == "descriptor-buffer-published"]
        self.assertEqual([row["binding"] for _, row in pubs], ["2", "3", "4"])
        self.assertEqual({row["generation"] for _, row in pubs}, {"1"})
        consume = next(row for _, event, row in rows if event == "consume")
        self.assertEqual(consume["pipeline_id"], stages[0]["pipeline_id"])
        self.assertEqual(consume["pipeline_alive"], "1")
        bound = next(row for _, event, row in rows if event == "consume-set")
        self.assertEqual((bound["bound_generation"], bound["publication_generation"], bound["set_alive"]), ("1", "1", "1"))
        offsets = [row["offset"] for _, event, row in rows if event == "consume-offset"]
        self.assertEqual(offsets, ["16", "32"])
        copy = next(row for _, event, row in rows if event == "buffer-copy-recorded")
        self.assertEqual(copy["bytes"], "16")  # destination extent, not source32
        marker = (directory / "publication-witness.complete").read_bytes()
        self.assertEqual(marker, f"schema=cfx-publication-complete-v1\nrecords={len(rows)}\nfailures=0\n".encode())
        self.assertEqual(marker, (directory / "publication-witness.complete.pending").read_bytes())

    def test_linked_libraries_retain_exact_stages_after_module_destruction(self):
        _, _, _, rows = self.run_fixture("library")
        pipelines = [row for _, event, row in rows if event == "pipeline-created"]
        self.assertEqual([row["kind"] for row in pipelines], ["graphics-library", "graphics-library", "graphics"])
        linked = pipelines[-1]
        self.assertEqual((linked["stages"], linked["libraries"]), ("2", "2"))
        stages = [row for _, event, row in rows if event == "pipeline-stage" and row["pipeline_id"] == linked["pipeline_id"]]
        self.assertEqual({row["source_pipeline_id"] for row in stages}, {row["pipeline_id"] for row in pipelines[:-1]})

    def test_descriptor_republication_is_not_silently_stale_bind_evidence(self):
        _, _, _, rows = self.run_fixture("stale")
        bound = next(row for _, event, row in rows if event == "consume-set")
        self.assertEqual((bound["bound_generation"], bound["publication_generation"]), ("1", "2"))

    def test_retired_wrappers_are_observed_without_dereferencing_freed_owners(self):
        _, _, _, rows = self.run_fixture("retired")
        self.assertEqual(next(row for _, event, row in rows if event == "consume")["pipeline_alive"], "0")
        self.assertEqual(next(row for _, event, row in rows if event == "consume-set")["set_alive"], "0")

    def test_recycled_handle_gets_new_allocation_identity(self):
        _, _, _, rows = self.run_fixture("reuse")
        created = [row for _, event, row in rows if event == "resource-create" and row["kind"] == "descriptor-set"]
        self.assertEqual(len(created), 2)
        self.assertEqual(created[0]["handle"], created[1]["handle"])
        self.assertNotEqual(created[0]["id"], created[1]["id"])

    def test_raw_handles_cannot_be_recovered_as_typed_identity(self):
        _, _, _, rows = self.run_fixture("raw")
        consumed = next(row for _, event, row in rows if event == "consume")
        self.assertEqual((consumed["pipeline_id"], consumed["coverage"]), ("0", "unknown"))

    def test_new_recording_clears_prior_bound_state(self):
        _, _, _, rows = self.run_fixture("reset")
        consumed = [row for _, event, row in rows if event == "consume"]
        self.assertEqual([row["recording"] for row in consumed], ["1", "2"])
        self.assertEqual(consumed[1]["pipeline_id"], "0")

    def test_binding_different_layout_disturbs_previously_retained_sets(self):
        _, _, _, rows = self.run_fixture("disturbed")
        bound = [row for _, event, row in rows if event == "consume-set"]
        self.assertEqual([row["set_index"] for row in bound], ["0", "1"])
        self.assertEqual([row["coverage"] for row in bound], ["unknown", "complete"])

    def test_witness_survives_legacy_resource_record_exhaustion(self):
        directory, _, text, _ = self.run_fixture("legacycap")
        self.assertTrue((directory / "publication-witness.complete").exists())
        for event in ("resource-create", "upload-packed", "buffer-copy-recorded", "consume"):
            self.assertIn(event, text)

    def test_witness_off_keeps_identical_vulkan_callback_arguments_and_counts(self):
        directory, stdout, _, _ = self.run_fixture(enabled=False)
        self.assertEqual(stdout, "shaders=2 graphics=1 compute=0 pipeline_binds=1 set_binds=1 draws=1 updates=1 copies=1\n")
        self.assertEqual(list(directory.iterdir()), [])

    def test_resources_off_refuses_witness_even_with_directory(self):
        directory, _, _, _ = self.run_fixture(resources=False)
        self.assertFalse((directory / "publication-witness.tsv").exists())
        self.assertFalse(list(directory.glob("*.spv")))

    def test_exclusive_stream_refuses_to_overwrite_existing_evidence(self):
        directory, _, text, _ = self.run_fixture(prepare=lambda d: (d / "publication-witness.tsv").write_text("sealed-original"))
        self.assertEqual(text, "sealed-original")
        self.assertFalse((directory / "publication-witness.complete").exists())

    def test_completion_conflict_never_produces_success_marker(self):
        directory, _, _, _ = self.run_fixture(prepare=lambda d: (d / "publication-witness.complete.pending").write_bytes(b"sealed-marker"))
        self.assertEqual((directory / "publication-witness.complete.pending").read_bytes(), b"sealed-marker")
        self.assertFalse((directory / "publication-witness.complete").exists())

    def test_completion_during_actual_pipeline_builder_fails_without_waiting(self):
        directory, _, text, _ = self.run_fixture("closemidbuild")
        self.assertIn("reason=in-flight-operation-at-finish", text)
        self.assertFalse((directory / "publication-witness.complete").exists())

    def test_record_cap_has_no_completion_marker(self):
        directory, _, text, _ = self.run_fixture("recordcap")
        self.assertIn("reason=record-limit", text)
        self.assertFalse((directory / "publication-witness.complete").exists())

    def test_byte_cap_has_no_completion_marker(self):
        directory, _, text, _ = self.run_fixture("streamcap")
        self.assertIn("reason=stream-byte-limit", text)
        self.assertFalse((directory / "publication-witness.complete").exists())

    def test_blob_budget_rejects_before_reading_invalid_pointer(self):
        directory, _, text, _ = self.run_fixture("blobcap")
        self.assertIn("reason=blob-budget-or-unavailable", text)
        self.assertFalse((directory / "publication-witness.complete").exists())

    def test_upload_budget_rejects_before_reading_invalid_pointer(self):
        directory, _, text, _ = self.run_fixture("uploadcap")
        self.assertIn("reason=upload-hash-budget-or-unavailable", text)
        self.assertFalse((directory / "publication-witness.complete").exists())


if __name__ == "__main__":
    unittest.main()
