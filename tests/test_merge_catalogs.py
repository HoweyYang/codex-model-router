import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "merge_catalogs", ROOT / "tools" / "merge-catalogs.py"
)
merge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(merge)


class MergeCatalogTests(unittest.TestCase):
    def test_include_filters_stale_models(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            gpt = home / "gpt.json"
            deepseek = home / "deepseek.json"
            output = home / "router.json"
            gpt.write_text(
                json.dumps(
                    {
                        "models": [
                            {"slug": "gpt-old", "visibility": "list"},
                            {"slug": "gpt-new", "visibility": "list"},
                            {"slug": "gpt-hidden", "visibility": "hide"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            deepseek.write_text(
                json.dumps({"models": [{"slug": "deepseek-flash", "visibility": "list"}]}),
                encoding="utf-8",
            )

            result = merge.main(
                [
                    str(gpt),
                    str(deepseek),
                    "--out",
                    str(output),
                    "--include",
                    "gpt-new",
                    "--include",
                    "deepseek-flash",
                ]
            )

            self.assertEqual(result, 0)
            slugs = [model["slug"] for model in json.loads(output.read_text())["models"]]
            self.assertEqual(slugs, ["gpt-new", "deepseek-flash"])

    def test_keep_hidden_option_keeps_hidden_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / "source.json"
            output = home / "router.json"
            source.write_text(
                json.dumps({"models": [{"slug": "internal", "visibility": "hide"}]}),
                encoding="utf-8",
            )

            self.assertEqual(
                merge.main(
                    [
                        str(source),
                        "--out",
                        str(output),
                        "--include",
                        "internal",
                        "--keep-hidden",
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(output.read_text())["models"][0]["slug"], "internal")


if __name__ == "__main__":
    unittest.main()
