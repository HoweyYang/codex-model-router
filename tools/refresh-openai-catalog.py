#!/usr/bin/env python3
"""Refresh Codex's native OpenAI model catalog without touching provider settings."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def timestamp():
    return time.strftime("%Y%m%d-%H%M%S")


def codex_home():
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def extract_catalog(text):
    try:
        catalog = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("Codex did not return JSON model catalog data") from error
    if not isinstance(catalog, dict) or not isinstance(catalog.get("models"), list):
        raise ValueError("Codex did not return a model catalog")
    return catalog


def write_catalog(catalog, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    backup = output.with_name(output.name + ".bak-" + timestamp())
    if output.exists():
        shutil.copy2(output, backup)

    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=str(output.parent)
        ) as handle:
            temporary = Path(handle.name)
            json.dump(catalog, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary.replace(output)
    except Exception:
        if temporary and temporary.exists():
            temporary.unlink()
        raise
    return backup if backup.exists() else None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Save the model catalog reported by the installed Codex CLI."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=codex_home() / "models-openai.json",
        help="catalog destination (default: ~/.codex/models-openai.json)",
    )
    parser.add_argument("--codex-bin", default="codex", help="Codex executable to run")
    args = parser.parse_args(argv)

    result = subprocess.run(
        [args.codex_bin, "debug", "models"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise SystemExit("codex debug models failed; existing catalog was left unchanged")
    try:
        catalog = extract_catalog(result.stdout)
    except ValueError as error:
        raise SystemExit(f"{error}; existing catalog was left unchanged") from error

    backup = write_catalog(catalog, args.out)
    print(f"wrote {args.out} ({len(catalog['models'])} models)")
    if backup:
        print(f"backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
