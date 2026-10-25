#!/usr/bin/env python3
"""End-to-end validation of the search programs on equations with KNOWN integral solutions.

No integral solution of the original equation (K = 19, i.e. 114 = A^3+B^3+C^3) is known,
so the integral-radical code paths cannot be tested on it directly.  They are tested on

    36 n^3 - K = -2 d x^2 ( -(x+6n) + sqrt( (x+6n)^2 + (36n^3-K)/x ) )

for other K, using the identity  A^3+B^3+C^3 - 6K = -6x(y^2 - (x+6n)^2 - (36n^3-K)/x)
with A = -x+y, B = -x-y, C = 2x+6n: every integer triple with A^3+B^3+C^3 = 6K and
6 | A+B+C gives solutions with an integral radical, in the integer chart (A+B even) or the
half chart (A+B odd, x = X/2).  Checks performed:

  1. xroots (fast path, with and without the local congruences, all three inner loops)
     against xroots --brute (direct enumeration, no cube roots / sieves / filters) on boxes
     |X| < XB, |n| < NB, for several K and both charts;
  2. every solution attached to the small triples of each K (found by enumerating triples)
     that lies in the box must be among them;
  3. dsweep --integral and dsmooth --integral (both charts, with and without the local
     congruences) must find every such solution whose certificate is below their bound;
  4. the Booker-Sutherland solutions of 42 (K = 7) and 906 (K = 151): xroots must find all
     three charts' versions of each, at n of sixteen digits;
  5. every line printed by any program is confirmed by verify.py (exact arithmetic).

Usage:  ./validate.py [--quick]        (run from the grid directory after building)
"""
import itertools
import os
import subprocess
import sys
from fractions import Fraction
from math import isqrt

HERE = os.path.dirname(os.path.abspath(__file__))
QUICK = "--quick" in sys.argv


def run(args):
    r = subprocess.run([os.path.join(HERE, args[0])] + [str(a) for a in args[1:]],
                       capture_output=True, text=True, check=True)
    return r.stdout


def lines(out, tags):
    return [l.split() for l in out.splitlines() if l.split() and l.split()[0] in tags]


def icbrt(v):
    """the integer cube root of v, or None if v is not a cube"""
    if v < 0:
        r = icbrt(-v)
        return None if r is None else -r
    r = round(v ** (1 / 3))
    for c in (r - 1, r, r + 1):
        if c**3 == v:
            return c
    return None


def triples(K, T):
    """integer triples (A,B,C), |A|,|B| <= T, with A^3+B^3+C^3 = 6K and 6 | A+B+C"""
    out = set()
    for A in range(-T, T + 1):
        for B in range(A, T + 1):
            C = icbrt(6 * K - A**3 - B**3)
            if C is None or (A + B + C) % 6:
                continue
            out.add(tuple(sorted((A, B, C))))
    return out


def chart_solutions(t):
    """(chart, X, n, G) for every solution of (E_K) attached to the triple t"""
    res = set()
    for a, b, c in set(itertools.permutations(t)):
        if a < b or a + b == 0:
            continue
        n = (a + b + c) // 6
        x = Fraction(-(a + b), 2)
        y = Fraction(a - b, 2)
        d = -(y + x + 6 * n) / (2 * x)
        if (a + b) % 2:
            X = -(a + b)
            G = d * X * X
            res.add(("half", X, n, int(G)))
        else:
            X = int(x)
            G = 2 * d * x * x
            res.add(("int", X, n, int(G)))
    return res


def verify_all(out, K):
    """every candidate line must be confirmed by verify.py with an integral radical"""
    path = os.path.join(HERE, ".validate_tmp.txt")
    with open(path, "w") as f:
        f.write(out)
    r = subprocess.run([sys.executable, os.path.join(HERE, "verify.py"), "--K", str(K), path],
                       capture_output=True, text=True, check=True).stdout
    os.remove(path)
    return r.splitlines()[-1]


FAIL = 0


def check(cond, msg):
    global FAIL
    if not cond:
        FAIL += 1
        print("  FAIL: " + msg)


def main():
    Ks = [573952, -493088, 1082612, 260392, 3, 19] if not QUICK else [573952, -493088, 19]
    XB, NB = (400, 200000) if QUICK else (1200, 400000)
    for K in Ks:
        print("K = %d (6K = %d)" % (K, 6 * K))
        T = 400 if not QUICK else 250
        known = set()
        for t in triples(K, T):
            known |= chart_solutions(t)
        for chart in ("int", "half"):
            flag = ["--half"] if chart == "half" else []
            base = ["xroots"] + flag + ["--K", K, "--X0", 1, "--X1", XB, "--n0", -NB, "--n1", NB]
            brute = set((l[1], int(l[2]), int(l[3])) for l in lines(run(base + ["--brute"]), ["ICAND"]))
            for extra in ([], ["--general"], ["--wheelmin", 0], ["--wheelmin", 10**12]):
                out = run(base + extra)
                fast = set((l[1], int(l[2]), int(l[3])) for l in lines(out, ["ICAND"]))
                check(fast == brute, "xroots %s %s differs from --brute (%d vs %d)"
                      % (chart, extra, len(fast), len(brute)))
            exp = set((c, X, n) for c, X, n, G in known if c == chart and 0 < abs(X) < XB
                      and -NB <= n < NB)
            check(exp <= brute, "xroots %s misses known solutions %s" % (chart, sorted(exp - brute)[:3]))
            if brute:
                v = verify_all("\n".join("ICAND %s %d %d" % s for s in sorted(brute)) + "\n", K)
                check(v.split()[3] == str(len(brute)) and " %d with an integral" % len(brute) in v,
                      "verify.py did not confirm all xroots hits: " + v)
            print("  %-4s xroots box |X|<%d |n|<%d: %d integral solutions (%d from small triples)"
                  % (chart, XB, NB, len(brute), len(exp)))
            # certificate sweeps: every known solution with |G| < GB must be found
            GB = 200000 if not QUICK else 50000
            expG = set((c, X, n) for c, X, n, G in known if c == chart and 2 <= abs(G) < GB)
            tag = "HHIT" if chart == "half" else "HIT"
            for prog in ("dsweep", "dsmooth"):
                for extra in ([], ["--general"]):
                    if prog == "dsweep":
                        args = ["dsweep", "--ulo", 2, "--uhi", GB, "--integral", "--K", K] + flag + extra
                    else:
                        args = ["dsmooth", "--lo", 2, "--hi", GB, "--B", GB, "--integral", "--K", K] + flag + extra
                    out = run(args)
                    got = set((chart, int(l[2]), int(l[3])) for l in lines(out, [tag]))
                    check(expG <= got, "%s %s %s misses %s" % (prog, chart, extra, sorted(expG - got)[:3]))
                    if got:
                        v = verify_all(out, K)
                        gen = int(v.split()[3])
                        nint = int(v.split(" with an integral")[0].split()[-1])
                        check(nint == gen and gen >= len(expG),
                              "%s %s: %d genuine, %d integral, %d expected" % (prog, chart, gen, nint, len(expG)))
            print("  %-4s dsweep/dsmooth --integral |G|<%d: all %d known certificates found"
                  % (chart, GB, len(expG)))
    # Booker-Sutherland solutions, at n of sixteen digits
    for K, t in ((7, (-80538738812075974, 80435758145817515, 12602123297335631)),
                 (151, (-74924259395610397, 72054089679353378, 35961979615356503))):
        for c, X, n, G in sorted(chart_solutions(t)):
            flag = ["--half"] if c == "half" else []
            out = run(["xroots"] + flag + ["--K", K, "--X0", abs(X) - 50, "--X1", abs(X) + 50,
                                           "--n0", n - 10**6, "--n1", n + 10**6])
            got = set((l[1], int(l[2]), int(l[3])) for l in lines(out, ["ICAND"]))
            check((c, X, n) in got, "xroots misses the %s solution of 6K = %d" % (c, 6 * K))
            print("6K = %4d: %s chart X = %d, n = %d found: %s" % (6 * K, c, X, n, (c, X, n) in got))
    print("validation FAILED (%d)" % FAIL if FAIL else "validation ok")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
