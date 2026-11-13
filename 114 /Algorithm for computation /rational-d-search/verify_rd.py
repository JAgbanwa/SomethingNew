#!/usr/bin/env python3
"""Exact verifier for rd_worker hits.

Given n and x (an integer, or X/2 with X odd), check with exact rational arithmetic that

    36n^3 - 19 = -2 d x^2 ( -(x+6n) + sqrt((x+6n)^2 + (36n^3-19)/x) )        (E)

holds for a rational d, and return that d (it is unique).  The square root is the principal
(non-negative) one and must be rational; d = -(sqrt(...) + x + 6n) / (2x).

usage:
    verify_rd.py HITFILE...        reads "HIT int n x" / "HIT half n X" lines, prints JSON lines
    verify_rd.py --nx n x          x may be written as an integer or as X/2
"""
from __future__ import annotations

import json
import sys
from fractions import Fraction
from math import isqrt


def rational_sqrt(q: Fraction):
    """Exact non-negative square root of a rational, or None."""
    if q < 0:
        return None
    a, b = q.numerator, q.denominator
    ra, rb = isqrt(a), isqrt(b)
    if ra * ra != a or rb * rb != b:
        return None
    return Fraction(ra, rb)


def solve(n: int, x: Fraction):
    """Return a dict describing the solution (n, x) of (E), or None if there is none."""
    if x == 0:
        return None
    if not (x.denominator == 1 or (x.denominator == 2 and x.numerator % 2)):
        return None
    N = 36 * n ** 3 - 19
    s = x + 6 * n
    rad = s * s + Fraction(N) / x
    R = rational_sqrt(rad)
    if R is None:
        return None
    d = -(R + s) / (2 * x)
    # (E) itself, exactly
    if Fraction(N) != -2 * d * x * x * (-s + R):
        return None
    chart = "int" if x.denominator == 1 else "half"
    return {
        "chart": chart,
        "n": n,
        "x": str(x),
        "d": str(d),
        "sqrt": str(R),
        "sqrt_integral": R.denominator in (1, 2) if chart == "half" else R.denominator == 1,
        "d_num_digits": len(str(abs(d.numerator))),
        "d_den_digits": len(str(d.denominator)),
    }


def parse_hit(line: str):
    p = line.split()
    if len(p) != 4 or p[0] != "HIT" or p[1] not in ("int", "half"):
        return None
    n, v = int(p[2]), int(p[3])
    x = Fraction(v) if p[1] == "int" else Fraction(v, 2)
    if p[1] == "half" and v % 2 == 0:
        return None
    return n, x


def main(argv):
    if len(argv) >= 3 and argv[0] == "--nx":
        n = int(argv[1])
        x = Fraction(argv[2])
        r = solve(n, x)
        print(json.dumps(r) if r else "NOT A SOLUTION")
        return 0 if r else 1
    bad = 0
    seen = set()
    for fn in argv or ["-"]:
        fh = sys.stdin if fn == "-" else open(fn)
        for line in fh:
            h = parse_hit(line)
            if h is None or h in seen:
                continue
            seen.add(h)
            r = solve(*h)
            if r is None:
                bad += 1
                print(json.dumps({"rejected": line.strip()}), file=sys.stderr)
            else:
                print(json.dumps(r))
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
