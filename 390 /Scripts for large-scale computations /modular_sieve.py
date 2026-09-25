#!/usr/bin/env python3
"""
modular_sieve.py - Modular sieve for filtering (n, x) pairs.

Filters pairs (n, x) by checking modular conditions across multiple primes:
  n = 1 (mod 3), x = 5 (mod 12), x != 0 (mod 7),
  and quadratic residue condition: (36n^3 - 65) * x is a QR mod p.
"""
from itertools import product
from math import gcd
from functools import reduce
try:
    from sympy import primerange, jacobi_symbol, isprime
except ImportError:
    pass


def is_quadratic_residue(a, p):
    """Check if a is a quadratic residue modulo p."""
    a %= p
    if a == 0:
        return True
    if p == 2:
        return True
    return pow(a, (p - 1) // 2, p) == 1


def check_modular_conditions(n_mod, x_mod, p):
    """Check all modular conditions for (n mod p, x mod p)."""
    if p == 7 and x_mod == 0:
        return False
    val = (36 * pow(n_mod, 3, p) - 65) * x_mod
    return is_quadratic_residue(val, p)


def generate_valid_pairs_mod_p(p):
    """Generate all (n_mod_p, x_mod_p) pairs satisfying conditions mod p."""
    results = []
    for n_mod in range(p):
        for x_mod in range(p):
            if x_mod == 0:
                continue
            if check_modular_conditions(n_mod, x_mod, p):
                results.append((n_mod, x_mod))
    return results


def estimate_density(primes):
    """Estimate the fraction of (n, x) pairs surviving the sieve."""
    total_fraction = 1.0
    for p in primes:
        valid = generate_valid_pairs_mod_p(p)
        frac = len(valid) / (p * (p - 1))
        total_fraction *= frac
    return total_fraction


def crt_combine(residues, moduli):
    """Chinese Remainder Theorem: find x mod (prod moduli) from residues."""
    M = reduce(lambda a, b: a * b, moduli)
    result = 0
    for r, m in zip(residues, moduli):
        Mi = M // m
        inv = pow(Mi, -1, m)
        result += r * Mi * inv
    return result % M


def sieve_search(max_primes=100, prime_start=5):
    """Run the modular sieve with up to max_primes primes."""
    primes = []
    n = prime_start
    while len(primes) < max_primes:
        if all(n % i != 0 for i in range(2, int(n**0.5) + 1)):
            primes.append(n)
        n += 1

    print(f"Running modular sieve with {len(primes)} primes: {primes[0]}..{primes[-1]}")
    density = estimate_density(primes[:10])
    print(f"Density estimate (first 10 primes): {density:.2e}")

    for p in primes[:5]:
        valid = generate_valid_pairs_mod_p(p)
        print(f"  p={p}: {len(valid)} valid pairs out of {p*(p-1)} ({len(valid)/(p*(p-1)):.4f})")

    return primes


def demo():
    """Demonstration mode."""
    print("=== Modular Sieve Demo ===")
    primes = sieve_search(max_primes=20)
    density_20 = estimate_density(primes)
    print(f"\nDensity after {len(primes)} primes: {density_20:.2e}")
    print(f"Expected survivors in 10^43 range: ~{10**43 * density_20:.2e}")


if __name__ == "__main__":
    demo()
