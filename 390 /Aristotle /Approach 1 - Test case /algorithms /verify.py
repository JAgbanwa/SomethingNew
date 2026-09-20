#!/usr/bin/env python3
"""
Exact verifier / collector.

Reads the raw output of any engine (lines containing "n=.. x=..") from stdin or
from files, re-derives d exactly in rational arithmetic, checks the ORIGINAL
equation
     36n^3 - 65 = -2 d x^2 ( -(x+6n) + sqrt( (x+6n)^2 + (36n^3-65)/x ) )
with an exact rational square root, and prints a sorted table.

usage:  cat hits*.txt | python3 verify.py
"""
import sys, re
from math import isqrt
from fractions import Fraction

def K(n): return 36*n**3 - 65

def solve(n, x):
    """exact d, or None if (n,x) is not a solution"""
    if x == 0: return None
    A = x*(x+6*n)
    D = A*A + x*K(n)
    if D < 0: return None
    T = isqrt(D)
    if T*T != D: return None
    return Fraction(-A - (1 if x > 0 else -1)*T, 2*x*x)

def check_original(n, x, d):
    """exact verification of the ORIGINAL radical equation"""
    inner = Fraction((x+6*n)**2) + Fraction(K(n), x)      # (x+6n)^2 + K/x
    if inner < 0: return False
    num, den = inner.numerator, inner.denominator
    sn, sd = isqrt(num), isqrt(den)
    if sn*sn != num or sd*sd != den: return False          # sqrt must be rational
    root = Fraction(sn, sd)                                # the principal square root
    return -2*d*x*x*(-(x+6*n) + root) == K(n)

def main():
    data = sys.stdin.read()
    pairs = set()
    for mt in re.finditer(r"n=(-?\d+)\s+x=(-?\d+)", data):
        pairs.add((int(mt.group(1)), int(mt.group(2))))
    rows = []
    for (n, x) in sorted(pairs):
        d = solve(n, x)
        if d is None:
            print(f"REJECT n={n} x={x}", file=sys.stderr); continue
        assert check_original(n, x, d), (n, x, d)
        rows.append((abs(float(d)), n, x, d))
    rows.sort(reverse=True)
    print(f"{len(rows)} verified solutions (sorted by |d| descending)\n")
    for _, n, x, d in rows:
        print(f"n = {n}\n  x = {x}\n  d = {d}   (~ {float(d):.10g})")
    return rows

if __name__ == "__main__":
    main()
