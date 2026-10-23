import importlib.util
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("codex_router", ROOT / "router.py")
router = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(router)


class UpstreamHandler(BaseHTTPRequestHandler):
    authorization = None
    payload = None

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        type(self).authorization = self.headers.get("authorization")
        type(self).payload = json.loads(self.rfile.read(length))
        body = b'{"output":[{"type":"message","content":[{"type":"output_text","text":"ROUTER_OK"}]}]}'
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class RouterTests(unittest.TestCase):
    def setUp(self):
        UpstreamHandler.authorization = None
        UpstreamHandler.payload = None
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        self.upstream_thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.upstream_thread.start()

        self.router_server = router.Server(("127.0.0.1", 0), router.Handler)
        router.Handler.routes = [
            {
                "name": "chatgpt",
                "match": ["gpt-"],
                "upstream": f"http://127.0.0.1:{self.upstream.server_port}/v1/responses",
                "auth": "passthrough",
                "proxy": "direct",
            }
        ]
        self.router_thread = threading.Thread(target=self.router_server.serve_forever, daemon=True)
        self.router_thread.start()

    def tearDown(self):
        self.router_server.shutdown()
        self.router_server.server_close()
        self.upstream.shutdown()
        self.upstream.server_close()
        router.Handler.routes = []

    def test_pick_route_uses_first_matching_prefix(self):
        routes = [
            {"name": "gpt", "match": ["gpt-"]},
            {"name": "deepseek", "match": ["deepseek-"]},
        ]
        self.assertEqual(router.pick_route(routes, "gpt-6-astra")["name"], "gpt")
        self.assertEqual(router.pick_route(routes, "deepseek-flash")["name"], "deepseek")
        self.assertIsNone(router.pick_route(routes, "unknown"))

    def test_router_forwards_chatgpt_credential_and_forces_streaming(self):
        body = json.dumps(
            {
                "model": "gpt-test",
                "input": [{"role": "user", "content": "hello"}],
                "store": False,
            }
        ).encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.router_server.server_port}/v1/responses",
            data=body,
            headers={
                "authorization": "Bearer chatgpt-token",
                "content-type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            result = response.read().decode()

        self.assertEqual(response.status, 200)
        self.assertIn("ROUTER_OK", result)
        self.assertEqual(UpstreamHandler.authorization, "Bearer chatgpt-token")
        self.assertTrue(UpstreamHandler.payload["stream"])

    def test_provider_auth_reads_env_key_from_codex_config(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "config.toml").write_text(
                '[model_providers.deepseek]\nenv_key = "ROUTER_TEST_KEY"\n',
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ,
                {"CODEX_HOME": str(home), "ROUTER_TEST_KEY": "deepseek-token"},
            ):
                self.assertEqual(router.provider_token("deepseek"), "deepseek-token")


if __name__ == "__main__":
    unittest.main()
