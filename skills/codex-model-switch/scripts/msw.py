#!/usr/bin/env python3
"""codex-model-switch — switch Codex between models and providers with one command.

Keeps a registry of "targets" (a model plus its provider and any extra
config.toml keys) and rewrites a single marked block inside
$CODEX_HOME/config.toml. Nothing outside that block is touched, and every
write is preceded by a timestamped backup.

Standard library only. Run `msw.py --help` for the command list.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

BLOCK_START = "# >>> codex-model-switch >>>"
BLOCK_END = "# <<< codex-model-switch <<<"
AGENTS_START = "# >>> codex-model-switch:agents >>>"
AGENTS_END = "# <<< codex-model-switch:agents <<<"

CORE_KEYS = ("model", "model_provider", "model_catalog_json")
ASSIGN_RE = re.compile(r"^\s*#?\s*([A-Za-z0-9_-]+)\s*=")
TABLE_RE = re.compile(r"^\s*\[")

# `codex doctor` prints box-drawing and check-mark glyphs that some Windows
# consoles cannot encode. Fold them down to ASCII so output never crashes.
SYMBOLS = {
    "\u2713": "[ok]",
    "\u2717": "[x]",
    "\u26a0": "[!]",
    "\u25b8": ">",
    "\u2192": "->",
    "\u00b7": "-",
    "\u2500": "-",
}


def safe(text: str) -> str:
    for glyph, ascii_form in SYMBOLS.items():
        text = text.replace(glyph, ascii_form)
    return text


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def registry_file() -> Path:
    return codex_home() / "model-switch.json"


def config_file() -> Path:
    return codex_home() / "config.toml"


def codex_bin() -> str:
    return os.environ.get("CODEX_BIN") or shutil.which("codex") or "codex"


def die(message: str) -> "None":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


# --------------------------------------------------------------------------- registry

def load_registry() -> dict:
    path = registry_file()
    if not path.exists():
        return {"version": 1, "current": None, "targets": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_registry(reg: dict) -> None:
    codex_home().mkdir(parents=True, exist_ok=True)
    registry_file().write_text(
        json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def get_target(reg: dict, name: str) -> dict:
    try:
        return reg["targets"][name]
    except KeyError:
        available = ", ".join(sorted(reg["targets"])) or "(none yet)"
        die(f"unknown target '{name}'. Known targets: {available}")


def managed_keys(reg: dict) -> set:
    keys = set(CORE_KEYS)
    for spec in reg["targets"].values():
        keys.update(spec)
    keys.discard("_note")
    return keys


# --------------------------------------------------------------------------- config.toml

def render_value(value) -> str:
    # JSON scalars are valid TOML scalars, which keeps this dependency-free.
    return json.dumps(value, ensure_ascii=False)


def render_block(keys: dict) -> list:
    lines = [BLOCK_START]
    for key in sorted(keys):
        lines.append(f"{key} = {render_value(keys[key])}")
    lines.append(BLOCK_END)
    return lines


def read_current_keys(reg: dict) -> dict:
    """Top-level keys this tool manages, as they appear in config.toml today."""
    path = config_file()
    if not path.exists():
        return {}
    wanted = managed_keys(reg)
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if TABLE_RE.match(line):
            break
        if line.strip().startswith("#"):
            continue
        match = ASSIGN_RE.match(line)
        if not match or match.group(1) not in wanted:
            continue
        raw = line.split("=", 1)[1].strip()
        try:
            found[match.group(1)] = json.loads(raw)
        except ValueError:
            found[match.group(1)] = raw.strip("'\"")
    return found


def apply_keys(keys: dict, reg: dict) -> Path:
    """Write `keys` into the managed block, returning the backup path."""
    path = config_file()
    if not path.exists():
        die(f"no config file at {path}")

    backup = path.with_name(f"{path.name}.bak-msw-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, backup)

    lines = path.read_text(encoding="utf-8").splitlines()
    block = render_block(keys)

    if BLOCK_START in lines:
        start = lines.index(BLOCK_START)
        end = lines.index(BLOCK_END, start)
        lines[start : end + 1] = block
    else:
        # Adopt the config: drop the managed top-level keys, then own them.
        first_table = next(
            (n for n, line in enumerate(lines) if TABLE_RE.match(line)), len(lines)
        )
        keep = managed_keys(reg)
        head = []
        for line in lines[:first_table]:
            match = ASSIGN_RE.match(line)
            if match and match.group(1) in keep:
                continue
            head.append(line)
        while head and not head[-1].strip():
            head.pop()
        tail = lines[first_table:]
        if head:
            head.append("")
        lines = head + block + ([""] if tail else []) + tail

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return backup


# --------------------------------------------------------------------------- commands

def cmd_list(args) -> int:
    reg = load_registry()
    if not reg["targets"]:
        print("No targets yet. Create one with:  msw.py add <name> --model <model>")
        print("Or adopt the current config:      msw.py adopt <name>")
        return 0
    current = read_current_keys(reg)
    for name in sorted(reg["targets"]):
        keys = {k: v for k, v in reg["targets"][name].items() if k != "_note"}
        same = all(current.get(k) == v for k, v in keys.items())
        marker = "*" if same else " "
        model = keys.get("model", "?")
        provider = keys.get("model_provider", "openai")
        note = reg["targets"][name].get("_note", "")
        print(f"{marker} {name:<16} {model}  [{provider}]  {note}".rstrip())
    print("\n* = matches the current config.toml")
    return 0


def cmd_adopt(args) -> int:
    reg = load_registry()
    keys = read_current_keys(reg)
    missing = [k for k in CORE_KEYS if k not in keys]
    if missing:
        print(f"warning: config.toml has no explicit {', '.join(missing)}", file=sys.stderr)
    reg["targets"][args.name] = keys
    reg["current"] = args.name
    save_registry(reg)
    print(f"adopted current config as target '{args.name}': {keys}")
    return 0


def cmd_add(args) -> int:
    reg = load_registry()
    keys = dict(reg["targets"].get(args.name, {}))
    if args.model:
        keys["model"] = args.model
    if args.provider:
        keys["model_provider"] = args.provider
    if args.catalog:
        keys["model_catalog_json"] = args.catalog
    if args.effort:
        keys["model_reasoning_effort"] = args.effort
    for extra in args.key or []:
        if "=" not in extra:
            die(f"--key expects key=value, got '{extra}'")
        key, value = extra.split("=", 1)
        keys[key.strip()] = value.strip()
    if not keys.get("model"):
        die("a target needs --model (or --key model=...)")
    if args.note:
        keys["_note"] = args.note
    reg["targets"][args.name] = keys
    save_registry(reg)
    print(f"target '{args.name}' saved: { {k: v for k, v in keys.items() if k != '_note'} }")
    return 0


def cmd_remove(args) -> int:
    reg = load_registry()
    if args.name not in reg["targets"]:
        die(f"unknown target '{args.name}'")
    del reg["targets"][args.name]
    if reg.get("current") == args.name:
        reg["current"] = None
    save_registry(reg)
    print(f"target '{args.name}' removed (config.toml untouched)")
    return 0


def cmd_switch(args) -> int:
    reg = load_registry()
    keys = {k: v for k, v in get_target(reg, args.name).items() if k != "_note"}
    if args.dry_run:
        print("would write into config.toml:")
        for key in sorted(keys):
            print(f"  {key} = {render_value(keys[key])}")
        return 0
    backup = apply_keys(keys, reg)
    reg["current"] = args.name
    save_registry(reg)
    print(f"switched to '{args.name}': {keys}")
    print(f"backup: {backup.name}")
    print("CLI CLIENTS: takes effect on the next `codex` run.")
    print("DESKTOP APP: start a new chat; restart the app if it still shows the old model.")
    return 0


def cmd_current(args) -> int:
    reg = load_registry()
    print(json.dumps(read_current_keys(reg), indent=2, ensure_ascii=False))
    return 0


def cmd_test(args) -> int:
    reg = load_registry()
    keys = {k: v for k, v in get_target(reg, args.name).items() if k != "_note"}
    cmd = [codex_bin(), "exec", "--skip-git-repo-check", "--sandbox", "read-only"]
    for key in sorted(keys):
        cmd += ["-c", f"{key}={render_value(keys[key])}"]
    cmd.append(args.prompt)
    print(f"running: {' '.join(cmd[:-1])} <prompt>")
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = (proc.stdout or "").strip().splitlines()[-8:]
    print("\n".join(tail))
    if proc.stderr.strip():
        print("stderr:", proc.stderr.strip().splitlines()[-3:])
    print(f"exit code: {proc.returncode}")
    return 0 if proc.returncode == 0 else 1


def cmd_run(args) -> int:
    reg = load_registry()
    keys = {k: v for k, v in get_target(reg, args.name).items() if k != "_note"}
    flags = " ".join(f'-c {k}={render_value(keys[k])}' for k in sorted(keys))
    print(f"codex {flags}   # one-off, does not touch config.toml")
    return 0


def cmd_doctor(args) -> int:
    proc = subprocess.run(
        [codex_bin(), "doctor"], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    wanted = ("model ", "model  ", "auth", "proxy", "config.toml", "reachab", "provider")
    for line in (proc.stdout or "").splitlines():
        if any(token in line for token in wanted):
            print(safe(line.rstrip()))
    # `codex doctor` exits non-zero when it reports warnings; showing them is
    # the successful outcome here, so this command always exits 0.
    return 0


# --------------------------------------------------------------------------- multi-model teams

def toml_multiline(text: str) -> str:
    body = text.strip().replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return f'developer_instructions = """\n{body}\n"""\n'


def agent_file(name: str) -> Path:
    return codex_home() / "agents" / f"{name}.toml"


def cmd_team_add(args) -> int:
    reg = load_registry()
    target = get_target(reg, args.target)
    lines = [f'name = "{args.name}"']
    lines.append(f'description = {render_value(args.description or f"{args.name} agent")}')
    if "model" in target:
        lines.append(f"model = {render_value(target['model'])}")
    if "model_provider" in target:
        lines.append(f"model_provider = {render_value(target['model_provider'])}")
    if args.effort:
        lines.append(f"model_reasoning_effort = {render_value(args.effort)}")
    if args.sandbox:
        lines.append(f"sandbox_mode = {render_value(args.sandbox)}")

    path = agent_file(args.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(lines) + "\n"
    if args.instructions:
        body += toml_multiline(args.instructions)
    path.write_text(body, encoding="utf-8")
    print(f"wrote {path}")
    print(f"  model    {target.get('model')}")
    print(f"  provider {target.get('model_provider', 'openai')}")
    return 0


def cmd_team_list(args) -> int:
    directory = codex_home() / "agents"
    if not directory.is_dir():
        print("no custom agents defined")
        return 0
    for path in sorted(directory.glob("*.toml")):
        text = path.read_text(encoding="utf-8")
        model = re.search(r'^model\s*=\s*"([^"]+)"', text, re.M)
        provider = re.search(r'^model_provider\s*=\s*"([^"]+)"', text, re.M)
        print(f"{path.stem:<20} {model.group(1) if model else '?':<22} [{provider.group(1) if provider else 'inherit'}]")
    return 0


def cmd_team_remove(args) -> int:
    path = agent_file(args.name)
    if not path.exists():
        die(f"no agent file at {path}")
    path.unlink()
    print(f"removed {path}")
    return 0


def cmd_team_init(args) -> int:
    path = config_file()
    text = path.read_text(encoding="utf-8")
    if re.search(r"^\s*\[agents\]", text, re.M):
        print("[agents] already present in config.toml; leaving it alone")
        return 0
    shutil.copy2(path, path.with_name(f"{path.name}.bak-msw-{time.strftime('%Y%m%d-%H%M%S')}"))
    block = [
        AGENTS_START,
        "[agents]",
        f"max_concurrent_threads_per_session = {args.max_threads}",
        "",
        "[agents.research]",
        AGENTS_END,
    ]
    path.write_text(text.rstrip("\n") + "\n\n" + "\n".join(block) + "\n", encoding="utf-8")
    print(f"added [agents] to {path}")
    print("Edit the table by hand to set defaults; custom per-agent files live in")
    print(f"  {codex_home() / 'agents'}")
    return 0


# --------------------------------------------------------------------------- cli

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="msw.py",
        description="Switch Codex between models/providers and set up multi-model teams.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list targets and mark the active one").set_defaults(func=cmd_list)
    sub.add_parser("current", help="show the managed keys as config.toml has them").set_defaults(func=cmd_current)
    sub.add_parser("doctor", help="show model/provider/auth/proxy lines from `codex doctor`").set_defaults(func=cmd_doctor)

    adopt = sub.add_parser("adopt", help="save the current config.toml settings as a target")
    adopt.add_argument("name")
    adopt.set_defaults(func=cmd_adopt)

    add = sub.add_parser("add", help="create or update a target")
    add.add_argument("name")
    add.add_argument("--model")
    add.add_argument("--provider")
    add.add_argument("--catalog", help="path to a model catalog json")
    add.add_argument("--effort", help="model_reasoning_effort")
    add.add_argument("--key", action="append", help="extra config.toml key=value, repeatable")
    add.add_argument("--note")
    add.set_defaults(func=cmd_add)

    remove = sub.add_parser("remove", help="delete a target (never touches config.toml)")
    remove.add_argument("name")
    remove.set_defaults(func=cmd_remove)

    switch = sub.add_parser("switch", help="make a target the default in config.toml")
    switch.add_argument("name")
    switch.add_argument("--dry-run", action="store_true")
    switch.set_defaults(func=cmd_switch)

    test = sub.add_parser("test", help="run one real request with a target, without switching")
    test.add_argument("name")
    test.add_argument("--prompt", default="Reply with exactly: OK")
    test.set_defaults(func=cmd_test)

    run = sub.add_parser("run", help="print the one-off command that uses a target")
    run.add_argument("name")
    run.set_defaults(func=cmd_run)

    team = sub.add_parser("team", help="multi-model collaboration helpers").add_subparsers(
        dest="team_command", required=True
    )
    team_add = team.add_parser("add", help="write a custom agent bound to a target")
    team_add.add_argument("name")
    team_add.add_argument("--target", required=True)
    team_add.add_argument("--effort")
    team_add.add_argument("--sandbox", default="read-only")
    team_add.add_argument("--description")
    team_add.add_argument("--instructions")
    team_add.set_defaults(func=cmd_team_add)
    team.add_parser("list", help="list custom agents").set_defaults(func=cmd_team_list)
    team_rm = team.add_parser("rm", help="delete a custom agent")
    team_rm.add_argument("name")
    team_rm.set_defaults(func=cmd_team_remove)
    team_init = team.add_parser("init", help="add an [agents] table to config.toml")
    team_init.add_argument("--max-threads", type=int, default=6)
    team_init.set_defaults(func=cmd_team_init)

    return parser


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
