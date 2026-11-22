#!/usr/bin/env python3
"""Independently re-verify every point in one or more hits.jsonl files.

Checks, in exact rational arithmetic,
  y^2 = (x + 6n+3)^2 + (36n^3 + 54n^2 + 27n - 58)/x
with n an integer, the form (x, y integers; or x = X/2, y = Y/2 with X, Y odd),
and the primitivity flags.
Usage: python3 verify_hits.py hits.jsonl [...] [--k 375]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from common375 import PRODUCTION_K, verify_hit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", type=Path, nargs="+")
    ap.add_argument("--k", type=int, default=PRODUCTION_K)
    args = ap.parse_args()
    bad = good = 0
    for path in args.files:
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                v = verify_hit(json.loads(line), args.k)
                good += 1
                tag = "DESIRED" if v["desired"] else "non-primitive"
                print(f"OK  [{tag}] form={v['form']} n={v['n']} x={v['x']} y=+-{v['y']}")
            except Exception as exc:  # noqa: BLE001
                bad += 1
                print(f"BAD {path}:{i}: {exc}")
    print(f"{good} verified, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
