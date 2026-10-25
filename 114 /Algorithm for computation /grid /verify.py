#!/usr/bin/env python3
"""Exact verifier for the hits returned by the grid work units (both charts).

Every search program in this directory is allowed to use floating point and modular
filters, so its output is only a *candidate*.  This script re-checks a candidate in exact
rational arithmetic and, if it is genuine, prints the rational value of d.

Equation (K = 19 by default; --K changes it, 6K is the sum of three cubes):

    36 n^3 - K = -2 d x^2 ( -(x+6n) + y ),    y = sqrt((x+6n)^2 + (36n^3-K)/x) >= 0.

Integer chart: x integer.  Half chart: x = X/2 with X odd.  For a given (n, x) a rational d
exists iff the radicand is the square of a rational y >= 0, and then d is unique:
d = -(y + x + 6n)/(2x).  The certificates printed by the sweeps are checked against the
proved integral forms

    U^2 + 2Ux(x+6n) = x(36n^3-K),  (U + x(x+6n))x <= 0,  d = U/(2x^2)       (integer chart)
    V^2 + VX(X+12n) = 2X(36n^3-K), (2V + X(X+12n))X <= 0, d = V/X^2           (half chart)

and, independently, against the original unsquared equation with the principal root.

A solution has an INTEGRAL radical when y is an integer (integer chart) or y = Y/2 with Y
odd (half chart).  Then A = -x+y, B = -x-y, C = 2x+6n are integers with A^3+B^3+C^3 = 6K
(for K = 19: 114), which the verifier prints and checks.

Input lines understood
----------------------
    HIT U x n          dsweep / dsmooth, integer chart
    HHIT V X n         dsweep / dsmooth, half chart (x = X/2)
    CAND x m           xscan, integer chart, n = 3m
    HCAND X m          xscan, half chart, n = 3m
    ICAND int|half X n xroots (integral radicals; X = x in the integer chart)
    HIT x=.. n=.. ...  xcurve.gp (key=value form; chart from "chart=half")

Usage
-----
    ./verify.py [--K k] hits.txt ...      check every candidate line in the files
    ./verify.py [--K k] --nx n x          integer-chart pair: is there a rational d?
    ./verify.py [--K k] --nX n X          half-chart pair (x = X/2)
    ./verify.py [--K k] --d p/q n x       does p/q solve the equation at (n, x)?
                                          (x may be written X/2)
    ./verify.py [--K k] --triple A B C    show the solutions of (E) attached to an integer
                                          triple with A^3+B^3+C^3 = 6K (all charts/orders)
"""
import sys
from fractions import Fraction
from math import isqrt

K = 19


def A_of(n):
    return 36 * n**3 - K


def rat_sqrt(q):
    """exact square root of a nonnegative Fraction, or None"""
    if q < 0:
        return None
    a, b = q.numerator, q.denominator
    ra, rb = isqrt(a), isqrt(b)
    if ra * ra != a or rb * rb != b:
        return None
    return Fraction(ra, rb)


def solve_pair(n, x):
    """(d, y) for which (n, x) is a solution, or None.  x is a Fraction, x != 0."""
    if x == 0:
        return None
    s = x + 6 * n
    y = rat_sqrt(s * s + Fraction(A_of(n)) / x)
    if y is None:
        return None
    if y + s == 0:
        return None                     # would need d = infinity... (36n^3 = K)
    d = -(y + s) / (2 * x)
    # the original, unsquared equation with the principal root
    if Fraction(A_of(n)) != -2 * d * x * x * (-s + y):
        return None
    return d, y


def chart_of(x):
    if x.denominator == 1:
        return "int"
    if x.denominator == 2:
        return "half"
    return "other"


def report(n, x, src=""):
    """print a certified solution (n, x) and return its record, or None if it is not one"""
    res = solve_pair(n, x)
    if res is None:
        return None
    d, y = res
    ch = chart_of(x)
    print("SOLUTION" + (" [%s]" % src if src else ""))
    print("  d = %s / %s" % (d.numerator, d.denominator))
    print("  n = %d   (%d digits)" % (n, len(str(abs(n)))))
    if ch == "half":
        X = int(2 * x)
        print("  x = %d/2   (half chart, X = %d, %d digits)" % (X, X, len(str(abs(X)))))
        G = d * X * X
        print("  V = dX^2 = %s" % G)
    else:
        print("  x = %s   (%d digits)" % (x, len(str(abs(x.numerator)))))
        G = 2 * d * x * x
        print("  U = 2dx^2 = %s" % G)
    print("  y = sqrt(...) = %s" % y)
    integral = (ch == "int" and y.denominator == 1) or \
               (ch == "half" and y.denominator == 2)
    rec = {"n": n, "x": x, "d": d, "y": y, "chart": ch, "integral": integral}
    if integral:
        Aa, Bb, Cc = -x + y, -x - y, 2 * x + 6 * n
        assert Aa.denominator == Bb.denominator == Cc.denominator == 1
        Aa, Bb, Cc = int(Aa), int(Bb), int(Cc)
        cs = Aa**3 + Bb**3 + Cc**3
        print("  INTEGRAL RADICAL: (A,B,C) = (-x+y, -x-y, 2x+6n) = (%d, %d, %d)" % (Aa, Bb, Cc))
        print("  A^3+B^3+C^3 = %d   %s" % (cs, "== 6K = %d  <<< sum of three cubes >>>" % (6 * K)
                                        if cs == 6 * K else "!= 6K  (BUG)"))
        rec["triple"] = (Aa, Bb, Cc)
    else:
        print("  radical not integral (rational y)")
    if K == 19 and ch == "int":
        xi = int(x)
        fam = "yes" if (n % 3 == 0 and (xi - 7) % 12 == 0) else "no"
        print("  in the family n=3m, x=12u+7: %s" % fam)
    if K == 19 and ch == "half":
        X = int(2 * x)
        fam = "yes" if (n % 3 == 0 and X % 6 == 5) else "no"
        print("  in the half-chart family n=3m, X=6u+5: %s" % fam)
    return rec


def check_cert(chart, G, X, n):
    """exact check of a certificate line; returns True iff it is a genuine certificate"""
    if X == 0:
        return False
    if chart == "int":
        x = X
        return (G * G + 2 * G * x * (x + 6 * n) == x * A_of(n)
                and (G + x * (x + 6 * n)) * x <= 0)
    if X % 2 == 0:
        return False
    return (G * G + G * X * (X + 12 * n) == 2 * X * A_of(n)
            and (2 * G + X * (X + 12 * n)) * X <= 0)


def parse_kv(parts):
    kv = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            kv[k] = v
    return kv


def process_file(fname, stats):
    with open(fname) as f:
        for line in f:
            p = line.split()
            if not p:
                continue
            tag = p[0]
            try:
                if tag in ("HIT", "HHIT") and len(p) >= 4 and "=" not in p[1]:
                    chart = "half" if tag == "HHIT" else "int"
                    G, X, n = int(p[1]), int(p[2]), int(p[3])
                    stats["cand"] += 1
                    if not check_cert(chart, G, X, n):
                        print("rejected (wrong branch or not a solution): %s %d %d %d" % (tag, G, X, n))
                        continue
                    x = Fraction(X, 2) if chart == "half" else Fraction(X)
                    rec = report(n, x, tag)
                elif tag == "HIT":                      # xcurve.gp, key=value
                    kv = parse_kv(p[1:])
                    n = int(kv["n"])
                    if kv.get("chart") == "half":
                        x = Fraction(int(kv["X"]), 2)
                    else:
                        x = Fraction(int(kv["x"]))
                    stats["cand"] += 1
                    rec = report(n, x, "xcurve")
                elif tag in ("CAND", "HCAND"):
                    X, m = int(p[1]), int(p[2])
                    n = 3 * m
                    x = Fraction(X, 2) if tag == "HCAND" else Fraction(X)
                    stats["cand"] += 1
                    rec = report(n, x, tag)
                    if rec is None:
                        stats["spurious"] += 1
                        continue
                elif tag == "ICAND":
                    chart, X, n = p[1], int(p[2]), int(p[3])
                    x = Fraction(X, 2) if chart == "half" else Fraction(X)
                    stats["cand"] += 1
                    rec = report(n, x, "ICAND " + chart)
                    if rec is None:
                        stats["spurious"] += 1
                        continue
                else:
                    continue
            except (ValueError, KeyError, IndexError):
                print("unparsable line: %s" % line.rstrip())
                continue
            if rec is not None:
                stats["good"] += 1
                if rec["integral"]:
                    stats["integral"] += 1
                stats["sols"].add((rec["n"], rec["x"]))


def main(argv):
    global K
    args = argv[1:]
    if len(args) >= 2 and args[0] == "--K":
        K = int(args[1])
        args = args[2:]
    if len(args) >= 3 and args[0] in ("--nx", "--nX"):
        n, X = int(args[1]), int(args[2])
        x = Fraction(X, 2) if args[0] == "--nX" else Fraction(X)
        if report(n, x, "pair") is None:
            print("no rational d exists for n=%d, x=%s" % (n, x))
            return 1
        return 0
    if len(args) >= 4 and args[0] == "--d":
        d = Fraction(args[1])
        n = int(args[2])
        x = Fraction(args[3])
        res = solve_pair(n, x)
        if res is None or res[0] != d:
            print("d = %s does NOT solve the equation at (n,x) = (%d,%s)" % (d, n, x))
            return 1
        report(n, x, "d")
        return 0
    if len(args) >= 4 and args[0] == "--triple":
        import itertools
        t = tuple(int(v) for v in args[1:4])
        if sum(v**3 for v in t) != 6 * K:
            print("A^3+B^3+C^3 = %d != 6K = %d" % (sum(v**3 for v in t), 6 * K))
            return 1
        for a, b, c in sorted(set(itertools.permutations(t))):
            if a < b or (a + b + c) % 6:
                continue
            n = (a + b + c) // 6
            report(n, Fraction(-(a + b), 2), "triple %d,%d,%d (C=%d)" % (a, b, c, c))
        return 0
    stats = {"cand": 0, "good": 0, "integral": 0, "spurious": 0, "sols": set()}
    for fname in args:
        process_file(fname, stats)
    print("%d candidate lines, %d genuine solutions (%d distinct pairs), %d with an integral "
          "radical, %d spurious filter survivors"
          % (stats["cand"], stats["good"], len(stats["sols"]), stats["integral"], stats["spurious"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
