"""Tests for to_d.py: representations -> rational d of the original equation, both charts."""
from __future__ import annotations

from fractions import Fraction
import json
from math import isqrt
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from to_d import points  # noqa: E402

WORKER = ROOT / "bin" / "gap_worker"
GRID_VERIFY = ROOT.parent / "grid " / "verify.py"

RECORDS = {  # k = 6m with m not divisible by 3
    42: (-80538738812075974, 80435758145817515, 12602123297335631),
    906: (-74924259395610397, 72054089679353378, 35961979615356503),
}


def frac_sqrt(q: Fraction) -> Fraction | None:
    if q < 0:
        return None
    a, b = isqrt(q.numerator), isqrt(q.denominator)
    return Fraction(a, b) if a * a == q.numerator and b * b == q.denominator else None


class Records(unittest.TestCase):
    def test_one_integer_and_two_half_chart_points(self):
        for k, t in RECORDS.items():
            pts = points(*t, k=k)
            self.assertEqual(sorted(p["result"] for p in pts), [1, 2, 2], k)
            for p in pts:
                n, x, s, d = int(p["n"]), Fraction(p["x"]), Fraction(p["sqrt"]), Fraction(p["d"])
                m = k // 6
                self.assertEqual(36 * n ** 3 - m, -2 * d * x * x * (-(x + 6 * n) + s))
                if p["result"] == 2:
                    self.assertTrue(int(p["X"]) % 2 and int(p["Y"]) % 2)

    @unittest.skipUnless(GRID_VERIFY.exists(), "grid/verify.py not present")
    def test_agrees_with_grid_verify(self):
        """The folder's earlier, independently written verifier gives the same d values."""
        for k, t in RECORDS.items():
            out = subprocess.run([sys.executable, str(GRID_VERIFY), "--K", str(k // 6), "--triple", *map(str, t)],
                                 capture_output=True, text=True, check=True).stdout
            theirs = {Fraction(int(a), int(b)) for a, b in re.findall(r"^\s*d = (-?\d+) / (\d+)", out, re.M)}
            mine = {Fraction(p["d"]) for p in points(*t, k=k)}
            self.assertEqual(mine, theirs, k)


class Equivalence(unittest.TestCase):
    """Brute force on the ORIGINAL equation, without the cube identity: every point of either
    acceptable chart in a box must come from a representation, and to_d must list it."""

    def test_brute_force_on_equation(self):
        total = 0
        for m in (1, 2, 4, 5, 7, 8, 10, 11, 19):
            k = 6 * m
            # independent: all (n, x), |n| <= 25, x = X/2 with 0 < |X| <= 120, of either acceptable chart
            found = 0
            for n in range(-25, 26):
                N = 36 * n ** 3 - m
                for X in range(-120, 121):
                    if X == 0:
                        continue
                    x = Fraction(X, 2)
                    s = frac_sqrt((x + 6 * n) ** 2 + N / x)
                    if s is None:
                        continue
                    if not ((x.denominator == 1 and s.denominator == 1) or (x.denominator == 2 and s.denominator == 2)):
                        continue
                    U = x + 6 * n
                    d = Fraction(N) / (-2 * x * x * (s - U))        # s != U since N != 0
                    A, B, C = -x + s, -x - s, 2 * x + 6 * n
                    self.assertTrue(all(v.denominator == 1 for v in (A, B, C)))
                    A, B, C = int(A), int(B), int(C)
                    self.assertEqual(A ** 3 + B ** 3 + C ** 3, k)    # the identity: a point is a representation
                    listed = {(Fraction(p["d"]), int(p["n"]), Fraction(p["x"])) for p in points(A, B, C, k=k)}
                    self.assertIn((d, n, x), listed, (m, n, x))       # and to_d lists that very point
                    found += 1
            if m == 19:
                self.assertEqual(found, 0)   # 114 has no representation that small (Booker-Sutherland)
            total += found
        self.assertGreater(total, 10)

    def test_repeated_component(self):
        # 8478 = 2(-21)^3 + 30^3: a repeated component gives only two distinct points
        self.assertEqual(sorted(p["result"] for p in points(-21, -21, 30, k=8478)), [1, 2])

    def test_rejects_non_representation(self):
        with self.assertRaises(ValueError):
            points(1, 2, 3, k=114)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class EndToEnd(unittest.TestCase):
    def test_worker_hit_to_d(self):
        k, t = 42, RECORDS[42]
        Z = min(t, key=abs)
        x, y = [v for v in t if v != Z]
        d0, z = abs(x + y), abs(Z)
        out = subprocess.run([str(WORKER), "--k", "42", "--d-start", str(d0 - 5), "--d-stop", str(d0 + 5),
                              "--ratio-max", str(-(-z // d0) + 1)], capture_output=True, text=True, check=True).stdout
        hits = [line for line in out.splitlines() if '"hit"' in line]
        self.assertEqual(len(hits), 1)
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "worker.out"          # raw worker output, with start/chunk/end records
            raw.write_text(out)
            dup = Path(td) / "hits.jsonl"         # the same hit again: must be listed once
            dup.write_text(hits[0] + "\n")
            r = subprocess.run([sys.executable, str(ROOT / "to_d.py"), "--k", "42", str(raw), str(dup)],
                               capture_output=True, text=True, check=True).stdout
        self.assertEqual(r.count("result 1 (integer chart)"), 1)
        self.assertEqual(r.count("result 2 (half chart)"), 2)


if __name__ == "__main__":
    unittest.main()


class Result3(unittest.TestCase):
    """x an integer and sqrt = Y/2 (Y odd) <=> 912 = a^3 + b^3 + c^3 with a, b odd and 4 | c."""

    def test_known_solution_from_912(self):
        from to_d import points_8k
        pts = points_8k(55956937, -55648340, -14232281, k=114)
        self.assertEqual(len(pts), 1)
        p = pts[0]
        self.assertEqual((p["n"], p["x"], p["sqrt"], p["d"]),
                         ("-1160307", "-10431164", "35094609/2", "308597/41724656"))

    def test_brute_force_small_box(self):
        # every result-3 point of (E) with m in a few values, |n| <= 30, |x| <= 400, against points_8k
        from to_d import points_8k
        for m in (1, 2, 4, 5, 7, 19):
            k = 6 * m
            for n in range(-30, 31):
                N = 36 * n ** 3 - m
                for x in range(-400, 401):
                    if x == 0:
                        continue
                    q = Fraction((x + 6 * n) ** 2) + Fraction(N, x)
                    r = frac_sqrt(q)
                    if r is None or r.denominator != 2:
                        continue
                    a, b, c = int(2 * (-x + r)), int(2 * (-x - r)), 2 * (2 * x + 6 * n)
                    self.assertEqual(a ** 3 + b ** 3 + c ** 3, 8 * k)
                    got = points_8k(a, b, c, k=k)
                    self.assertEqual([(int(g["n"]), int(g["x"])) for g in got], [(n, x)])
