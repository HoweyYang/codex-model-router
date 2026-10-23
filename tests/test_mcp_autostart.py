import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "router_mcp_autostart", ROOT / "mcp-autostart.py"
)
mcp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mcp)


class McpAutostartTests(unittest.TestCase):
    def test_handshake_exposes_no_tools(self):
        messages = "\n".join(
            [
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            ]
        )
        output = io.StringIO()
        with mock.patch.object(mcp, "ensure_router"), mock.patch.object(
            sys, "stdin", io.StringIO(messages + "\n")
        ), mock.patch.object(sys, "stdout", output):
            self.assertEqual(mcp.main(), 0)

        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "router-autostart")
        self.assertEqual(responses[1]["result"]["tools"], [])


if __name__ == "__main__":
    unittest.main()
