"""Exact certificate tests, independent of the GMP search implementation."""

from fractions import Fraction
import json
from math import gcd, isqrt
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verify import Bounds, VerificationError, integer, verify_record


# Historical solutions of the equation, NOT hits in the production box.
# The expected d values are independent fixed regression values.
FIXTURES = [
    (-5, 81, Fraction(-913, 1458)),
    (-2960189, 34556096, Fraction(-262121371, 552897536)),
    (46219, -394731, Fraction(-144791, 2368386)),
    (1847965, -16010260, Fraction(-761139263, 13896905680)),
    (166, -2500, Fraction(-1103, 250000)),
    (2047, -45972, Fraction(-599, 551664)),
    (-5877899, 11122866225, Fraction(-2338707218296801, 2346146172839250)),
]
FIXTURE_BOUNDS = Bounds(-10**10, 10**10, -10**12, 10**12)


def certificate(n, x, d):
    """Generate test data by a direct square test, never by worker formulas."""
    radicand_times_x_squared = x*x*(x+6*n)**2 + (36*n**3-65)*x
    m = isqrt(radicand_times_x_squared)
    if m*m != radicand_times_x_squared:
        raise ValueError("fixture is not an exact rational radical")
    y = Fraction(m, abs(x))
    return {
        "n": str(n), "x": str(x),
        "d_num": str(d.numerator), "d_den": str(d.denominator),
        "y_num": str(y.numerator), "y_den": str(y.denominator),
        "sqrt_integer": y.denominator == 1,
    }


class CertificateTests(unittest.TestCase):
    def relaxed(self, record, **kwargs):
        return verify_record(record, FIXTURE_BOUNDS, require_congruences=False, **kwargs)

    def test_seven_original_equation_certificates(self):
        for n, x, d in FIXTURES:
            with self.subTest(n=n, x=x):
                result = self.relaxed(certificate(n, x, d))
                self.assertEqual(result["d_num"], str(d.numerator))
                self.assertEqual(result["d_den"], str(d.denominator))

    def test_nonprimitive_fixture(self):
        n, x, d = FIXTURES[3]
        self.assertEqual(gcd(n, x), 35)
        self.assertEqual(self.relaxed(certificate(n, x, d))["n"], str(n))

    def test_signed_x_uses_absolute_denominator_for_principal_sqrt(self):
        n, x, d = FIXTURES[2]
        result = self.relaxed(certificate(n, x, d))
        self.assertEqual(Fraction(int(result["y_num"]), int(result["y_den"])), Fraction(207460, 3))

    def test_wrong_sqrt_branch_rejected(self):
        item = certificate(*FIXTURES[0])
        item["y_num"] = str(-int(item["y_num"]))
        with self.assertRaisesRegex(VerificationError, "principal"):
            self.relaxed(item)

    def test_other_algebraic_d_branch_rejected(self):
        n, x, d = FIXTURES[0]
        item = certificate(n, x, d)
        y = Fraction(int(item["y_num"]), int(item["y_den"]))
        other_d = (y-(x+6*n))/(2*x)
        item.update(d_num=str(other_d.numerator), d_den=str(other_d.denominator))
        with self.assertRaisesRegex(VerificationError, "unsquared"):
            self.relaxed(item)

    def test_tampered_d_rejected(self):
        item = certificate(*FIXTURES[0])
        d = Fraction(int(item["d_num"]), int(item["d_den"])) + 1
        item.update(d_num=str(d.numerator), d_den=str(d.denominator))
        with self.assertRaisesRegex(VerificationError, "unsquared"):
            self.relaxed(item)

    def test_tampered_y_rejected(self):
        item = certificate(*FIXTURES[0])
        y = Fraction(int(item["y_num"]), int(item["y_den"])) + 1
        item.update(y_num=str(y.numerator), y_den=str(y.denominator))
        with self.assertRaisesRegex(VerificationError, "reported y"):
            self.relaxed(item)

    def test_congruences_are_enforced_by_default(self):
        with self.assertRaisesRegex(VerificationError, "congruences"):
            verify_record(certificate(*FIXTURES[0]), FIXTURE_BOUNDS)

    def test_congruences_apply_to_signed_values_not_magnitudes(self):
        positive_n, positive_x = 10**43, 10**54+1
        self.assertEqual(positive_n % 3, 1)
        self.assertEqual(positive_x % 12, 5)
        for n, x in ((-positive_n, positive_x), (positive_n, -positive_x)):
            item = {"n": str(n), "x": str(x), "y_num": "0", "y_den": "1",
                    "d_num": "1", "d_den": "2"}
            with self.subTest(n=n, x=x), self.assertRaisesRegex(VerificationError, "congruences"):
                verify_record(item)

    def test_production_bounds_are_enforced_by_default(self):
        with self.assertRaisesRegex(VerificationError, "bounds"):
            verify_record(certificate(*FIXTURES[0]), require_congruences=False)

    def test_inclusive_custom_bounds(self):
        n, x, d = FIXTURES[0]
        verify_record(certificate(n, x, d), Bounds(n, n, x, x), require_congruences=False)
        with self.assertRaisesRegex(VerificationError, "bounds"):
            verify_record(certificate(n, x, d), Bounds(n+1, n+1, x, x), require_congruences=False)

    def test_magnitude_bounds_accept_signed_historical_solutions(self):
        for n, x, d in FIXTURES:
            with self.subTest(n=n, x=x):
                bounds = Bounds(abs(n), abs(n), abs(x), abs(x), magnitudes=True)
                result = verify_record(certificate(n, x, d), bounds, require_congruences=False)
                self.assertEqual((int(result["n"]), int(result["x"])), (n, x))
                with self.assertRaisesRegex(VerificationError, "bounds"):
                    verify_record(certificate(n, x, d),
                                  Bounds(abs(n)+1, abs(n)+1, abs(x), abs(x), magnitudes=True),
                                  require_congruences=False)

    def test_requested_signs_are_enforced(self):
        n, x, d = FIXTURES[0]
        item = certificate(n, x, d)
        for signs in ("all", "np"):
            verify_record(item, Bounds(5, 5, 81, 81, magnitudes=True, signs=signs),
                          require_congruences=False)
        for signs in ("pp", "pn", "nn"):
            with self.assertRaisesRegex(VerificationError, "signs"):
                verify_record(item, Bounds(5, 5, 81, 81, magnitudes=True, signs=signs),
                              require_congruences=False)

    def test_bounds_validation_rejects_bad_magnitudes_and_signs(self):
        for kwargs in ({"n_min": 0, "magnitudes": True},
                       {"x_min": -1, "magnitudes": True}, {"signs": "mixed"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Bounds(**kwargs)

    def test_absolute_slope_metadata_is_verified(self):
        # This is a genuine negative-n solution, with an independently fixed
        # auxiliary fraction.  It is not a production-size search hit.
        item = certificate(*FIXTURES[0])
        item.update(a="545", q="729")
        self.relaxed(item)
        for a, q in (("547", "729"), ("1090", "1458"), ("729", "729")):
            bad = dict(item, a=a, q=q)
            with self.subTest(a=a, q=q), self.assertRaises(VerificationError):
                self.relaxed(bad)

    def test_rational_sqrt_is_not_silently_called_integer(self):
        item = certificate(*FIXTURES[0])
        self.assertFalse(item["sqrt_integer"])
        with self.assertRaisesRegex(VerificationError, "not an integer"):
            self.relaxed(item, require_integer_sqrt=True)
        item["sqrt_integer"] = True
        with self.assertRaisesRegex(VerificationError, "sqrt_integer"):
            self.relaxed(item)

    def test_noncanonical_and_bad_numbers_rejected(self):
        for value in [1.0, True, "1e2", "+1", "01", " 1", "1 ", None]:
            with self.subTest(value=value), self.assertRaises(VerificationError):
                integer(value, "test")
        item = certificate(*FIXTURES[0])
        item["d_num"] = str(2*int(item["d_num"]))
        item["d_den"] = str(2*int(item["d_den"]))
        with self.assertRaisesRegex(VerificationError, "reduced"):
            self.relaxed(item)
        item = certificate(*FIXTURES[0])
        item["d_den"] = "0"
        with self.assertRaisesRegex(VerificationError, "positive"):
            self.relaxed(item)

    def test_zero_x_rejected_before_division(self):
        item = certificate(*FIXTURES[0])
        item["x"] = "0"
        with self.assertRaisesRegex(VerificationError, "nonzero"):
            self.relaxed(item)

    def test_production_size_near_square_cannot_pass(self):
        n, x = 10**43, 10**54+1
        self.assertEqual(n % 3, 1)
        self.assertEqual(x % 12, 5)
        self.assertNotEqual(x % 7, 0)
        m2 = x*x*(x+6*n)**2+(36*n**3-65)*x
        m = isqrt(m2)
        self.assertNotEqual(m*m, m2)
        y = Fraction(m, x)
        d = -(y+x+6*n)/(2*x)
        item = {"n":str(n), "x":str(x), "y_num":str(y.numerator),
                "y_den":str(y.denominator), "d_num":str(d.numerator),
                "d_den":str(d.denominator)}
        with self.assertRaisesRegex(VerificationError, "not rational"):
            verify_record(item)

    def test_default_magnitude_policy_reaches_radical_check_in_all_quadrants(self):
        # Synthetic near-squares must get past magnitude and signed residue
        # filters, then be rejected by the actual mathematics in every quadrant.
        for nsign in (-1, 1):
            for xsign in (-1, 1):
                n = nsign * (10**43 + 10)
                n += (1-n) % 3
                x = xsign * (10**54 + 100)
                x += (5-x) % 12
                if x % 7 == 0:
                    x += 12
                with self.subTest(nsign=nsign, xsign=xsign):
                    self.assertEqual(n % 3, 1)
                    self.assertEqual(x % 12, 5)
                    m2 = x*x*(x+6*n)**2+(36*n**3-65)*x
                    m = isqrt(m2)
                    self.assertNotEqual(m*m, m2)
                    y = Fraction(m, abs(x))
                    d = -(y+x+6*n)/(2*x)
                    item = {"n": str(n), "x": str(x), "y_num": str(y.numerator),
                            "y_den": str(y.denominator), "d_num": str(d.numerator),
                            "d_den": str(d.denominator)}
                    with self.assertRaisesRegex(VerificationError, "not rational"):
                        verify_record(item)

    def test_cli_accepts_fixture_and_reports_exact_count(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"fixture.jsonl"
            path.write_text(json.dumps(certificate(*FIXTURES[0]))+"\n", encoding="utf-8")
            run = subprocess.run([sys.executable, str(ROOT/"verify.py"), str(path),
                                  "--n-min=-5", "--n-max=-5", "--x-min=81", "--x-max=81",
                                  "--signed-intervals", "--relax-congruences"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["unique_solutions"], 1)

    def test_cli_magnitude_defaults_accept_negative_n(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"fixture.jsonl"
            path.write_text(json.dumps(certificate(*FIXTURES[0]))+"\n", encoding="utf-8")
            run = subprocess.run([sys.executable, str(ROOT/"verify.py"), str(path),
                                  "--n-min=5", "--n-max=5", "--x-min=81", "--x-max=81",
                                  "--relax-congruences"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["unique_solutions"], 1)

    def test_cli_empty_file_does_not_claim_a_hit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"empty.jsonl"
            path.write_text("", encoding="utf-8")
            run = subprocess.run([sys.executable, str(ROOT/"verify.py"), str(path)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["unique_solutions"], 0)


if __name__ == "__main__":
    unittest.main()
