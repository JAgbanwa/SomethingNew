#!/usr/bin/env python3
"""Turn representations k = a^3 + b^3 + c^3 into the points (n, x, +-y) of the CE375 equation

    y^2 = (x + 6n + 3)^2 + N(n)/x,   N(n) = 36n^3 + 54n^2 + 27n - 58 = ((6n+3)^3 - 375)/6,

with n an integer, in the two accepted charts of ../Scripts for large-scale computations/README.md:
  integer chart  n, x, y integers;
  half chart     x = X/2, y = Y/2, X, Y odd.
Each point carries primitive_point (gcd(n, x, y) = 1, resp. gcd(X, Y) = 1),
primitive_cubes (gcd(a, b, c) = 1) and desired (both). The point-gcd test agrees
with the fixed-g folder; its diagnostic desired flag is point-only, whereas
this primitive-cube search requires both flags. Every point is checked exactly
on the equation before it is printed.

  python3 to_points375.py collected/hits.jsonl     # worker hits (raw output lines are accepted too)
  python3 to_points375.py --triple a b c [--k 375]

(Each point also determines d = -(x + 6n + 3 + y)/(2x); it is kept in the returned records for
cross-checks with the d-first folder but not printed.)
"""
from __future__ import annotations

import argparse
from fractions import Fraction
from math import gcd
import json
from pathlib import Path
import sys


def points(a: int, b: int, c: int, k: int) -> list[dict]:
    if a ** 3 + b ** 3 + c ** 3 != k:
        raise ValueError("not a representation of k")
    S = a + b + c
    if (S - 3) % 6:
        raise ValueError("a + b + c must be 3 (mod 6) for an integer n")
    n = (S - 3) // 6
    cube_gcd = gcd(gcd(a, b), c)
    out, seen = [], set()
    trip = (a, b, c)
    for i in range(3):
        C = trip[i]
        A, B = sorted((trip[(i + 1) % 3], trip[(i + 2) % 3]), reverse=True)
        if A + B == 0 or (A, B, C) in seen:
            continue
        seen.add((A, B, C))
        x, s = Fraction(-(A + B), 2), Fraction(A - B, 2)
        N = Fraction(S ** 3 - k, 6)
        if s * s != (x + S) ** 2 + N / x:               # the equation itself, exactly
            raise AssertionError("point fails the equation")
        d = -(x + S + s) / (2 * x)
        d_conj = -(x + S - s) / (2 * x)
        if d != Fraction(A + C, A + B) or d_conj != Fraction(B + C, A + B):
            raise AssertionError("closed form of d disagrees")
        if x.denominator == 1:
            chart, pg = "integer", gcd(gcd(n, int(x)), int(s))
        else:
            X, Y = int(2 * x), int(2 * s)
            if X % 2 == 0 or Y % 2 == 0:
                raise AssertionError("half chart needs X, Y odd")
            chart, pg = "half", gcd(X, Y)
        out.append({"chart": chart, "n": n, "x": x, "y": s, "d": d, "d_conjugate": d_conj,
                    "cubes": (A, B, C), "point_gcd": pg, "cube_gcd": cube_gcd,
                    "primitive_point": pg == 1, "primitive_cubes": cube_gcd == 1,
                    "desired": pg == 1 and cube_gcd == 1})
    return out


def show(p: dict) -> str:
    tag = "DESIRED" if p["desired"] else "non-primitive"
    return (f"{tag:13s} chart={p['chart']:7s} n = {p['n']}  x = {p['x']}  y = +-{p['y']}  "
            f"cubes = {p['cubes']}  gcd(point) = {p['point_gcd']}  gcd(cubes) = {p['cube_gcd']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hits", nargs="?", type=Path)
    ap.add_argument("--triple", nargs=3, type=int, metavar=("A", "B", "C"))
    ap.add_argument("--k", type=int, default=375)
    a = ap.parse_args()
    reps = []
    if a.triple:
        reps.append((tuple(a.triple), a.k))
    if a.hits:
        for line in a.hits.read_text().splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            rec = json.loads(line)
            if rec.get("type", "hit") != "hit":
                continue
            reps.append(((int(rec["x"]), int(rec["y"]), int(rec["z"])), int(rec["k"])))
    if not reps:
        ap.error("give a hits file or --triple")
    done = set()
    for (x, y, z), k in reps:
        key = (k, tuple(sorted((x, y, z))))
        if key in done:
            continue
        done.add(key)
        print(f"{x}^3 + {y}^3 + {z}^3 = {k}")
        for p in points(x, y, z, k):
            print("  " + show(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
