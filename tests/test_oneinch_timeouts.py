import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = PROJECT_ROOT / "defi_complete_risk_assessment.py"


class TestOneInchTimeouts(unittest.TestCase):
    def test_all_fetch_1inch_requests_have_timeout(self):
        tree = ast.parse(SOURCE_FILE.read_text(encoding="utf-8"))
        target_functions = {}

        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("fetch_1inch_"):
                target_functions[node.name] = node

        self.assertTrue(target_functions, "Expected fetch_1inch_* functions to exist")

        missing_timeout = []
        for fn_name, fn_node in target_functions.items():
            for call in ast.walk(fn_node):
                if not isinstance(call, ast.Call):
                    continue
                if not isinstance(call.func, ast.Attribute):
                    continue
                if call.func.attr != "get":
                    continue
                if not isinstance(call.func.value, ast.Name) or call.func.value.id != "requests":
                    continue

                has_timeout = any(
                    isinstance(kw, ast.keyword) and kw.arg == "timeout" for kw in call.keywords
                )
                if not has_timeout:
                    missing_timeout.append((fn_name, call.lineno))

        self.assertEqual(
            missing_timeout,
            [],
            f"Missing timeout in 1inch request calls: {missing_timeout}",
        )


if __name__ == "__main__":
    unittest.main()
