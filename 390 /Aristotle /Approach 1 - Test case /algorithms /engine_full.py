#!/usr/bin/env python3
"""
ENGINE F -- THE COMPLETE ENGINE.

For a FIXED n it finds *every* integer x (of ANY size -- there is no search
window at all) such that the equation has a rational d.  Cost: one
factorisation of K = 36n^3-65 plus a handful of O(1) cubic solves.

Derivation.  Every solution has x = s t^2 with s squarefree, and (pruning
theorem) s | K.  Writing K = s K' one computes

      D = x^2 (x+6n)^2 + x K = s^2 t^2 ( t^2 (x+6n)^2 + K' ) ,

so D is a perfect square  <=>  t^2 (x+6n)^2 + K' = G^2 , i.e.

      K'  =  (G - W)(G + W),      W = t (s t^2 + 6 n) .          (*)

Therefore: factor K, run over the squarefree divisors s of K (both signs),
run over the factorisations K/s = u·v, put W = (v-u)/2, and solve the cubic

      s t^3 + 6 n t - W = 0

for an integer t (exact binary search on its monotone branches).  Each integer
root yields x = s t^2, and every solution for this n arises this way.

This is what makes the "search over d" feasible: d = (-x(x+6n) - sgn(x)T)/(2x^2)
is then read off directly, with denominator dividing 2x^2.

usage:  python3 engine_full.py NMIN NMAX [workers]
"""
import sys, random
from math import isqrt
from fractions import Fraction
from multiprocessing import Pool

# ----------------------------------------------------------------- factoring
def is_prime(n):
    if n < 2: return False
    for p in (2,3,5,7,11,13,17,19,23,29,31,37):
        if n % p == 0: return n == p
    d, s = n-1, 0
    while d % 2 == 0: d //= 2; s += 1
    for a in (2,3,5,7,11,13,17,19,23,29,31,37):
        y = pow(a, d, n)
        if y in (1, n-1): continue
        for _ in range(s-1):
            y = y*y % n
            if y == n-1: break
        else:
            return False
    return True

def _pollard(n):
    if n % 2 == 0: return 2
    while True:
        x = random.randrange(2, n); y = x; c = random.randrange(1, n); d = 1
        while d == 1:
            x = (x*x + c) % n
            y = (y*y + c) % n; y = (y*y + c) % n
            d = __import__('math').gcd(abs(x-y), n)
        if d != n: return d

def _small_primes(lim=10000):
    sieve = bytearray([1])*lim; sieve[0:2] = b"\x00\x00"
    for i in range(2, int(lim**0.5)+1):
        if sieve[i]: sieve[i*i::i] = bytearray(len(sieve[i*i::i]))
    return [i for i in range(lim) if sieve[i]]

SMALL_PRIMES = _small_primes()

def factor(n, out=None):
    if out is None:
        out = {}
        for p in SMALL_PRIMES:            # cheap trial division first
            if p*p > n: break
            while n % p == 0:
                n //= p; out[p] = out.get(p, 0) + 1
    if n == 1: return out
    if is_prime(n):
        out[n] = out.get(n, 0) + 1; return out
    d = _pollard(n)
    factor(d, out); factor(n//d, out)
    return out

def divisors_from(f):
    ds = [1]
    for p, e in f.items():
        ds = [d * p**k for d in ds for k in range(e+1)]
    return ds

def squarefree_divisors(f):
    ds = [1]
    for p in f:
        ds = ds + [d * p for d in ds]
    return ds

# ------------------------------------------------------------- cubic solving
def cubic_int_roots(a, b, c):
    """all integer roots of a t^3 + b t + c = 0 (a != 0), exact."""
    roots = []
    # rigorous bound: |a t^3| <= |b t| + |c| forces
    #    |t| <= max( (2|c|/|a|)^(1/3), (2|b|/|a|)^(1/2), 1 )
    B = 2
    v = 2*abs(c)//abs(a) + 2
    r = 1
    while r**3 < v: r *= 2
    B = max(B, 2*r)
    B = max(B, 2*(isqrt(2*abs(b)//abs(a) + 2) + 2))
    def f(t): return a*t**3 + b*t + c
    # critical points: 3 a t^2 + b = 0  ->  t^2 = -b/(3a)
    crit = []
    q = -b
    if (a > 0 and q > 0) or (a < 0 and q < 0):
        cc = isqrt(abs(q) // (3*abs(a))) + 2
        crit = [-cc, cc]
    pts = [-B] + crit + [B]
    for i in range(len(pts)-1):
        lo, hi = pts[i], pts[i+1]
        flo, fhi = f(lo), f(hi)
        if flo == 0: roots.append(lo)
        if fhi == 0: roots.append(hi)
        if flo == 0 or fhi == 0 or (flo > 0) == (fhi > 0): continue
        inc = fhi > flo
        while hi - lo > 1:
            mid = (lo + hi) // 2
            fm = f(mid)
            if fm == 0: roots.append(mid); break
            if (fm < 0) == inc: lo = mid
            else: hi = mid
    return sorted(set(t for t in roots if t != 0 and f(t) == 0))

# ------------------------------------------------------------------- solving
def K(n): return 36*n**3 - 65

def d_of(n, x):
    if x == 0: return None
    A = x*(x+6*n); D = A*A + x*K(n)
    if D < 0: return None
    T = isqrt(D)
    if T*T != D: return None
    return Fraction(-A - (1 if x > 0 else -1)*T, 2*x*x)

def solutions_for_n(n):
    """ALL integer x (unbounded!) solving the equation for this n."""
    k = K(n)
    if k == 0: return []
    f = factor(abs(k))
    sgnk = 1 if k > 0 else -1
    out = set()
    for s0 in squarefree_divisors(f):
        for s in (s0, -s0):
            if k % s: continue
            Kp = k // s                      # K' = K/s
            fp = factor(abs(Kp)) if abs(Kp) > 1 else {}
            for u0 in divisors_from(fp):
                for u in (u0, -u0):
                    if Kp % u: continue
                    v = Kp // u
                    if (u + v) % 2: continue
                    W = (v - u) // 2
                    # s t^3 + 6 n t - W = 0
                    for t in cubic_int_roots(s, 6*n, -W):
                        x = s * t * t
                        if x == 0: continue
                        if d_of(n, x) is not None:
                            out.add(x)
    return [(n, x) for x in sorted(out)]

def worker(n):
    try:
        return solutions_for_n(n)
    except RecursionError:
        return []

def main():
    nmin, nmax = int(sys.argv[1]), int(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    ns = [n for n in range(nmin, nmax+1) if n != 0]
    with Pool(workers) as pool:
        for batch in pool.imap_unordered(worker, ns, chunksize=4):
            for (n, x) in batch:
                print(f"HIT n={n} x={x} d={d_of(n,x)}", flush=True)

if __name__ == "__main__":
    main()
