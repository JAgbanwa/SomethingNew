"""Scan over x: for fixed x != 0, integer solutions n of
      t^2 = 36x n^3 + 36x^2 n^2 + 12x^3 n + x^4 - 19x
correspond to points (Z,Y) on the Mordell curve Y^2 = Z^3 + k,
k = -432 x^3 (x^3+57), via Z = 36 x n + 12 x^2, Y = 36 x t.

For each x we ask PARI for Mordell-Weil generators (ellrank) and enumerate
small combinations of them, keeping the points whose n is an integer.
This finds solutions with *arbitrarily large* n for small |x|, which the
n-by-n divisor search cannot reach.
"""
import sys, time, math
import cypari
pari = cypari.pari
pari.allocatemem(1 << 28, silent=True)

INF = pari('[0]')


def is_sq(v):
    if v < 0:
        return False
    r = math.isqrt(v)
    return r * r == v


def check(n, x):
    V = x * x * (x + 6 * n) ** 2 + x * (36 * n ** 3 - 19)
    return V >= 0 and is_sq(V)


BMAP = {1: 24, 2: 8, 3: 5, 4: 3, 5: 2, 6: 2, 7: 2, 8: 2}


def combos(rank, B):
    rng = list(range(-B, B + 1))
    def rec(i, cur):
        if i == rank:
            yield tuple(cur)
            return
        for c in rng:
            yield from rec(i + 1, cur + [c])
    yield from rec(0, [])


def scan_x(x, effort=1):
    k = -432 * x ** 3 * (x ** 3 + 57)
    E = pari.ellinit([0, 0, 0, 0, k])
    r = E.ellrank(effort)
    gens = list(r[3])
    rank = len(gens)
    tpts = list(E.elltors()[2])
    if rank == 0 and not tpts:
        return []
    try:
        if rank:
            gens = list(pari.ellsaturation(E, pari.vector(rank, gens), 20))
    except Exception:
        pass
    B = BMAP.get(rank, 2)
    mults = []
    for g in gens:
        row = {0: INF}
        for c in range(1, B + 1):
            row[c] = E.ellmul(g, c)
            row[-c] = E.ellmul(g, -c)
        mults.append(row)
    mod, off = 36 * x, 12 * x * x
    res, seen = [], set()
    for co in combos(rank, B):
        P = INF
        for i, c in enumerate(co):
            if c:
                P = E.elladd(P, mults[i][c])
        for T in [None] + tpts:
            Q = E.elladd(P, T) if T is not None else P
            if len(Q) != 2:
                continue
            Z = Q[0]
            if Z.denominator() != 1:
                continue
            Zi = int(Z)
            num = Zi - off
            if num % mod:
                continue
            n = num // mod
            if n == 0 or (n, x) in seen:
                continue
            seen.add((n, x))
            if check(n, x):
                res.append((n, x))
    return res


if __name__ == '__main__':
    lo, hi, sgn = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    effort = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    t0 = time.time()
    for ax in range(lo, hi + 1):
        x = sgn * ax
        try:
            for (n, xx) in scan_x(x, effort):
                print("SOL n=%d x=%d ndig=%d xdig=%d" % (n, xx, len(str(abs(n))), len(str(abs(xx)))), flush=True)
        except Exception as ex:
            print("ERR x=%d %s" % (x, ex), file=sys.stderr, flush=True)
        if ax % 50 == 0:
            print("x=%d  %.1fs" % (x, time.time() - t0), file=sys.stderr, flush=True)
