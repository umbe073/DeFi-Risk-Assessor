import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from working_progress_bar import WorkingProgressBar


def _fake_create_progress_window(bar: WorkingProgressBar) -> None:
    """Avoid launching a real browser during tests."""
    bar.is_running = True
    bar.html_file = "/tmp/progress_bar_test_placeholder.html"
    bar.html_temp = "/tmp/progress_bar_test_placeholder.html.tmp"


class WorkingProgressBarRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def _make_bar(self) -> WorkingProgressBar:
        with patch.object(WorkingProgressBar, "_create_progress_window", new=_fake_create_progress_window):
            bar = WorkingProgressBar(total_tokens=1, title="Test Progress")
        bar.html_file = str(Path(self._tmpdir.name) / "progress.html")
        bar.html_temp = str(Path(self._tmpdir.name) / "progress.html.tmp")
        bar.is_running = True
        bar.current_token = 1
        bar.current_phase = 0
        bar.current_message = "Testing"
        return bar

    def _read_html(self, bar: WorkingProgressBar) -> str:
        return Path(bar.html_file).read_text(encoding="utf-8")

    def test_update_progress_no_forced_query_redirect(self) -> None:
        bar = self._make_bar()
        bar.completed_phases = 1

        bar._update_progress_bar()
        html = self._read_html(bar)

        self.assertIn('<meta http-equiv="refresh" content="1">', html)
        self.assertNotIn("window.location.search", html)
        self.assertNotIn("?t=", html)

    def test_finish_no_final_query_redirect(self) -> None:
        bar = self._make_bar()

        bar.finish("Done")
        html = self._read_html(bar)

        self.assertIn("This page will be closed in 10 seconds...", html)
        self.assertNotIn("final=1", html)
        self.assertNotIn("window.location.search", html)

    def test_complete_phase_renders_final_state_before_stop(self) -> None:
        bar = self._make_bar()
        bar.completed_phases = bar.total_phases - 1
        bar.current_phase = 1

        bar.complete_phase()
        html = self._read_html(bar)

        self.assertIn("Risk Assessment Completed!", html)
        self.assertNotIn('<meta http-equiv="refresh" content="1">', html)
        self.assertFalse(bar.is_running)


if __name__ == "__main__":
    unittest.main()
