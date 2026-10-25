#!/usr/bin/env python3
"""Algorithm C, phase 2, in pure Python: the Mordell curve of a fixed x (both charts).

For a fixed x the solutions (n, x) of the equation  36n^3 - K = -2dx^2(-(x+6n) + y)
(K = 19 by default) correspond to the integral points of

    integer chart (x = X):    E_X : V^2 = Z^3 - 432 X^3 (X^3 + 3K),
                              Z = 12X(3n + X),   V = 36 X W,   W^2 = X^2(X+6n)^2 + X(36n^3-K)
    half chart (x = X/2):     E_X : V^2 = Z^3 - 432 X^3 (X^3 + 24K),
                              Z = 12X(6n + X),   V = 36 X W,   W^2 = X^2(X+12n)^2 + 8X(36n^3-K)

(`DEquation.mordell_of_sat`, proved in RequestProject/Algorithm.lean for the integer chart;
the half-chart curve is the same curve at x = X/2 after the change of variables
(Z, V) -> (4Z, 8V), see HALF_INTEGER.md).  In both charts y = |W| / (b|X|) with b = 1, 2
and d = -(y + x + 6n)/(2x).  This module provides

  * curve_k(X)                   the Mordell coefficient of E_X,
  * recover(X, Z, V)             turn a point into (n, d) if it has the required shape,
  * add / mul                    the group law on E_X over the rationals,
  * search_points(X, ...)        a naive search for rational points of small height,
  * amplify(X, P, kmax)          multiples of a point, each tested for integrality.

The group law is exact (`fractions.Fraction`), so what comes out is certified by
verify.py.  For production runs on a grid node use grid/xcurve.gp (PARI/GP), which has a
real descent (`ellrank`) and a fast point search; this file is the reference
implementation and the self test.

Run `./xcurve.py --selftest` to check the correspondence on the known solutions, and
`./xcurve.py --u u0 u1 [--half] [--K k]` for a block of x = 12u+7 (resp. X = 6u+5).
"""
import sys
from fractions import Fraction
from math import isqrt


HALF = False
K = 19


def curve_k(x):
    if HALF:
        return -432 * x**3 * (x**3 + 24 * K)
    return -432 * x**3 * (x**3 + 3 * K)


def on_curve(x, Z, V):
    return V * V == Z**3 + curve_k(x)


def F_of(n, x):
    """W^2 for the pair (n, X): the integral form of the radicand times X^2"""
    if HALF:
        return x * x * (x + 12 * n) ** 2 + 8 * x * (36 * n**3 - K)
    return x * x * (x + 6 * n) ** 2 + x * (36 * n**3 - K)


def point_of_solution(n, x):
    """The point (Z,V) of E_X attached to a solution (n,X), or None."""
    v = F_of(n, x)
    if v < 0:
        return None
    W = isqrt(v)
    if W * W != v:
        return None
    if HALF:
        return (12 * x * (6 * n + x), 36 * x * W)
    return (12 * x * (3 * n + x), 36 * x * W)


def recover(x, Z, V, family=True):
    """(n, d) if the point (Z,V) comes from an integer n, else None."""
    Z = Fraction(Z)
    V = Fraction(V)
    n = (Z - 12 * x * x) / ((72 if HALF else 36) * x)
    if n.denominator != 1:
        return None
    n = int(n)
    W = V / (36 * x)
    if W.denominator != 1:
        return None
    W = int(W)
    if W * W != F_of(n, x):
        return None
    if family and K == 19 and n % 3 != 0:      # the requested family n = 3m
        return None
    xx = Fraction(x, 2) if HALF else Fraction(x)
    y = Fraction(abs(W), (2 if HALF else 1) * abs(x))
    return n, -(y + xx + 6 * n) / (2 * xx)


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


# half chart: the two rational-radical solutions with |n| <= 300, |X| <= 4e5 (found by
# dsweep --half --rational-sqrt and by brute force), and the integral solution attached to
# 42 = (-80538738812075974)^3 + 80435758145817515^3 + 12602123297335631^3 (K = 7).
KNOWN_HALF = [
    (19, Fraction(-142, 4913), 15, -289),
    (19, Fraction(-9671, 625), 114, 125),
    (7, Fraction(-93037881443153146, 102980666258459), 2083190438512862, 102980666258459),
]


def check_one(d, n, x):
    P = point_of_solution(n, x)
    if P is None or not on_curve(x, *P):
        print("FAIL: no point for (n,X) = (%d,%d) half=%s" % (n, x, HALF))
        return 1
    got = recover(x, P[0], P[1], family=False)
    if got is None or got[1] != d:
        print("FAIL: recovery for (n,X) = (%d,%d) gave %s, expected %s" % (n, x, got, d))
        return 1
    k = curve_k(x)
    Q = mul(k, (Fraction(P[0]), Fraction(P[1])), 3)
    if Q[1] ** 2 != Q[0] ** 3 + k:
        print("FAIL: group law off the curve at (n,X) = (%d,%d)" % (n, x))
        return 1
    return 0


def selftest():
    global HALF, K
    bad = 0
    HALF, K = False, 19
    for d, n, x in KNOWN:
        bad += check_one(d, n, x)
    HALF = True
    for k, d, n, x in KNOWN_HALF:
        K = k
        bad += check_one(d, n, x)
    HALF, K = False, 19
    print("selftest FAILED" if bad else "selftest ok (%d solutions checked)" % (len(KNOWN) + len(KNOWN_HALF)))
    return bad


def main(argv):
    global HALF, K
    args = argv[1:]
    if "--half" in args:
        HALF = True
        args.remove("--half")
    if "--K" in args:
        i = args.index("--K")
        K = int(args[i + 1])
        del args[i:i + 2]
    if args and args[0] == "--selftest":
        return selftest()
    if len(args) >= 3 and args[0] == "--u":
        u0, u1 = int(args[1]), int(args[2])
        for u in range(u0, u1):
            x = 6 * u + 5 if HALF else 12 * u + 7
            tag = "chart=half X=%d" % x if HALF else "x=%d" % x
            pts, sols = search_points(x)
            for n, d in sols:
                print("HIT %s n=%d m=%d u=%d d=%s" % (tag, n, n // 3, u, d))
            for P in pts:
                for t, (n, d) in amplify(x, P):
                    print("HIT %s n=%d m=%d u=%d d=%s mult=%d" % (tag, n, n // 3, u, d, t))
        print("DONE u=[%d,%d) chart=%s K=%d" % (u0, u1, "half" if HALF else "int", K))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
