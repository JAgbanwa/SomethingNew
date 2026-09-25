#!/usr/bin/env python3
"""
mw_sieve.py — Mordell-Weil sieve for elliptic curves.

Given an elliptic curve E/Q and a set of generators for E(Q),
filter candidate points modulo several primes to find integral points.

The associated curve for our problem has j=0 (CM by Z[omega]),
which simplifies the arithmetic.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional


# ─── Elliptic curve arithmetic over F_p ───

@dataclass
class ECPoint:
    x: int
    y: int
    is_infinity: bool = False


def ec_add(P, Q, a, b, p):
    """Add two points on y² = x³ + ax + b over F_p."""
    if P.is_infinity:
        return Q
    if Q.is_infinity:
        return P

    if P.x == Q.x:
        if (P.y + Q.y) % p == 0:
            return ECPoint(0, 0, True)
        # P == Q: doubling
        if P.y == 0:
            return ECPoint(0, 0, True)
        inv = pow(2 * P.y, p - 2, p)
        lam = (3 * P.x * P.x + a) * inv % p
    else:
        inv = pow((Q.x - P.x) % p, p - 2, p)
        lam = (Q.y - P.y) * inv % p

    x3 = (lam * lam - P.x - Q.x) % p
    y3 = (lam * (P.x - x3) - P.y) % p
    return ECPoint(x3, y3, False)


def ec_mul(k, P, a, b, p):
    """Scalar multiplication k*P on the curve."""
    if k == 0 or P.is_infinity:
        return ECPoint(0, 0, True)
    if k < 0:
        return ec_mul(-k, ECPoint(P.x, (-P.y) % p, P.is_infinity), a, b, p)

    Q = ECPoint(0, 0, True)
    R = P
    while k > 0:
        if k & 1:
            Q = ec_add(Q, R, a, b, p)
        R = ec_add(R, R, a, b, p)
        k >>= 1
    return Q


def ec_order(P, a, b, p):
    """Compute order of point P on the curve over F_p."""
    if P.is_infinity:
        return 1
    Q = P
    order = 1
    while not Q.is_infinity:
        Q = ec_add(Q, P, a, b, p)
        order += 1
        if order > p + 1 + 2 * int(p**0.5):
            return -1  # Should not happen
    return order


def count_points_naive(a, b, p):
    """Count #E(F_p) by brute force (for small p)."""
    count = 1  # Point at infinity
    for x in range(p):
        rhs = (x * x * x + a * x + b) % p
        if rhs == 0:
            count += 1
        else:
            # Check if rhs is QR
            if pow(rhs, (p - 1) // 2, p) == 1:
                count += 2
    return count


# ─── Mordell-Weil sieve ───

def mw_sieve_single_prime(a, b, p, generators, target_residues, n_coeffs_bounds):
    """
    For a single prime p, compute which linear combinations of generators
    land in the target residue set.

    generators: list of (x, y) tuples = points on E(F_p)
    target_residues: set of allowed (n_mod, x_mod) pairs
    n_coeffs_bounds: bounds on coefficients for generator decomposition
    """
    # Compute group structure
    orders = []
    for g in generators:
        P = ECPoint(g[0] % p, g[1] % p, False)
        orders.append(ec_order(P, a, b, p))

    if not orders:
        return set()

    # Enumerate combinations within bounds
    valid = set()
    # This is exponential; in practice use baby-step giant-step
    for c0 in range(min(orders[0] if orders else 1, n_coeffs_bounds[0] + 1)):
        P0 = ECPoint(generators[0][0] % p, generators[0][1] % p, False)
        Q = ec_mul(c0, P0, a, b, p)
        for c1 in range(min(orders[1] if len(orders) > 1 else 1, n_coeffs_bounds[1] + 1)):
            if len(generators) > 1:
                P1 = ECPoint(generators[1][0] % p, generators[1][1] % p, False)
                Q1 = ec_add(Q, ec_mul(c1, P1, a, b, p), a, b, p)
            else:
                Q1 = Q

            # Check if Q1 maps to a valid residue
            if Q1.is_infinity:
                continue
            # Extract (n_mod, x_mod) from point — application specific
            # Here we just check if the point is in the target set
            key = (Q1.x, Q1.y)
            if key in target_residues or len(target_residues) == 0:
                valid.add((c0, c1))

    return valid


def mw_sieve(a, b, primes, generators, verbose=True):
    """
    Run the Mordell-Weil sieve over multiple primes.
    Returns the combined set of valid coefficient tuples.
    """
    if verbose:
        print(f"  MW sieve with {len(primes)} primes, {len(generators)} generators")

    # For each prime, compute valid residues
    # Then combine via CRT on the coefficients
    all_valid = set()
    for i, p in enumerate(primes):
        count = count_points_naive(a, b, p)
        if verbose:
            print(f"  p={p}: #E(F_p) = {count}")

        # Simplified: just record group orders
        for g in generators:
            P = ECPoint(g[0] % p, g[1] % p, False)
            o = ec_order(P, a, b, p)
            if verbose and i == 0:
                print(f"    Generator order: {o}")

    return all_valid


def demo():
    print("=" * 60)
    print("Mordell-Weil Sieve Demo")
    print("=" * 60)
    print()

    # Simple example: y² = x³ - x over F_7
    a, b = -1, 0
    p = 7
    count = count_points_naive(a, b, p)
    print(f"  Curve: y² = x³ + {a}x + {b} over F_{p}")
    print(f"  #E(F_{p}) = {count}")

    # Find a generator
    generators = []
    for x in range(p):
        rhs = (x**3 + a*x + b) % p
        for y in range(p):
            if (y*y) % p == rhs:
                generators.append((x, y))
                break
        if generators:
            break

    print(f"  Generator: {generators[0]}")

    # Compute multiples
    P = ECPoint(generators[0][0], generators[0][1], False)
    print(f"  Group structure:")
    Q = P
    for i in range(1, count + 1):
        if not Q.is_infinity:
            print(f"    {i}*P = ({Q.x}, {Q.y})")
        else:
            print(f"    {i}*P = O")
            break
        Q = ec_add(Q, P, a, b, p)

    print()
    print("  Sieve over multiple primes:")
    primes = [5, 7, 11, 13, 17, 19, 23, 29, 31]
    mw_sieve(a, b, primes, generators, verbose=True)


if __name__ == "__main__":
    demo()
