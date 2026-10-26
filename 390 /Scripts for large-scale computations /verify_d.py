#!/usr/bin/env python3
"""Independently re-verify d-first hits with exact rational arithmetic.

For each record: x = X/2 and y = Y/2 with X, Y odd, y > 0 is the square root of
(x+6n)^2 + (36n^3-m)/x, the ORIGINAL unsquared equation
36n^3 - m = -2 d x^2 (y - (x+6n)) holds, and the integer cube components
-x+y, -x-y, 2x+6n have cube sum 6m. With --task, d must also lie in the task's
height shells. Uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from run_task import load_json
from dfirst_common import validate_task, verify_hit


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hits", type=Path)
    ap.add_argument("--m", type=int, default=65)
    ap.add_argument("--task", type=Path, help="also check that d lies in this task's shells")
    a = ap.parse_args(argv)
    m, shells = a.m, None
    if a.task:
        parsed = validate_task(load_json(a.task))
        m, shells = parsed["m"], (parsed["start"], parsed["stop"])
    count = 0
    for number, line in enumerate(a.hits.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            v = verify_hit(json.loads(line), m, shells)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            print(f"line {number}: INVALID: {exc}", file=sys.stderr)
            return 1
        count += 1
        A, B, C = v["components"]
        print(f"OK d={v['d']} n={v['n']} x={v['x']} y={v['y']}  ({A})^3 + ({B})^3 + ({C})^3 = {6 * m}")
    print(f"{count} hit(s) verified exactly for m={m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
