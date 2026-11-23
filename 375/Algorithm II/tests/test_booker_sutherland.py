"""Independent arithmetic oracles for the Booker--Sutherland backend."""

from __future__ import annotations

import sys
import unittest
from math import isqrt, prod
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from booker_sutherland import (  # noqa: E402
    SearchStats,
    _factor_interval,
    cube_roots_mod,
    cube_roots_prime,
    cube_roots_prime_power,
    passes_square_sieve,
    search,
)


def trial_prime(value: int) -> bool:
    return value >= 2 and all(value % d for d in range(2, isqrt(value) + 1))


class ModularRootTests(unittest.TestCase):
    def test_prime_roots_against_all_residues(self):
        # Includes primes with large 3-adic valuation of p-1, e.g. 487.
        for prime in range(2, 600):
            if not trial_prime(prime):
                continue
            expected = [[] for _ in range(prime)]
            for root in range(prime):
                expected[root ** 3 % prime].append(root)
            for value in range(prime):
                self.assertEqual(cube_roots_prime(value, prime), tuple(expected[value]),
                                 (value, prime))

    def test_prime_powers_with_singular_and_negative_targets(self):
        targets = (-375, -125, -27, -3, -1, 0, 1, 3, 8, 24, 27, 125, 375, 7125)
        for prime in (2, 3, 5, 7, 13, 19):
            for exponent in range(1, 8):
                modulus = prime ** exponent
                if modulus > 4000:
                    break
                for value in targets:
                    expected = tuple(r for r in range(modulus) if (r ** 3 - value) % modulus == 0)
                    self.assertEqual(cube_roots_prime_power(value, prime, exponent), expected,
                                     (value, prime, exponent))

    def test_singular_five_roots_at_large_exponents(self):
        for exponent in (3, 4, 8, 11, 17, 30):
            modulus = 5 ** exponent
            for target in (375, -375):
                roots = cube_roots_prime_power(target, 5, exponent)
                self.assertEqual(len(roots), 25)
                self.assertEqual(len(set(roots)), 25)
                self.assertTrue(all(0 <= r < modulus and pow(r, 3, modulus) == target % modulus
                                    for r in roots))

    def test_crt_roots_against_direct_enumeration(self):
        for modulus, factors in _factor_interval(1, 600, block_size=17):
            for target in (-375, 0, 3, 24, 375, 7125):
                expected = tuple(r for r in range(modulus) if (r ** 3 - target) % modulus == 0)
                self.assertEqual(cube_roots_mod(target, modulus, factors), expected,
                                 (target, modulus))

    def test_segmented_factorization_is_exact(self):
        for lower, upper in ((1, 500), (9940, 10020), (999_900, 1_000_010)):
            records = list(_factor_interval(lower, upper, block_size=7))
            self.assertEqual([value for value, _ in records], list(range(lower, upper + 1)))
            for value, factors in records:
                self.assertEqual(prod(p ** e for p, e in factors), value)
                self.assertTrue(all(trial_prime(p) and e > 0 for p, e in factors))
                self.assertEqual(len(factors), len({p for p, _ in factors}))


class SearchArithmeticTests(unittest.TestCase):
    def test_square_sieve_has_no_false_negative_on_squares(self):
        for value in range(20_000):
            self.assertTrue(passes_square_sieve(value * value), value)
        for value in (2 ** 64 + 1, 2 ** 127 + 12345, 10 ** 100 + 7):
            self.assertTrue(passes_square_sieve(value * value))
        self.assertFalse(passes_square_sieve(-1))

    def test_progress_only_after_whole_gap(self):
        reports = []
        stats = SearchStats()
        found = list(search(375, 1, 50, -30, 30, stats=stats, on_progress=reports.append))
        self.assertEqual([r["completed_D"] for r in reports], list(range(1, 51)))
        self.assertEqual([r["next_D"] for r in reports], list(range(2, 52)))
        self.assertEqual([r["counters"]["D_processed"] for r in reports], list(range(1, 51)))
        self.assertEqual(stats.D_processed, 50)
        self.assertEqual(stats.hits, len(found))
        self.assertIn((20, -25, 20), found)
        self.assertIn((20, 20, -25), found)
        self.assertIn((5, 5, 5), found)

    def test_primitive_cube_factor_filter_and_high_five_valuation(self):
        # 7125=57*5^3 has the primitive representation (-67,-46,74).
        found = set(search(7125, 1, 160, -80, 80, primitive_only=True))
        self.assertIn((-46, -67, 74), found)
        self.assertIn((74, -67, -46), found)
        self.assertIn((74, -46, -67), found)
        self.assertEqual(list(search(375, 1, 50, -30, 30, primitive_only=True)), [])
        # A constructed primitive triple with exactly 5^3 dividing its gap.
        # The target also has v_5(k)=3, so this exercises singular roots in
        # the search itself and guards against an overbroad primitive filter.
        target = 127 ** 3 + (-2) ** 3 + (-5) ** 3
        self.assertEqual(list(search(target, 125, 125, -5, -5, primitive_only=True)),
                         [(127, -2, -5)])

    def test_rejects_invalid_regions_and_nonintegers(self):
        for args in ((375, 0, 1, -1, 1), (375, 2, 1, -1, 1),
                     (375, 1, 2, 1, -1), (375, True, 2, -1, 1),
                     (375, 1, 2, -1.0, 1)):
            with self.assertRaises(ValueError):
                list(search(*args))


if __name__ == "__main__":
    unittest.main()
