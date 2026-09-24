#!/usr/bin/env python3
"""
factorization_search.py
=======================

Factorization-based search for solutions.

Key identity:
    (y - w)(y + w) = (36*n^3 - 65) * x
where w = x*(x + 6*n) and y = sqrt(w^2 + (36*n^3 - 65)*x).

For a given (n, x) with x | (36*n^3 - 65), we need to find a factorization
    (36*n^3 - 65) * x = a * b
such that:
    a + 2*w = b   (i.e., b - a = 2*w)
    y = (a + b) / 2 is integer

This module provides:
  1. Validation of (n, x) candidates.
  2. Factorization-based search for admissible (n, x).
  3. Modular pre-filtering to quickly reject bad candidates.
"""

from math import gcd, isqrt
from sympy import factorint, isprime, primerange
from functools import reduce


def check_divisibility(n: int, x: int) -> bool:
    """Check whether x divides 36*n^3 - 65."""
    return (36 * n**3 - 65) % x == 0


def compute_w(n: int, x: int) -> int:
    """Compute w = x * (x + 6*n)."""
    return x * (x + 6 * n)


def factorization_search(n: int, x: int, max_factors=10000):
    """
    For a given (n, x) with x | (36*n^3 - 65), search for factorizations
    of (36*n^3 - 65) * x = a * b such that b - a = 2*w.

    Returns a list of (a, b, y, d_num, d_den) tuples for valid solutions,
    or empty list if none found.

    d = (y - w) / (2 * x^2)  [root near 0]
    or
    d = -(y + w) / (2 * x^2) [root near -1]
    """
    if not check_divisibility(n, x):
        return []

    K = 36 * n**3 - 65
    product = K * x
    w = compute_w(n, x)

    # We need: a * b = product, b - a = 2*w
    # => b = a + 2*w, so a*(a + 2*w) = product
    # => a^2 + 2*w*a - product = 0
    # => a = (-2*w + sqrt(4*w^2 + 4*product)) / 2 = -w + sqrt(w^2 + product)
    # This is exactly y = sqrt(w^2 + product), a = y - w

    disc = w * w + product  # = w^2 + (36*n^3-65)*x
    sq = isqrt(disc)
    if sq * sq != disc:
        return []  # y is not integer

    y = sq
    a = y - w
    b = y + w

    # Verify: a * b == product
    if a * b != product:
        return []

    results = []

    # Root near 0: d = (y - w) / (2 * x^2) = a / (2*x^2)
    d_num_1 = a
    d_den_1 = 2 * x * x
    g1 = gcd(abs(d_num_1), d_den_1)
    d_num_1 //= g1
    d_den_1 //= g1
    results.append((a, b, y, d_num_1, d_den_1, "near 0"))

    # Root near -1: d = -(y + w) / (2 * x^2) = -b / (2*x^2)
    d_num_2 = -b
    d_den_2 = 2 * x * x
    g2 = gcd(abs(d_num_2), d_den_2)
    d_num_2 //= g2
    d_den_2 //= g2
    results.append((a, b, y, d_num_2, d_den_2, "near -1"))

    return results


def modular_prefilter(n: int, x: int, primes=None):
    """
    Quick modular pre-filter: check whether (36*n^3 - 65)*x
    is a quadratic residue modulo several primes.

    Returns True if the candidate passes all prime checks.
    """
    if primes is None:
        primes = list(primerange(5, 200))

    K = (36 * pow(n, 3) - 65) % (x * x)  # not needed directly

    for p in primes:
        val = ((36 * pow(n, 3, p) - 65) % p * (x % p)) % p
        if val == 0:
            continue  # zero is fine
        if pow(val, (p - 1) // 2, p) != 1:
            return False

    return True


def search_with_modular_filter(n_candidates, x_candidates, primes=None):
    """
    Search over (n, x) candidate pairs using modular pre-filtering.

    n_candidates: iterable of n values
    x_candidates: callable(n) -> iterable of x values (e.g., divisors)

    Returns list of (n, x, results) for valid solutions.
    """
    if primes is None:
        primes = list(primerange(5, 500))

    solutions = []

    for n in n_candidates:
        if n % 3 != 1 and n % 3 != (-2) % 3:  # n ≡ 1 (mod 3) or handle negative
            if n % 3 != 1:
                continue

        K = 36 * n**3 - 65

        # Get x candidates: divisors of K with correct modular conditions
        x_cands = x_candidates(n) if callable(x_candidates) else x_candidates

        for x in x_cands:
            # Modular conditions
            if x % 12 != 5 and x % 12 != -7:  # x ≡ 5 (mod 12)
                if x % 12 != 5:
                    continue
            if x % 7 == 0:
                continue

            # Modular pre-filter
            if not modular_prefilter(n, x, primes):
                continue

            # Full factorization search
            results = factorization_search(n, x)
            if results:
                solutions.append((n, x, results))
                print(f"  FOUND: n={n}, x={x}")
                for a, b, y, d_num, d_den, root_type in results:
                    print(f"    d = {d_num}/{d_den} ({root_type}), y={y}")

    return solutions


def get_divisors(n, K):
    """
    Get divisors of K in the approximate range [n^(5/4) * 0.5, n^(5/4) * 2]
    that satisfy x ≡ 5 (mod 12) and 7 ∤ x.
    """
    if K == 0:
        return []

    K_abs = abs(K)
    factors = factorint(K_abs)
    divs = [1]
    for p, e in factors.items():
        new_divs = []
        for d in divs:
            pk = 1
            for _ in range(e + 1):
                new_divs.append(d * pk)
                pk *= p
        divs = new_divs

    # Filter by size and modular conditions
    n_abs = abs(n)
    if n_abs < 2:
        return []

    lower = int(n_abs**1.25 * 0.1)
    upper = int(n_abs**1.25 * 10)

    result = []
    for d in sorted(divs):
        if d < lower or d > upper:
            continue
        # Check both d and -d (since K can be negative)
        for x_val in [d, -d]:
            if x_val % 12 == 5 and x_val % 7 != 0:
                result.append(x_val)

    return result


if __name__ == "__main__":
    # Demo: search over small n values
    print("=" * 60)
    print("FACTORIZATION SEARCH DEMO")
    print("=" * 60)

    # Try a few small n values (n ≡ 1 mod 3)
    for n in [1, 4, 7, 10, 13, 16, 19, 22, 25, 28]:
        K = 36 * n**3 - 65
        x_cands = get_divisors(n, K)
        if x_cands:
            print(f"n={n}: K={K}, x candidates={x_cands[:10]}")
            for x in x_cands[:5]:
                results = factorization_search(n, x)
                if results:
                    for a, b, y, d_num, d_den, root_type in results:
                        print(f"  SOLUTION: n={n}, x={x}, d={d_num}/{d_den} ({root_type})")
                else:
                    print(f"  n={n}, x={x}: no integer y found")
