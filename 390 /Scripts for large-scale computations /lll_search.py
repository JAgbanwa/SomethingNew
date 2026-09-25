#!/usr/bin/env python3
"""
lll_search.py — LLL lattice reduction and Coppersmith's method for
finding small roots of polynomial equations.

Used to search for solutions where n is large (~10^43) and x ~ n^{5/4},
by encoding the constraints into a lattice and finding short vectors.
"""

import math
from typing import List, Tuple, Optional


# ─── LLL Implementation ───

def gram_schmidt(B):
    """Gram-Schmidt orthogonalization. B is list of row vectors."""
    n = len(B)
    m = len(B[0]) if n > 0 else 0

    # B* = orthogonal vectors
    Bstar = [list(v) for v in B]
    mu = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(i):
            dot = sum(B[i][k] * Bstar[j][k] for k in range(m))
            norm = sum(Bstar[j][k] ** 2 for k in range(m))
            if norm == 0:
                mu[i][j] = 0
            else:
                mu[i][j] = dot / norm
            for k in range(m):
                Bstar[i][k] -= mu[i][j] * Bstar[j][k]

    return Bstar, mu


def lll_reduce(B, delta=0.75):
    """
    LLL reduction of a lattice basis B (list of integer row vectors).
    Returns the reduced basis.
    """
    B = [list(v) for v in B]
    n = len(B)
    m = len(B[0]) if n > 0 else 0

    if n == 0:
        return B

    Bstar, mu = gram_schmidt(B)

    def size_reduce(i, j):
        if abs(mu[i][j]) > 0.5:
            q = round(mu[i][j])
            for k in range(m):
                B[i][k] -= q * B[j][k]
            for k in range(n):
                mu[i][k] -= q * mu[j][k]

    k = 1
    while k < n:
        for j in range(k - 1, -1, -1):
            size_reduce(k, j)

        Bstar, mu = gram_schmidt(B)

        # Lovász condition
        norm_k = sum(Bstar[k][i] ** 2 for i in range(m))
        norm_k1 = sum(Bstar[k-1][i] ** 2 for i in range(m))

        lhs = delta * norm_k1
        rhs = norm_k + mu[k][k-1]**2 * norm_k1

        if lhs <= rhs:
            k += 1
        else:
            B[k], B[k-1] = B[k-1], B[k]
            Bstar, mu = gram_schmidt(B)
            k = max(k - 1, 1)

    return B


def shortest_vector(B):
    """Find approximately shortest vector in lattice basis B."""
    reduced = lll_reduce(B)
    # Shortest vector is typically first after LLL
    norms = [math.sqrt(sum(v[i]**2 for i in range(len(v)))) for v in reduced]
    min_idx = norms.index(min(norms))
    return reduced[min_idx], norms[min_idx]


# ─── Coppersmith's method (skeleton) ───

def coppersmith_univariate(f_coeffs, modulus, bound, degree=None):
    """
    Find small roots of f(x) ≡ 0 (mod modulus) with |x| < bound.
    f_coeffs: list of coefficients [a0, a1, ..., ad] for f(x) = sum(a_i * x^i).

    Uses LLL on the lattice formed by powers of x and shifts by modulus.
    """
    if degree is None:
        degree = len(f_coeffs) - 1

    # Dimension of lattice
    dim = degree + 1

    # Build lattice matrix
    # Rows: [N, 0, 0, ...], [a0, a1, ..., ad], [0, X, 0, ...], etc.
    X = bound
    M = [[0] * dim for _ in range(dim)]

    # First row: modulus * [1, 0, 0, ...]
    M[0][0] = modulus

    # Remaining rows: shifted polynomial
    for i in range(degree):
        for j in range(degree + 1):
            if j == i:
                M[i + 1][j] = X ** i
            elif j < i:
                M[i + 1][j] = f_coeffs[j] * X ** i

    # Actually, let's use the standard Howgrave-Graham approach
    M = [[0] * dim for _ in range(dim)]
    for i in range(dim):
        M[i][i] = modulus * (X ** i)
    # Add polynomial coefficients
    for j in range(degree + 1):
        M[0][j] = f_coeffs[j] * (X ** j)

    reduced = lll_reduce(M)

    # Extract polynomial from shortest vector
    # The shortest vector gives coefficients of a polynomial g(x)
    # such that g(x0) = 0 over the integers
    sv, sv_norm = shortest_vector(reduced)

    # Convert back to polynomial coefficients
    poly_coeffs = [sv[i] // (X ** i) if X ** i != 0 else sv[i] for i in range(dim)]

    # Find integer roots
    roots = find_integer_roots(poly_coeffs, bound)
    return roots


def find_integer_roots(coeffs, bound):
    """Find integer roots of polynomial with given coefficients."""
    degree = len(coeffs) - 1
    # Rational root theorem: p/q where p | a0, q | a_n
    a0 = coeffs[0]
    an = coeffs[-1]

    if a0 == 0:
        return [0]

    roots = []
    # Check simple candidates
    for x in range(-bound, bound + 1):
        val = sum(c * x**i for i, c in enumerate(coeffs))
        if val == 0:
            roots.append(x)

    return roots


def lattice_search(n_approx, x_approx, verbose=True):
    """
    Use lattice methods to search for exact (n, x) near approximate values.
    """
    if verbose:
        print(f"  Lattice search near n ≈ {n_approx}, x ≈ {x_approx}")

    # Build constraint lattice from:
    # 36n³ - 24d·n·x² - 4d(1+d)·x³ = 65
    # n ≡ 1 (mod 3)
    # x ≡ 5 (mod 12)
    # x ≢ 0 (mod 7)

    # Encode as lattice problem
    # This is a simplified demonstration

    # Lattice for modular conditions:
    # [3  0  0]   [n]   [1]
    # [0 12  0] * [x] = [5]
    # [0  0  7]   [k]   [r]

    M = [
        [3, 0, 0],
        [0, 12, 0],
        [0, 0, 7]
    ]

    reduced = lll_reduce(M)
    if verbose:
        print(f"  Reduced lattice basis:")
        for v in reduced:
            print(f"    {v}")

    return reduced


def demo():
    print("=" * 60)
    print("LLL Search Demo")
    print("=" * 60)
    print()

    # Simple LLL demo
    print("LLL reduction of a simple lattice:")
    B = [[1, 1, 1], [0, 1, 0], [0, 0, 1]]
    print(f"  Original basis: {B}")
    reduced = lll_reduce(B)
    print(f"  Reduced basis: {reduced}")
    sv, norm = shortest_vector(B)
    print(f"  Shortest vector: {sv}, norm = {norm:.4f}")

    print()

    # Larger example
    print("LLL on a 4D lattice:")
    B2 = [
        [1, 0, 2, -1],
        [0, 1, 1, 3],
        [2, -1, 3, 0],
        [1, 2, 0, 1]
    ]
    reduced2 = lll_reduce(B2)
    print(f"  Reduced basis:")
    for v in reduced2:
        print(f"    {v}")
    sv2, norm2 = shortest_vector(B2)
    print(f"  Shortest vector: {sv2}, norm = {norm2:.4f}")

    print()

    # Coppersmith demo (simple case)
    print("Coppersmith: finding small root of x³ + 10x² + 3x - 1 ≡ 0 (mod 17)")
    roots = coppersmith_univariate(
        f_coeffs=[-1, 3, 10, 1],
        modulus=17,
        bound=5
    )
    print(f"  Found roots: {roots}")

    print()

    # Lattice search demo
    print("Lattice search for modular constraints:")
    lattice_search(10**43, 10**53, verbose=True)


if __name__ == "__main__":
    demo()
