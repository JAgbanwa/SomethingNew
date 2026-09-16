#!/usr/bin/env python3
"""Algorithm C, phase 2, in pure Python: the Mordell curve of a fixed x.

For a fixed x the solutions (n, x) of the equation correspond to the integral points of

    E_x :  V^2 = Z^3 - 432 x^3 (x^3 + 57),     Z = 12x(3n + x),  V = 36xY,

where Y^2 = x^2 (x+6n)^2 + x (36 n^3 - 19)  (`DEquation.mordell_of_sat`, proved in
RequestProject/Algorithm.lean; the converse `DEquation.sat_of_mordell` turns a point back
into an explicit rational d).  This module provides

  * curve_k(x)                   the Mordell coefficient k of E_x,
  * recover(x, Z, V)             turn a point into (n, d) if it has the required shape,
  * add / mul                    the group law on E_x over the rationals,
  * search_points(x, ...)        a naive search for rational points of small height,
  * amplify(x, P, kmax)          multiples of a point, each tested for integrality.

The group law is exact (`fractions.Fraction`), so what comes out is certified by
verify.py.  For production runs on a grid node use grid/xcurve.gp (PARI/GP), which has a
real descent (`ellrank`) and a fast point search; this file is the reference
implementation and the self test.

Run `./xcurve.py --selftest` to check the correspondence on the known solutions.
"""
import sys
from fractions import Fraction
from math import isqrt


def curve_k(x):
    return -432 * x**3 * (x**3 + 57)


def on_curve(x, Z, V):
    return V * V == Z**3 + curve_k(x)


def point_of_solution(n, x):
    """The point (Z,V) of E_x attached to a solution (n,x), or None."""
    v = x * x * (x + 6 * n) ** 2 + x * (36 * n**3 - 19)
    if v < 0:
        return None
    Y = isqrt(v)
    if Y * Y != v:
        return None
    return (12 * x * (3 * n + x), 36 * x * Y)


def recover(x, Z, V, family=True):
    """(n, d) if the point (Z,V) comes from an integer solution, else None."""
    Z = Fraction(Z)
    V = Fraction(V)
    n = (Z - 12 * x * x) / (36 * x)
    if n.denominator != 1:
        return None
    n = int(n)
    Y = V / (36 * x)
    if Y.denominator != 1:
        return None
    Y = int(Y)
    if Y * Y != x * x * (x + 6 * n) ** 2 + x * (36 * n**3 - 19):
        return None
    if family and n % 3 != 0:
        return None
    s = x + 6 * n
    U = Y - x * s
    if (U + x * s) * x > 0:
        U = -Y - x * s
    if (U + x * s) * x > 0:
        return None
    return n, Fraction(U, 2 * x * x)


# ------------------------------------------------------------------ group law

def add(k, P, Q):
    """P + Q on V^2 = Z^3 + k over the rationals; None is the point at infinity."""
    if P is None:
        return Q
    if Q is None:
        return P
    x1, y1 = P
    x2, y2 = Q
    if x1 == x2 and y1 == -y2:
        return None
    if P == Q:
        if y1 == 0:
            return None
        lam = Fraction(3 * x1 * x1, 2 * y1)
    else:
        lam = Fraction(y2 - y1, x2 - x1)
    x3 = lam * lam - x1 - x2
    y3 = lam * (x1 - x3) - y1
    return (x3, y3)


def mul(k, P, t):
    R = None
    Q = P
    while t:
        if t & 1:
            R = add(k, R, Q)
        Q = add(k, Q, Q)
        t >>= 1
    return R


# --------------------------------------------------------------- point search

def search_points(x, emax=6, window=200000, family=True):
    """Naive search for rational points (Z,V) = (p/e^2, q/e^3) of small height.

    For each denominator e the smallest possible p is about (|k| e^6)^(1/3); the window
    scans upwards from there.  Returns the list of points found (as Fractions) together
    with any solutions they already produce."""
    k = curve_k(x)
    pts, sols = [], []
    for e in range(1, emax + 1):
        base = -k * e**6
        p0 = 0
        if base > 0:
            p0 = int(round(base ** (1 / 3))) - 2
        for p in range(max(p0, 0), max(p0, 0) + window):
            v = p**3 + k * e**6
            if v < 0:
                continue
            r = isqrt(v)
            if r * r != v:
                continue
            P = (Fraction(p, e * e), Fraction(r, e**3))
            pts.append(P)
            got = recover(x, P[0], P[1], family)
            if got:
                sols.append(got)
    return pts, sols


def amplify(x, P, kmax=8, family=True):
    """Multiples 2P .. kmax*P, each tested for being an integral solution."""
    k = curve_k(x)
    out = []
    for t in range(2, kmax + 1):
        Q = mul(k, P, t)
        if Q is None:
            continue
        got = recover(x, Q[0], Q[1], family)
        if got:
            out.append((t, got))
    return out


# -------------------------------------------------------------------- selftest

KNOWN = [
    (Fraction(-1, 54), 1, -9),
    (Fraction(1583, 54), -54, -9),
    (Fraction(-414553, 43904), 909, 784),
    (Fraction(-25160015, 2249728), 14709, 10816),
    (Fraction(-15849629, 24357888), -29317, 507456),
    (Fraction(-1, 965662992), 798, -1642284),
    (Fraction(308597, 41724656), -1160307, -10431164),
    (Fraction(-186487860451, 3639943440), 12512774, 2548980),
    (Fraction(1706615972245, 230860333818), -64722106, -23707161),
    (Fraction(-336451937, 111613781466), 101116178, -1691117901),
    (Fraction(-14123191460839, 14966022419456), -516368250, 55022141248),
]


def selftest():
    bad = 0
    for d, n, x in KNOWN:
        P = point_of_solution(n, x)
        if P is None or not on_curve(x, *P):
            print("FAIL: no point for (n,x) = (%d,%d)" % (n, x))
            bad += 1
            continue
        got = recover(x, P[0], P[1], family=False)
        if got is None or got[1] != d:
            print("FAIL: recovery for (n,x) = (%d,%d) gave %s, expected %s" % (n, x, got, d))
            bad += 1
            continue
        # the group law must stay on the curve
        k = curve_k(x)
        Q = mul(k, (Fraction(P[0]), Fraction(P[1])), 3)
        if Q[1] ** 2 != Q[0] ** 3 + k:
            print("FAIL: group law off the curve at (n,x) = (%d,%d)" % (n, x))
            bad += 1
    print("selftest FAILED" if bad else "selftest ok (%d solutions checked)" % len(KNOWN))
    return bad


def main(argv):
    if len(argv) > 1 and argv[1] == "--selftest":
        return selftest()
    if len(argv) >= 3 and argv[1] == "--u":
        u0, u1 = int(argv[2]), int(argv[3])
        for u in range(u0, u1):
            x = 12 * u + 7
            pts, sols = search_points(x)
            for n, d in sols:
                print("HIT x=%d n=%d m=%d u=%d d=%s" % (x, n, n // 3, u, d))
            for P in pts:
                for t, (n, d) in amplify(x, P):
                    print("HIT (%dP) x=%d n=%d m=%d u=%d d=%s" % (t, x, n, n // 3, u, d))
        print("DONE u=[%d,%d)" % (u0, u1))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
