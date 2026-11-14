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
        """All three components of the split renderer lane stay hosted."""
        import re

        text = (ROOT / ".github" / "workflows" / "continuous_integration.yml").read_text()
        jobs = list(re.finditer(r"(?m)^  ([A-Za-z_][\w-]*):\s*$", text))
        blocks = {match.group(1): text[match.end():jobs[index + 1].start()
                  if index + 1 < len(jobs) else len(text)]
                  for index, match in enumerate(jobs)}
        for name in ("vulkan_build", "vulkan_qualification", "vulkan_evidence"):
            self.assertIn(name, blocks)
            self.assertIn("runs-on: ubuntu-24.04", blocks[name])
        self.assertIn("suite: [corpus, publication]", blocks["vulkan_qualification"])
        self.assertIn("needs: vulkan_build", blocks["vulkan_qualification"])
        self.assertIn("needs: [vulkan_build, vulkan_qualification]", blocks["vulkan_evidence"])
        self.assertIn("sdvk009_publication qualify", blocks["vulkan_qualification"])
        self.assertIn("name: Linux software Vulkan | RelWithDebInfo", blocks["vulkan_evidence"])
        self.assertNotIn("SDVK_REQUESTED_RUNNER", text)
        self.assertNotIn("sdvk009-avrea-ci.py", text)
        self.assertIn("renderer_evidence.py pack", text)
        self.assertIn("renderer_evidence.py merge", text)
        self.assertIn("renderer_evidence.py verify-final", text)
        self.assertIn("--complete", text)
        self.assertIn("renderer-software-vulkan.tar.xz", text)
        self.assertIn("XZ_OPT='-6 --lzma2=dict=64MiB'", text)
        self.assertIn("compression-level: 1", text)
        self.assertIn("software-vulkan-runtime.tar.gz.sha256", text)
        self.assertIn("renderer-sdvk014-controlled", (ROOT / "tools" / "ci" / "renderer_evidence.py").read_text())
        self.assertIn("sdvk014_controlled_planes", blocks["vulkan_qualification"])
        self.assertIn("if: always()", blocks["vulkan_evidence"])
        self.assertIn('test "${{ needs.vulkan_qualification.result }}" = success', blocks["vulkan_evidence"])
        self.assertIn("test_*.py", blocks["pf_oracle"])

    def test_shared_native_guard_requires_github_hosted(self):
        text = (ROOT / "tools" / "renderer_oracle" / "sdvk010_sun_native.py").read_text()
        self.assertIn('os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"', text)
        self.assertNotIn("avrea", text.lower())
        self.assertNotIn("self-hosted", text.lower())
        self.assertNotIn("== 16", text)
        self.assertIn("llvmpipe", text)


if __name__ == "__main__":
    unittest.main()
