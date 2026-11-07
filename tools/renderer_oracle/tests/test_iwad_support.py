"""CPU-only support-WAD preregistration and retained-request controls."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common
import run


class IWADSupportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.exe = self.root / "vkdoom.exe"
        self.iwad = self.root / "doom2kex.wad"
        self.support = self.root / "id24res.wad"
        self.scene = self.root / "scene.pk3"
        for path, data in ((self.exe, b"synthetic executable; never run"),
                           (self.iwad, b"synthetic KEX IWAD"),
                           (self.support, b"synthetic support WAD"),
                           (self.scene, b"synthetic authored scene"),
                           (self.root / "vkdoom.pk3", b"synthetic engine package")):
            path.write_bytes(data)
        self.iwad_pin = common.pin(self.iwad)
        self.support_pin = common.pin(self.support)
        self.declaration = {"iwad": self.iwad_pin, "packages": [self.support_pin]}

    def pins(self, declaration=None, **kwargs):
        return run.support_package_pins(declaration, self.iwad_pin, self.exe, **kwargs)

    def request(self):
        packages = {str(path): common.pin(path) for path in
                    (self.root / "vkdoom.pk3", self.iwad, self.scene, self.support)}
        return {"executable": common.pin(self.exe), "packages": packages,
                "iwad_support": copy.deepcopy(self.declaration),
                "reproduction": {"iwad_support": copy.deepcopy(self.declaration)}}

    def validate_request(self, request):
        return run.validate_support_request(request, self.iwad_pin, common.pin(self.scene))

    def test_only_explicit_iwad_bound_support_is_selected(self):
        self.assertEqual(self.pins(), {})
        self.assertNotIn("id24res.wad", run.PACKAGES)
        self.assertEqual(self.pins(self.declaration), {str(self.support): self.support_pin})
        # A different IWAD in the same directory cannot inherit the declaration.
        other = self.root / "freedoom2.wad"
        other.write_bytes(b"another synthetic IWAD")
        with self.assertRaises(common.EvidenceError):
            run.support_package_pins(self.declaration, common.pin(other), self.exe)

    def test_changed_or_missing_support_cannot_enter_preregistration(self):
        self.support.write_bytes(b"changed support")
        with self.assertRaises(common.EvidenceError):
            self.pins(self.declaration)
        self.support.unlink()
        with self.assertRaises((common.EvidenceError, FileNotFoundError)):
            self.pins(self.declaration)

    def test_wrong_iwad_identity_and_original_path_are_rejected(self):
        for key, value in (("sha256", "0" * 64), ("bytes", self.iwad_pin["bytes"] + 1),
                           ("path", str(self.root / "different.wad"))):
            declaration = copy.deepcopy(self.declaration)
            declaration["iwad"][key] = value
            with self.subTest(key=key), self.assertRaises(common.EvidenceError):
                self.pins(declaration)

    def test_empty_extra_and_duplicate_declarations_are_rejected(self):
        mutations = []
        empty = copy.deepcopy(self.declaration); empty["packages"] = []; mutations.append(empty)
        extra = copy.deepcopy(self.declaration); extra["automatic"] = True; mutations.append(extra)
        duplicate = copy.deepcopy(self.declaration)
        duplicate["packages"].append(copy.deepcopy(self.support_pin)); mutations.append(duplicate)
        alias = copy.deepcopy(self.declaration)
        alias["packages"].append({**self.support_pin, "path": str(self.support).upper()})
        mutations.append(alias)
        self_wad = copy.deepcopy(self.declaration); self_wad["packages"] = [self.iwad_pin]
        mutations.append(self_wad)
        extra_pin = copy.deepcopy(self.declaration)
        extra_pin["packages"][0]["selection"] = "learned-from-stdout"; mutations.append(extra_pin)
        for declaration in mutations:
            with self.subTest(declaration=declaration), self.assertRaises(common.EvidenceError):
                self.pins(declaration, verify_files=False)

    def test_support_cannot_escape_runtime_or_use_traversal(self):
        for path in (self.root.parent / "outside.wad", self.root / "nested/support.wad",
                     self.root / "nested/../id24res.wad", Path("id24res.wad"),
                     self.root / "support.pk3"):
            declaration = copy.deepcopy(self.declaration)
            declaration["packages"][0]["path"] = str(path)
            with self.subTest(path=path), self.assertRaises(common.EvidenceError):
                self.pins(declaration, verify_files=False)

    def test_support_symlink_is_rejected_before_resolution(self):
        alias = self.root / "alias.wad"
        try:
            alias.symlink_to(self.support)
        except (OSError, NotImplementedError):
            self.skipTest("Creating symlinks requires a host privilege")
        declaration = {"iwad": self.iwad_pin,
                       "packages": [{**self.support_pin, "path": str(alias)}]}
        with self.assertRaises(common.EvidenceError):
            self.pins(declaration)

    def test_retained_validation_uses_pins_without_live_external_files(self):
        copied_iwad = {**self.iwad_pin, "path": str(self.root / "capture/input/doom2kex.wad")}
        self.support.unlink()
        self.iwad.unlink()
        with mock.patch.object(run, "pin", side_effect=AssertionError("live read during retained validation")):
            self.assertEqual(run.support_package_pins(self.declaration, copied_iwad, self.exe,
                verify_files=False, require_iwad_path=False), {str(self.support): self.support_pin})

    def test_retained_request_needs_exact_declared_support_pin(self):
        request = self.request()
        self.validate_request(request)
        for key, value in (("sha256", "0" * 64), ("bytes", self.support_pin["bytes"] + 1)):
            invalid = copy.deepcopy(request)
            invalid["packages"][str(self.support)][key] = value
            with self.subTest(key=key), self.assertRaises(common.EvidenceError):
                self.validate_request(invalid)
        invalid = copy.deepcopy(request); del invalid["packages"][str(self.support)]
        with self.assertRaises(common.EvidenceError):
            self.validate_request(invalid)

    def test_retained_request_profile_and_exact_loaded_set_cannot_diverge(self):
        request = self.request()
        changed_profile = copy.deepcopy(request)
        changed_profile["reproduction"]["iwad_support"]["iwad"]["sha256"] = "0" * 64
        extra = copy.deepcopy(request)
        path = str(self.root / "unreviewed.wad")
        extra["packages"][path] = {**self.support_pin, "path": path}
        missing_engine = copy.deepcopy(request)
        del missing_engine["packages"][str(self.root / "vkdoom.pk3")]
        for invalid in (changed_profile, extra, missing_engine):
            with self.subTest(invalid=invalid), self.assertRaises(common.EvidenceError):
                self.validate_request(invalid)

    def test_unrelated_iwad_request_does_not_select_present_support(self):
        request = self.request()
        del request["iwad_support"]
        del request["reproduction"]["iwad_support"]
        del request["packages"][str(self.support)]
        self.validate_request(request)
        request["packages"][str(self.support)] = self.support_pin
        with self.assertRaises(common.EvidenceError):
            self.validate_request(request)

    def test_synthetic_capture_preregisters_support_and_rejects_rehashed_support_receipt(self):
        # Reuse the full synthetic executable/PNG/state fixture. Its subprocess
        # handler delegates only read-only Git and never executes the placeholder.
        import test_run_receipt
        original_capture = run.capture
        original_validate = run.validate_run
        observed = {"target_requests": 0, "rewritten_receipt_rejected": False}

        def capture_with_support(args):
            support = args.exe.parent / "id24res.wad"
            support.write_bytes(b"SYNTHETIC support-WAD placeholder; never rendered\n")
            args.iwad_support = {"iwad": common.pin(args.iwad),
                                 "packages": [common.pin(support)]}
            synthetic_handler = run.subprocess.run

            def assert_preregistration_before_target(argv, *positional, **kwargs):
                if str(argv[0]) == str(args.exe) and argv[1:] != ["--version"]:
                    request = common.read_json(args.out / "request.json")
                    self.assertEqual(request["iwad_support"], args.iwad_support)
                    self.assertEqual(request["reproduction"]["iwad_support"], args.iwad_support)
                    self.assertEqual(request["packages"][str(support)], common.pin(support))
                    observed["target_requests"] += 1
                return synthetic_handler(argv, *positional, **kwargs)

            with mock.patch.object(run.subprocess, "run", side_effect=assert_preregistration_before_target):
                return original_capture(args)

        def validate_with_rehashed_support_negative(path):
            result = original_validate(path)
            if not observed["rewritten_receipt_rejected"]:
                root = result[0]
                request_path, receipt_path = root / "request.json", root / "run.json"
                originals = request_path.read_bytes(), receipt_path.read_bytes()
                request = common.read_json(request_path)
                receipt = common.read_json(receipt_path)
                declaration = request["iwad_support"]
                declaration["packages"][0]["sha256"] = "0" * 64
                request["reproduction"]["iwad_support"] = copy.deepcopy(declaration)
                receipt["reproduction"] = copy.deepcopy(request["reproduction"])
                try:
                    request_path.write_bytes(common.canonical(request))
                    receipt["artifacts"]["request.json"] = common.pin(request_path, relative_to=root)
                    receipt_path.write_bytes(common.canonical(receipt))
                    with self.assertRaisesRegex(common.EvidenceError, "support set differs"):
                        original_validate(root)
                    observed["rewritten_receipt_rejected"] = True
                finally:
                    request_path.write_bytes(originals[0])
                    receipt_path.write_bytes(originals[1])
            return result

        harness = test_run_receipt.SyntheticRunReceiptTests(
            "test_capture_validate_and_rehashed_packet_negatives")
        with mock.patch.object(run, "capture", side_effect=capture_with_support), \
                mock.patch.object(run, "validate_run", side_effect=validate_with_rehashed_support_negative):
            harness.test_capture_validate_and_rehashed_packet_negatives()
        self.assertEqual(observed["target_requests"], 3)
        self.assertTrue(observed["rewritten_receipt_rejected"])


if __name__ == "__main__":
    unittest.main()
