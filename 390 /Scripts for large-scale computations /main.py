#!/usr/bin/env python3
"""
main.py
=======

Orchestrator for the diophantine equation solver.

Modes:
  demo        — Run demonstrations of all algorithms
  sieve       — Run modular sieve report
  factor      — Run factorization search on small n
  search-small— Search for small solutions (|n| <= 10^6)
  search-large— Generate parameters and commands for large n (~10^43)
  verify      — Verify a specific solution (n, x, d_num, d_den)

Usage:
  python main.py --mode demo
  python main.py --mode sieve
  python main.py --mode factor
  python main.py --mode search-small
  python main.py --mode search-large
  python main.py --mode verify <n> <x> [<d_num> <d_den>]
"""

import argparse
import sys


def run_demo():
    """Run demonstrations of all algorithm modules."""
    print("=" * 60)
    print("DIOPHANTINE EQUATION SOLVER — DEMO MODE")
    print("=" * 60)

    # 1. Modular sieve
    print("\n[1] Modular Sieve\n")
    from modular_sieve import sieve_report
    sieve_report(num_primes=20, prime_start=5)

    # 2. Thue parameterization
    print("\n[2] Thue Parameterization\n")
    from thue_param import make_thue_form, gen_pari_commands, estimate_field_difficulty
    form = make_thue_form(1, 10**11)
    print(f"  d = {form['d']}")
    print(f"  Form: {form['a']}*n^3 + {form['b']}*n*x^2 + {form['c']}*x^3 = {form['rhs']}")
    print(estimate_field_difficulty(form))
    print()
    print(gen_pari_commands(form))

    # 3. Factorization search
    print("\n[3] Factorization Search\n")
    from factorization_search import factorization_search
    # Try n=1, x=5
    results = factorization_search(1, 5)
    if results:
        for r in results:
            print(f"  Found: {r}")
    else:
        print("  No solution for n=1, x=5 (expected)")

    # 4. Mordell-Weil sieve
    print("\n[4] Mordell-Weil Sieve\n")
    from mw_sieve import mw_sieve_combine
    from sympy import primerange
    primes = list(primerange(5, 50))
    mw_sieve_combine(5, primes, verbose=True)

    # 5. CM descent
    print("\n[5] 3-Descent on CM Curve\n")
    from cm_descent import compute_selmer_3_curve, prime_splitting_in_Zomega
    result = compute_selmer_3_curve(5)
    for key, val in result.items():
        print(f"  {key}: {val}")

    # 6. LLL
    print("\n[6] LLL Search\n")
    from lll_search import lll_reduce
    B = [[1, 0, 3], [0, 1, 5], [7, 3, 1]]
    reduced = lll_reduce(B)
    print(f"  Original: {B}")
    print(f"  Reduced:  {reduced}")

    # 7. Verification
    print("\n[7] Verification\n")
    from verify import verify_solution
    verify_solution(1, 5, verbose=True)


def run_sieve():
    """Run modular sieve report."""
    from modular_sieve import sieve_report
    sieve_report(num_primes=50, prime_start=5)


def run_factor():
    """Run factorization search on small n."""
    from factorization_search import search_with_modular_filter, get_divisors
    from sympy import primerange

    primes = list(primerange(5, 200))

    print("=" * 60)
    print("FACTORIZATION SEARCH (small n)")
    print("=" * 60)

    for n in range(1, 1001):
        if n % 3 != 1:
            continue
        K = 36 * n**3 - 65
        x_cands = get_divisors(n, K)
        if not x_cands:
            continue

        for x in x_cands:
            if x % 12 != 5:
                continue
            if x % 7 == 0:
                continue
            results = factorization_search(n, x)
            if results:
                for a, b, y, d_num, d_den, root_type in results:
                    print(f"  FOUND: n={n}, x={x}, d={d_num}/{d_den} ({root_type})")

    print("Search complete.")


def run_search_small():
    """Search for small solutions with |n| <= 10^6."""
    from modular_sieve import admissible_pairs_mod_p
    from factorization_search import factorization_search, modular_prefilter
    from sympy import primerange
    from math import isqrt

    print("=" * 60)
    print("SMALL SOLUTION SEARCH (|n| <= 10^6)")
    print("=" * 60)

    primes = list(primerange(5, 500))
    found = 0

    for n in range(1, 10**6 + 1):
        if n % 3 != 1:
            continue
        if n % 10000 == 1:
            print(f"  Progress: n={n}...")

        K = 36 * n**3 - 65

        # Quick check: K must have divisors ≡ 5 (mod 12)
        # Only check if K is divisible by some number ≡ 5 (mod 12)
        # For efficiency, just check small divisors
        for x in range(5, min(isqrt(abs(K)) + 1, 10**5 + 1), 12):
            if K % x != 0:
                continue
            if x % 7 == 0:
                continue
            if not modular_prefilter(n, x, primes):
                continue
            results = factorization_search(n, x)
            if results:
                for a, b, y, d_num, d_den, root_type in results:
                    print(f"  FOUND: n={n}, x={x}, d={d_num}/{d_den} ({root_type})")
                    found += 1

    print(f"\nSearch complete. Found {found} solutions.")


def run_search_large():
    """Generate parameters and commands for large n (~10^43)."""
    from thue_param import make_thue_form, gen_pari_commands, gen_magma_commands, estimate_field_difficulty

    print("=" * 70)
    print("LARGE SOLUTION SEARCH — PARAMETER GENERATION")
    print("=" * 70)

    print("\n--- Root d ≈ -1 (recommended: smaller q) ---\n")

    # For d ≈ -1: d = -1 - p/q, q ~ 10^11
    for p in [1, 2, 3, 5, 6, 7, 10, 14]:
        q = 10**11 + p
        from math import gcd
        if gcd(p, q) != 1:
            q = 10**11 + p + 1
        if gcd(p, q) != 1:
            continue

        form = make_thue_form(p, q)
        print(f"\n  d = {form['d']}")
        print(f"  Thue form: {form['a']}*n^3 + {form['b']}*n*x^2 + {form['c']}*x^3 = {form['rhs']}")
        print(estimate_field_difficulty(form))
        print("\n  PARI/GP commands:")
        print(gen_pari_commands(form))

    print("\n--- Root d ≈ 0 (larger q, harder) ---\n")

    # For d ≈ 0: d = p/q, q ~ 10^32
    for p in [1, 2, 3]:
        q = 10**32 + 1
        from math import gcd
        if gcd(p, q) != 1:
            continue

        from thue_param import make_thue_form_near_zero
        form = make_thue_form_near_zero(p, q)
        print(f"\n  d = {form['d']}")
        print(f"  Thue form: {form['a']}*n^3 + {form['b']}*n*x^2 + {form['c']}*x^3 = {form['rhs']}")
        print(estimate_field_difficulty(form))

    print("\n" + "=" * 70)
    print("NEXT STEPS:")
    print("  1. Run the PARI/GP commands above to solve each Thue equation.")
    print("  2. Verify solutions using: python main.py --mode verify <n> <x> <d_num> <d_den>")
    print("  3. For Mordell-Weil sieve, fix x and use mw_sieve.py to filter n.")
    print("  4. For 3-descent, use cm_descent.py to compute Selmer group.")
    print("=" * 70)


def run_verify(args):
    """Verify a specific solution."""
    from verify import verify_solution

    n = int(args.n)
    x = int(args.x)

    if args.d_num is not None and args.d_den is not None:
        d_num = int(args.d_num)
        d_den = int(args.d_den)
        verify_solution(n, x, d_num, d_den, verbose=True)
    else:
        verify_solution(n, x, verbose=True)


def main():
    parser = argparse.ArgumentParser(
        description="Diophantine equation solver for 36*n^3 - 65 = -2*d*x^2*(...)"
    )
    parser.add_argument("--mode", required=True,
                        choices=["demo", "sieve", "factor", "search-small",
                                 "search-large", "verify"],
                        help="Operation mode")
    parser.add_argument("n", nargs="?", type=int, help="n value (for verify mode)")
    parser.add_argument("x", nargs="?", type=int, help="x value (for verify mode)")
    parser.add_argument("d_num", nargs="?", type=int, help="d numerator (for verify mode)")
    parser.add_argument("d_den", nargs="?", type=int, help="d denominator (for verify mode)")

    args = parser.parse_args()

    if args.mode == "demo":
        run_demo()
    elif args.mode == "sieve":
        run_sieve()
    elif args.mode == "factor":
        run_factor()
    elif args.mode == "search-small":
        run_search_small()
    elif args.mode == "search-large":
        run_search_large()
    elif args.mode == "verify":
        if args.n is None or args.x is None:
            print("Error: verify mode requires n and x arguments.")
            print("Usage: python main.py --mode verify <n> <x> [<d_num> <d_den>]")
            sys.exit(1)
        run_verify(args)


if __name__ == "__main__":
    main()
