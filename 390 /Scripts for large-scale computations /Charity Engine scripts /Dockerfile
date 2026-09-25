#!/usr/bin/env python3
"""
modular_sieve.py
================

Modular sieve for filtering candidate pairs (n, x) modulo a set of primes.

Given the diophantine conditions:
    n ≡ 1 (mod 3)
    x ≡ 5 (mod 12)
    x ≢ 0 (mod 7)
    (36*n^3 - 65) * x  is a quadratic residue (i.e. the square root is integer-valued)

this module computes, for each small prime p, the set of admissible
residue pairs (n mod p, x mod p).  The density of admissible pairs per
prime gives an estimate of the sieving power.

The CRT combination of multiple primes allows us to narrow down the
search space exponentially.
"""

from sympy import isprime, primerange
from functools import reduce


def is_quadratic_residue(a: int, p: int) -> bool:
    """Check whether `a` is a quadratic residue modulo prime `p`."""
    if a % p == 0:
        return True  # zero is a square
    return pow(a, (p - 1) // 2, p) == 1


def admissible_pairs_mod_p(p: int):
    """
    Compute all admissible (n_mod, x_mod) pairs modulo p.

    Conditions checked:
      - n ≡ 1 (mod 3)   [only if 3 | p, otherwise always satisfiable via CRT]
      - x ≡ 5 (mod 12)   [only if gcd(p,12)>1, otherwise via CRT]
      - x ≢ 0 (mod 7)    [only if 7 | p]
      - (36*n^3 - 65) * x is a quadratic residue mod p
    """
    pairs = []

    for n_mod in range(p):
        # Condition: n ≡ 1 (mod 3) — apply locally only when p == 3
        if p == 3 and n_mod % 3 != 1:
            continue

        n3_term = (36 * pow(n_mod, 3, p) - 65) % p

        for x_mod in range(p):
            # Condition: x ≡ 5 (mod 12) — apply locally only when p divides 12
            if p == 2:
                # 5 mod 12 -> odd, so x_mod must be 1 mod 2
                if x_mod % 2 != 1:
                    continue
            if p == 3:
                # 5 mod 12 -> 5 mod 3 = 2
                if x_mod % 3 != 2:
                    continue

            # Condition: x ≢ 0 (mod 7) — apply locally only when p == 7
            if p == 7 and x_mod == 0:
                continue

            # Core condition: (36*n^3 - 65) * x must be a quadratic residue
            val = (n3_term * x_mod) % p
            if not is_quadratic_residue(val, p):
                continue

            pairs.append((n_mod, x_mod))

    return pairs


def estimate_density(primes):
    """
    Estimate the sieving density across a list of primes.

    Returns a list of (prime, count, density) tuples.
    """
    results = []
    for p in primes:
        pairs = admissible_pairs_mod_p(p)
        density = len(pairs) / (p * p)
        results.append((p, len(pairs), density))
    return results


def crt_combine(residue_sets):
    """
    Combine residue sets via CRT.

    Given a list of (prime, pairs) where pairs is a list of (n_mod, x_mod),
    compute the combined modulus M = product of primes and the set of
    admissible (n_mod_M, x_mod_M) pairs modulo M.

    Returns (M, combined_pairs) where combined_pairs is a list of tuples.
    """
    if not residue_sets:
        return 1, []

    # Start with the first prime
    M = residue_sets[0][0]
    combined = list(residue_sets[0][1])  # list of (n_mod, x_mod)

    for p, pairs in residue_sets[1:]:
        new_combined = []
        M_new = M * p

        for n1, x1 in combined:
            for n2, x2 in pairs:
                # CRT for n
                # n ≡ n1 (mod M), n ≡ n2 (mod p)
                n_combined = crt_two(n1, M, n2, p)
                # CRT for x
                x_combined = crt_two(x1, M, x2, p)
                new_combined.append((n_combined, x_combined))

        combined = new_combined
        M = M_new

        # Prune if the list gets too large (practical limit)
        if len(combined) > 10_000_000:
            print(f"  [Warning] Combined pair count exceeded 10M at M={M}, truncating.")
            combined = combined[:10_000_000]
            break

    return M, combined


def crt_two(a, m1, b, m2):
    """Solve x ≡ a (mod m1), x ≡ b (mod m2) via extended Euclidean."""
    # Assumes gcd(m1, m2) = 1
    g, s, t = extended_gcd(m1, m2)
    # x = a + m1 * ((b - a) * s mod m2)
    diff = (b - a) % m2
    x = (a + m1 * ((diff * s) % m2)) % (m1 * m2)
    return x


def extended_gcd(a, b):
    """Extended Euclidean: returns (gcd, s, t) with a*s + b*t = gcd."""
    if b == 0:
        return a, 1, 0
    g, s, t = extended_gcd(b, a % b)
    return g, t, s - (a // b) * t


def sieve_report(num_primes=50, prime_start=5):
    """
    Generate a sieving report for the first `num_primes` primes
    starting from `prime_start`.

    Prints density per prime and cumulative sieving factor.
    """
    primes = list(primerange(prime_start, prime_start + 1000))[:num_primes]
    results = estimate_density(primes)

    print("=" * 60)
    print("MODULAR SIEVE REPORT")
    print("=" * 60)
    print(f"{'Prime':>8} {'Admissible':>12} {'Density':>10} {'Log10 factor':>14}")
    print("-" * 60)

    cumulative_log = 0.0
    for p, count, density in results:
        log_factor = -density  # negative because we are removing pairs
        cumulative_log += log_factor * (1.0 / p)  # rough cumulative estimate

        print(f"{p:>8} {count:>12} {density:>10.6f} {'':>14}")

    print("-" * 60)

    # Estimate total compression
    total_pairs = 1.0
    for p, count, density in results:
        total_pairs *= density

    print(f"Product of densities: ~{total_pairs:.2e}")
    print(f"Approximate compression: 1 in {1/total_pairs:.2e}")
    print("=" * 60)

    return results


if __name__ == "__main__":
    sieve_report(num_primes=30, prime_start=5)
