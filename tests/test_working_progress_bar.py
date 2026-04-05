import os
import tempfile
import unittest
from unittest import mock

from working_progress_bar import WorkingProgressBar


class TestWorkingProgressBarLoginRedirectRegression(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.html_file = os.path.join(self.temp_dir.name, "progress_bar.html")
        self.html_temp = os.path.join(self.temp_dir.name, "progress_bar.html.tmp")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _build_bar(self):
        with mock.patch.object(WorkingProgressBar, "_create_progress_window"):
            bar = WorkingProgressBar(total_tokens=1, title="Test Progress")
        bar.is_running = True
        bar.finished = False
        bar.html_file = self.html_file
        bar.html_temp = self.html_temp
        return bar

    def test_update_html_does_not_force_timestamp_query_redirect(self):
        bar = self._build_bar()
        bar.current_token = 1
        bar.completed_phases = 1
        bar.current_phase = 1
        bar.current_message = "Running"

        with mock.patch("working_progress_bar.time.sleep", return_value=None):
            bar._update_progress_bar()

        with open(self.html_file, "r", encoding="utf-8") as handle:
            html = handle.read()

        self.assertNotIn("window.location.search = '?t=", html)
        self.assertIn('<meta http-equiv="refresh" content="1">', html)

    def test_finish_html_does_not_force_final_query_redirect(self):
        bar = self._build_bar()
        bar.finish()

        with open(self.html_file, "r", encoding="utf-8") as handle:
            html = handle.read()

        self.assertNotIn("window.location.search = '?final=1'", html)
        self.assertIn("This page will be closed in 10 seconds...", html)

    def test_complete_phase_renders_final_completion_before_stopping(self):
        bar = self._build_bar()
        bar.current_token = 1
        bar.completed_phases = bar.total_phases - 1
        bar.current_phase = 1
        bar.current_message = "Almost done"

        with mock.patch("working_progress_bar.time.sleep", return_value=None):
            bar.complete_phase()

        with open(self.html_file, "r", encoding="utf-8") as handle:
            html = handle.read()

        self.assertIn("Risk Assessment Completed!", html)
        self.assertFalse(bar.is_running)


if __name__ == "__main__":
    unittest.main()
