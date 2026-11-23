"""Independent exact controls for the optional rational-parameter search."""
from __future__ import annotations

from fractions import Fraction
from itertools import product
from math import gcd
from pathlib import Path
import random
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from equation375 import RationalDFilter, validate_point  # noqa: E402
from rational_d import SearchStats, integer_roots, rational_parameters, search  # noqa: E402


def evaluate(coefficients, x):
    return sum(coefficient * x ** exponent
               for exponent, coefficient in enumerate(reversed(coefficients)))


class IntegerRootControls(unittest.TestCase):
    def test_entire_small_cubic_coefficient_grid(self):
        for a in (-2, -1, 1, 2):
            for b, c, d in product(range(-4, 5), repeat=3):
                expected = tuple(x for x in range(-6, 7)
                                 if a*x**3+b*x*x+c*x+d == 0)
                self.assertEqual(integer_roots((a, b, c, d)), expected,
                                 (a, b, c, d))

    def test_exhaustive_oracle_for_small_general_polynomials(self):
        rng = random.Random(375)
        for index in range(240):
            degree = index % 4
            coefficients = [rng.randint(-60, 60) for _ in range(degree + 1)]
            if coefficients[0] == 0:
                coefficients[0] = 1
            # A Cauchy bound encloses all complex roots. The oracle evaluates
            # every integer in that interval, with no derivative isolation.
            lead = abs(coefficients[0])
            bound = 1 + max((abs(c) + lead - 1) // lead
                            for c in coefficients[1:]) if degree else 0
            expected = tuple(x for x in range(-bound, bound + 1)
                             if evaluate(coefficients, x) == 0)
            with self.subTest(coefficients=coefficients):
                self.assertEqual(integer_roots(coefficients), expected)
                self.assertEqual(integer_roots([0, 0, *coefficients]), expected)

    def test_huge_signed_and_repeated_constructed_roots(self):
        huge = 10 ** 70 + 37
        for roots in ((huge, -10 ** 50 - 9, 7),
                      (huge, huge, -huge),
                      (-huge, -huge, -huge),
                      (0, huge, huge + 1)):
            a, b, c = roots
            for scale in (1, -7):
                coefficients = (scale, -scale * (a + b + c),
                                scale * (a*b + a*c + b*c), -scale * a*b*c)
                with self.subTest(roots=roots, scale=scale):
                    self.assertEqual(integer_roots(coefficients),
                                     tuple(sorted(set(roots))))

    def test_integer_root_among_nonintegral_roots_and_degree_drops(self):
        large = 10 ** 50 + 11
        # (2m-1)(3m+2)(m-large): only large is an integer root.
        self.assertEqual(integer_roots((6, 1-6*large, -2-large, 2*large)),
                         (large,))
        self.assertEqual(integer_roots((0, 1, -2*large, large*large)), (large,))
        self.assertEqual(integer_roots((0, 0, -7, 7*large)), (large,))
        self.assertEqual(integer_roots((0, 0, 0, 5)), ())
        with self.assertRaises(ValueError):
            integer_roots((0, 0, 0, 0))


class RationalParameterControls(unittest.TestCase):
    def test_height_enumeration_against_full_numerator_denominator_oracle(self):
        for low, high in ((1, 1), (1, 20), (4, 12), (7, 7), (18, 20)):
            expected = {
                Fraction(p, q)
                for p in range(-high, high + 1)
                for q in range(1, high + 1)
                if gcd(p, q) == 1 and q % 2 == 1 and q % 3 != 0
                and p % 3 == q % 3 and low <= max(abs(p), q) <= high
            }
            got = list(rational_parameters(low, high))
            with self.subTest(bounds=(low, high)):
                self.assertEqual(set(got), expected)
                self.assertEqual(len(got), len(set(got)))

    def test_nonunit_scale_is_examined_but_not_misreported_as_primitive(self):
        # For d=-8,n=2, the exact m polynomial has root m=5, not +/-1.
        self.assertEqual(integer_roots((56, -240, 0, -1000)), (5,))
        diagnostic = validate_point(2, 5, 45, Fraction(-8), require_coprime=False)
        self.assertEqual(diagnostic.d, Fraction(-8))
        self.assertEqual(gcd(diagnostic.X, diagnostic.Y), 5)
        stats = SearchStats()
        found = list(search(8, 8, 2, 2,
                            d_filter=RationalDFilter(values=frozenset({Fraction(-8)})),
                            stats=stats))
        self.assertEqual(found, [])
        self.assertEqual(stats.parameters, 1)
        self.assertEqual(stats.n_values, 1)
        self.assertEqual(stats.integer_scales, 1)
        self.assertEqual(stats.accepted_points, 0)

    def test_rational_filters_use_signed_exact_values_and_height(self):
        d = Fraction(-2, 67)
        self.assertTrue(RationalDFilter().accepts(d))
        self.assertTrue(RationalDFilter(values=frozenset({Fraction(-4, 134)})).accepts(d))
        self.assertFalse(RationalDFilter(values=frozenset({abs(d)})).accepts(d))
        self.assertTrue(RationalDFilter(minimum=d, maximum=d).accepts(d))
        self.assertFalse(RationalDFilter(maximum=d-Fraction(1, 2**100)).accepts(d))
        self.assertFalse(RationalDFilter(minimum=d+Fraction(1, 2**100)).accepts(d))
        self.assertFalse(RationalDFilter(height=66).accepts(d))
        self.assertTrue(RationalDFilter(height=67).accepts(d))
        with self.assertRaises(ValueError):
            RationalDFilter(minimum=Fraction(1), maximum=Fraction(0))
        with self.assertRaises(ValueError):
            RationalDFilter(height=0)


if __name__ == "__main__":
    unittest.main()
