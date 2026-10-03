"""Regression checks for application-observed Vulkan loss versus watchdog timeout."""
import pathlib
import tempfile
import unittest

from cfx_capture import scan_failure


class FailureClassificationTests(unittest.TestCase):
    def classify(self, trace="", stdout="", stderr="", timed_out=True, code=1):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            paths = [root / name for name in ("timeline.tsv", "stdout.log", "stderr.log")]
            for path, data in zip(paths, (trace, stdout, stderr)):
                path.write_text(data)
            return scan_failure(*paths, timed_out, code)

    def test_p400_submit_loss_before_fatal_dialog_timeout(self):
        # Reduced physical P400 trace: Execute throws before vk-return is emitted.
        trace = (
            "1790805815795\tthread\t7\t8\t11\tpostprocess\tvk-enter\tvkQueueSubmit\t0\n"
            "1790805815808\tthread\t7\t8\t11\tpostprocess\tvk-error\tCould not submit command buffer\t-4\n"
            "1790805815808\tthread\t7\t8\t11\tpostprocess\tdevice-lost-observed\tCould not submit command buffer\t-4\n"
        )
        self.assertEqual(self.classify(trace), "VK_ERROR_DEVICE_LOST")

    def test_error_record_alone_proves_device_loss(self):
        self.assertEqual(self.classify("vk-error\tCould not submit command buffer\t-4\n"),
                         "VK_ERROR_DEVICE_LOST")

    def test_explicit_loss_event_alone(self):
        self.assertEqual(self.classify("device-lost-observed\tCould not wait for commands\t-4\n"),
                         "VK_ERROR_DEVICE_LOST")

    def test_primary_fence_return_remains_device_loss(self):
        self.assertEqual(self.classify("vk-return\tvkWaitForFences/frame\t-4\n"),
                         "VK_ERROR_DEVICE_LOST")

    def test_other_negative_result_is_not_device_loss(self):
        self.assertEqual(self.classify("vk-error\tallocation failed\t-2\n"),
                         "other Vulkan error")

    def test_unreturned_submit_stays_unknown(self):
        self.assertEqual(self.classify("vk-enter\tvkQueueSubmit\t0\n"),
                         "timeout; no Vulkan return proven")

    def test_clean_exit(self):
        self.assertIsNone(self.classify(timed_out=False, code=0))

    def test_cpu_exception_status(self):
        self.assertEqual(self.classify(timed_out=False, code=0xC0000005),
                         "application CPU exception status; inspect Windows Application event")


if __name__ == "__main__":
    unittest.main(verbosity=2)
