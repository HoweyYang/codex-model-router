import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProfileTemplateTests(unittest.TestCase):
    def test_example_profiles_are_native_and_router_free(self):
        profiles = json.loads(
            (ROOT / "examples" / "model-switch.json").read_text(encoding="utf-8")
        )

        self.assertGreaterEqual(set(profiles["targets"]), {"gpt", "deepseek"})
        self.assertTrue(
            all(
                target.get("model_provider") != "router"
                for target in profiles["targets"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
