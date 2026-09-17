#!/usr/bin/env python3
"""codex-model-router - put one provider in front of many model backends.

Codex can only talk to one provider per process, and its model picker can only
list models that provider knows about. This router presents a single provider
to Codex and dispatches each request to the right upstream based on the model
name, so every backend shows up in the same picker.

Two auth styles:

  passthrough  forward whatever credential Codex sent (this is what keeps the
               ChatGPT subscription working with no API key), including 401s,
               so Codex refreshes its own token.
  provider     look the key up from Codex's own config.toml provider entry or
               from an environment variable.

Standard library only. Configure with ~/.codex/model-router.json.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOP_BY_HOP = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "accept-encoding",
    "te",
    "trailer",
    "upgrade",
}


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def log(message: str) -> None:
    """Write to stdout when there is one, otherwise to a log file.

    Started with pythonw.exe there is no console, so stdout is unavailable and
    the log file is the only way to see what the router did.
    """
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n"
    stream = sys.stdout
    if stream is not None:
        try:
            stream.write(line)
            stream.flush()
            return
        except Exception:
            pass
    try:
        with open(codex_home() / "model-router.log", "a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass


def load_config() -> dict:
    path = codex_home() / "model-router.json"
    if not path.exists():
        raise SystemExit(
            f"missing {path}\n"
            "Copy examples/model-router.json there and edit the routes."
        )
    config = json.loads(path.read_text(encoding="utf-8"))
    if not config.get("routes"):
        raise SystemExit(f"{path} defines no routes")
    for route in config["routes"]:
        for field in ("name", "match", "upstream"):
            if field not in route:
                raise SystemExit(f"route is missing '{field}': {route}")
    return config


def provider_token(provider_id: str) -> str | None:
    """Read a bearer token from Codex's config.toml for the given provider."""
    config = codex_home() / "config.toml"
    if not config.exists():
        return None
    section = re.compile(rf"^\s*\[model_providers\.{re.escape(provider_id)}\]\s*$")
    assignment = re.compile(r'^\s*(experimental_bearer_token|env_key)\s*=\s*"([^"]+)"')
    inside = False
    for line in config.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("["):
            inside = bool(section.match(line))
            continue
        if not inside:
            continue
        match = assignment.match(line)
        if not match:
            continue
        if match.group(1) == "experimental_bearer_token":
            return match.group(2)
        return os.environ.get(match.group(2))
    return None


def resolve_auth(route: dict) -> str | None:
    auth = route.get("auth", "passthrough")
    if auth == "passthrough":
        return None
    if isinstance(auth, str) and auth.startswith("env:"):
        return os.environ.get(auth[4:])
    if isinstance(auth, dict):
        if "env" in auth:
            return os.environ.get(auth["env"])
        if "provider" in auth:
            return provider_token(auth["provider"])
    return None


def pick_route(routes: list, model: str) -> dict | None:
    for route in routes:
        patterns = route.get("match") or []
        if any(model == p or model.startswith(p) for p in patterns):
            return route
    return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    routes: list = []

    def log_message(self, *args):
        pass

    def _fail(self, status: int, message: str) -> None:
        body = json.dumps({"error": {"message": message}}).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw)
            model = payload["model"]
        except Exception as error:
            self._fail(400, f"could not read model from request: {error}")
            return

        route = pick_route(self.routes, model)
        if route is None:
            self._fail(404, f"no route configured for model '{model}'")
            return

        # The ChatGPT backend rejects non-streaming requests.
        payload["stream"] = True
        body = json.dumps(payload).encode()

        headers = {}
        for key, value in self.headers.items():
            if key.lower() in HOP_BY_HOP:
                continue
            headers[key] = value
        headers["content-type"] = "application/json"
        headers["accept"] = "text/event-stream"
        headers["accept-encoding"] = "identity"

        token = resolve_auth(route)
        if token:
            headers["authorization"] = f"Bearer {token}"

        request = urllib.request.Request(
            route["upstream"], data=body, headers=headers, method="POST"
        )
        try:
            response = urllib.request.urlopen(request, timeout=route.get("timeout", 600))
        except urllib.error.HTTPError as error:
            # Pass upstream errors straight through, including 401, so Codex's
            # own token refresh keeps working.
            detail = error.read()
            log(f"{model} -> {route['name']} -> HTTP {error.code}")
            self.send_response(error.code)
            self.send_header("content-type", error.headers.get("content-type", "application/json"))
            self.send_header("content-length", str(len(detail)))
            self.end_headers()
            self.wfile.write(detail)
            return
        except Exception as error:
            log(f"{model} -> {route['name']} -> FAILED {error}")
            self._fail(502, f"upstream unreachable: {error}")
            return

        log(f"{model} -> {route['name']} -> HTTP {response.status}")
        self.send_response(response.status)
        self.send_header("content-type", response.headers.get("content-type", "text/event-stream"))
        self.send_header("cache-control", "no-cache")
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()

        try:
            while True:
                chunk = response.read(4096)
                if not chunk:
                    break
                self.wfile.write(f"{len(chunk):X}\r\n".encode())
                self.wfile.write(chunk)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            response.close()

    def do_GET(self):
        body = json.dumps({"status": "ok", "routes": [r["name"] for r in self.routes]}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    config = load_config()
    Handler.routes = config["routes"]
    host, _, port = config.get("listen", "127.0.0.1:8765").rpartition(":")
    server = ThreadingHTTPServer((host or "127.0.0.1", int(port)), Handler)
    log(f"router listening on http://{host}:{port}")
    for route in Handler.routes:
        log(f"  {route['name']:<12} {'/'.join(route['match'])} -> {route['upstream']}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
