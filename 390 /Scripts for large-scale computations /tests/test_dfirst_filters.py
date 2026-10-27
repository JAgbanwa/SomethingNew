"""Independent checks of the half-chart congruence exclusions.

These tests need no native compiler. Native/Python agreement and recovery of
all seven known k=6 points are also exercised by test_dfirst.py.
"""
from fractions import Fraction
from math import gcd
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfirst_common import admissible, half_chart_mod4, shell_pairs, thue_form, verify_hit


def previous_admissibility(p, q, m):
    """Independent oracle for the filters used before the mod-4 improvement.

    Trial division is deliberately implemented here rather than calling the
    implementation's factor/prime-cap helpers, so the recorded 789-to-517
    regression is not a comparison of the same routine with itself.
    """
    if not p or q <= 0 or q % 2 == 0 or gcd(p, q) != 1:
        return False
    if p % 3 == 0 or q % 3 == 0 or (p - q) % 3:
        return False
    if m % 2 and p % 4 == 0:
        return False
    remaining = abs(p * q)
    prime = 2
    while remaining > 1:
        if prime * prime > remaining:
            prime = remaining
        exponent = 0
        while remaining % prime == 0:
            exponent += 1
            remaining //= prime
        if exponent and prime > 3:
            value, valuation = abs(m), 0
            while value % prime == 0:
                value //= prime
                valuation += 1
            if valuation:
                if valuation <= 2 and exponent > valuation:
                    return False
            elif prime % 3 == 1:
                # Independent cube enumeration for small oracle inputs.
                if not any((36 * t**3 - m) % prime == 0 for t in range(prime)):
                    return False
        prime += 1
    return True


def k6_certificate(d, n, X, Y):
    """Build a recorded known answer, independently of the search worker."""
    x, y = Fraction(X, 2), Fraction(Y, 2)
    A, B, C = -x + y, -x - y, 2*x + 6*n
    return {"type": "hit", "chart": "half", "m": "1",
            "d_num": str(d.numerator), "d_den": str(d.denominator),
            "n_num": str(n), "n_den": "1", "x_num": str(X), "x_den": "2",
            "y_num": str(Y), "y_den": "2", "cube_plus": str(A),
            "cube_minus": str(B), "cube_third": str(C), "cube_sum": "6"}


KNOWN_K6 = (
    (Fraction(1), 0, -1, 3),
    (Fraction(22, 7), -6, -7, 123),
    (Fraction(-22, 101), -6, 101, 15),
    (Fraction(1, 181), -9, -181, 291),
    (Fraction(181), -9, -1, 471),
    (Fraction(7, 439), -33, -439, 849),
    (Fraction(439, 7), -33, -7, 1281),
)


class HalfChartFilterTests(unittest.TestCase):
    def test_mod4_condition_matches_exhaustive_cubic_residues(self):
        # Both signed representatives of every p residue, both odd q/g
        # residues, and all n residues: the filter is equivalent to local
        # solvability modulo 4, not merely a heuristic based on examples.
        for m in (-65, -1, 1, 65):
            for p in range(-8, 9):
                for q in range(1, 8, 2):
                    possible = any(thue_form(p, q, n, g) % 4 == (2*m) % 4
                                   for n in range(4) for g in (1, 3))
                    self.assertEqual(half_chart_mod4(p, q, m), possible, (p, q, m))

    def test_negative_numerators_use_signed_residue(self):
        # Taking abs(p) would reject the first two and retain the next two.
        for p, q in ((-11, 1), (-23, 13), (-22, 101), (22, 7)):
            self.assertTrue(half_chart_mod4(p, q, 65), (p, q))
        for p, q in ((-1, 5), (-5, 1), (5, 11), (11, 5)):
            self.assertFalse(half_chart_mod4(p, q, 65), (p, q))
            self.assertTrue(previous_admissibility(p, q, 65), (p, q))
            self.assertFalse(admissible(p, q, 65), (p, q))
        for p, q in ((-11, 1), (-23, 13)):
            self.assertTrue(admissible(p, q, 65), (p, q))

    def test_small_height_regression_keeps_517_of_previous_789(self):
        previous, retained = set(), set()
        for h in range(1, 121):
            for p, q in shell_pairs(h):
                if previous_admissibility(p, q, 65):
                    previous.add((p, q))
                if admissible(p, q, 65):
                    retained.add((p, q))
        self.assertEqual(len(previous), 789)
        self.assertEqual(len(retained), 517)
        self.assertEqual(previous - retained,
                         {(p, q) for p, q in previous if (p * (p + q)) % 4 != 2})
        self.assertTrue(retained <= previous)

    def test_even_m_admissibility_is_unchanged(self):
        for m in (-2, 2, 4, 10):
            for h in range(1, 31):
                for p, q in shell_pairs(h):
                    self.assertTrue(half_chart_mod4(p, q, m))
                    self.assertEqual(admissible(p, q, m), previous_admissibility(p, q, m),
                                     (p, q, m))

    def test_all_seven_known_answers_survive_and_verify(self):
        for d, n, X, Y in KNOWN_K6:
            self.assertTrue(admissible(d.numerator, d.denominator, 1), d)
            verify_hit(k6_certificate(d, n, X, Y), 1)

    def test_production_congruence_assertion_is_explicit_and_target_specific(self):
        for n in (-6, -3, 0, 2, 3):
            hit = k6_certificate(Fraction(1), n, -1, 3)
            hit["m"] = "65"
            with self.assertRaisesRegex(ValueError, "production n must be congruent to 1 modulo 3"):
                verify_hit(hit, 65)
        # Wrong-target n=0 remains valid for the genuine k=6 known answer.
        verify_hit(k6_certificate(Fraction(1), 0, -1, 3), 1)

    def test_cube_residues_imply_required_n_congruence(self):
        # Check the algebraic implication independently of the new assertion.
        for A in range(54):
            for B in range(54):
                for C in range(54):
                    if (A**3 + B**3 + C**3 - 390) % 54 == 0:
                        self.assertEqual((A + B + C) % 6, 0)
                        self.assertEqual(((A + B + C) // 6) % 3, 1)


if __name__ == "__main__":
    unittest.main()
