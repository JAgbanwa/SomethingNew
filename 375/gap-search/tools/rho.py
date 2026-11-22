#!/usr/bin/env python3
"""Heath-Brown density rho for (primitive) solutions of x^3 + y^3 + z^3 = k, in the normalisation of
Booker-Sutherland's Table 1, computed from local densities.

  rho_k = C * prod_p sigma_p(k)

* p = 2 (mod 3), p !| 3k: sigma_p = 1 (cubing is a bijection mod p, the surface is smooth mod p).
* p = 1 (mod 3), p !| 3k: sigma_p = N_p / p^2 with N_p = p^2 + 6p - L if k is a cube mod p, else
  p^2 - 3p - L, where 4p = L^2 + 27 M^2, L = 1 (mod 3)  (Jacobi sums; checked by brute force).
* p | 3k: sigma_p = lim_e N*(p^e)/p^(2e), counted exactly, where N* counts solutions mod p^e that are
  not all divisible by p (primitive solutions; for cube-free k this is every solution).

The product over p = 1 (mod 3) converges conditionally (it is an Euler product for a cubic Hecke
L-function at s = 1), so it is truncated at P and the convergence is shown. The archimedean factor C
does not depend on k (the log B growth comes from the cone x^3 + y^3 + z^3 = 0); it is calibrated on
Booker-Sutherland's published rho for cube-free k and its constancy across k is the check.

  python3 tools/rho.py --P 1e8        # about 10 s; prints the local factors, the calibration and rho_375
"""
from __future__ import annotations

import argparse
from math import isqrt, log
import sys

import numpy as np

# Booker-Sutherland 2021, Table 1 (rho_sol), cube-free k used for calibration.
BS_RHO = {114: 0.058459, 390: 0.032935, 627: 0.129565}


def local_density(k: int, p: int, e_max: int | None = None, primitive: bool = True) -> list[float]:
    """N*(p^e)/p^(2e) for e = 1..e_max (exact counts)."""
    out = []
    e = 1
    if e_max is None:
        e_max = {2: 12, 3: 7, 5: 6, 7: 4}.get(p, 3)
    while e <= e_max:
        m = p ** e
        xs = np.arange(m, dtype=np.int64)
        cubes = (xs * xs % m) * xs % m
        h = np.bincount(cubes, minlength=m).astype(np.int64)
        # N = sum_{u,v} h(u) h(v) h(k-u-v)
        total = 0
        idx = np.arange(m, dtype=np.int64)
        for u in np.nonzero(h)[0]:
            w = (k - u - idx) % m
            total += int(h[u]) * int(np.dot(h, h[w]))
        if primitive:
            # subtract triples with all coordinates divisible by p
            hp = np.bincount(cubes[::p], minlength=m).astype(np.int64)
            sub = 0
            for u in np.nonzero(hp)[0]:
                w = (k - u - idx) % m
                sub += int(hp[u]) * int(np.dot(hp, hp[w]))
            total -= sub
        out.append(total / m ** 2)
        e += 1
    return out


def L_of(p: int) -> int:
    for M in range(0, isqrt(4 * p // 27) + 1):
        r = 4 * p - 27 * M * M
        L = isqrt(r)
        if L * L == r:
            return L if L % 3 == 1 else -L
    raise ValueError(p)


def primes_1mod3(P: int) -> np.ndarray:
    s = np.ones(P + 1, dtype=bool)
    s[:2] = False
    for i in range(2, isqrt(P) + 1):
        if s[i]:
            s[i * i::i] = False
    ps = np.nonzero(s)[0].astype(np.int64)
    return ps[ps % 3 == 1]


def powmod_vec(a: np.ndarray, e: np.ndarray, m: np.ndarray) -> np.ndarray:
    """a^e mod m elementwise, m < 3e9 so products fit in uint64."""
    a = (a % m).astype(np.uint64)
    m = m.astype(np.uint64)
    e = e.astype(np.uint64)
    r = np.ones_like(a)
    while e.any():
        odd = (e & np.uint64(1)).astype(bool)
        r[odd] = (r[odd] * a[odd]) % m[odd]
        a = (a * a) % m
        e >>= np.uint64(1)
    return r


def good_product(k: int, ps: np.ndarray, L_cache: dict[int, int], L_upto: int, P_max: int) -> dict[int, float]:
    """log prod over p = 1 mod 3, p !| 3k, of sigma_p, reported at checkpoints of P."""
    ps = ps[(k % ps) != 0]
    chi = powmod_vec(np.full(ps.shape, k % (1 << 62), dtype=np.int64) % ps, (ps - 1) // 3, ps)
    cube = chi == 1
    pf = ps.astype(np.float64)
    Ls = np.array([L_cache[int(p)] if p <= L_upto else 0 for p in ps[ps <= L_upto]] +
                  [0] * int((ps > L_upto).sum()), dtype=np.float64)
    term = np.log1p(np.where(cube, 6.0, -3.0) / pf - Ls / pf ** 2)
    csum = np.cumsum(term)
    out = {}
    for P in (10 ** 5, 10 ** 6, 10 ** 7, 10 ** 8, 10 ** 9):
        if P > P_max:
            break
        i = int(np.searchsorted(ps, P, side="right"))
        out[P] = float(csum[i - 1])
    return out


def bad_primes(k: int) -> list[int]:
    a, out, p = abs(3 * k), [], 2
    while p * p <= a:
        if a % p == 0:
            out.append(p)
            while a % p == 0:
                a //= p
        p += 1
    if a > 1:
        out.append(a)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--P", type=float, default=1e8)
    ap.add_argument("--k", type=int, nargs="*", default=[114, 390, 627, 375])
    a = ap.parse_args()
    P = int(a.P)
    ps = primes_1mod3(P)
    L_upto = 10 ** 6
    L_cache = {int(p): L_of(int(p)) for p in ps[ps <= L_upto]}
    rows = {}
    for k in a.k:
        bad = {}
        for p in bad_primes(k):
            seq = local_density(k, p)
            bad[p] = seq
        logbad = sum(log(seq[-1]) for seq in bad.values())
        good = good_product(k, ps, L_cache, L_upto, P)
        rows[k] = (bad, logbad, good)
        print(f"k = {k}")
        for p, seq in bad.items():
            print(f"   sigma_{p}: " + ", ".join(f"{v:.6f}" for v in seq))
        for Pc, lg in good.items():
            print(f"   prod_(p=1 mod 3, p<= {Pc:.0e}) sigma_p = {np.exp(lg):.6f}   all local = {np.exp(lg + logbad):.6f}")
    Pmax = max(next(iter(rows.values()))[2])
    print(f"\ncalibration at P = {Pmax:.0e}:  C = rho_BS / prod sigma_p")
    Cs = []
    for k, rho in BS_RHO.items():
        if k in rows:
            bad, logbad, good = rows[k]
            loc = float(np.exp(good[Pmax] + logbad))
            Cs.append(rho / loc)
            print(f"   k = {k}: prod = {loc:.6f}, rho_BS = {rho}, C = {rho / loc:.6f}")
    if Cs:
        C = sum(Cs) / len(Cs)
        print(f"   C = {C:.6f}  (spread {100 * (max(Cs) - min(Cs)) / C:.2f} %)")
        for k, (bad, logbad, good) in rows.items():
            for Pc, lg in good.items():
                print(f"   rho_{k} (primitive) at P = {Pc:.0e}: {C * np.exp(lg + logbad):.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
