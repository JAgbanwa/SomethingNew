#!/usr/bin/env python3
"""
verify.py
=========

Complete verification of candidate solutions (n, x, d).

Given a candidate triple (n, x, d) where d = d_num/d_den is rational,
this module checks ALL conditions:

  1. n is integer, x is integer
  2. n ≡ 1 (mod 3)
  3. x ≡ 5 (mod 12)
  4. x ≢ 0 (mod 7)
  5. x divides 36*n^3 - 65
  6. sqrt((x + 6n)^2 + (36n^3 - 65)/x) is integer
  7. The original equation is satisfied:
     36*n^3 - 65 = -2*d*x^2 * (-(x + 6n) + sqrt(...))
  8. d is rational (non-integer expected)

The module also computes d from (n, x) and checks consistency.
"""

from math import gcd, isqrt
from fractions import Fraction


def verify_solution(n: int, x: int, d_num: int = None, d_den: int = None, verbose=True):
    """
    Verify a candidate solution (n, x, d_num/d_den).

    If d_num and d_den are not provided, they are computed from (n, x).

    Returns (is_valid, details_dict).
    """
    details = {}
    errors = []

    if verbose:
        print("=" * 60)
        print("SOLUTION VERIFICATION")
        print("=" * 60)
        print(f"  n = {n}")
        print(f"  x = {x}")

    # 1. Integer check
    details["n_integer"] = isinstance(n, int)
    details["x_integer"] = isinstance(x, int)

    # 2. n ≡ 1 (mod 3)
    details["n_mod3"] = n % 3
    details["n_mod3_ok"] = (n % 3 == 1)
    if not details["n_mod3_ok"]:
        errors.append(f"n ≡ {n%3} (mod 3), expected 1")

    # 3. x ≡ 5 (mod 12)
    details["x_mod12"] = x % 12
    details["x_mod12_ok"] = (x % 12 == 5)
    if not details["x_mod12_ok"]:
        errors.append(f"x ≡ {x%12} (mod 12), expected 5")

    # 4. x ≢ 0 (mod 7)
    details["x_mod7"] = x % 7
    details["x_mod7_ok"] = (x % 7 != 0)
    if not details["x_mod7_ok"]:
        errors.append(f"x ≡ 0 (mod 7), expected nonzero")

    # 5. x divides 36*n^3 - 65
    K = 36 * n**3 - 65
    details["K"] = K
    details["x_divides_K"] = (K % x == 0)
    if not details["x_divides_K"]:
        errors.append(f"x={x} does not divide K=36*n^3-65={K}")

    if verbose:
        print(f"  K = 36*n^3 - 65 = {K}")
        print(f"  K/x = {K // x if x != 0 and K % x == 0 else 'NOT INTEGER'}")

    # 6. Square root is integer
    if x != 0 and K % x == 0:
        A = x + 6 * n
        inner = A * A + K // x
        details["inner"] = inner
        sq = isqrt(inner) if inner >= 0 else None
        details["sqrt_integer"] = (sq is not None and sq * sq == inner)
        details["sqrt_value"] = sq if details["sqrt_integer"] else None

        if details["sqrt_integer"]:
            S = sq
            if verbose:
                print(f"  A = x + 6n = {A}")
                print(f"  A^2 + K/x = {inner}")
                print(f"  sqrt(...) = {S} ✓ (integer)")
        else:
            errors.append(f"sqrt({inner}) is not integer")
            S = None
    else:
        details["sqrt_integer"] = False
        details["sqrt_value"] = None
        S = None
        if x == 0:
            errors.append("x = 0")

    # 7. Compute d from (n, x) and check equation
    if S is not None:
        A = x + 6 * n
        # Original equation: 36*n^3 - 65 = -2*d*x^2 * (-(x + 6n) + S)
        # => K = -2*d*x^2 * (S - A)
        # => d = K / (-2*x^2 * (S - A)) = -K / (2*x^2*(S - A))

        denom_part = 2 * x * x * (S - A)
        if denom_part != 0:
            d_computed = Fraction(-K, denom_part)
            details["d_computed"] = d_computed
            details["d_computed_str"] = f"{d_computed.numerator}/{d_computed.denominator}"

            if verbose:
                print(f"  d (computed) = {d_computed.numerator}/{d_computed.denominator}")

            # Check if d matches provided values
            if d_num is not None and d_den is not None:
                d_provided = Fraction(d_num, d_den)
                details["d_provided"] = d_provided
                details["d_match"] = (d_computed == d_provided)

                if verbose:
                    print(f"  d (provided) = {d_num}/{d_den}")
                    if details["d_match"]:
                        print(f"  d values MATCH ✓")
                    else:
                        print(f"  d values DO NOT MATCH ✗")
                        errors.append("Computed d does not match provided d")
            else:
                details["d_match"] = True  # No provided value to check against

            # Check d is non-integer (rational but not integer)
            details["d_is_rational"] = True
            details["d_is_integer"] = (d_computed.denominator == 1)
            if verbose:
                if details["d_is_integer"]:
                    print(f"  Note: d is integer (expected non-integer)")
                else:
                    print(f"  d is non-integer ✓ (rational)")

            # Verify original equation directly
            lhs = K
            rhs = -2 * d_computed * x * x * (-(A) + S)
            # Use Fraction arithmetic
            rhs_exact = Fraction(-2) * d_computed * x * x * (S - A)
            details["equation_check"] = (Fraction(lhs) == rhs_exact)

            if verbose:
                print(f"  LHS = 36*n^3 - 65 = {lhs}")
                print(f"  RHS = -2*d*x^2*(S - A) = {rhs_exact}")
                if details["equation_check"]:
                    print(f"  Equation satisfied ✓")
                else:
                    print(f"  Equation NOT satisfied ✗")
                    errors.append("Original equation not satisfied")

        else:
            errors.append("Denominator part is zero (S - A = 0)")
            details["equation_check"] = False

    # 8. Asymptotic check (optional)
    if abs(n) > 0:
        ratio = abs(x) / abs(n)**1.25 if abs(n) > 1 else float('inf')
        details["x_over_n_5_4"] = ratio
        if verbose:
            print(f"  x / n^(5/4) = {ratio:.6f} (asymptotic ratio)")

    # Summary
    all_ok = (details.get("n_mod3_ok", False) and
              details.get("x_mod12_ok", False) and
              details.get("x_mod7_ok", False) and
              details.get("x_divides_K", False) and
              details.get("sqrt_integer", False) and
              details.get("equation_check", False) and
              details.get("d_match", True))

    if verbose:
        print("-" * 60)
        if all_ok:
            print("  ✓ ALL CHECKS PASSED — VALID SOLUTION")
        else:
            print("  ✗ SOME CHECKS FAILED:")
            for err in errors:
                print(f"    - {err}")
        print("=" * 60)

    return all_ok, details


def batch_verify(solutions, verbose=False):
    """
    Verify a batch of candidate solutions.

    solutions: list of (n, x) or (n, x, d_num, d_den) tuples.
    Returns list of (is_valid, details) for each.
    """
    results = []
    for sol in solutions:
        if len(sol) == 2:
            n, x = sol
            result = verify_solution(n, x, verbose=verbose)
        elif len(sol) == 4:
            n, x, d_num, d_den = sol
            result = verify_solution(n, x, d_num, d_den, verbose=verbose)
        else:
            continue
        results.append(result)

    valid_count = sum(1 for ok, _ in results if ok)
    print(f"\nBatch verification: {valid_count}/{len(results)} valid")

    return results


if __name__ == "__main__":
    # Demo: verify a known-bad solution (should fail most checks)
    print("--- Demo: n=1, x=5 (expected to fail) ---\n")
    verify_solution(1, 5, verbose=True)

    print()

    # Demo: verify with computed d
    print("--- Demo: n=4, x=5 (expected to fail) ---\n")
    verify_solution(4, 5, verbose=True)
