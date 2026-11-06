#!/usr/bin/env python3
"""Turn representations k = a^3 + b^3 + c^3 into the rational d of the original equation.

For k = 6m (production: m = 19, k = 114) the equation is

    36n^3 - m = -2 d x^2 ( -(x + 6n) + s ),   s = sqrt((x + 6n)^2 + (36n^3 - m)/x) >= 0,   (E)

and the two acceptable results are

    1. integer chart: n, x integers and s an integer;
    2. half chart:    n an integer, x = X/2 and s = Y/2 with X, Y odd.

With A = -x + s, B = -x - s, C = 2x + 6n one has, identically,
    A^3 + B^3 + C^3 - 6m = -6x (s^2 - (x+6n)^2 - (36n^3 - m)/x),
so a point of either chart is exactly a representation 6m = A^3 + B^3 + C^3 with
6 | A + B + C. Conversely, from a representation, choose which component is C,
order the other two so that A >= B, and put

    n = (A + B + C)/6,   x = -(A + B)/2,   s = (A - B)/2,   d = (A + C)/(A + B)   (A + B != 0).

A + B even gives the integer chart, A + B odd the half chart. Every point found is
checked here exactly against (E), the square-root condition and its chart.

For k = 114 every representation has exactly one even component and three distinct
components (c^3 + 2a^3 = 114 has no integer solution: PARI thue(thueinit(x^3+2,1),114) = []),
so it gives exactly one point of result 1 and two of result 2. A representation with a
repeated component (possible for other k) gives fewer distinct points.

  python3 to_d.py collected/hits.jsonl            # worker hits (fields x, y, z)
  python3 to_d.py --triple A B C [--k 114]        # one representation
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys


def points(a: int, b: int, c: int, k: int = 114) -> list[dict]:
    """All points of (E) attached to the representation k = a^3 + b^3 + c^3, each verified."""
    if a ** 3 + b ** 3 + c ** 3 != k:
        raise ValueError("not a representation of k")
    if k % 6:
        raise ValueError("k must be 6m")
    m = k // 6
    if (a + b + c) % 6:
        raise ValueError("a + b + c is not divisible by 6 (n would not be an integer)")
    out, seen = [], set()
    trip = (a, b, c)
    for i in range(3):
        C = trip[i]
        A, B = sorted((trip[(i + 1) % 3], trip[(i + 2) % 3]), reverse=True)
        if A + B == 0:
            continue                         # x = 0: the equation is undefined
        n = (A + B + C) // 6
        x = Fraction(-(A + B), 2)
        s = Fraction(A - B, 2)
        d = Fraction(A + C, A + B)
        key = (d, n, x)
        if key in seen:
            continue
        seen.add(key)
        # exact checks of everything the problem asks for
        N = 36 * n ** 3 - m
        U = x + 6 * n
        if s < 0 or s * s != U * U + N / x:
            raise AssertionError("square-root condition fails")
        if Fraction(N) != -2 * d * x * x * (-U + s):
            raise AssertionError("equation (E) fails")
        if x.denominator == 1 and s.denominator == 1:
            chart = "integer"                # result 1
        elif x.denominator == 2 and s.denominator == 2:
            chart = "half"                   # result 2: X = 2x and Y = 2s are odd
        else:
            raise AssertionError("point is in neither acceptable chart")
        out.append({"chart": chart, "result": 1 if chart == "integer" else 2, "d": f"{d.numerator}/{d.denominator}",
                    "n": str(n), "x": str(x), "sqrt": str(s),
                    "X": str(2 * x) if chart == "half" else None, "Y": str(2 * s) if chart == "half" else None,
                    "cubes": [str(A), str(B), str(C)]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hits", type=Path, nargs="*", help="hits.jsonl files from collect_gap.py or run_gap_task.py")
    ap.add_argument("--triple", type=int, nargs=3, metavar=("A", "B", "C"))
    ap.add_argument("--k", type=int, default=114)
    ap.add_argument("--json", type=Path, help="also write all points as JSON lines here")
    a = ap.parse_args()
    reps, seen = [], set()

    def add(r):
        key = tuple(sorted(r))
        if key not in seen:                  # the same representation from several files: once
            seen.add(key)
            reps.append(r)

    if a.triple:
        add(tuple(a.triple))
    for path in a.hits:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                h = json.loads(line)
                if h.get("type", "hit") != "hit":
                    continue                 # raw worker output: start / chunk / end records
                if int(h["k"]) != a.k:
                    raise SystemExit(f"hit for k={h['k']}, expected {a.k}")
                add((int(h["x"]), int(h["y"]), int(h["z"])))
    if not reps:
        print("no representations given (no hits yet)")
        return 0
    allp = []
    for r in reps:
        for p in points(*r, k=a.k):
            allp.append(p)
            extra = f"  X={p['X']}  Y={p['Y']}" if p["chart"] == "half" else ""
            print(f"result {p['result']} ({p['chart']} chart): d = {p['d']}   n = {p['n']}   x = {p['x']}   "
                  f"sqrt = {p['sqrt']}{extra}   [from {' + '.join(f'({c})^3' for c in p['cubes'])} = {a.k}]")
    if a.json:
        a.json.write_text("".join(json.dumps(p) + "\n" for p in allp), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
