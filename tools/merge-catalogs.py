#!/usr/bin/env python3
"""Merge several Codex model catalogs into one, which is what lets a single
picker list models from every backend the router fronts.

Hidden entries (visibility = "hide") are dropped, and the first occurrence of
a slug wins so an earlier file can override a later one.
"""

import argparse
import json
from pathlib import Path


def load(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    models = data.get("models", data if isinstance(data, list) else [])
    return [entry for entry in models if entry.get("visibility") != "hide"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalogs", nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--keep-hidden", action="store_true")
    args = parser.parse_args()

    merged, seen = [], set()
    for path in args.catalogs:
        for entry in load(path):
            slug = entry.get("slug")
            if not slug or slug in seen:
                continue
            seen.add(slug)
            merged.append(entry)

    if not merged:
        raise SystemExit("no models found in the given catalogs")

    args.out.write_text(
        json.dumps({"models": merged}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {args.out} with {len(merged)} models")
    for entry in merged:
        print(f"  {entry['slug']:<24} {entry.get('display_name', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
