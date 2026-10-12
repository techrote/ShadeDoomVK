"""CPU-only contract tests for the Avrea 16-vCPU publication wrapper."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.renderer_oracle import sdvk009_avrea16_publication as wrapper
from tools.renderer_oracle import sdvk009_publication as publication


class Avrea16PublicationWrapperTests(unittest.TestCase):
    def test_wrapper_preserves_frozen_publication_plan(self):
        self.assertEqual(publication.PLAN, (
            ("compositing-control", "compositing", False),
            ("shadow-control", "shadow-boundary", False),
            ("shadow-witness-1", "shadow-boundary", True),
            ("shadow-witness-2", "shadow-boundary", True),
        ))
        self.assertEqual(publication.IWAD_SHA256,
                         "a8772e088847032510d97ba2312406a6998f21cbab44d4ff10696faa9c0ecd4b")

    def test_wrapper_changes_only_execution_guard_before_delegating(self):
        original = publication.hosted_software_guard
        try:
            with patch.object(publication, "main", return_value=17) as delegated:
                self.assertEqual(wrapper.main(["qualify"]), 17)
                self.assertIs(publication.hosted_software_guard, wrapper.avrea16_software_guard)
                delegated.assert_called_once_with(["qualify"])
        finally:
            publication.hosted_software_guard = original


if __name__ == "__main__":
    unittest.main()
