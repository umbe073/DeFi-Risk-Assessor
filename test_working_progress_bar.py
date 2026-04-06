import base64
import tempfile
import unittest
from pathlib import Path

from working_progress_bar import WorkingProgressBar


class TestWorkingProgressBarLogoDataUrls(unittest.TestCase):
    def test_prefers_image_file_when_available(self):
        progress_bar = WorkingProgressBar.__new__(WorkingProgressBar)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image_name = "logo.png"
            image_bytes = b"\x89PNG\r\n\x1a\nfake-image"
            (tmp_path / image_name).write_bytes(image_bytes)

            progress_bar.LOGO_FILES = [
                (image_name, str(tmp_path / "legacy.b64"), "image/png"),
            ]

            urls = progress_bar._get_logo_data_urls(logo_dir=tmp)
            self.assertEqual(len(urls), 1)
            self.assertEqual(
                urls[0],
                f"data:image/png;base64,{base64.b64encode(image_bytes).decode('ascii')}",
            )

    def test_falls_back_to_legacy_b64_file(self):
        progress_bar = WorkingProgressBar.__new__(WorkingProgressBar)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image_name = "logo.png"
            legacy_value = base64.b64encode(b"legacy").decode("ascii")
            legacy_path = tmp_path / "legacy.b64"
            legacy_path.write_text(f"{legacy_value}\n")

            progress_bar.LOGO_FILES = [
                (image_name, str(legacy_path), "image/png"),
            ]

            urls = progress_bar._get_logo_data_urls(logo_dir=tmp)
            self.assertEqual(len(urls), 1)
            self.assertEqual(urls[0], f"data:image/png;base64,{legacy_value}")

    def test_returns_empty_string_when_no_sources_exist(self):
        progress_bar = WorkingProgressBar.__new__(WorkingProgressBar)
        progress_bar.LOGO_FILES = [("missing.png", "/tmp/missing.b64", "image/png")]

        urls = progress_bar._get_logo_data_urls(logo_dir="/tmp/does-not-exist")
        self.assertEqual(urls, [""])


if __name__ == "__main__":
    unittest.main()
