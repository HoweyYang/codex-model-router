import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "refresh-openai-catalog.py"
SPEC = importlib.util.spec_from_file_location("refresh_openai_catalog", SCRIPT)
refresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh)


class RefreshOpenAICatalogTests(unittest.TestCase):
    def test_extract_catalog_rejects_non_catalog_json(self):
        with self.assertRaises(ValueError):
            refresh.extract_catalog('{"unexpected": true}')

    def test_write_catalog_backs_up_and_replaces_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "models-openai.json"
            output.write_text('{"models": []}\n', encoding="utf-8")

            backup = refresh.write_catalog(
                {"models": [{"slug": "gpt-test"}]}, output
            )

            self.assertTrue(backup.exists())
            self.assertEqual(
                json.loads(backup.read_text(encoding="utf-8")), {"models": []}
            )
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["models"][0]["slug"],
                "gpt-test",
            )


if __name__ == "__main__":
    unittest.main()
