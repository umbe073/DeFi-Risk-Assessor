import base64
import os
import tempfile
import unittest

from working_progress_bar import WorkingProgressBar


class WorkingProgressBarLogoTests(unittest.TestCase):
    def test_get_logo_data_urls_reads_image_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logo_payloads = {
                "1inch-exchange-logo.png": b"\x89PNG\r\n\x1a\nfakepng",
                "bitquery-logo.jpg": b"\xff\xd8\xff\xe0fakejpg",
            }

            for filename, payload in logo_payloads.items():
                path = os.path.join(tmpdir, filename)
                with open(path, "wb") as image_file:
                    image_file.write(payload)

            progress_bar = WorkingProgressBar.__new__(WorkingProgressBar)
            urls = progress_bar._get_logo_data_urls(logo_dir=tmpdir)

            self.assertEqual(len(urls), 5)
            self.assertTrue(urls[0].startswith("data:image/png;base64,"))
            self.assertTrue(urls[1].startswith("data:image/jpeg;base64,"))

            encoded_png = urls[0].split(",", 1)[1]
            self.assertEqual(base64.b64decode(encoded_png), logo_payloads["1inch-exchange-logo.png"])

            self.assertEqual(urls[2], "")
            self.assertEqual(urls[3], "")
            self.assertEqual(urls[4], "")


if __name__ == "__main__":
    unittest.main()
