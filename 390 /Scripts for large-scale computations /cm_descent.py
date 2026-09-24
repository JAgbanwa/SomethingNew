#!/usr/bin/env python3
"""
cm_descent.py
=============

3-descent on the CM elliptic curve with j-invariant 0.

The associated elliptic curve has j = 0, meaning it has complex
multiplication by the ring Z[omega], where omega = e^{2*pi*i/3} is a
primitive cube root of unity.  This is the ring of integers of
Q(sqrt(-3)).

Key properties of Z[omega]:
  - Elements: a + b*omega, with a, b in Z
  - Norm: N(a + b*omega) = a^2 - a*b + b^2
  - Units: {1, -1, omega, -omega, omega^2, -omega^2} (6 units)
  - Splitting of primes:
      p = 3: ramified (3) = -(1 - omega)^2 * (unit)
      p ≡ 1 (mod 3): split, p = pi * pi_bar
      p ≡ 2 (mod 3): inert (remains prime)

For the 3-descent, we factor the right-hand side in Z[omega] and
compute the 3-Selmer group.

The curve is: Y^2 = N^3 + k, with k = -(x^3 + 195)/108.
In Z[omega], N^3 + k = (N + alpha)(N + omega*alpha)(N + omega^2*alpha)
where alpha = cbrt(k).
"""

from math import gcd
from sympy import primerange, factorint
from collections import defaultdict


class EisensteinInt:
    """
    Element of Z[omega], where omega = e^{2*pi*i/3}.
    Represented as (a, b) for a + b*omega.
    """

    def __init__(self, a: int, b: int = 0):
        self.a = a
        self.b = b

    def __repr__(self):
        if self.b == 0:
            return f"EisensteinInt({self.a})"
        elif self.b == 1:
            return f"EisensteinInt({self.a} + omega)"
        elif self.b == -1:
            return f"EisensteinInt({self.a} - omega)"
        else:
            return f"EisensteinInt({self.a} + {self.b}*omega)"

    def __add__(self, other):
        return EisensteinInt(self.a + other.a, self.b + other.b)

    def __sub__(self, other):
        return EisensteinInt(self.a - other.a, self.b - other.b)

    def __mul__(self, other):
        # (a + b*w)(c + d*w) = ac + ad*w + bc*w + bd*w^2
        # w^2 = -1 - w, so bd*w^2 = bd*(-1 - w) = -bd - bd*w
        a, b = self.a, self.b
        c, d = other.a, other.b
        return EisensteinInt(a*c - b*d, a*d + b*c - b*d)

    def norm(self) -> int:
        """N(a + b*omega) = a^2 - a*b + b^2"""
        return self.a**2 - self.a * self.b + self.b**2

    def conjugate(self):
        """Conjugate in Z[omega]: a + b*omega -> a + b*omega^2 = (a-b) - b*omega"""
        return EisensteinInt(self.a - self.b, -self.b)

    def __eq__(self, other):
        return self.a == other.a and self.b == other.b

    def is_unit(self) -> bool:
        return abs(self.norm()) == 1

    def divides(self, other) -> bool:
        """Check if self divides other in Z[omega]."""
        if self.norm() == 0:
            return other.norm() == 0
        # other / self = other * conj(self) / N(self)
        n = self.norm()
        prod = other * self.conjugate()
        return prod.a % n == 0 and prod.b % n == 0

    def __floordiv__(self, other):
        """Exact division in Z[omega] (assumes divisibility)."""
        n = other.norm()
        prod = self * other.conjugate()
        return EisensteinInt(prod.a // n, prod.b // n)


def prime_splitting_in_Zomega(p: int):
    """
    Determine how a rational prime p splits in Z[omega].

    Returns:
      ('ramified',)           if p = 3
      ('split', pi, pi_bar)   if p ≡ 1 (mod 3), with pi * pi_bar = p
      ('inert',)              if p ≡ 2 (mod 3)
    """
    if p == 3:
        return ('ramified',)
    elif p % 3 == 2:
        return ('inert',)
    else:
        # p ≡ 1 (mod 3): find a, b such that a^2 - a*b + b^2 = p
        # Search for representation
        for a in range(isqrt(p) + 1):
            for b in range(a + 1):
                if a*a - a*b + b*b == p:
                    pi = EisensteinInt(a, b)
                    pi_bar = pi.conjugate()
                    return ('split', pi, pi_bar)
        # Should not happen for p ≡ 1 (mod 3)
        return ('inert',)  # fallback


def factorize_in_Zomega(n: int):
    """
    Factorize a rational integer n in Z[omega].

    Returns a list of (EisensteinInt, exponent) pairs.
    """
    if n == 0:
        return []
    if n < 0:
        return [(EisensteinInt(-1, 0), 1)] + factorize_in_Zomega(-n)

    factors = []
    rational_factors = factorint(n)

    for p, e in rational_factors.items():
        splitting = prime_splitting_in_Zomega(p)

        if splitting[0] == 'ramified':
            # 3 = -(1 - omega)^2 * unit, so (1-omega) has norm 3
            lam = EisensteinInt(1, -1)  # 1 - omega, norm = 3
            factors.append((lam, 2 * e))
            # Also a unit factor, but we track principal factors only

        elif splitting[0] == 'inert':
            # p remains prime in Z[omega]
            factors.append((EisensteinInt(p, 0), e))

        else:  # split
            _, pi, pi_bar = splitting
            # Determine split: try to divide n by pi and pi_bar
            factors.append((pi, e))
            factors.append((pi_bar, e))

    return factors


def compute_selmer_3_curve(x: int, S_primes=None):
    """
    Compute the 3-Selmer group data for the curve Y^2 = N^3 + k
    with k = -(x^3 + 195)/108.

    The 3-descent factors N^3 + k in Z[omega] as:
      (N + alpha)(N + omega*alpha)(N + omega^2*alpha)
    where alpha = cbrt(k).

    The Selmer group is a subgroup of K(S, 3)* / K*^3, where K = Q(omega, cbrt(k)).

    For practical purposes, we compute:
      1. Factorization of k in Z[omega]
      2. The set S of bad primes
      3. Local conditions at each prime in S

    Returns a dict with Selmer group information.
    """
    k_num = -(x**3 + 195)
    k_den = 108

    g = gcd(abs(k_num), k_den)
    k_num //= g
    k_den //= g

    if S_primes is None:
        # S includes primes dividing k and the primes dividing 6*discriminant
        S_primes = set()
        for p, _ in factorint(abs(k_num)).items():
            S_primes.add(p)
        for p, _ in factorint(k_den).items():
            S_primes.add(p)
        S_primes.add(2)
        S_primes.add(3)
        S_primes = sorted(S_primes)

    # Factorize k in Z[omega]
    k_factors = factorize_in_Zomega(abs(k_num))

    # For each prime in S, compute local conditions
    local_conditions = {}
    for p in S_primes:
        splitting = prime_splitting_in_Zomega(p)
        local_conditions[p] = splitting

    return {
        "x": x,
        "k": (k_num, k_den),
        "S_primes": S_primes,
        "k_factors_in_Zomega": [(str(f), e) for f, e in k_factors],
        "local_conditions": {p: str(c) for p, c in local_conditions.items()},
        "selmer_upper_bound": 3**len(S_primes),  # rough upper bound
    }


def heegner_point_approach(x: int):
    """
    Generate Magma/Sage commands for computing the Heegner point
    on the CM curve Y^2 = N^3 + k.

    For j = 0 curves, Heegner points can be computed efficiently
    using CM theory.
    """
    k_num = -(x**3 + 195)
    k_den = 108
    g = gcd(abs(k_num), k_den)
    k_num //= g
    k_den //= g

    return f"""// Magma commands for CM curve with j=0, x={x}
// Curve: Y^2 = N^3 + ({k_num}/{k_den})

Q := RationalField();
R := PolynomialRing(Q);
// Minimal Weierstrass model: y^2 = x^3 + {k_num}/{k_den}
E := EllipticCurve([0, 0, 0, 0, {k_num}/{k_den}]);
print "Curve:", E;
print "Conductor:", Conductor(E);
print "Rank bounds:", RankBounds(E);
// Heegner point computation (if rank is 1):
// HP := HeegnerPoint(E);
// print "Heegner point:", HP;
// P := HeegnerLift(E, ...);
"""


if __name__ == "__main__":
    from math import isqrt

    print("=" * 60)
    print("3-DESCENT ON CM CURVE (j=0)")
    print("=" * 60)

    # Demo: factorization in Z[omega]
    print("\n--- Factorization in Z[omega] ---\n")

    test_primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31]
    for p in test_primes:
        splitting = prime_splitting_in_Zomega(p)
        print(f"  {p}: {splitting[0]}", end="")
        if splitting[0] == 'split':
            print(f"  pi={splitting[1]}, pi_bar={splitting[2]}, N(pi)={splitting[1].norm()}")
        else:
            print()

    # Demo: 3-descent for small x
    print("\n--- 3-Descent for x=5 ---\n")
    result = compute_selmer_3_curve(5)
    for key, val in result.items():
        print(f"  {key}: {val}")

    print("\n--- Heegner point commands for x=5 ---\n")
    print(heegner_point_approach(5))
