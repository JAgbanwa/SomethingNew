#!/usr/bin/env python3
"""Embed common.m in the scripts, or check their embedded copies with --check.

The resulting Magma files require no load statements or other local files.
Only the marked helper region is generated; edit settings and drivers directly.
"""
import argparse
from pathlib import Path

START = "// BEGIN SHARED HELPERS (generated from common.m)"
END = "// END SHARED HELPERS"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    helpers = (root / "common.m").read_text(encoding="utf-8").rstrip()
    targets = [root / f"folder{i} " / f"codes.folder{i}" for i in range(1, 5)]
    targets.append(root / "self_test.m")
    stale = []
    for target in targets:
        text = target.read_text(encoding="utf-8")
        assert text.count(START) == text.count(END) == 1, target
        before, tail = text.split(START)
        _, after = tail.split(END)
        expected = before + START + "\n" + helpers + "\n" + END + after
        assert len(expected.encode("utf-8")) < 50000, target
        assert 'load "common.m";' not in expected, target
        if args.check:
            if text != expected:
                stale.append(str(target.relative_to(root)))
        else:
            target.write_text(expected, encoding="utf-8")
    if stale:
        raise SystemExit("Stale helper copies: " + ", ".join(stale))
    print("PASS: five standalone Magma files are synchronized and below 50000 bytes."
          if args.check else "Updated five standalone Magma files.")


if __name__ == "__main__":
    main()
