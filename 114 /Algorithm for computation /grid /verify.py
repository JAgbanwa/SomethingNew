#!/usr/bin/env python3
"""Exact verifier for the hits returned by the grid work units.

Every search program in this directory is allowed to use floating point and modular
filters, so its output is only a *candidate*.  This script re-checks a candidate in exact
integer arithmetic and, if it is genuine, prints the rational value of d.

The criteria are the ones proved in `RequestProject/Main.lean` and
`RequestProject/Algorithm.lean`:

    U^2 + 2 U x (x + 6n) = x (36 n^3 - 19)      (the integral equation, `sat_of_U`)
    (U + x (x + 6n)) * x <= 0                   (the branch of the square root)
    d = U / (2 x^2)

Usage
-----
    ./verify.py hits.txt ...        check lines "HIT U x n" (dsweep)
    ./verify.py --nx n x            check a pair (n,x): is x^2(x+6n)^2 + x(36n^3-19)
                                    a square?  if so print the unique d
    ./verify.py --d p/q n x         check that the rational p/q solves the equation at (n,x)
"""
import sys
from fractions import Fraction
from math import isqrt


def A(n):
    return 36 * n**3 - 19


def check_U(U, x, n):
    """True iff (U,x,n) is a genuine certificate (equation + branch condition)."""
    if x == 0:
        return False
    if U * U + 2 * U * x * (x + 6 * n) != x * A(n):
        return False
    return (U + x * (x + 6 * n)) * x <= 0


def d_of_U(U, x):
    return Fraction(U, 2 * x * x)


def solve_nx(n, x):
    """Return the unique d for which (n,x) is a solution, or None."""
    if x == 0:
        return None
    v = x * x * (x + 6 * n) ** 2 + x * A(n)
    if v < 0:
        return None
    r = isqrt(v)
    if r * r != v:
        return None
    for U in (r - x * (x + 6 * n), -r - x * (x + 6 * n)):
        if check_U(U, x, n):
            return d_of_U(U, x), U
    return None


def report(U, x, n):
    if not check_U(U, x, n):
        return False
    d = d_of_U(U, x)
    m = Fraction(n, 3)
    u = Fraction(x - 7, 12)
    fam = "yes" if (n % 3 == 0 and (x - 7) % 12 == 0) else "no"
    print("SOLUTION")
    print("  d = %s / %s" % (d.numerator, d.denominator))
    print("  n = %d   (%d digits)" % (n, len(str(abs(n)))))
    print("  x = %d   (%d digits)" % (x, len(str(abs(x)))))
    print("  U = 2dx^2 = %d" % U)
    print("  in the family n=3m, x=12u+7: %s" % fam)
    if fam == "yes":
        print("  m = %d, u = %d" % (m, u))
    return True


def main(argv):
    if len(argv) >= 4 and argv[1] == "--nx":
        n, x = int(argv[2]), int(argv[3])
        res = solve_nx(n, x)
        if res is None:
            print("no d exists for n=%d, x=%d" % (n, x))
            return 1
        d, U = res
        report(U, x, n)
        return 0
    if len(argv) >= 5 and argv[1] == "--d":
        d = Fraction(argv[2])
        n, x = int(argv[3]), int(argv[4])
        U = 2 * d * x * x
        if U.denominator != 1:
            print("d = %s does not give an integral certificate at x=%d" % (d, x))
            return 1
        ok = report(int(U), x, n)
        if not ok:
            print("d = %s does NOT solve the equation at (n,x) = (%d,%d)" % (d, n, x))
            return 1
        return 0
    good = 0
    for fname in argv[1:]:
        with open(fname) as f:
            for line in f:
                p = line.split()
                if not p or p[0] != "HIT":
                    continue
                U, x, n = int(p[1]), int(p[2]), int(p[3])
                if report(U, x, n):
                    good += 1
                else:
                    print("rejected (wrong branch or not a solution): U=%d x=%d n=%d" % (U, x, n))
    print("%d genuine solutions" % good)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
