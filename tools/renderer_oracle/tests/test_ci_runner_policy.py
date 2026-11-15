#!/usr/bin/env python3
"""Current CI runner policy: all active ShadeDoomVK workflows are GitHub-hosted."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]


class GithubHostedRunnerPolicyTests(unittest.TestCase):
    def test_active_workflows_do_not_request_avrea_or_self_hosted(self):
        workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertTrue(workflows)
        for path in workflows:
            text = path.read_text()
            with self.subTest(path=path.name):
                self.assertNotIn("avrea", text.lower())
                self.assertNotIn("self-hosted", text.lower())

    def test_software_vulkan_lane_is_github_hosted_ubuntu_2404(self):
        text = (ROOT / ".github" / "workflows" / "continuous_integration.yml").read_text()

        self.assertIn("name: Linux software Vulkan | RelWithDebInfo", text)
        self.assertIn("name: R-001 | One source-authenticated software Vulkan build", text)
        self.assertIn("name: R-001 | Hosted Vulkan", text)
        self.assertEqual(text.count("runs-on: ubuntu-24.04"), 3)
        self.assertIn('test "$RUNNER_ENVIRONMENT" = github-hosted', text)
        self.assertIn("lvp_icd*.json", text)
        self.assertIn("sha256sum -c r001-native-runtime.tar.xz.sha256", text)
        self.assertNotIn("SDVK_REQUESTED_RUNNER", text)
        self.assertNotIn("sdvk009-avrea-ci.py", text)
        self.assertIn("tools/ci/routine_native.py", text)
        self.assertNotIn("sdvk009_publication qualify", text)
        deep = (ROOT / ".github" / "workflows" / "renderer_deep.yml").read_text()
        self.assertIn("sdvk009_publication qualify", deep)
        self.assertIn("workflow_dispatch:", deep)
        self.assertNotIn("  pull_request:", deep)

    def test_shared_native_guard_requires_github_hosted(self):
        text = (ROOT / "tools" / "renderer_oracle" / "sdvk010_sun_native.py").read_text()
        self.assertIn('os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"', text)
        self.assertNotIn("avrea", text.lower())
        self.assertNotIn("self-hosted", text.lower())
        self.assertNotIn("== 16", text)
        self.assertIn("llvmpipe", text)


if __name__ == "__main__":
    unittest.main()
