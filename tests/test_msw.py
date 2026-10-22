import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "codex-model-switch" / "scripts" / "msw.py"
SPEC = importlib.util.spec_from_file_location("msw", SCRIPT)
msw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(msw)


def registry():
    return {
        "version": 1,
        "current": "deepseek",
        "targets": {
            "deepseek": {
                "model": "deepseek-flash",
                "model_provider": "deepseek",
            }
        },
    }


class ModelSwitchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.config = self.home / "config.toml"
        self.env = mock.patch.dict(os.environ, {"CODEX_HOME": str(self.home)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_apply_keys_replaces_only_managed_block(self):
        self.config.write_text(
            'model = "old"\n\n[model_providers.deepseek]\nname = "DeepSeek"\n',
            encoding="utf-8",
        )

        backup = msw.apply_keys(
            {"model": "deepseek-flash", "model_provider": "deepseek"}, registry()
        )

        text = self.config.read_text(encoding="utf-8")
        self.assertTrue(backup.exists())
        self.assertIn("# >>> codex-model-switch >>>", text)
        self.assertIn('[model_providers.deepseek]\nname = "DeepSeek"', text)

    def test_switch_dry_run_does_not_write_config(self):
        original = 'model = "old"\n'
        self.config.write_text(original, encoding="utf-8")
        (self.home / "model-switch.json").write_text(
            json.dumps(registry()), encoding="utf-8"
        )

        self.assertEqual(msw.main(["switch", "deepseek", "--dry-run"]), 0)
        self.assertEqual(self.config.read_text(encoding="utf-8"), original)

    def test_unterminated_managed_block_fails_without_rewriting_config(self):
        original = '# >>> codex-model-switch >>>\nmodel = "old"\n'
        self.config.write_text(original, encoding="utf-8")

        with self.assertRaises(SystemExit) as error:
            msw.apply_keys({"model": "deepseek-flash"}, registry())

        self.assertEqual(error.exception.code, 1)
        self.assertEqual(self.config.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
