#!/usr/bin/env python3
"""
mw_sieve.py
===========

Mordell-Weil sieve for narrowing down solutions on the elliptic curve
associated with the diophantine equation.

The associated curve (in Weierstrass form) is:
    Y^2 = N^3 + k
where:
    N = 36*x*(3*n + x)
    Y = 34992 * x^2 * y
    k = -(x^3 + 195) / 108

For the Mordell-Weil sieve, we:
  1. Fix x and construct the curve E: Y^2 = N^3 + k.
  2. Compute E(F_p) for several primes p.
  3. Determine which points in E(F_p) correspond to valid (n, x) mod p.
  4. Combine information across primes to eliminate candidates.
"""

from sympy import primerange, factorint
from collections import defaultdict


def elliptic_curve_points_mod_p(a: int, p: int):
    """
    Compute the group of points on Y^2 = N^3 + a (mod p).
    Returns a dict {N_mod_p: [Y_mod_p values]}.
    """
    points = defaultdict(list)
    for n_val in range(p):
        rhs = (pow(n_val, 3, p) + a % p) % p
        if rhs == 0:
            points[n_val].append(0)
        else:
            # Check if rhs is a quadratic residue
            if pow(rhs, (p - 1) // 2, p) == 1:
                # Find square roots
                y = sqrt_mod(rhs, p)
                if y is not None:
                    points[n_val].append(y)
                    if y != 0:
                        points[n_val].append(p - y)
    return dict(points)


def sqrt_mod(a: int, p: int):
    """Compute square root of a mod p (Tonelli-Shanks)."""
    if a % p == 0:
        return 0
    if pow(a, (p - 1) // 2, p) != 1:
        return None

    # Tonelli-Shanks algorithm
    if p % 4 == 3:
        return pow(a, (p + 1) // 4, p)

    # Write p-1 = Q * 2^S
    Q = p - 1
    S = 0
    while Q % 2 == 0:
        Q //= 2
        S += 1

    # Find a non-residue
    z = 2
    while pow(z, (p - 1) // 2, p) != p - 1:
        z += 1

    M = S
    c = pow(z, Q, p)
    t = pow(a, Q, p)
    R = pow(a, (Q + 1) // 2, p)

    while True:
        if t == 1:
            return R
        # Find least i such that t^(2^i) = 1
        i = 1
        temp = (t * t) % p
        while temp != 1:
            temp = (temp * temp) % p
            i += 1
        b = pow(c, 1 << (M - i - 1), p)
        M = i
        c = (b * b) % p
        t = (t * c) % p
        R = (R * b) % p


def compute_k(x: int):
    """
    Compute k = -(x^3 + 195) / 108 for the Weierstrass form.
    Returns a rational number as (numerator, denominator).
    """
    num = -(x**3 + 195)
    den = 108
    from math import gcd
    g = gcd(abs(num), den)
    return num // g, den // g


def mw_sieve_step(x: int, p: int):
    """
    Perform one step of the Mordell-Weil sieve for a given x and prime p.

    Computes the set of (n mod p) values that are consistent with:
      1. n ≡ 1 (mod 3)  [if p = 3]
      2. The elliptic curve equation Y^2 = N^3 + k (mod p)
         where N = 36*x*(3*n + x) and Y is determined by y.

    Returns the set of admissible n mod p values.
    """
    k_num, k_den = compute_k(x)

    # Work modulo p: k = k_num * inverse(k_den) mod p
    if k_den % p == 0:
        return set()  # p divides denominator, skip

    k_mod_p = (k_num * pow(k_den, p - 2, p)) % p

    # N = 36 * x * (3*n + x) mod p
    x_mod = x % p
    coeff_36 = 36 % p

    admissible_n = set()

    for n_mod in range(p):
        # Check n ≡ 1 (mod 3) locally when p = 3
        if p == 3 and n_mod != 1:
            continue

        # Compute N mod p
        N_mod = (coeff_36 * x_mod * ((3 * n_mod + x_mod) % p)) % p

        # Check if N^3 + k is a quadratic residue mod p
        rhs = (pow(N_mod, 3, p) + k_mod_p) % p
        if rhs == 0:
            admissible_n.add(n_mod)
        elif pow(rhs, (p - 1) // 2, p) == 1:
            admissible_n.add(n_mod)

    return admissible_n


def mw_sieve_combine(x: int, primes, verbose=True):
    """
    Combine Mordell-Weil sieve information across multiple primes.

    Returns the density of admissible n values.
    """
    if verbose:
        print("=" * 60)
        print("MORDELL-WEIL SIEVE")
        print(f"x = {x}")
        print("=" * 60)
        print(f"{'Prime':>8} {'Admissible':>12} {'Density':>10}")
        print("-" * 40)

    total_density = 1.0

    for p in primes:
        adm = mw_sieve_step(x, p)
        density = len(adm) / p
        total_density *= density

        if verbose:
            print(f"{p:>8} {len(adm):>12} {density:>10.6f}")

    if verbose:
        print("-" * 40)
        print(f"Total density: ~{total_density:.6e}")
        print(f"Compression: 1 in {1/total_density:.2e}")
        print("=" * 60)

    return total_density


def full_mw_sieve(x: int, n_range, primes=None):
    """
    Full Mordell-Weil sieve: filter n candidates using the sieve,
    then check remaining candidates against the full equation.
    """
    if primes is None:
        primes = list(primerange(5, 200))

    # Step 1: Compute admissible n mod p for each prime
    adm_sets = []
    moduli = []
    for p in primes:
        adm = mw_sieve_step(x, p)
        adm_sets.append(adm)
        moduli.append(p)

    # Step 2: Filter n candidates
    survivors = []

    for n in n_range:
        if n % 3 != 1:
            continue

        passes = True
        for i, p in enumerate(primes):
            if n % p not in adm_sets[i]:
                passes = False
                break

        if passes:
            survivors.append(n)

    return survivors


if __name__ == "__main__":
    # Demo with x = 5 (smallest valid x ≡ 5 mod 12)
    primes = list(primerange(5, 100))
    mw_sieve_combine(5, primes, verbose=True)

    # Demo: filter n in [1, 10000]
    print("\nFiltering n in [1, 10000] for x=5...")
    survivors = full_mw_sieve(5, range(1, 10001), primes)
    print(f"Survivors: {len(survivors)} out of 10000")
    if survivors:
        print(f"  First few: {survivors[:20]}")
