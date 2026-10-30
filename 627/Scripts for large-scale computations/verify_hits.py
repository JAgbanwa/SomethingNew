#!/usr/bin/env python3
"""Independently re-verify every hit in one or more hits.jsonl files.

Checks, in exact rational arithmetic, the ORIGINAL equation
  36n^3+54n^2+27n-100 = -2*d*x^2*(-(x+6n+3) + s),  s = sqrt((x+6n+3)^2 + N/x) >= 0,
the chart (x, s integers; or x = X/2, s = Y/2 with X, Y odd) and the cube identity.
Usage: python3 verify_hits.py hits.jsonl [...] [--k 627]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from common627 import PRODUCTION_K, verify_hit


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
                print(f"OK  d={v['d']} chart={v['chart']} n={v['n']} x={v['x']} s={v['s']}")
            except Exception as exc:  # noqa: BLE001
                bad += 1
                print(f"BAD {path}:{i}: {exc}")
    print(f"{good} verified, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
