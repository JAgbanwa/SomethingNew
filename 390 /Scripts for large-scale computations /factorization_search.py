#!/usr/bin/env python3
"""
factorization_search.py — Factorization-based search using the identity:

  (y - w)(y + w) = (36n³ - 65) * x

where w = x(x + 6n) and y = sqrt(w² + (36n³ - 65)*x).

For given (n, x), find divisors a of (36n³ - 65)*x such that
  a + 2*w = ((36n³ - 65)*x) / a
i.e., a² + 2*w*a - (36n³ - 65)*x = 0
"""

from math import isqrt, gcd


def factorize(n):
    """Trial division factorization (for moderate-sized numbers)."""
    if n < 0:
        factors = factorize(-n)
        return [(-1, 1)] + factors
    if n <= 1:
        return []
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors


def divisors_from_factors(factors):
    """Generate all divisors from a list of prime factors."""
    if not factors:
        return [1]
    # Group into prime powers
    from collections import Counter
    counts = Counter(factors)
    primes = list(counts.keys())
    divs = [1]
    for p, e in counts.items():
        new_divs = []
        for d in divs:
            pe = 1
            for _ in range(e + 1):
                new_divs.append(d * pe)
                pe *= p
        divs = new_divs
    return sorted(divs)


def get_divisors(n):
    """Get all positive divisors of n."""
    if n == 0:
        return []
    factors = factorize(abs(n))
    return divisors_from_factors(factors)


def check_solution(n, x):
    """
    Check if (n, x) yields an integer square root.
    Returns (y, d) if valid, None otherwise.
    """
    N = 36 * n**3 - 65
    if N % x != 0:
        return None

    w = x * (x + 6 * n)
    discriminant = w * w + N * x

    if discriminant < 0:
        return None

    y = isqrt(discriminant)
    if y * y != discriminant:
        return None

    # Compute d from y and w
    # d = (y - w) / (2 * x^2) or d = -(y + w) / (2 * x^2)
    d_num1 = y - w
    d_den = 2 * x * x
    g = gcd(abs(d_num1), d_den)
    d1 = (d_num1 // g, d_den // g)

    d_num2 = -(y + w)
    g2 = gcd(abs(d_num2), d_den)
    d2 = (d_num2 // g2, d_den // g2)

    return {
        'n': n, 'x': x, 'y': y, 'w': w,
        'd1': f"{d1[0]}/{d1[1]}",
        'd2': f"{d2[0]}/{d2[1]}"
    }


def search_range(n_start, n_end, x_max_factor=2, verbose=True):
    """
    Search for solutions in a range of n values.
    For each n, check divisors of 36n³ - 65 as candidates for x.
    """
    results = []
    for n in range(n_start, n_end + 1):
        if n % 3 != 1:
            continue
        N = 36 * n**3 - 65
        if N == 0:
            continue
        # Get divisors of N as candidates for x
        divs = get_divisors(N)
        for x in divs:
            # Apply modular filters
            if x % 12 != 5:
                continue
            if x % 7 == 0:
                continue
            result = check_solution(n, x)
            if result is not None:
                results.append(result)
                if verbose:
                    print(f"  FOUND: n={n}, x={x}, y={result['y']}")
                    print(f"    d1={result['d1']}, d2={result['d2']}")

    return results


def modular_prefilter(n, p):
    """
    For prime p, check if there exists x mod p satisfying:
    - x ≡ 5 (mod 12)  [reduced mod p]
    - 7 ∤ x
    - (36n³ - 65) * x is a QR mod p
    """
    N_mod_p = (36 * pow(n, 3, p) - 65) % p
    found = False
    for x_mod in range(p):
        if x_mod % 7 == 0:
            continue
        val = (N_mod_p * x_mod) % p
        if val == 0:
            continue
        # Check QR using Euler's criterion
        if pow(val, (p - 1) // 2, p) == 1:
            found = True
            break
    return found


def demo():
    print("=" * 60)
    print("Factorization Search Demo")
    print("=" * 60)
    print()

    # Small search
    print("Searching n in [1, 1000]...")
    results = search_range(1, 1000, verbose=True)

    if results:
        print(f"\n  Found {len(results)} solution(s).")
    else:
        print("\n  No solutions found in this range.")
        print("  (Expected — minimal |n| ~ 10^43)")

    print()
    print("Modular prefilter test:")
    for p in [17, 19, 23, 29, 31]:
        count = 0
        for n in range(p):
            if modular_prefilter(n, p):
                count += 1
        print(f"  p={p}: {count}/{p} values of n pass prefilter")


if __name__ == "__main__":
    demo()
