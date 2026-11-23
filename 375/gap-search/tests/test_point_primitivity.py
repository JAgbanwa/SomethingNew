"""Regression for the three-coordinate integer point-gcd contract."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from to_points375 import points


class PointPrimitivity(unittest.TestCase):
    def test_y_can_remove_a_common_factor_of_n_and_x(self):
        # n=5, x=-5, y=3 is primitive as a point, although gcd(n,x)=5.
        matches = [p for p in points(8, 2, 23, 12687)
                   if p["n"] == 5 and p["x"] == -5 and p["y"] == 3]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0]["primitive_point"])
        self.assertTrue(matches[0]["desired"])

    def test_nonprimitive_cubes_remain_diagnostic(self):
        p = points(5, 5, 5, 375)[0]
        self.assertTrue(p["primitive_point"])
        self.assertFalse(p["primitive_cubes"])
        self.assertFalse(p["desired"])
