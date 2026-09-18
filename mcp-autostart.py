#!/usr/bin/env python3
"""Autostart hook for codex-model-router.

Register this file as a no-tool MCP server in ~/.codex/config.toml:

    [mcp_servers.router-autostart]
    command = "python.exe"
    args = ["<path-to-this-file>"]

Codex launches every configured MCP server when it starts. This one exposes no
tools; its only job is to be launched. On startup it makes sure the router is
listening, then answers the MCP handshake and idles on stdin. When Codex exits,
stdin closes and this process goes away with it. No logon task, no Startup
folder, no separate lifetime: the router only exists while Codex does.

If the router is already up (e.g. you started it by hand), this exits the
ensure step immediately and does not launch a second copy.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def router_port() -> int:
    try:
        cfg = json.loads((codex_home() / "model-router.json").read_text(encoding="utf-8"))
        listen = cfg.get("listen", "127.0.0.1:8765")
        return int(str(listen).rsplit(":", 1)[-1])
    except Exception:
        return 8765


def router_alive(port: int) -> bool:
    try:
        urllib.request.urlopen(
            f"http://127.0.0.1:{port}/v1/models", timeout=1.0
        )
        return True
    except Exception:
        return False


def ensure_router() -> None:
    port = router_port()
    if router_alive(port):
        return
    root = Path(__file__).resolve().parent
    # We are running under python.exe; the router itself should run hidden as
    # pythonw.exe, next to this interpreter.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        pythonw = Path("pythonw.exe")
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    subprocess.Popen(
        [str(pythonw), str(root / "router.py")],
        creationflags=flags,
        close_fds=True,
    )
    for _ in range(20):
        time.sleep(0.25)
        if router_alive(port):
            return


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main() -> int:
    ensure_router()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        msg_id = msg.get("id")
        method = msg.get("method", "")
        if msg_id is None:
            # Notifications (e.g. notifications/initialized) need no reply.
            continue
        if method == "initialize":
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {
                        "name": "router-autostart",
                        "version": "0.1.0",
                    },
                },
            })
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": []}})
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": msg_id, "result": {}})
        else:
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
