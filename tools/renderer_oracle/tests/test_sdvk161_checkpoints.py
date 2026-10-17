"""Real PNG admission and exact phase-image comparison; synthetic pixels only."""
from __future__ import annotations

import ast
import copy
import inspect
from pathlib import Path
import tempfile
import unittest

from tools.renderer_oracle import run, sdvk161_special_surfaces as gate
from tools.renderer_oracle.common import EvidenceError, checked, pin
from tools.renderer_oracle.tests.test_evidence import png


def checkpoints():
    return {"observed_frames": 96, "records": [
        {"kind": "surface-checkpoint", "frame": frame, "count": 1, "data": {
            "producer": "completed-main-view-screenshot", "map": "SDV161A" if frame <= 48 else "SDV161B",
            "image": f"native.surface-{frame}.png", "main_views": 32 + frame}}
        for frame in range(8, 97, 8)]}


def write_images(root, *, width=640, height=480):
    content = png(bytes(width * height * 3), width=width, height=height)
    for frame in range(8, 97, 8):
        (root / f"native.surface-{frame}.png").write_bytes(content)


class SpecialSurfaceCheckpointTests(unittest.TestCase):
    def test_all_twelve_real_pngs_admit_with_exact_frame_map_extent_and_file_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_images(root)
            result = gate.validate_checkpoint_images(root, checkpoints())
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["image_policy"], {"metric": "exact-rgb8"})
            self.assertEqual([row["frame"] for row in result["checkpoints"]], list(range(8, 97, 8)))
            self.assertEqual(len({row["rgb_sha256"] for row in result["checkpoints"]}), 1)
            self.assertTrue(all(row["extent"] == [640, 480] and row["image"]["bytes"] > 0
                                for row in result["checkpoints"]))

    def test_one_channel_lifecycle_equivalent_state_rgb_change_rejects_before_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_images(root)
            (root / "native.surface-16.png").write_bytes(png(bytes([1]) + bytes(640 * 480 * 3 - 1), width=640, height=480))
            with self.assertRaisesRegex(EvidenceError, r"lifecycle equivalent-state RGB.*group=a-nearest.*frame=16.*changed_pixels=1"):
                gate.validate_checkpoint_images(root, checkpoints())

    def test_equivalent_groups_repeat_exactly_without_cross_map_or_sampler_equality(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_images(root)
            # Independent group declaration: phase/map RGB may differ. Only
            # within-group lifecycle convergence is an equality obligation.
            groups = {"a-nearest": ([8, 16, 40, 48], 0), "a-linear": ([24, 32], 1),
                      "b-nearest": ([56, 64, 88, 96], 2), "b-linear": ([72, 80], 3)}
            for frames, marker in groups.values():
                content = png(bytes([marker]) + bytes(640 * 480 * 3 - 1), width=640, height=480)
                for frame in frames:
                    (root / f"native.surface-{frame}.png").write_bytes(content)
            result = gate.validate_checkpoint_images(root, checkpoints())
            reports = result["lifecycle_equivalent_state_rgb"]
            self.assertEqual(set(reports), set(groups))
            self.assertEqual(sum(len(report["comparisons"]) for report in reports.values()), 8)
            for name, (frames, _) in groups.items():
                self.assertEqual(reports[name]["frames"], frames)
                self.assertEqual(reports[name]["gl_texture_filter"], 4 if name.endswith("linear") else 0)
                for comparison in reports[name]["comparisons"]:
                    self.assertEqual(comparison["reference_frame"], frames[0])
                    self.assertEqual(comparison["comparison"]["changed_pixels"], 0)
                    self.assertEqual(comparison["comparison"]["policy"], {"metric": "exact-rgb8"})

    def test_missing_duplicate_wrong_frame_or_foreign_map_checkpoint_records_fail(self):
        mutations = (
            lambda raw: raw["records"].pop(),
            lambda raw: raw["records"].append(copy.deepcopy(raw["records"][0])),
            lambda raw: raw["records"][0].update(frame=7),
            lambda raw: raw["records"][0]["data"].update(map="SDV161B"),
            lambda raw: raw["records"][0]["data"].update(image="native.surface-16.png"),
            lambda raw: raw["records"][0]["data"].update(main_views=41),
            lambda raw: raw["records"][0]["data"].update(producer="cpu-generated-reference"),
            lambda raw: raw["records"][0].update(count=True),
        )
        with tempfile.TemporaryDirectory() as directory:
            for mutation in mutations:
                raw = checkpoints()
                mutation(raw)
                with self.subTest(mutation=mutation), self.assertRaises(EvidenceError):
                    gate.validate_checkpoint_images(Path(directory), raw)

    def test_unregistered_missing_wrong_extent_or_symlink_image_is_not_accepted(self):
        for edit in ("missing", "extra", "extent", "symlink"):
            with self.subTest(edit=edit), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_images(root, height=479 if edit == "extent" else 480)
                first = root / "native.surface-8.png"
                if edit == "missing": first.unlink()
                elif edit == "extra": (root / "native.surface-7.png").write_bytes(first.read_bytes())
                elif edit == "symlink":
                    (root / "other.png").write_bytes(first.read_bytes())
                    first.unlink()
                    first.symlink_to(root / "other.png")
                with self.assertRaises(EvidenceError):
                    gate.validate_checkpoint_images(root, checkpoints())

    def test_exact_phase_comparison_catches_one_channel_in_map_a_or_reloaded_b(self):
        # Small real PNGs isolate comparison; 640x480 admission is tested above.
        for changed_frame in (None, 8, 80):
            with self.subTest(changed_frame=changed_frame), tempfile.TemporaryDirectory() as directory:
                left, right = (Path(directory) / name for name in ("left", "right"))
                left.mkdir(); right.mkdir()
                write_images(left, width=2, height=1)
                write_images(right, width=2, height=1)
                if changed_frame is not None:
                    (right / f"native.surface-{changed_frame}.png").write_bytes(png(bytes([1]) + bytes(5)))
                result = gate.compare_checkpoint_images(left, right)
                self.assertEqual(result["status"], "PASS" if changed_frame is None else "FAIL")
                failures = [row["frame"] for row in result["comparisons"] if not row["comparison"]["passed"]]
                self.assertEqual(failures, [] if changed_frame is None else [changed_frame])
                self.assertTrue(all(row["comparison"]["policy"] == {"metric": "exact-rgb8"}
                                    for row in result["comparisons"]))

    def test_one_directory_cannot_supply_independent_phase_image_evidence(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(EvidenceError, "independent"):
            gate.compare_checkpoint_images(Path(directory), Path(directory))


class SpecialSurfaceCheckpointArtifactTests(unittest.TestCase):
    def manifest(self, root):
        write_images(root, width=2, height=1)
        return {path.name: pin(path, relative_to=root) for path in root.glob("native.surface-*.png")}

    def test_all_twelve_original_manifest_pins_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.manifest(Path(directory))
            self.assertIsNone(gate.validate_checkpoint_artifacts(manifest))
            for missing in ("one", "all"):
                changed = copy.deepcopy(manifest)
                if missing == "one": changed.pop("native.surface-8.png")
                else: changed.clear()
                with self.subTest(missing=missing), self.assertRaisesRegex(EvidenceError, "original artifact manifest"):
                    gate.validate_checkpoint_artifacts(changed)

    def test_wrong_manifest_path_extra_checkpoint_and_malformed_pin_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            original = self.manifest(Path(directory))
            mutations = (
                lambda manifest: manifest["native.surface-8.png"].update(path="native.surface-16.png"),
                lambda manifest: manifest["native.surface-8.png"].update(path="elsewhere/native.surface-8.png"),
                lambda manifest: manifest["native.surface-8.png"].update(bytes=True),
                lambda manifest: manifest["native.surface-8.png"].update(sha256="a" * 63),
                lambda manifest: manifest["native.surface-8.png"].pop("sha256"),
                lambda manifest: manifest["native.surface-8.png"].update(re_pinned=True),
                lambda manifest: manifest.update({"native.surface-7.png": copy.deepcopy(manifest["native.surface-8.png"])}),
            )
            for mutation in mutations:
                changed = copy.deepcopy(original)
                mutation(changed)
                with self.subTest(mutation=mutation), self.assertRaises(EvidenceError):
                    gate.validate_checkpoint_artifacts(changed)

    def test_original_pin_integrity_prevents_current_file_repinning_after_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.manifest(root)
            gate.validate_checkpoint_artifacts(manifest)
            for value in manifest.values():
                checked(root, value)
            (root / "native.surface-8.png").write_bytes(png(bytes([1]) + bytes(5)))
            # Shape/membership remain true, but the actual run validator's
            # existing checked() pass must reject the original pinned bytes.
            gate.validate_checkpoint_artifacts(manifest)
            with self.assertRaisesRegex(EvidenceError, "Artifact identity changed"):
                for value in manifest.values():
                    checked(root, value)

    def test_retained_run_calls_original_manifest_gate_before_checkpoint_readmission(self):
        tree = ast.parse(inspect.getsource(run._validate_run))
        branches = [node for node in ast.walk(tree) if isinstance(node, ast.If)
                    and "special_surface_lifecycle" in ast.unparse(node.test)]
        self.assertEqual(len(branches), 1)
        calls = [node for node in ast.walk(branches[0]) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        manifests = [node for node in calls if node.func.id == "validate_checkpoint_artifacts"]
        images = [node for node in calls if node.func.id == "validate_checkpoint_images"]
        self.assertEqual(len(manifests), 1)
        self.assertEqual(len(images), 1)
        self.assertEqual([ast.unparse(argument) for argument in manifests[0].args], ["artifacts"])
        self.assertLess(manifests[0].lineno, images[0].lineno)
        original_checks = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                           and isinstance(node.func, ast.Name) and node.func.id == "checked"]
        self.assertTrue(original_checks)
        self.assertLess(min(node.lineno for node in original_checks), manifests[0].lineno)

    def test_recipe_pins_exactly_one_quiet_checkpoint_screenshot_command(self):
        from tools.renderer_oracle.tests.test_sdvk161_special_surfaces import native_recipe
        for change in ("missing", "false", "duplicate", "later-override"):
            native = native_recipe()
            commands = native["console_commands"]
            if change == "missing": commands.remove("screenshot_quiet true")
            elif change == "false": commands[-1] = "screenshot_quiet false"
            elif change == "duplicate": commands.append("screenshot_quiet true")
            else: commands.append("echo later; SCREENSHOT_QUIET false")
            with self.subTest(change=change), self.assertRaisesRegex(EvidenceError, "quiet-output"):
                gate.validate_recipe({"id": gate.SCENE, "native": native})


if __name__ == "__main__":
    unittest.main()
