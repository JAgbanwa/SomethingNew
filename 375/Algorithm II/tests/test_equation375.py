"""Independent exact controls for the original half-integer equation.

Targets other than 375 are mathematical controls for the shared verifier only;
the production search keeps the user's target and acceptance conditions.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import permutations
from math import gcd
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from equation375 import coefficient, points_from_cubes, validate_point  # noqa: E402


def point_key(point):
    return point.n, point.X, point.Y, point.d


class OriginalEquationControls(unittest.TestCase):
    def assert_original_equation(self, point, target):
        """Check the displayed radical equation directly, independently of maps."""
        n, X, Y, d = point_key(point)
        self.assertIs(type(n), int)
        self.assertIs(type(X), int)
        self.assertIs(type(Y), int)
        self.assertIsInstance(d, Fraction)
        self.assertEqual(X % 2, 1)
        self.assertEqual(Y % 2, 1)
        self.assertGreater(Y, 0)  # principal square root, not just a square
        x, y = Fraction(X, 2), Fraction(Y, 2)
        self.assertEqual(point.x, x)
        self.assertEqual(point.y, y)
        s = 6 * n + 3
        A = Fraction(s ** 3 - target, 6)
        self.assertNotEqual(A, 0)
        self.assertEqual(y * y, (x + s) ** 2 + A / x)
        self.assertEqual(A, -2 * d * x * x * (y - (x + s)))
        self.assertEqual(d, -(y + x + s) / (2 * x))

    def test_original_coefficient_is_exact_at_large_and_negative_n(self):
        for n in (-10 ** 40, -3, -1, 0, 1, 2, 10 ** 40):
            with self.subTest(n=n):
                expected = 36 * n ** 3 + 54 * n ** 2 + 27 * n - 58
                self.assertEqual(coefficient(n), expected)
                self.assertNotEqual(expected, 0)
        self.assertEqual(coefficient(0, target=3), Fraction(4))
        self.assertEqual(coefficient(0, target=15), Fraction(2))

    def test_nonempty_positive_controls_for_both_x_signs(self):
        controls = (
            (3, 0, 1, 9, Fraction(-8)),
            (15, 0, -1, 3, Fraction(4)),
            (105, -1, 11, 3, Fraction(-4, 11)),
        )
        for target, n, X, Y, d in controls:
            with self.subTest(target=target, n=n, X=X):
                p = validate_point(n, X, Y, target=target)
                self.assertEqual(point_key(p), (n, X, Y, d))
                self.assertEqual(point_key(validate_point(n, X, Y, d, target=target)),
                                 point_key(p))
                self.assert_original_equation(p, target)

    def test_wrong_d_and_negative_square_root_are_rejected(self):
        # Same squared equation but the negative branch is not the user's y.
        with self.assertRaises(ValueError):
            validate_point(0, 1, -9, target=3)
        # Omitting the +3 in the original expression would incorrectly give -5.
        with self.assertRaises(ValueError):
            validate_point(0, 1, 9, Fraction(-5), target=3)
        # This rational differs by less than binary64 resolution at -8.
        with self.assertRaises(ValueError):
            validate_point(0, 1, 9, Fraction(-8) + Fraction(1, 2 ** 100), target=3)
        with self.assertRaises(ValueError):
            validate_point(0, 1, 11, target=3)

    def test_scaled375_identity_is_not_an_accepted_discovery(self):
        cubes = (20, -25, 20)
        self.assertEqual(sum(c ** 3 for c in cubes), 375)
        self.assertEqual(points_from_cubes(cubes), [])
        with self.assertRaises(ValueError):
            validate_point(2, 5, 45)
        diagnostics = points_from_cubes(cubes, require_coprime=False)
        self.assertEqual([point_key(p) for p in diagnostics],
                         [(2, 5, 45, Fraction(-8))])
        self.assert_original_equation(diagnostics[0], 375)
        self.assertEqual(gcd(diagnostics[0].X, diagnostics[0].Y), 5)

    def test_cube_primitivity_does_not_replace_xy_coprimality(self):
        cubes = (4, -5, 10)
        target = 939
        self.assertEqual(sum(c ** 3 for c in cubes), target)
        self.assertEqual(gcd(gcd(cubes[0], cubes[1]), cubes[2]), 1)
        with self.assertRaises(ValueError):
            validate_point(1, -5, 15, Fraction(14, 5), target=target)
        # A different permutation does give a valid coprime chart point.
        accepted = points_from_cubes(cubes, target=target)
        self.assertEqual({point_key(p) for p in accepted},
                         {(1, 1, 9, Fraction(-14))})
        diagnostic = validate_point(1, -5, 15, Fraction(14, 5),
                                    target=target, require_coprime=False)
        self.assert_original_equation(diagnostic, target)

    def test_all_permutations_and_deduplication(self):
        for cubes, target, expected in (
            ((4, -5, 4), 3, {(0, 1, 9, Fraction(-8))}),
            ((2, -1, 2), 15, {(0, -1, 3, Fraction(4))}),
            ((8, -7, -4), 105,
             {(-1, 11, 3, Fraction(-4, 11)), (-1, -1, 15, Fraction(4))}),
        ):
            for permuted in set(permutations(cubes)):
                with self.subTest(cubes=permuted, target=target):
                    points = points_from_cubes(permuted, target=target)
                    keys = [point_key(p) for p in points]
                    self.assertEqual(set(keys), expected)
                    self.assertEqual(len(keys), len(set(keys)))
                    for p in points:
                        self.assert_original_equation(p, target)

    def test_valid_cubes_can_fail_the_required_chart(self):
        self.assertEqual(points_from_cubes((1, 1, 1), target=3), [])
        self.assertEqual(points_from_cubes((5, 5, 5)), [])
        # Even target forces even sum of coordinates; integral n needs odd sum.
        self.assertEqual(points_from_cubes((2, -1, -1), target=6), [])
        with self.assertRaises(ValueError):
            points_from_cubes((20, -25, 21))

    def test_huge_scaled375_identity_uses_exact_arithmetic(self):
        # Five times the known nontrivial representation of 3; all conditions
        # are recomputed, so this is an arithmetic control, not a trusted hit.
        cubes = (-2363577467266635160,
                 -2849684105567817467545,
                 2849684106109811903600)
        self.assertEqual(sum(c ** 3 for c in cubes), 375)
        self.assertEqual(gcd(gcd(cubes[0], cubes[1]), cubes[2]), 5)
        self.assertEqual(points_from_cubes(cubes), [])
        diagnostic_points = points_from_cubes(cubes, require_coprime=False)
        self.assertTrue(diagnostic_points)
        self.assertTrue(any(abs(p.X) > 2 ** 64 for p in diagnostic_points))
        for p in diagnostic_points:
            self.assert_original_equation(p, 375)
            self.assertGreater(gcd(p.X, p.Y), 1)


if __name__ == "__main__":
    unittest.main()
