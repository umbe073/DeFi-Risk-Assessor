import re
import unittest
from pathlib import Path


class StyleCssRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.css = Path("style.css").read_text(encoding="utf-8")

    def test_body_uses_readable_default_font_size(self) -> None:
        body_match = re.search(r"body\s*\{(?P<body>.*?)\}", self.css, flags=re.S)
        self.assertIsNotNone(body_match, "Missing body selector in style.css")
        body_block = body_match.group("body")
        self.assertRegex(body_block, r"font-size:\s*16px\s*;")
        self.assertRegex(body_block, r"font-weight:\s*400\s*;")

    def test_h1_uses_responsive_clamped_size(self) -> None:
        h1_match = re.search(r"h1\s*\{(?P<h1>.*?)\}", self.css, flags=re.S)
        self.assertIsNotNone(h1_match, "Missing h1 selector in style.css")
        h1_block = h1_match.group("h1")
        self.assertRegex(h1_block, r"font-size:\s*clamp\(")
        self.assertNotIn("120pt", h1_block)
        self.assertNotIn("!important", h1_block)


if __name__ == "__main__":
    unittest.main()
