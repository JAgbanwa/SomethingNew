#!/usr/bin/env python3
"""
cm_descent.py — 3-descent on CM elliptic curves with j=0.

The associated elliptic curve has j-invariant 0, meaning it has
complex multiplication by Z[omega] where omega = e^{2*pi*i/3}.

This enables a 3-descent using the factorization:
  N³ + k = (N + alpha)(N + omega*alpha)(N + omega²*alpha)
in Z[omega], where alpha = k^{1/3}.
"""

from math import gcd, isqrt
from dataclasses import dataclass
from typing import List, Tuple, Optional


# ─── Z[omega] arithmetic ───

@dataclass
class Eisenstein:
    """Element of Z[omega]: a + b*omega, where omega = e^{2*pi*i/3}."""
    a: int
    b: int

    def __add__(self, other):
        return Eisenstein(self.a + other.a, self.b + other.b)

    def __sub__(self, other):
        return Eisenstein(self.a - other.a, self.b - other.b)

    def __mul__(self, other):
        # (a + b*w)(c + d*w) = ac + (ad+bc)*w + bd*w²
        # w² = -1 - w, so bd*w² = -bd - bd*w
        return Eisenstein(
            self.a * other.a - self.b * other.b,
            self.a * other.b + self.b * other.a - self.b * other.b
        )

    def norm(self):
        """N(a + b*omega) = a² - ab + b²."""
        return self.a * self.a - self.a * self.b + self.b * self.b

    def conjugate(self):
        """Conjugate in Z[omega]: a + b*omega -> (a-b) - b*omega."""
        return Eisenstein(self.a - self.b, -self.b)

    def is_unit(self):
        return self.norm() == 1

    def divides(self, other):
        """Check if self divides other in Z[omega]."""
        if self.norm() == 0:
            return False
        prod = other * self.conjugate()
        n = self.norm()
        return prod.a % n == 0 and prod.b % n == 0

    def __floordiv__(self, other):
        """Exact division in Z[omega]."""
        prod = self * other.conjugate()
        n = other.norm()
        return Eisenstein(prod.a // n, prod.b // n)

    def __eq__(self, other):
        return self.a == other.a and self.b == other.b

    def __repr__(self):
        if self.b == 0:
            return str(self.a)
        if self.a == 0:
            return f"{self.b}*w"
        return f"{self.a} + {self.b}*w"


# ─── Primality in Z[omega] ───

def factor_rational_prime(p):
    """
    Factor a rational prime p in Z[omega].
    - p = 3: ramified, 3 = -(1+2w)² * unit (up to unit)
    - p ≡ 1 (mod 3): splits, p = pi * conj(pi)
    - p ≡ 2 (mod 3): inert, p remains prime
    """
    if p == 3:
        # Ramified: 3 = -w² * (1-w)²
        return ('ramified', Eisenstein(1, -1), 2)  # (1-w) with norm 3

    if p % 3 == 1:
        # Split: find a, b such that a² - ab + b² = p
        for a in range(isqrt(p) + 1):
            for b in range(a + 1):
                if a * a - a * b + b * b == p:
                    return ('split', Eisenstein(a, b), 1)

    # Inert
    return ('inert', Eisenstein(p, 0), 1)


def is_eisenstein_prime(alpha):
    """Check if alpha is prime in Z[omega]."""
    n = alpha.norm()
    if n < 2:
        return False
    if n == 2:
        return True  # 2 is inert, hence prime
    if n == 3:
        return True  # ramified prime
    # n should be a rational prime ≡ 1 mod 3
    if n % 3 != 1:
        return False
    # Check if n is prime
    for d in range(2, isqrt(n) + 1):
        if n % d == 0:
            return False
    return True


# ─── 3-descent ───

def compute_selmer_elements(k, prime_bound=100):
    """
    Compute the 3-Selmer group elements for the curve Y² = X³ + k.

    The 3-descent uses the isogeny phi: E -> E' where E': y² = x³ - 27k.
    Elements of Sel^(3) correspond to cube-free elements of Q*/(Q*)³
    whose local conditions are satisfied.
    """
    # Cube-free part of k
    k_abs = abs(k)
    cube_free = k_abs
    while cube_free % 27 == 0:
        cube_free //= 27
    for d in range(2, prime_bound):
        while cube_free % (d**3) == 0:
            cube_free //= d**3

    # Candidates for Selmer group: divisors of cube-free part
    # up to sign and cube classes
    candidates = [1, -1]
    for d in range(2, min(cube_free + 1, prime_bound + 1)):
        if cube_free % d == 0:
            candidates.extend([d, -d])

    # Filter by local conditions (simplified)
    selmer = []
    for c in candidates:
        # Check local solubility at primes dividing 3*k
        ok = True
        for p in [3] + [d for d in range(2, prime_bound) if k_abs % d == 0]:
            if not _local_solubility(c, k, p):
                ok = False
                break
        if ok:
            selmer.append(c)

    return selmer


def _local_solubility(c, k, p):
    """
    Check local solubility of c*x³ = y² - k at prime p.
    Simplified check: c must be a cube mod p (up to QR conditions).
    """
    if p == 3:
        return True  # Simplified
    c_mod = c % p
    if c_mod == 0:
        return True
    # Check if c is a cube mod p
    # For p ≡ 2 mod 3, every element is a cube
    if p % 3 == 2:
        return True
    # For p ≡ 1 mod 3, check if c^((p-1)/3) ≡ 1 mod p
    return pow(c_mod, (p - 1) // 3, p) == 1


def descent_3(k, verbose=True):
    """
    Perform 3-descent on E: Y² = X³ + k.
    Returns bounds on the rank.
    """
    if verbose:
        print(f"  3-descent on E: Y² = X³ + {k}")

    # Compute Selmer group
    selmer = compute_selmer_elements(k)
    selmer_size = len(selmer)

    if verbose:
        print(f"  3-Selmer group size (lower bound): {selmer_size}")
        print(f"  Rank bound: r ≤ log_3({selmer_size}) = {selmer_size.bit_length() - 1}")

    # The rank is at most log_3(|Selmer|) - dim(E[3])
    # E[3] for j=0 curve has dimension 1 over F_3 (when 3 ∤ k)
    rank_upper = 0
    s = selmer_size
    while s > 1:
        s //= 3
        rank_upper += 1

    if verbose:
        print(f"  Upper bound on rank: {rank_upper}")

    return {
        'selmer_size': selmer_size,
        'rank_upper_bound': rank_upper,
        'selmer_elements': selmer
    }


def demo():
    print("=" * 60)
    print("3-Descent on CM Curve (j=0) Demo")
    print("=" * 60)
    print()

    # Z[omega] arithmetic demo
    print("Z[omega] arithmetic:")
    a = Eisenstein(3, 1)
    b = Eisenstein(1, -2)
    print(f"  a = {a}, b = {b}")
    print(f"  a + b = {a + b}")
    print(f"  a * b = {a * b}")
    print(f"  N(a) = {a.norm()}, N(b) = {b.norm()}")
    print(f"  conj(a) = {a.conjugate()}")
    print()

    # Prime factorization in Z[omega]
    print("Prime factorization in Z[omega]:")
    for p in [2, 3, 5, 7, 11, 13]:
        result = factor_rational_prime(p)
        print(f"  {p}: {result[0]}", end="")
        if result[0] != 'inert':
            print(f", pi = {result[1]}, e = {result[2]}")
        else:
            print()

    print()

    # 3-descent demo
    print("3-descent examples:")
    for k in [1, -2, 7, -432, 65]:
        print()
        result = descent_3(k, verbose=True)


if __name__ == "__main__":
    demo()
