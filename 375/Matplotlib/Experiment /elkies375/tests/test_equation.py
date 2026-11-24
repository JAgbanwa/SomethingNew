"""Independent exact controls for the user equation and cube-coordinate mapping."""
from fractions import Fraction
from itertools import permutations
from math import gcd, isqrt
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from equation import (check_point, constants, points_from_cube, rational_point_at,
                      same_parity_pairs)


class EquationAdapter(unittest.TestCase):
    def assert_original_equation(self, record):
        n, x = int(record["n"]), int(record["x"])
        y = Fraction(record["y"])
        numerator = 36*n**3+54*n*n+27*n-58
        denominator = x*(6*n+3+x)**2
        self.assertEqual(y*y, 1+Fraction(numerator, denominator))
        xyz = tuple(Fraction(z) for z in record["cube_triple"])
        self.assertEqual(sum(z**3 for z in xyz), 375)
        self.assertTrue(record["exact"])
        self.assertEqual(record["residual"], "0")

    def test_375_nonprimitive_controls(self):
        for triple, expected_x in [((5, 5, 5), -5), ((-25, 20, 20), -20)]:
            records = points_from_cube(triple)
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assert_original_equation(record)
            self.assertEqual((int(record["n"]), int(record["x"]), Fraction(record["y"])),
                             (2, expected_x, 0))
            self.assertEqual(record["cube_gcd"], "5")
            self.assertTrue(record["integral_lift"])
            self.assertFalse(record["primitive"])
            self.assertEqual(record["status"], "cubes")

    def test_every_input_permutation_produces_same_distinct_points(self):
        for triple in ((5, 5, 5), (-25, 20, 20)):
            expected = {(r["n"], r["x"], r["y"]) for r in points_from_cube(triple)}
            for permuted in permutations(triple):
                self.assertEqual({(r["n"], r["x"], r["y"]) for r in points_from_cube(permuted)}, expected)

    def test_rational_only_point_is_not_integer_or_primitive(self):
        # Independently check the equation before relying on the adapter.
        n, x, y = 13, -144, Fraction(695, 756)
        self.assertEqual(y*y, 1+Fraction(36*n**3+54*n*n+27*n-58, x*(6*n+3+x)**2))
        record = check_point(n, x, y)
        self.assert_original_equation(record)
        self.assertFalse(record["integral_lift"])
        self.assertFalse(record["primitive"])
        self.assertIsNone(record["cube_gcd"])
        self.assertEqual(record["status"], "rational")
        self.assertEqual(Fraction(record["t"]), Fraction(-695, 12))
        self.assertEqual(rational_point_at(n, x), record)
        negative = check_point(n, x, -y)
        self.assertEqual(negative["cube_triple"][:2], list(reversed(record["cube_triple"][:2])))

    def test_wrong_nearby_rational_value_remains_trial(self):
        record = check_point(13, -144, Fraction(695, 756)+Fraction(1, 10**60))
        self.assertFalse(record["exact"])
        self.assertFalse(record["primitive"])
        self.assertFalse(record["integral_lift"])
        self.assertNotEqual(Fraction(record["residual"]), 0)
        self.assertEqual(record["status"], "trial")

    def test_huge_integer_cube_control_and_exact_n_filter(self):
        # Known representation of 3, scaled by five. This is a nonprimitive
        # arithmetic control, not a discovery or a positive-n search result.
        triple = (-2363577467266635160, -2849684105567817467545, 2849684106109811903600)
        self.assertEqual(sum(v**3 for v in triple), 375)
        self.assertEqual(gcd(gcd(abs(triple[0]), abs(triple[1])), abs(triple[2])), 5)
        S = sum(triple)
        n = (S-3)//6
        self.assertLess(n, 0)
        records = points_from_cube(triple, n_min=n, n_max=n)
        self.assertEqual(len(records), 1)
        for record in records:
            self.assert_original_equation(record)
            self.assertFalse(record["primitive"])
            self.assertEqual(record["cube_gcd"], "5")
        self.assertEqual(points_from_cube(triple, n_min=10**17, n_max=10**20), [])
        self.assertEqual(points_from_cube(triple, n_min=n+1), [])

    def test_all_same_parity_pairs_are_preserved(self):
        # This is a parity-only control, not a claimed solution of 375.
        self.assertEqual(same_parity_pairs((1, 3, 5)),
                         [(1, 3, 5), (1, 5, 3), (3, 5, 1)])
        self.assertEqual(same_parity_pairs((-25, 20, 20)), [(20, 20, -25)])
        self.assertEqual(same_parity_pairs((5, 5, 5)), [(5, 5, 5)])
        # For a small exhaustive independent control, compare every exact
        # equation point with integral t in this box to the cube adapter.
        observed = set()
        for n in range(-30, 31):
            S, N = constants(n)
            for x in range(-180, 181):
                T = S+x
                if not x or not T or N % x:
                    continue
                t2 = T*T+N//x
                if t2 < 0:
                    continue
                t = isqrt(t2)
                if t*t != t2:
                    continue
                triple = (-x-t, -x+t, S+2*x)
                mapped = points_from_cube(triple)
                expected = (str(n), str(x), str(abs(Fraction(t, T))))
                self.assertIn(expected, {(r["n"], r["x"], r["y"]) for r in mapped})
                observed.add(expected)
        self.assertGreaterEqual(len(observed), 2)

    def test_poles_invalid_numbers_and_wrong_cube_identity(self):
        for x in (0, -81):
            with self.assertRaises(ValueError):
                check_point(13, x, 0)
            with self.assertRaises(ValueError):
                rational_point_at(13, x)
        for n, x, y in ((True, -5, 0), (2, -5.0, 0), (2, -5, 0.0)):
            with self.assertRaises(ValueError):
                check_point(n, x, y)
        with self.assertRaises(ValueError):
            points_from_cube((1, 2, 3))
        with self.assertRaises(ValueError):
            points_from_cube((5, 5, 5), n_min=3, n_max=2)


if __name__ == "__main__":
    unittest.main()
