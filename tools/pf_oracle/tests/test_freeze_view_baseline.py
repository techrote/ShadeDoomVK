#!/usr/bin/env python3
"""Fail-closed source derivation and byte-preserving export controls; no compiler."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle import derive_freeze_view_baseline as D

# Exact original/after Git blobs and full patches, compressed only for this
# archive-safe CPU fixture. Production bodies are not reimplemented. The Git
# service/ancestry response below is modeled; it is not remote/native evidence.
_PINNED_INPUTS = json.loads(zlib.decompress(base64.b85decode(
    "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"
)))

class _PinnedGit:
    commit = "f" * 40

    def call(self, repo, *args):
        if args == ("rev-parse", "--verify", self.commit + "^{commit}"):
            return (self.commit + "\n").encode()
        if args == ("rev-parse", self.commit + "^{tree}"):
            return ("a" * 40 + "\n").encode()
        if args[:3] == ("show", "-s", "--format=%P"):
            matches = [h for h in D.HISTORIES.values() if h["merge"] == args[3]]
            if len(matches) != 1:
                raise AssertionError("unexpected ancestry service query")
            h = matches[0]
            return (h["before"] + " " + h["after"] + "\n").encode()
        if args[:2] == ("merge-base", "--is-ancestor"):
            accepted = {D.MINIMUM_ACCEPTED_BASE} | {h["merge"] for h in D.HISTORIES.values()}
            if args[2] not in accepted or args[3] != self.commit:
                raise AssertionError("unexpected ancestor service query")
            return b""
        if args[:2] == ("diff", "--name-only"):
            h = next(h for h in D.HISTORIES.values()
                     if h["before"] == args[3] and h["after"] == args[4])
            issue = next(issue for issue, value in D.HISTORIES.items() if value == h)
            paths = sorted(p for p, pin in D.HISTORICAL_FILES.items() if pin["issue"] == issue)
            return ("\n".join(paths) + "\n").encode()
        if args[0] == "show" and len(args) == 2:
            commit, path = args[1].split(":", 1)
            if commit == self.commit:
                return (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
            return _PINNED_INPUTS["blobs"][args[1]].encode("utf-8")
        if args[0] == "diff" and args[-2] == "--":
            return _PINNED_INPUTS["patches"][args[-1]].encode("utf-8")
        if args[0] == "ls-tree":
            if args[1] + ":" + args[-1] in _PINNED_INPUTS["blobs"]:
                raise AssertionError("unexpected present original header")
            return b""
        raise AssertionError("unexpected Git service query: " + repr(args))



def temporary_test_directory():
    parent = ROOT / "build" / "pf020-view-baseline-tests"
    parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(dir=parent)
    if not Path(temporary.name).resolve().is_relative_to(parent.resolve()):
        raise RuntimeError("temporary test path escaped bounded build directory")
    return temporary


class LiteralHunkTests(unittest.TestCase):
    def setUp(self):
        self.hunk = D.Hunk(b"left\nold\nright\n", b"left\nnew\nright\n")
        self.patch = (b"diff --git a/a.cpp b/a.cpp\n--- a/a.cpp\n+++ b/a.cpp\n"
                      b"@@ -1,3 +1,3 @@\n left\n-old\n+new\n right\n")

    def test_parse_preserves_context_and_exact_changed_bytes(self):
        self.assertEqual(D.parse_hunks(self.patch), [self.hunk])

    def test_literal_reverse_preserves_surrounding_final_fixes(self):
        current = b"accepted-PF014\n" + self.hunk.after + b"accepted-CFX-PF015\n"
        baseline, rows = D.exact_reverse(current, [self.hunk])
        self.assertEqual(baseline, b"accepted-PF014\n" + self.hunk.before
                         + b"accepted-CFX-PF015\n")
        self.assertEqual(rows[0]["current_after_sha256"], D.sha256(self.hunk.after))
        self.assertEqual(rows[0]["current_first_line"], 2)

    def test_whitespace_changed_current_body_is_rejected(self):
        with self.assertRaisesRegex(D.DerivationError, "exactly once"):
            D.exact_reverse(self.hunk.after.replace(b"new", b" new"), [self.hunk])

    def test_inserted_observer_inside_full_hunk_is_rejected(self):
        with self.assertRaises(D.DerivationError):
            D.exact_reverse(self.hunk.after.replace(b"right", b"Observe();\nright"),
                            [self.hunk])

    def test_observer_outside_hunk_is_preserved(self):
        baseline, _ = D.exact_reverse(b"Observe();\n" + self.hunk.after, [self.hunk])
        self.assertEqual(baseline, b"Observe();\n" + self.hunk.before)

    def test_duplicate_after_body_is_rejected(self):
        with self.assertRaises(D.DerivationError):
            D.exact_reverse(self.hunk.after * 2, [self.hunk])

    def test_overlapping_hunks_are_rejected(self):
        with self.assertRaisesRegex(D.DerivationError, "overlapping"):
            D.exact_reverse(b"abc\n", [D.Hunk(b"x", b"abc"), D.Hunk(b"y", b"bc")])

    def test_missing_hunk_is_rejected(self):
        with self.assertRaises(D.DerivationError):
            D.exact_reverse(b"unrelated\n", [self.hunk])

    def test_no_newline_patch_is_rejected(self):
        with self.assertRaises(D.DerivationError):
            D.parse_hunks(self.patch + b"\\ No newline at end of file\n")

    def test_binary_and_multiple_file_patches_are_rejected(self):
        for source in (self.patch + b"GIT binary patch\n", self.patch * 2):
            with self.subTest(source=source):
                with self.assertRaises(D.DerivationError):
                    D.parse_hunks(source)

    def test_malformed_header_and_non_text_line_are_rejected(self):
        for source in (self.patch.replace(b"@@ -1,3", b"@@ unknown"),
                       self.patch + b"unexpected\n"):
            with self.subTest(source=source):
                with self.assertRaises(D.DerivationError):
                    D.parse_hunks(source)

    def test_historical_sha_and_git_blob_identity_both_required(self):
        data = b"original\n"
        pin = {"before_blob": D.git_blob_id(data), "before_sha256": D.sha256(data)}
        D.verify_historical_blob(data, pin, "before", "a.cpp")
        for key in pin:
            changed = dict(pin)
            changed[key] = "0" * len(pin[key])
            with self.assertRaises(D.DerivationError):
                D.verify_historical_blob(data, changed, "before", "a.cpp")

    def test_literal_key_body_must_remain_original(self):
        path = "src/common/rendering/vulkan/shaders/vk_shader.h"
        before = b"class VkShaderKey\n{\n int Padding = 0;\n bool Original();\n};\n"
        D.body_guards(before, b"// accepted instrumentation\n" + before, path)
        with self.assertRaises(D.DerivationError):
            D.body_guards(before, before.replace(b"Original", b"Guessed"), path)

    def test_full_sha_not_branch_or_prefix(self):
        for commit in ("HEAD", "0ffded431", "0" * 39, "A" * 40, "0" * 40 + ":src"):
            with self.subTest(commit=commit):
                with self.assertRaises(D.DerivationError):
                    D.derive_plan(ROOT, commit)


class PathAndClosureTests(unittest.TestCase):
    def test_path_traversal_and_git_paths_rejected(self):
        for path in ("../a", "a/../b", "/absolute", "C:/x", "a\\b", ".git/config",
                     "a//b", "a/./b"):
            with self.subTest(path=path):
                with self.assertRaises(D.DerivationError):
                    D.safe_relative(path)
        self.assertEqual(D.safe_relative("src/a.cpp"), "src/a.cpp")

    def test_link_submodule_and_unknown_modes_rejected(self):
        for mode, kind in (("120000", "blob"), ("160000", "commit"), ("100600", "blob")):
            raw = f"{mode} {kind} {'0' * 40}\ta\0".encode()
            with patch.object(D, "git", return_value=raw):
                with self.assertRaises(D.DerivationError):
                    D.tree_entries(ROOT, "0" * 40)

    def test_case_collision_is_rejected(self):
        raw = (f"100644 blob {'0' * 40}\ta.cpp\0"
               f"100644 blob {'1' * 40}\tA.cpp\0").encode()
        with patch.object(D, "git", return_value=raw):
            with self.assertRaises(D.DerivationError):
                D.tree_entries(ROOT, "0" * 40)

    def test_output_must_be_ignored_fresh_build_child(self):
        with temporary_test_directory() as temp:
            repo = Path(temp)
            (repo / "build").mkdir()
            with patch.object(D, "git", return_value=b"") as read:
                self.assertEqual(D.choose_output(repo, Path("build/new")), repo / "build/new")
                self.assertEqual(read.call_args.args[1], "check-ignore")
            for output in (repo, repo / "outside", repo / "build", Path("build/../escape")):
                with self.assertRaises(D.DerivationError):
                    D.choose_output(repo, output)
            (repo / "build" / "retained").mkdir()
            with self.assertRaises(D.DerivationError):
                D.choose_output(repo, Path("build/retained"))

    def test_unignored_output_rejected_before_write(self):
        with temporary_test_directory() as temp:
            repo = Path(temp)
            with patch.object(D, "git", side_effect=D.DerivationError("not ignored")):
                with self.assertRaises(D.DerivationError):
                    D.choose_output(repo, Path("build/new"))
            self.assertFalse((repo / "build").exists())

    def test_closure_digest_covers_path_mode_and_bytes(self):
        row = {"path": "a", "mode": "100644", "sha256": "1" * 64, "bytes": 4}
        original = D.closure_digest([row])
        for key, value in (("path", "b"), ("mode", "100755"),
                           ("sha256", "2" * 64), ("bytes", 5)):
            changed = {**row, key: value}
            self.assertNotEqual(D.closure_digest([changed]), original)


class _Batch:
    """Bounded Git service model; export logic and output bytes remain real."""
    def __init__(self, blobs, corrupt=False):
        self.blobs, self.corrupt = blobs, corrupt
        self.stdout = io.BytesIO()
        self.stderr = io.BytesIO()
        self.stdin = self
        self.returncode = None

    def write(self, oid):
        oid = oid.decode().strip()
        body = self.blobs[oid]
        if self.corrupt:
            body = body[:-1]
        self.stdout = io.BytesIO(f"{oid} blob {len(self.blobs[oid])}\n".encode()
                                + body + b"\n")

    def flush(self): pass
    def close(self): pass
    def wait(self, timeout=None):
        self.returncode = 0
        return 0
    def poll(self): return self.returncode
    def kill(self): self.returncode = -1


class ExportTests(unittest.TestCase):
    def _fixture(self):
        changes = {path: (None if pin["before_blob"] is None else b"literal-original\n")
                   for path, pin in D.HISTORICAL_FILES.items()}
        blobs, entries = {}, []
        for index, path in enumerate(changes):
            data = ("current-" + str(index) + "\n").encode()
            oid = D.git_blob_id(data)
            blobs[oid] = data
            entries.append((path, "100644", oid))
        binary = b"\x00\xff\r\n\x80\n"
        oid = D.git_blob_id(binary)
        blobs[oid] = binary
        entries.append(("wadsrc/private-control.bin", "100644", oid))
        report = {"schema": D.SCHEMA, "commit": "1" * 40, "changed_paths": sorted(changes),
                  "native_executed": False, "native_acceptance": False}
        return changes, blobs, entries, report, binary

    def test_export_preserves_binary_bytes_and_actual_nine_path_difference(self):
        changes, blobs, entries, report, binary = self._fixture()
        with temporary_test_directory() as temp:
            out = Path(temp) / "build" / "new"
            with (patch.object(D, "derive_plan", return_value=(changes, report)),
                  patch.object(D, "tree_entries", return_value=entries),
                  patch.object(D, "choose_output", return_value=out),
                  patch.object(D.subprocess, "Popen", return_value=_Batch(blobs))):
                result = D.export(Path(temp), "1" * 40, out)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["closure"]["current"]["file_count"], 10)
            self.assertEqual(result["closure"]["original-seams"]["file_count"], 7)
            for variant in ("current", "original-seams"):
                self.assertEqual((out / variant / "wadsrc/private-control.bin").read_bytes(), binary)
            self.assertFalse(result["native_acceptance"])
            receipt = (out / "derivation.json").read_bytes()
            self.assertNotIn(b"\r\n", receipt)
            self.assertEqual(json.loads(receipt)["changed_paths"], sorted(changes))

    def test_truncated_git_blob_retains_fail_receipt_and_never_passes(self):
        changes, blobs, entries, report, _ = self._fixture()
        with temporary_test_directory() as temp:
            out = Path(temp) / "build" / "failed"
            with (patch.object(D, "derive_plan", return_value=(changes, report)),
                  patch.object(D, "tree_entries", return_value=entries),
                  patch.object(D, "choose_output", return_value=out),
                  patch.object(D.subprocess, "Popen", return_value=_Batch(blobs, corrupt=True))):
                with self.assertRaises(D.DerivationError):
                    D.export(Path(temp), "1" * 40, out)
            result = json.loads((out / "derivation.json").read_bytes())
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(result["partial_export_retained"])
            self.assertFalse(result["native_executed"])

    def test_missing_changed_entry_fails_export_closure(self):
        changes, blobs, entries, report, _ = self._fixture()
        with temporary_test_directory() as temp:
            out = Path(temp) / "build" / "missing"
            with (patch.object(D, "derive_plan", return_value=(changes, report)),
                  patch.object(D, "tree_entries", return_value=entries[1:]),
                  patch.object(D, "choose_output", return_value=out),
                  patch.object(D.subprocess, "Popen", return_value=_Batch(blobs))):
                with self.assertRaisesRegex(D.DerivationError, "allowlist"):
                    D.export(Path(temp), "1" * 40, out)
            self.assertEqual(json.loads((out / "derivation.json").read_bytes())["status"], "FAIL")


class PinnedInputGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = _PinnedGit()
        cls.commit = cls.model.commit
        cls.service = cls.model.call
        cls.calls = []
        original = cls.service
        def observed(repo, *args):
            cls.calls.append(args[0])
            return original(repo, *args)
        with patch.object(D, "git", side_effect=observed):
            cls.changes, cls.report = D.derive_plan(ROOT, cls.commit)

    def test_authenticated_history_and_22_full_hunks_really_match(self):
        self.assertEqual(len(self.changes), 9)
        self.assertEqual(sum(len(row.get("hunks", []))
                             for h in self.report["historical"] for row in h["files"]), 22)
        self.assertEqual(self.report["removed_headers"], 3)
        self.assertFalse(self.report["fresh_network_check"] if "fresh_network_check" in self.report
                         else any(h["fresh_network_check"] for h in self.report["historical"]))

    def test_original_key_bodies_and_old_sprite_consumption_are_real(self):
        shader = self.changes["src/common/rendering/vulkan/shaders/vk_shader.h"]
        pipeline = self.changes["src/common/rendering/vulkan/pipelines/vk_renderpass.h"]
        sprite = self.changes["src/rendering/hwrenderer/scene/hw_sprites.cpp"]
        self.assertIn(b"memcmp(this, &other, sizeof(VkShaderKey))", shader)
        self.assertIn(b"int Padding1 = 0;", pipeline)
        self.assertIn(b"int Padding3 = 0;", pipeline)
        self.assertNotIn(b"CanonicalState()", shader + pipeline)
        self.assertNotIn(b"UpdateRenderSurfaceState", sprite)
        self.assertIn(b"const bool drawWithXYBillboard = ((particle", sprite)
        self.assertIn(b"uint32_t spritetype = (uint32_t)-1;", sprite)

    def test_baseline_has_no_production_context_and_preserves_accepted_fixes(self):
        portal = self.changes["src/rendering/hwrenderer/scene/hw_portal.h"]
        entry = self.changes["src/rendering/hwrenderer/hw_entrypoint.cpp"]
        sprite = self.changes["src/rendering/hwrenderer/scene/hw_sprites.cpp"]
        self.assertNotIn(b"HWRenderContext RenderContext;", portal)
        self.assertNotIn(b"MakeHWPortalRenderContext(", portal)
        self.assertNotIn(b"MakeHWRootRenderContext(", entry)
        self.assertIn(b"return x_offset[0] == inf.x_offset[0]", portal)
        self.assertIn(b"top != -NO_VAL", sprite)
        self.assertIn(b"if (top == -NO_VAL)", sprite)
        self.assertEqual(self.report["compile_definitions"]["original-seams"],
                         ["PF020_ORIGINAL_SEAMS=1"])

    def test_actual_git_calls_are_read_only(self):
        self.assertLessEqual(set(self.calls), {"rev-parse", "show", "merge-base", "diff", "ls-tree"})

    def test_changed_current_or_historical_objects_are_rejected(self):
        original = self.service
        target = "src/rendering/hwrenderer/scene/hw_sprites.cpp"
        def changed_current(repo, *args):
            result = original(repo, *args)
            if args == ("show", self.commit + ":" + target):
                result = result.replace(b"UpdateRenderSurfaceState(di);",
                                        b"UpdateRenderSurfaceState(di); /* unexpected */", 1)
            return result
        with patch.object(D, "git", side_effect=changed_current):
            with self.assertRaises(D.DerivationError):
                D.derive_plan(ROOT, self.commit)

    def test_changed_added_header_is_rejected(self):
        original = self.service
        target = "src/common/rendering/vulkan/vk_keyidentity.h"
        def changed_current(repo, *args):
            result = original(repo, *args)
            if args == ("show", self.commit + ":" + target):
                result += b"// changed header\n"
            return result
        with patch.object(D, "git", side_effect=changed_current):
            with self.assertRaisesRegex(D.DerivationError, "deletion guard"):
                D.derive_plan(ROOT, self.commit)

    def test_wrong_merge_parents_are_rejected(self):
        original = self.service
        def wrong_ancestry(repo, *args):
            if args[:3] == ("show", "-s", "--format=%P"):
                return b"0" * 40 + b" " + b"1" * 40
            return original(repo, *args)
        with patch.object(D, "git", side_effect=wrong_ancestry):
            with self.assertRaisesRegex(D.DerivationError, "ancestry pin"):
                D.derive_plan(ROOT, self.commit)

    def test_unassigned_historical_production_path_is_rejected(self):
        original = self.service
        def unexpected_path(repo, *args):
            data = original(repo, *args)
            if args[:2] == ("diff", "--name-only"):
                return data + b"src/unsafe_extra.cpp\n"
            return data
        with patch.object(D, "git", side_effect=unexpected_path):
            with self.assertRaisesRegex(D.DerivationError, "allowlist"):
                D.derive_plan(ROOT, self.commit)

    def test_changed_historical_original_object_is_rejected(self):
        original = self.service
        target = D.HISTORIES["006"]["before"] + ":src/common/rendering/vulkan/shaders/vk_shader.h"
        def changed_original(repo, *args):
            data = original(repo, *args)
            return data + b"// unsafe guessed adaptation\n" if args == ("show", target) else data
        with patch.object(D, "git", side_effect=changed_original):
            with self.assertRaisesRegex(D.DerivationError, "historical before blob"):
                D.derive_plan(ROOT, self.commit)


if __name__ == "__main__":
    unittest.main()
