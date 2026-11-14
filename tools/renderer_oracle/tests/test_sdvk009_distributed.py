"""CPU adversarial controls for distributed publication qualification.

Native captures are explicitly synthetic: the native process and full native
receipt admission are mocked. Registration, workload binding, evidence hashes,
restoration, comparison policy, witness falsification and failure handling run
their real implementations. No executable, Vulkan device or download is used.
"""
from argparse import Namespace
from contextlib import ExitStack, redirect_stdout
import copy
import io
import itertools
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_evidence import png
from test_sdvk009_publication import synthetic_packet
from test_validation import observation
from tools.renderer_oracle import sdvk009_distributed as distributed
from tools.renderer_oracle.common import EvidenceError, canonical, pin, read_json, sha256


COMMIT = "a" * 40


def rewrite(path, value):
    path.write_bytes(canonical(value))


def reseal(path, value):
    rewrite(path, value)
    Path(str(path) + ".sha256").write_text(sha256(path.read_bytes()) + "  " + path.name + "\n")


def refresh_inventory(root):
    manifest = read_json(root / "manifest.json")
    manifest["files"] = distributed.inventory(root, exclude=("manifest.json", "manifest.json.sha256"))
    reseal(root / "manifest.json", manifest)


class DistributedControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sdvk009-distributed-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.environment = {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "1",
                            "GITHUB_SHA": COMMIT, "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_NAME": "build"}
        self.stack.enter_context(patch.dict(os.environ, self.environment, clear=True))
        self.stack.enter_context(patch.object(distributed, "source_identity", return_value={"commit": COMMIT, "tree": "b" * 40}))
        self.stack.enter_context(patch.object(distributed, "host_identity", side_effect=lambda:
            {"boot_id": str(uuid.uuid5(uuid.NAMESPACE_URL, os.environ["RUNNER_NAME"]))}))
        self.stack.enter_context(patch.object(distributed.publication, "hosted_software_guard", return_value={"synthetic_only": True}))
        self.stack.enter_context(patch.object(distributed.native_ci, "preflight", side_effect=self.preflight))
        self.stack.enter_context(patch.object(distributed, "matching_content", side_effect=self.content))
        self.stack.enter_context(patch.object(distributed.run, "capture", side_effect=self.capture))
        self.stack.enter_context(patch.object(distributed.run, "validate_run", side_effect=self.validate_synthetic))
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.exe = self.runtime / "synthetic-engine"
        self.iwad = self.root / "synthetic.wad"
        self.license = self.root / "COPYING.txt"
        self.archive = self.root / "runtime.tar.gz"
        for path, data in ((self.exe, b"SYNTHETIC engine never executed"),
                           (self.runtime / "vkdoom.pk3", b"SYNTHETIC engine pk3"),
                           (self.iwad, b"SYNTHETIC IWAD never rendered"),
                           (self.license, b"SYNTHETIC license"), (self.archive, b"SYNTHETIC runtime archive")):
            path.write_bytes(data)
        self.calls = []
        self.fail_at = None
        self.interrupt_at = None
        self.synthetic_generations = {}
        self.synthetic_elapsed = {}

    def args(self, **kwargs):
        return Namespace(exe=self.exe, iwad=self.iwad, iwad_license=self.license, runtime_archive=self.archive,
                         expected_commit=COMMIT, **kwargs)

    def content(self, iwad, prepared):
        return {"iwad": {"bytes": distributed.publication.IWAD_BYTES, "sha256": distributed.publication.IWAD_SHA256},
                "historical_manifest": distributed.file_identity(distributed.publication.HISTORICAL_MANIFEST),
                "inputs": {scene + "/" + name: pin(prepared / "scenes" / scene / name, relative_to=prepared)
                           for scene in ("compositing", "shadow-boundary")
                           for name in ("scene.pk3", "fixture.ini", "capture.cfg")}}

    def register(self, probe=False, startup_probe=False, cohort=False, cohort_probe=False):
        self.plan_path = self.root / "renderer-sdvk009-plan/preregistration.json"
        result = distributed.register(self.args(out=self.plan_path.parent, compatibility_probe=probe,
                                                shadow_startup_probe=startup_probe, cohort=cohort, cohort_probe=cohort_probe))
        self.assertEqual(result["status"], "REGISTERED")
        return result

    @staticmethod
    def preflight(args, out):
        provenance = out / "provenance"
        provenance.mkdir()
        (provenance / "host.json").write_bytes(b'{"synthetic_only":true}\n')
        return {"status": "PASS", "provenance": pin(provenance / "host.json", relative_to=out)}

    def capture(self, args):
        self.calls.append(args)
        phase = "probe" if args.out.parent.parent.name.startswith("renderer-sdvk009-probe-") else "worker"
        self.assertTrue((args.out.parent.parent / (phase + "-registration.json")).is_file())
        self.assertTrue((args.out.parent.parent / "launches" / (args.out.name + ".json")).is_file())
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / "stdout.log").write_text("SYNTHETIC native boundary; no engine executed\n")
        if len(self.calls) == self.interrupt_at:
            raise KeyboardInterrupt()
        if len(self.calls) == self.fail_at:
            raise EvidenceError("SYNTHETIC native process failure")
        shutil.copyfile(args.prepared / "prepared.json", args.out / "prepared.json")
        profile = {"scene": args.scene, "extent": [640, 480], "warmup_frames": args.warmup, "frames": args.frames,
                   "image_policy": {"metric": "exact-rgb8"}, "gpu_timestamps_requested": False,
                   "iwad_sha256": distributed.publication.IWAD_SHA256, "clock": "static_after_initialization"}
        request = {"cwd": str(args.out), "reproduction": profile, "mode": "state", "timeout_seconds": args.timeout,
                   "automatic_retries": 0, "environment": {}, "argv": []}
        if args.publication_witness:
            request["diagnostics"] = {"run_id": "sdvk009-publication-" + uuid.uuid4().hex}
            profile["collision_snapshot"] = "production-cpu-state; no submitted-GPU-byte claim"
            synthetic_packet(args.out)
        rewrite(args.out / "request.json", request)
        (args.out / "native.png").write_bytes(png(bytes(640 * 480 * 3), width=640, height=480))
        build = {"commit": COMMIT, "working_tree": "clean", "backend": "vulkan", "renderer": "SYNTHETIC Vulkan",
                 "device": "SYNTHETIC llvmpipe", "vulkan": {"driver": "SYNTHETIC Mesa", "driverVersion": 1},
                 "application_cache": {"available": True, "path": str(args.out / "cache")}}
        data = {"status": "COLLECTED", "build": build, "reproduction": profile, "mode": "state", "scene": args.scene,
                "executable": pin(self.exe), "elapsed_seconds": self.synthetic_elapsed.get(args.out.name, 0.001),
                "loaded_packages": [{**pin(self.runtime / "vkdoom.pk3"), "lumps": 1}]}
        rewrite(args.out / "run.json", data)
        return data

    def validate_synthetic(self, root):
        root = Path(root)
        if root.name == "run.json":
            root = root.parent
        raw = observation()
        raw["records"][1]["data"]["resource"]["generation"] = self.synthetic_generations.get(root.name, 1)
        return root, read_json(root / "run.json"), raw, {}

    def run_worker(self, name):
        extra = {"peers": self.root / "cohort-peers", "artifact_set": self.root / "cohort-artifacts.json"}
        with patch.dict(os.environ, {"RUNNER_NAME": "hosted-" + name}):
            return distributed.worker(self.args(plan=self.plan_path, worker=name,
                out=self.root / ("renderer-sdvk009-worker-" + name), **extra))

    def run_probe(self, name):
        with patch.dict(os.environ, {"RUNNER_NAME": "hosted-" + name}):
            return distributed.probe(self.args(plan=self.plan_path, worker=name,
                out=self.root / ("renderer-sdvk009-probe-" + name)))

    def collect_probes(self):
        results = [self.run_probe(name) for name in distributed.PROBE_WORKERS]
        self.assertEqual([result["status"] for result in results], ["PASS"] * 3)
        peers = self.root / "cohort-peers"
        peers.mkdir()
        for name in distributed.PROBE_WORKERS:
            shutil.copytree(self.root / ("renderer-sdvk009-probe-" + name), peers / name)
        artifacts = {"schema": distributed.ARTIFACT_SET_SCHEMA, "github_run_id": "12345", "github_run_attempt": "1",
                     "source_commit": COMMIT, "plan_sha256": distributed.file_identity(self.plan_path)["sha256"],
                     "artifacts": [{"worker": name, "artifact_id": 100 + ordinal,
                         "name": "sdvk-cohort-probe-12345-1-" + name,
                         "archive_sha256": sha256(("SYNTHETIC ZIP " + name).encode()), "archive_bytes": 1000,
                         "manifest_sha256": distributed.file_identity(peers / name / "manifest.json")["sha256"]}
                         for ordinal, name in enumerate(distributed.PROBE_WORKERS)]}
        rewrite(self.root / "cohort-artifacts.json", artifacts)
        return results

    def refresh_peer_artifact(self, name):
        peer = self.root / "cohort-peers" / name
        refresh_inventory(peer)
        path = self.root / "cohort-artifacts.json"
        value = read_json(path)
        next(item for item in value["artifacts"] if item["worker"] == name)["manifest_sha256"] = \
            distributed.file_identity(peer / "manifest.json")["sha256"]
        rewrite(path, value)

    def run_workers(self):
        return [self.run_worker(name) for name in read_json(self.plan_path)["workers"]]

    def assemble(self):
        return distributed.assemble(Namespace(plan=self.plan_path, workers=self.root,
            out=self.root / "renderer-sdvk009-publication", expected_commit=COMMIT))

    def allocation(self):
        return distributed.derive_allocation(read_json(self.plan_path), distributed.file_identity(self.plan_path),
            distributed.file_identity(self.plan_path.parent / "prepared/prepared.json"),
            {name: self.root / "cohort-peers" / name for name in distributed.PROBE_WORKERS},
            read_json(self.root / "cohort-artifacts.json"))

    @staticmethod
    def placement(mask, elapsed):
        pairs = itertools.combinations(distributed.PROBE_WORKERS, 2)
        comparisons = [{"left": left, "right": right, "status": "PASS" if mask & (1 << index) else "FAIL"}
                       for index, (left, right) in enumerate(pairs)]
        return distributed.compatible_placement(comparisons, elapsed)

    def test_all_seven_subset_candidates_ties_and_nontransitive_pair_results(self):
        # Eight possible graphs, including every single compatible pair and all
        # non-transitive two-edge graphs. Never merge a failing third edge.
        pairs = [("controls", "witness-1"), ("controls", "witness-2"), ("witness-1", "witness-2")]
        expected = {0: ["controls"], 1: ["controls", "witness-1"], 2: ["controls", "witness-2"],
                    3: ["controls", "witness-1"], 4: ["witness-1", "witness-2"],
                    5: ["controls", "witness-1"], 6: ["controls", "witness-2"],
                    7: ["controls", "witness-1", "witness-2"]}
        for mask, group in expected.items():
            comparisons = [{"left": left, "right": right, "status": "PASS" if mask & (1 << index) else "FAIL"}
                           for index, (left, right) in enumerate(pairs)]
            with self.subTest(mask=mask):
                placement = distributed.compatible_placement(comparisons, dict.fromkeys(distributed.PROBE_WORKERS, 1))
                self.assertEqual(placement["cohort"], group)
                self.assertEqual(placement["assignment_order"], group)
                self.assertEqual(len(placement["placement"]["candidates"]), 7)
        with self.assertRaisesRegex(EvidenceError, "Incomplete"):
            distributed.compatible_placement(comparisons[:-1], dict.fromkeys(distributed.PROBE_WORKERS, 1))
        with self.assertRaisesRegex(EvidenceError, "Incomplete"):
            distributed.compatible_placement(comparisons[::-1], dict.fromkeys(distributed.PROBE_WORKERS, 1))

    def test_actual_625_elapsed_selects_faster_singleton_over_slower_compatible_pair(self):
        # Authenticated native elapsed from #625; only the first two hosts had
        # equal protected state. No CPU vendor or post-proof outcome is an input.
        elapsed = {"controls": 133.391190131, "witness-1": 135.591586732, "witness-2": 72.14588943100003}
        value = self.placement(1, elapsed)
        self.assertEqual(value["cohort"], ["witness-2"])
        self.assertEqual(value["assignment_order"], ["witness-2"])
        self.assertEqual(value["placement"]["minimum_score_milliseconds"], 216438)
        self.assertEqual(value["placement"]["selected_score_milliseconds"], 216438)
        self.assertEqual([row["ceil_milliseconds"] for row in value["placement"]["weights"]], [133392, 135592, 72146])
        self.assertEqual({row["worker"]: row["native_elapsed_seconds"] for row in value["placement"]["weights"]}, elapsed)
        pair = next(row for row in value["placement"]["candidates"] if row["cohort"] == ["controls", "witness-1"])
        self.assertEqual(pair["score_milliseconds"], 266784)
        self.assertTrue(pair["compatible"])
        self.assertFalse(pair["within_near_minimum"])
        self.assertTrue(all(not row["within_near_minimum"] for row in value["placement"]["candidates"] if not row["compatible"]))

    def test_pair_assigns_two_roles_to_faster_host_and_retains_canonical_membership(self):
        value = self.placement(2, {"controls": 100, "witness-1": 170, "witness-2": 60})
        self.assertEqual(value["cohort"], ["controls", "witness-2"])
        self.assertEqual(value["assignment_order"], ["witness-2", "controls"])
        self.assertEqual(value["placement"]["selected_score_milliseconds"], 120000)
        pair = next(row for row in value["placement"]["candidates"] if row["cohort"] == value["cohort"])
        self.assertEqual(pair["role_counts"], {"controls": 1, "witness-2": 2})

    def test_largest_cohort_wins_exact_ten_percent_boundary_but_not_one_millisecond_outside(self):
        for slow, expected in ((22.0, list(distributed.PROBE_WORKERS)), (22.000001, ["controls", "witness-1"])):
            with self.subTest(slow=slow):
                value = self.placement(7, {"controls": 10, "witness-1": 10, "witness-2": slow})
                self.assertEqual(value["cohort"], expected)
                self.assertEqual(value["placement"]["minimum_score_milliseconds"], 20000)
        near = self.placement(1, {"controls": 10, "witness-1": 32, "witness-2": 170})
        self.assertEqual(near["cohort"], ["controls", "witness-1"])
        self.assertEqual(near["placement"]["minimum_score_milliseconds"], 30000)
        self.assertEqual(near["placement"]["selected_score_milliseconds"], 32000)

    def test_equal_sized_near_candidates_use_lower_score_before_lexical_tie(self):
        value = self.placement(3, {"controls": 20, "witness-1": 19, "witness-2": 18})
        self.assertEqual(value["cohort"], ["controls", "witness-2"])
        pairs = [row for row in value["placement"]["candidates"] if len(row["cohort"]) == 2 and row["within_near_minimum"]]
        self.assertEqual([row["score_milliseconds"] for row in pairs], [38000, 36000])
        tied = self.placement(3, {"controls": 20, "witness-1": 30, "witness-2": 22})
        self.assertEqual(tied["cohort"], ["controls", "witness-1"])

    def test_three_host_assignment_preserves_role_order_and_weight_mapping_permutations(self):
        elapsed = {"controls": 10, "witness-1": 9, "witness-2": 8}
        expected = self.placement(7, elapsed)
        self.assertEqual(expected["assignment_order"], list(distributed.PROBE_WORKERS))
        for items in itertools.permutations(elapsed.items()):
            self.assertEqual(canonical(self.placement(7, dict(items))), canonical(expected))

    def test_native_weight_ceil_is_exact_and_has_no_new_capture_timeout_acceptance(self):
        value = self.placement(0, {"controls": 0.001, "witness-1": 0.0010000000000000002, "witness-2": 180.001})
        self.assertEqual([row["ceil_milliseconds"] for row in value["placement"]["weights"]], [1, 2, 180001])
        self.assertEqual(value["cohort"], ["controls"])
        # The existing native deadline validator, not the routing score, decides
        # whether subprocess creation/wait overhead is a successful collection.
        self.assertEqual(value["placement"]["weights"][2]["native_elapsed_seconds"], 180.001)

    def test_missing_extra_and_nonpositive_nonfinite_or_non_numeric_weights_fail_closed(self):
        valid = dict.fromkeys(distributed.PROBE_WORKERS, 1)
        for invalid in (0, -1, float("nan"), float("inf"), float("-inf"), None, True, False, "1", []):
            with self.subTest(invalid=repr(invalid)), self.assertRaisesRegex(EvidenceError, "positive and finite"):
                self.placement(7, {**valid, "controls": invalid})
        for invalid in ({"controls": 1, "witness-1": 1}, {**valid, "unregistered": 1}):
            with self.assertRaisesRegex(EvidenceError, "All three authenticated"):
                self.placement(7, invalid)

    def test_cohort_plan_preserves_original_full_workload_and_distinct_probe_authorizations(self):
        plan = self.register(cohort=True)
        self.assertEqual(plan["kind"], distributed.COHORT_KIND)
        self.assertEqual([(row["name"], row["scene"], row["publication_witness"]) for row in plan["captures"]],
                         list(distributed.publication.PLAN))
        self.assertEqual([row["worker"] for row in plan["captures"]], ["publication", "cohort", "cohort", "cohort"])
        self.assertTrue(all((row["warmup_frames"], row["frames"], row["timeout_seconds"]) == (120, 1, 3600)
                            for row in plan["captures"]))
        self.assertTrue(all((row["warmup_frames"], row["frames"], row["timeout_seconds"], row["publication_witness"]) ==
                            (5, 1, 180, False) for row in plan["probes"]))
        self.assertEqual(len({row["authorization_id"] for row in [*plan["captures"], *plan["probes"]]}), 7)
        original = read_json(self.plan_path)
        for mutation in (lambda value: value["probes"][0].update(warmup_frames=1),
                         lambda value: value["probes"].reverse(),
                         lambda value: value["allocation_policy"].update(reassignment=True),
                         lambda value: value["allocation_policy"]["near_minimum"].update(numerator=111),
                         lambda value: value.update(kind=distributed.COHORT_PROBE_KIND),
                         lambda value: value["captures"][1].update(worker="controls"),
                         lambda value: value["probes"][0].update(authorization_id=value["captures"][0]["authorization_id"])):
            changed = copy.deepcopy(original)
            mutation(changed)
            reseal(self.plan_path, changed)
            with self.assertRaises(EvidenceError):
                distributed.load_plan(self.plan_path, COMMIT)
        reseal(self.plan_path, original)

    def test_two_host_cohort_runs_original_full_four_once_and_retains_zero_assigned_worker(self):
        self.register(cohort=True)
        self.synthetic_generations["cohort-probe-witness-1"] = 2
        self.collect_probes()
        allocation = self.allocation()
        self.assertEqual(allocation["cohort"], ["controls", "witness-2"])
        self.assertEqual([row["worker"] for row in allocation["captures"]],
                         ["publication", "controls", "witness-2", "controls"])
        workers = self.run_workers()
        self.assertEqual([value["status"] for value in workers], ["PASS"] * 4)
        self.assertEqual([len(value["captures"]) for value in workers], [1, 2, 0, 1])
        self.assertEqual(len({value["allocation_sha256"] for value in workers}), 1)
        self.assertEqual([call.out.name for call in self.calls[3:]],
                         ["compositing-control", "shadow-control", "shadow-witness-2", "shadow-witness-1"])
        self.assertTrue(all((call.warmup, call.frames, call.timeout) == (120, 1, 3600) for call in self.calls[3:]))
        before = {name: identity for name, identity in distributed.inventory(self.root).items()
                  if name.startswith(("renderer-sdvk009-worker-", "renderer-sdvk009-probe-", "renderer-sdvk009-plan/"))}
        result = self.assemble()
        self.assertEqual(result["status"], "PASS", result.get("error"))
        self.assertTrue(result["qualification_awarded"])
        self.assertEqual(result["cohort_allocation"], allocation)
        self.assertEqual([step["name"] for step in result["steps"]], ["preflight", *[row[0] for row in distributed.publication.PLAN]])
        final = self.root / "renderer-sdvk009-publication"
        for name in distributed.PROBE_WORKERS:
            self.assertTrue((final / "distributed-probes" / name / "probe.json").is_file())
        self.assertEqual(read_json(final / "distributed-workers/witness-1/worker.json")["captures"], [])
        self.assertEqual(set(read_json(final / "relocation.json")["files"]), set(before))
        for name in ("shadow-witness-1", "shadow-witness-2"):
            self.assertEqual(len(read_json(final / (name + "-negative-controls.json"))["controls"]), 9)

    def test_weighted_full_workers_and_aggregator_agree_on_two_roles_for_faster_host(self):
        self.register(cohort=True)
        self.synthetic_generations["cohort-probe-witness-1"] = 2
        self.synthetic_elapsed = {"cohort-probe-controls": 100, "cohort-probe-witness-1": 170,
                                  "cohort-probe-witness-2": 60}
        self.collect_probes()
        allocation = self.allocation()
        self.assertEqual(allocation["cohort"], ["controls", "witness-2"])
        self.assertEqual(allocation["assignment_order"], ["witness-2", "controls"])
        self.assertEqual([row["worker"] for row in allocation["captures"]],
                         ["publication", "witness-2", "controls", "witness-2"])
        workers = self.run_workers()
        self.assertEqual([value["status"] for value in workers], ["PASS"] * 4)
        self.assertEqual([len(value["captures"]) for value in workers], [1, 1, 0, 2])
        self.assertEqual({value["allocation_sha256"] for value in workers}, {sha256(canonical(allocation))})
        self.assertEqual([call.out.name for call in self.calls[3:]],
                         ["compositing-control", "shadow-witness-1", "shadow-control", "shadow-witness-2"])
        self.assertTrue(all((call.warmup, call.frames, call.timeout) == (120, 1, 3600) for call in self.calls[3:]))
        result = self.assemble()
        self.assertEqual(result["status"], "PASS", result.get("error"))
        self.assertTrue(result["qualification_awarded"])
        self.assertEqual(result["cohort_allocation"], allocation)
        self.assertEqual([step["name"] for step in result["steps"]], ["preflight", *[row[0] for row in distributed.publication.PLAN]])
        final = self.root / "renderer-sdvk009-publication"
        self.assertEqual(sum(len(read_json(final / (name + "-negative-controls.json"))["controls"])
                             for name in ("shadow-witness-1", "shadow-witness-2")), 18)

    def test_invalid_native_weight_cannot_be_silently_excluded_from_a_valid_cohort(self):
        self.register(cohort=True)
        self.synthetic_generations["cohort-probe-controls"] = 2
        self.synthetic_elapsed["cohort-probe-controls"] = -1
        self.collect_probes()
        result = self.run_worker("witness-1")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("positive and finite", result["error"])
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(result["captures"], [])

    def test_cohort_post_probe_is_nonqualifying_and_retains_cold_to_warm_differences(self):
        self.register(cohort_probe=True)
        self.collect_probes()
        for name in ("cohort-proof-shadow-control", "cohort-proof-shadow-witness-1", "cohort-proof-shadow-witness-2"):
            self.synthetic_generations[name] = 2
        with patch.object(distributed.publication, "validate_witness", side_effect=AssertionError("full proof forbidden")), \
             patch.object(distributed.publication, "negative_controls", side_effect=AssertionError("full negatives forbidden")):
            workers = self.run_workers()
            self.assertEqual([value["status"] for value in workers], ["PASS"] * 4)
            result = self.assemble()
        self.assertEqual(result["status"], "PROBE_PASS", result.get("error"))
        self.assertFalse(result["qualification_awarded"])
        self.assertEqual(len(self.calls), 7)
        self.assertTrue(all(call.frames == 1 and call.timeout == 180 and not call.publication_witness for call in self.calls))
        self.assertTrue(all(call.warmup == (120 if call.scene == "compositing" else 5) for call in self.calls))
        self.assertEqual([item["comparison"]["status"] for item in result["startup_history"]], ["FAIL"] * 3)
        self.assertEqual(result["cohort_allocation"]["cohort"], list(distributed.PROBE_WORKERS))

    def test_singleton_cohort_is_serial_original_order_without_reassignment(self):
        self.register(cohort_probe=True)
        self.synthetic_generations.update({"cohort-probe-witness-1": 2, "cohort-probe-witness-2": 3})
        self.collect_probes()
        allocation = self.allocation()
        self.assertEqual(allocation["cohort"], ["controls"])
        workers = self.run_workers()
        self.assertEqual([len(value["captures"]) for value in workers], [1, 3, 0, 0])
        self.assertEqual([entry["name"] for entry in workers[1]["captures"]],
                         ["cohort-proof-shadow-control", "cohort-proof-shadow-witness-1", "cohort-proof-shadow-witness-2"])
        self.assertEqual(self.assemble()["status"], "PROBE_PASS")

    def test_singleton_empty_workers_survive_real_tar_transport_and_assembly(self):
        from tools.ci import renderer_evidence
        self.register(cohort_probe=True)
        self.synthetic_generations.update({"cohort-probe-witness-1": 2, "cohort-probe-witness-2": 3})
        self.collect_probes()
        workers = self.run_workers()
        self.assertEqual([value["status"] for value in workers], ["PASS"] * 4,
                         [value.get("error") for value in workers])
        parts = self.root / "transport-parts"
        parts.mkdir()
        for suite in renderer_evidence.COHORT_PROBE_SUITES:
            renderer_evidence.pack(self.root, suite, expected_commit=COMMIT,
                runtime_sha256=distributed.file_identity(self.archive)["sha256"],
                plan_sha256=distributed.file_identity(self.plan_path)["sha256"], job_status="success")
            for suffix in ("tar", "tar.sha256", "manifest.json"):
                shutil.move(str(self.root / ("renderer-" + suite + "." + suffix)), str(parts))
        restored = self.root / "restored"
        # This isolates transport of this module's packet; the six companion
        # modules are not synthesized and complete-workflow gates are not awarded.
        renderer_evidence.merge(parts, restored, complete=False, suites=renderer_evidence.COHORT_PROBE_SUITES,
            expected_commit=COMMIT, runtime_sha256=distributed.file_identity(self.archive)["sha256"],
            plan_sha256=distributed.file_identity(self.plan_path)["sha256"])
        self.assertTrue((restored / "renderer-sdvk009-worker-witness-1/captures").is_dir())
        result = distributed.assemble(Namespace(plan=restored / "renderer-sdvk009-plan/preregistration.json",
            workers=restored, out=restored / "renderer-sdvk009-publication", expected_commit=COMMIT))
        self.assertEqual(result["status"], "PROBE_PASS", result.get("error"))
        self.assertFalse(result["qualification_awarded"])
        final = restored / "renderer-sdvk009-publication"
        self.assertTrue((final / "distributed-workers/witness-1/captures").is_dir())
        self.assertTrue((final / "distributed-probes/witness-2/probe.json").is_file())

    def test_missing_probe_never_becomes_a_smaller_cohort(self):
        self.register(cohort=True)
        self.collect_probes()
        shutil.rmtree(self.root / "cohort-peers/witness-2")
        result = self.run_worker("controls")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("peer directory", result["error"])
        self.assertEqual(len(self.calls), 3)
        self.assertTrue((self.root / "renderer-sdvk009-worker-controls/worker-start.json").is_file())

    def test_corrupt_or_failed_probe_cannot_be_excluded_from_a_passing_group(self):
        self.register(cohort=True)
        self.collect_probes()
        peer = self.root / "cohort-peers/witness-2"
        result = read_json(peer / "probe.json")
        result["status"] = "FAIL"
        rewrite(peer / "probe.json", result)
        self.refresh_peer_artifact("witness-2")
        with self.assertRaisesRegex(EvidenceError, "Worker failed"):
            self.allocation()
        result["status"] = "PASS"
        rewrite(peer / "probe.json", result)
        self.refresh_peer_artifact("witness-2")
        image = peer / "captures/cohort-probe-witness-2/native.png"
        image.write_bytes(image.read_bytes() + b"CORRUPTION")
        with self.assertRaisesRegex(EvidenceError, "missing, added or altered"):
            self.allocation()
        self.assertEqual(len(self.calls), 3)

    def test_rehashed_cross_wired_probe_request_is_rejected(self):
        self.register(cohort=True)
        self.collect_probes()
        peer = self.root / "cohort-peers/witness-2"
        shutil.copyfile(self.root / "cohort-peers/witness-1/captures/cohort-probe-witness-1/request.json",
                        peer / "captures/cohort-probe-witness-2/request.json")
        self.refresh_peer_artifact("witness-2")
        with self.assertRaisesRegex(EvidenceError, "another capture/worker"):
            self.allocation()

    def test_incompatible_probe_device_is_global_failure_not_an_excluded_cohort_member(self):
        self.register(cohort=True)
        self.collect_probes()
        peer = self.root / "cohort-peers/witness-2"
        capture = peer / "captures/cohort-probe-witness-2"
        data = read_json(capture / "run.json")
        data["build"]["vulkan"]["driverVersion"] = 2
        rewrite(capture / "run.json", data)
        result = read_json(peer / "probe.json")
        plan = read_json(self.plan_path)
        result["captures"][0]["admission"] = distributed.admit_capture(capture, plan["probes"][2], plan,
            distributed.file_identity(self.plan_path.parent / "prepared/prepared.json"), probe=True)
        step_path = peer / "steps/cohort-probe-witness-2.json"
        step = read_json(step_path)
        step["result"] = data
        rewrite(step_path, step)
        result["steps"][1]["receipt"] = pin(step_path, relative_to=peer)
        rewrite(peer / "probe.json", result)
        self.refresh_peer_artifact("witness-2")
        with self.assertRaisesRegex(EvidenceError, "Vulkan identity differs"):
            self.allocation()
        self.assertEqual(len(self.calls), 3)

    def test_probe_boot_identity_cannot_be_relabelled_as_an_independent_peer(self):
        self.register(cohort=True)
        self.collect_probes()
        peer = self.root / "cohort-peers/witness-2"
        other = read_json(self.root / "cohort-peers/controls/probe.json")
        for name in ("probe.json", "probe-start.json", "probe-registration.json"):
            value = read_json(peer / name)
            value["host_identity"] = other["host_identity"]
            rewrite(peer / name, value)
        self.refresh_peer_artifact("witness-2")
        with self.assertRaisesRegex(EvidenceError, "three independent hosted runners"):
            self.allocation()

    def test_cohort_artifacts_require_exact_run_attempt_plan_ids_and_order(self):
        self.register(cohort=True)
        self.collect_probes()
        path = self.root / "cohort-artifacts.json"
        original = read_json(path)
        mutations = [lambda value: value.update(github_run_attempt="2"),
                     lambda value: value.update(source_commit="f" * 40),
                     lambda value: value.update(plan_sha256="f" * 64),
                     lambda value: value["artifacts"].reverse(),
                     lambda value: value["artifacts"].pop(),
                     lambda value: value["artifacts"][1].update(artifact_id=value["artifacts"][0]["artifact_id"]),
                     lambda value: value["artifacts"][1].update(archive_sha256=value["artifacts"][0]["archive_sha256"]),
                     lambda value: value["artifacts"][1].update(manifest_sha256="f" * 64)]
        for mutation in mutations:
            changed = copy.deepcopy(original)
            mutation(changed)
            rewrite(path, changed)
            with self.assertRaises(EvidenceError):
                self.allocation()
        rewrite(path, original)

    def test_worker_cannot_adopt_another_hosts_successful_probe(self):
        self.register(cohort=True)
        self.collect_probes()
        with patch.object(distributed, "host_identity", return_value={"boot_id": str(uuid.uuid4())}):
            result = self.run_worker("controls")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("own prior cohort probe", result["error"])
        self.assertEqual(len(self.calls), 3)

    def test_uniform_full_capture_device_drift_cannot_reuse_probe_based_placement(self):
        self.register(cohort=True)
        self.collect_probes()
        def drift(args):
            data = self.capture(args)
            data["build"]["vulkan"]["driverVersion"] = 2
            rewrite(args.out / "run.json", data)
            return data
        with patch.object(distributed.run, "capture", side_effect=drift):
            workers = self.run_workers()
        self.assertEqual([value["status"] for value in workers], ["FAIL"] * 4)
        self.assertTrue(all("changed after the cohort probes" in value["error"] for value in workers))
        self.assertEqual(len(self.calls), 7)
        self.assertEqual(self.assemble()["status"], "FAIL")

    def test_rehashed_worker_allocation_disagreement_fails_before_relocation(self):
        self.register(cohort_probe=True)
        self.collect_probes()
        self.run_workers()
        worker = self.root / "renderer-sdvk009-worker-witness-2"
        path = worker / "allocation.json"
        value = read_json(path)
        value["cohort"] = ["witness-2"]
        rewrite(path, value)
        refresh_inventory(worker)
        result = self.assemble()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("allocation missing or disagrees", result["error"])
        self.assertTrue((worker / "captures/cohort-proof-shadow-witness-2/run.json").is_file())

    def test_all_workers_agreeing_on_rehashed_false_scores_cannot_override_raw_probe_recomputation(self):
        self.register(cohort_probe=True)
        self.collect_probes()
        self.assertEqual([value["status"] for value in self.run_workers()], ["PASS"] * 4)
        forged = self.allocation()
        forged["placement"]["selected_score_milliseconds"] += 1
        forged_hash = sha256(canonical(forged))
        for name in distributed.WORKERS:
            root = self.root / ("renderer-sdvk009-worker-" + name)
            rewrite(root / "allocation.json", forged)
            registration = read_json(root / "worker-registration.json")
            registration["allocation_sha256"] = forged_hash
            rewrite(root / "worker-registration.json", registration)
            worker = read_json(root / "worker.json")
            worker["allocation_sha256"] = forged_hash
            for entry in worker["captures"]:
                path = root / entry["launch"]["path"]
                launch = read_json(path)
                launch["allocation_sha256"] = forged_hash
                rewrite(path, launch)
                entry["launch"] = pin(path, relative_to=root)
            rewrite(root / "worker.json", worker)
            refresh_inventory(root)
        result = self.assemble()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("allocation missing or disagrees", result["error"])
        self.assertFalse(result["qualification_awarded"])
        self.assertTrue((self.root / "renderer-sdvk009-worker-controls/captures/cohort-proof-shadow-control/run.json").is_file())

    def test_empty_assignment_worker_remains_mandatory(self):
        self.register(cohort_probe=True)
        self.synthetic_generations.update({"cohort-probe-witness-1": 2, "cohort-probe-witness-2": 3})
        self.collect_probes()
        self.run_workers()
        (self.root / "renderer-sdvk009-worker-witness-2/manifest.json").unlink()
        result = self.assemble()
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["qualification_awarded"])

    def test_cohort_full_failure_suppresses_only_later_local_assignments_without_takeover(self):
        self.register(cohort=True)
        self.synthetic_generations["cohort-probe-witness-1"] = 2
        self.collect_probes()
        self.fail_at = 5  # Three probes, compositing, then the assigned control.
        workers = self.run_workers()
        self.assertEqual([value["status"] for value in workers], ["PASS", "FAIL", "PASS", "PASS"])
        self.assertEqual([call.out.name for call in self.calls[3:]],
                         ["compositing-control", "shadow-control", "shadow-witness-1"])
        self.assertTrue((self.root / "renderer-sdvk009-worker-controls/captures/shadow-control/stdout.log").is_file())
        self.assertEqual(self.assemble()["status"], "FAIL")

    def test_cohort_post_probe_protected_mismatch_fails_and_retains_raw_evidence(self):
        self.register(cohort_probe=True)
        self.collect_probes()
        self.run_workers()
        self.synthetic_generations["cohort-proof-shadow-witness-2"] = 2
        result = self.assemble()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("Post-probe cohort shadows", result["error"])
        self.assertFalse(result["qualification_awarded"])
        final = self.root / "renderer-sdvk009-publication"
        self.assertTrue((final / "captures/cohort-proof-shadow-witness-2/run.json").is_file())
        self.assertTrue((final / "distributed-probes/witness-2/probe.json").is_file())

    def test_singleton_full_collection_does_not_imply_deferred_negative_controls_pass(self):
        self.register(cohort=True)
        self.synthetic_generations.update({"cohort-probe-witness-1": 2, "cohort-probe-witness-2": 3})
        self.collect_probes()
        failed_negatives = {"status": "FAIL", "controls": [{"status": "FAIL"}, *[{"status": "PASS"}] * 8]}
        with patch.object(distributed.publication, "negative_controls", return_value=failed_negatives) as negatives:
            workers = self.run_workers()
            self.assertEqual([value["status"] for value in workers], ["PASS"] * 4)
            self.assertEqual([call.out.name for call in self.calls[3:]], [row[0] for row in distributed.publication.PLAN])
            negatives.assert_not_called()  # Local fail-stop is collection/admission, not final qualification.
            result = self.assemble()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("nine original publication negative controls", result["error"])
        self.assertFalse(result["qualification_awarded"])
        final = self.root / "renderer-sdvk009-publication"
        self.assertTrue(all((final / "captures" / name / "run.json").is_file() for name, _, _ in distributed.publication.PLAN))
        self.assertEqual(read_json(final / "shadow-witness-1-negative-controls.json"), failed_negatives)

    def test_cohort_probe_cancellation_and_rerun_fail_closed(self):
        self.register(cohort=True)
        self.interrupt_at = 1
        result = self.run_probe("controls")
        self.assertEqual(result["status"], "CANCELLED")
        root = self.root / "renderer-sdvk009-probe-controls"
        self.assertEqual(read_json(root / "manifest.json")["status"], "CANCELLED")
        self.assertTrue((root / "captures/cohort-probe-controls/stdout.log").is_file())
        with self.assertRaises(FileExistsError):
            self.run_probe("controls")
        self.assertEqual(len(self.calls), 1)

    def test_original_four_captures_and_complete_restored_consumer_packet(self):
        plan = self.register()
        original_plan_bytes = self.plan_path.read_bytes()
        self.assertEqual([(row["name"], row["scene"], row["publication_witness"]) for row in plan["captures"]],
                         list(distributed.publication.PLAN))
        self.assertEqual(plan["workers"], ["publication", "controls", "witness-1", "witness-2"])
        self.assertEqual([row["worker"] for row in plan["captures"]], plan["workers"])
        workers = self.run_workers()
        self.assertEqual([value["status"] for value in workers], ["PASS"] * 4)
        for value, row in zip(workers, plan["captures"]):
            self.assertEqual([step["name"] for step in value["steps"]], ["preflight", row["name"]])
            self.assertEqual([entry["name"] for entry in value["captures"]], [row["name"]])
        self.assertEqual(len(self.calls), 4)
        self.assertTrue(all((call.warmup, call.frames, call.timeout, call.gpu, call.image_policy) ==
                            (120, 1, 3600, False, "exact") for call in self.calls))
        source_files = {name: value for name, value in distributed.inventory(self.root).items()
                        if name.startswith(("renderer-sdvk009-worker-", "renderer-sdvk009-plan/"))}
        result = self.assemble()
        self.assertEqual(result["status"], "PASS", result.get("error"))
        self.assertTrue(result["qualification_awarded"])
        self.assertEqual([step["name"] for step in result["steps"]],
                         ["preflight", *[row["name"] for row in plan["captures"]]])
        final = self.root / "renderer-sdvk009-publication"
        self.assertEqual((final / "preregistration.json").read_bytes(), original_plan_bytes)
        self.assertEqual((final / "steps/preflight.json").read_bytes(),
                         (final / "distributed-workers/controls/steps/preflight.json").read_bytes())
        for name, _, _ in distributed.publication.PLAN:
            self.assertTrue((final / "captures" / name / "run.json").is_file())
            self.assertTrue((final / "steps" / (name + ".json")).is_file())
        for name in ("shadow-witness-1", "shadow-witness-2"):
            controls = read_json(final / (name + "-negative-controls.json"))
            self.assertEqual(len(controls["controls"]), 9)
            self.assertTrue(all(control["status"] == "PASS" for control in controls["controls"]))
            self.assertEqual(read_json(final / (name + "-control-comparison.json"))["status"], "PASS")
        self.assertEqual(read_json(final / "witness-repeat-comparison.json")["status"], "PASS")
        relocations = read_json(final / "relocation.json")["files"]
        self.assertEqual(set(relocations), set(source_files))
        for source, destination in relocations.items():
            self.assertEqual(distributed.file_identity(self.root / destination["destination"]), source_files[source])
            self.assertFalse((self.root / source).exists())
        self.assertFalse(result["physical_gpu_qualified"])
        self.assertFalse(result["performance_accepted"])

    def test_probe_can_never_award_publication_qualification(self):
        self.register(probe=True)
        self.assertEqual([value["status"] for value in self.run_workers()], ["PASS"] * 3)
        self.assertEqual(len(self.calls), 3)
        self.assertTrue(all((call.scene, call.warmup, call.frames, call.timeout, call.publication_witness) ==
                            ("compositing", 120, 1, 180, False) for call in self.calls))
        result = self.assemble()
        self.assertEqual(result["status"], "PROBE_PASS", result.get("error"))
        self.assertFalse(result["qualification_awarded"])
        self.assertEqual(result["kind"], distributed.PROBE_KIND)

    def test_startup_probe_keeps_exact_original_comparators_and_cannot_qualify(self):
        plan = self.register(startup_probe=True)
        self.assertEqual(plan["kind"], distributed.STARTUP_PROBE_KIND)
        self.assertEqual(plan["workers"], ["controls", "witness-1", "witness-2"])
        self.assertEqual([row["name"] for row in plan["captures"]],
                         ["startup-control-cold", "startup-compositing-primer", "startup-control-warm",
                          "startup-witness-1", "startup-witness-2"])
        self.assertEqual([value["status"] for value in self.run_workers()], ["PASS"] * 3)
        self.assertEqual(len(self.calls), 5)
        for call in self.calls:
            self.assertEqual((call.frames, call.timeout, call.publication_witness, call.collision_snapshot),
                             (1, 180, False, False))
            self.assertEqual(call.warmup, 120 if call.scene == "compositing" else 5)
        # A protected startup-history difference remains visible and is never
        # normalized away. It describes the probe, not full qualification.
        self.synthetic_generations["startup-control-warm"] = 2
        with patch.object(distributed.run, "compare_runs", wraps=distributed.run.compare_runs) as compare, \
             patch.object(distributed.publication, "validate_witness", side_effect=AssertionError("full witness API")), \
             patch.object(distributed.publication, "negative_controls", side_effect=AssertionError("full negative API")):
            result = self.assemble()
        self.assertEqual(result["status"], "PROBE_PASS", result.get("error"))
        self.assertFalse(result["qualification_awarded"])
        self.assertEqual(compare.call_count, 4)
        self.assertTrue(all(not call.kwargs for call in compare.call_args_list))
        self.assertEqual(result["startup_history"]["comparison"]["status"], "FAIL")
        self.assertFalse(result["startup_history"]["comparison"]["state_equal"])
        self.assertTrue(all(comparison["status"] == "PASS" for comparison in result["comparisons"]))
        final = self.root / "renderer-sdvk009-publication"
        self.assertTrue((final / "startup-history-comparison.json").is_file())
        self.assertFalse((final / "shadow-witness-1-publication.json").exists())

    def test_startup_probe_cannot_hide_a_first_use_state_mismatch(self):
        self.register(startup_probe=True)
        self.run_workers()
        self.synthetic_generations["startup-witness-1"] = 2
        result = self.assemble()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("original exact comparison", result["error"])
        self.assertFalse(result["qualification_awarded"])
        final = self.root / "renderer-sdvk009-publication"
        comparison = read_json(final / "startup-cold-control-witness-1-comparison.json")
        self.assertFalse(comparison["state_equal"])
        self.assertTrue((final / "captures/startup-control-warm/run.json").is_file())

    def test_startup_probe_scope_and_worker_set_cannot_be_relabelled_as_full(self):
        self.register(startup_probe=True)
        original = read_json(self.plan_path)
        mutations = [lambda value: value.update(kind=distributed.FULL_KIND),
                     lambda value: value.update(workers=list(distributed.WORKERS)),
                     lambda value: value["captures"][3].update(publication_witness=True),
                     lambda value: value["captures"][0].update(warmup_frames=120),
                     lambda value: value.update(qualification_awarded=True)]
        for mutate in mutations:
            changed = copy.deepcopy(original)
            mutate(changed)
            reseal(self.plan_path, changed)
            with self.assertRaises(EvidenceError):
                distributed.load_plan(self.plan_path, COMMIT)
        reseal(self.plan_path, original)
        worker = self.run_worker("publication")
        self.assertEqual(worker["status"], "FAIL")
        self.assertIn("not authorized", worker["error"])
        self.assertEqual(self.calls, [])

    def test_immutable_registration_rejects_shortened_reordered_or_reassigned_work(self):
        self.register()
        original = read_json(self.plan_path)
        mutations = [lambda value: value["captures"].reverse(),
                     lambda value: value["captures"].pop(),
                     lambda value: value["captures"][2].update(warmup_frames=119),
                     lambda value: value["captures"][2].update(timeout_seconds=600),
                     lambda value: value["captures"][2].update(worker="controls"),
                     lambda value: value["captures"][2].update(image_policy={"metric": "tolerant"}),
                     lambda value: value["captures"][2].update(authorization_id=value["captures"][3]["authorization_id"]),
                     lambda value: value["matching_content"]["inputs"].pop("compositing/scene.pk3"),
                     lambda value: value.update(automatic_retries=1)]
        for mutation in mutations:
            changed = copy.deepcopy(original)
            mutation(changed)
            reseal(self.plan_path, changed)
            with self.assertRaises((EvidenceError, KeyError)):
                distributed.load_plan(self.plan_path, COMMIT)
        reseal(self.plan_path, original)
        self.plan_path.write_bytes(self.plan_path.read_bytes() + b" ")
        with self.assertRaisesRegex(EvidenceError, "SHA-256"):
            distributed.load_plan(self.plan_path, COMMIT)
        self.assertEqual(self.calls, [])

    def test_failed_compositing_leaves_three_independent_shadows_authorized(self):
        self.register()
        self.fail_at = 1
        results = self.run_workers()
        self.assertEqual([value["status"] for value in results], ["FAIL", "PASS", "PASS", "PASS"])
        self.assertEqual([call.out.name for call in self.calls],
                         ["compositing-control", "shadow-control", "shadow-witness-1", "shadow-witness-2"])
        self.assertTrue((self.root / "renderer-sdvk009-worker-publication/captures/compositing-control/stdout.log").is_file())
        self.assertEqual(self.assemble()["status"], "FAIL")

    def test_startup_probe_failure_suppresses_local_later_launches_only(self):
        self.register(startup_probe=True)
        self.fail_at = 1
        results = self.run_workers()
        self.assertEqual([value["status"] for value in results], ["FAIL", "PASS", "PASS"])
        self.assertEqual([call.out.name for call in self.calls],
                         ["startup-control-cold", "startup-witness-1", "startup-witness-2"])
        self.assertTrue((self.root / "renderer-sdvk009-worker-controls/captures/startup-control-cold/stdout.log").is_file())
        self.assertEqual(self.assemble()["status"], "FAIL")

    def test_cancellation_preserves_partial_failure_and_cannot_be_resumed(self):
        self.register()
        self.interrupt_at = 1
        result = self.run_worker("controls")
        self.assertEqual(result["status"], "CANCELLED")
        root = self.root / "renderer-sdvk009-worker-controls"
        self.assertEqual(read_json(root / "manifest.json")["status"], "CANCELLED")
        self.assertTrue((root / "captures/shadow-control/stdout.log").is_file())
        with self.assertRaises(FileExistsError):
            self.run_worker("controls")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.assemble()["status"], "FAIL")

    def test_runtime_or_source_change_prevents_any_native_launch(self):
        self.register()
        self.archive.write_bytes(b"REPLACED runtime even if compiled commit text matches")
        result = self.run_worker("controls")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("runtime/archive", result["error"])
        self.assertEqual(self.calls, [])

    def test_missing_worker_artifact_or_manifest_never_passes(self):
        self.register(probe=True)
        self.run_workers()
        (self.root / "renderer-sdvk009-worker-witness-2/manifest.json").unlink()
        result = self.assemble()
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue((self.root / "renderer-sdvk009-worker-controls").is_dir())

    def test_full_qualification_requires_publication_capture_worker_manifest(self):
        self.register()
        self.run_workers()
        (self.root / "renderer-sdvk009-worker-publication/manifest.json").unlink()
        result = self.assemble()
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["qualification_awarded"])
        self.assertTrue((self.root / "renderer-sdvk009-worker-controls/captures/shadow-control/run.json").is_file())

    def test_raw_file_corruption_rejected_before_any_relocation(self):
        self.register(probe=True)
        self.run_workers()
        path = self.root / "renderer-sdvk009-worker-witness-1/captures/compatibility-witness-1/native.png"
        path.write_bytes(path.read_bytes() + b"CORRUPTED")
        result = self.assemble()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("missing, added or altered", result["error"])
        self.assertTrue(path.is_file())

    def test_rehashed_wrong_device_still_rejected_by_cross_runner_identity(self):
        self.register(probe=True)
        self.run_workers()
        worker = self.root / "renderer-sdvk009-worker-witness-1"
        capture = worker / "captures/compatibility-witness-1"
        data = read_json(capture / "run.json")
        data["build"]["vulkan"]["driverVersion"] = 2
        rewrite(capture / "run.json", data)
        result = read_json(worker / "worker.json")
        row = read_json(self.plan_path)["captures"][1]
        result["captures"][0]["admission"] = distributed.admit_capture(capture, row,
            read_json(self.plan_path), distributed.file_identity(self.plan_path.parent / "prepared/prepared.json"))
        step_path = worker / "steps/compatibility-witness-1.json"
        step = read_json(step_path)
        step["result"] = data
        rewrite(step_path, step)
        result["steps"][1]["receipt"] = pin(step_path, relative_to=worker)
        rewrite(worker / "worker.json", result)
        refresh_inventory(worker)
        outcome = self.assemble()
        self.assertEqual(outcome["status"], "FAIL")
        self.assertIn("Vulkan identity differs", outcome["error"])

    def test_rehashed_cross_wired_request_is_not_an_independent_execution(self):
        self.register(probe=True)
        self.run_workers()
        worker = self.root / "renderer-sdvk009-worker-witness-2"
        request = worker / "captures/compatibility-witness-2/request.json"
        source = self.root / "renderer-sdvk009-worker-witness-1/captures/compatibility-witness-1/request.json"
        shutil.copyfile(source, request)
        refresh_inventory(worker)
        outcome = self.assemble()
        self.assertEqual(outcome["status"], "FAIL")
        self.assertIn("another capture/worker", outcome["error"])

    def test_successful_process_receipt_must_bind_the_actual_retained_capture(self):
        self.register(probe=True)
        self.run_workers()
        worker = self.root / "renderer-sdvk009-worker-witness-2"
        step_path = worker / "steps/compatibility-witness-2.json"
        step = read_json(step_path)
        step["result"]["elapsed_seconds"] = 99
        rewrite(step_path, step)
        result = read_json(worker / "worker.json")
        result["steps"][1]["receipt"] = pin(step_path, relative_to=worker)
        rewrite(worker / "worker.json", result)
        refresh_inventory(worker)
        outcome = self.assemble()
        self.assertEqual(outcome["status"], "FAIL")
        self.assertIn("does not describe", outcome["error"])

    def test_distinct_boot_policy_rejects_one_host_relabelled_as_siblings(self):
        self.register(probe=True)
        self.run_workers()
        worker = self.root / "renderer-sdvk009-worker-witness-2"
        sibling = read_json(self.root / "renderer-sdvk009-worker-witness-1/worker.json")
        for name in ("worker.json", "worker-start.json", "worker-registration.json"):
            value = read_json(worker / name)
            value["host_identity"] = sibling["host_identity"]
            rewrite(worker / name, value)
        refresh_inventory(worker)
        outcome = self.assemble()
        self.assertEqual(outcome["status"], "FAIL")
        self.assertIn("independent hosted runners", outcome["error"])

    def test_shared_runner_name_does_not_erase_distinct_boot_identities(self):
        self.register(probe=True)
        self.run_workers()
        for worker_name in read_json(self.plan_path)["workers"]:
            worker = self.root / ("renderer-sdvk009-worker-" + worker_name)
            for name in ("worker.json", "worker-start.json", "worker-registration.json"):
                value = read_json(worker / name)
                value["hosted_run"]["RUNNER_NAME"] = "Non-unique hosted runner name"
                rewrite(worker / name, value)
            refresh_inventory(worker)
        outcome = self.assemble()
        self.assertEqual(outcome["status"], "PROBE_PASS", outcome.get("error"))

    def test_missing_or_malformed_kernel_boot_identity_is_rejected(self):
        for value in ({}, {"boot_id": None}, {"boot_id": "unknown"}, {"boot_id": "a" * 32},
                      {"boot_id": "a" * 8 + "-" + "b" * 27}, {"boot_id": str(uuid.uuid4()), "extra": True}):
            with self.subTest(value=value), self.assertRaisesRegex(EvidenceError, "boot identity"):
                distributed.validate_host_identity(value)

    def test_changed_exact_rgb_fails_after_restoration_and_retains_complete_evidence(self):
        self.register(probe=True)
        self.run_workers()
        worker = self.root / "renderer-sdvk009-worker-witness-2"
        image = worker / "captures/compatibility-witness-2/native.png"
        image.write_bytes(png(b"\xff" + bytes(640 * 480 * 3 - 1), width=640, height=480))
        refresh_inventory(worker)
        outcome = self.assemble()
        self.assertEqual(outcome["status"], "FAIL")
        self.assertIn("exact comparison", outcome["error"])
        final = self.root / "renderer-sdvk009-publication"
        self.assertTrue((final / "captures/compatibility-witness-2/native.png").is_file())
        self.assertTrue(read_json(final / "relocation.json")["files"])
        self.assertFalse(outcome["qualification_awarded"])

    def test_worker_has_no_automatic_retry_and_rejects_second_execution(self):
        self.register(probe=True)
        self.assertEqual(self.run_worker("controls")["status"], "PASS")
        with self.assertRaises(FileExistsError):
            self.run_worker("controls")
        self.assertEqual(len(self.calls), 1)

    def test_mismatched_hosted_attempt_fails_before_provenance_or_native(self):
        self.register(probe=True)
        with patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "2"}):
            result = self.run_worker("controls")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("another hosted run", result["error"])
        self.assertEqual(self.calls, [])

    def test_symlink_and_unexpected_capture_rejected_even_with_successful_job(self):
        self.register(probe=True)
        self.run_workers()
        root = self.root / "renderer-sdvk009-worker-controls"
        (root / "captures/unregistered-duplicate").mkdir()
        refresh_inventory(root)
        outcome = self.assemble()
        self.assertEqual(outcome["status"], "FAIL")
        self.assertIn("Unexpected capture", outcome["error"])
        with tempfile.TemporaryDirectory() as temporary:
            link_root = Path(temporary)
            (link_root / "link").symlink_to(self.exe)
            with self.assertRaisesRegex(EvidenceError, "Nonregular"):
                distributed.inventory(link_root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
