"""Negative controls for authoritative --version output validation.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import unittest
from tools.check_build_identity import validate_identity_output


class BuildIdentityOutputTests(unittest.TestCase):
    def setUp(self):
        self.constants = {
            "SDVK_PROJECT_NAME": "ShadeDoomVK",
            "SDVK_VERSIONSTR": "0.1.0-dev",
            "SDVK_FOUNDING_COMMIT": "a" * 40,
            "SDVK_PF_FREEZE_COMMIT": "b" * 40,
        }
        self.arguments = dict(commit="c" * 40, state="clean", description="v;punctuation", constants=self.constants)
        self.lines = [
            "ShadeDoomVK 0.1.0-dev", "Commit: " + "c" * 40,
            "Working tree: clean", "Git description: v;punctuation",
            "VKDoom lineage: nashmuhandes/VkDoom@" + "a" * 40,
            "PF-020 freeze: " + "b" * 40,
        ]

    def validate(self, lines, **overrides):
        return validate_identity_output("\n".join(lines) + "\n", **(self.arguments | overrides))

    def test_exact_ordered_output_accepts_punctuated_tag(self):
        self.validate(self.lines)

    def test_missing_description_with_arbitrary_sixth_line_rejected(self):
        lines = self.lines.copy()
        lines[3] = "unverified data"
        # The former four-in-six membership check accepted these six lines.
        self.assertEqual(len(lines), 6)
        self.assertTrue(all(line in lines for line in (self.lines[0], self.lines[1], self.lines[4], self.lines[5])))
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.validate(lines)

    def test_wrong_git_description_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(self.lines, description="different-tag")

    def test_changed_worktree_state_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(self.lines, state="modified")

    def test_reordered_identity_fields_rejected(self):
        lines = self.lines.copy()
        lines[2], lines[3] = lines[3], lines[2]
        with self.assertRaises(ValueError):
            self.validate(lines)

    def test_duplicate_or_extra_line_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(self.lines + [self.lines[0]])

    def test_missing_trailing_newline_rejected(self):
        with self.assertRaises(ValueError):
            validate_identity_output("\n".join(self.lines), **self.arguments)


if __name__ == "__main__":
    unittest.main()
