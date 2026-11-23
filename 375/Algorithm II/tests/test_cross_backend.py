"""Compare both search kernels with an independent exhaustive cube oracle.

The oracle never uses modular cube roots, square discriminants, tangent tiles,
lattice reduction, or the rational-d equation. It enumerates two cube
coordinates and looks up the third in a complete finite cube table.
"""
from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
from math import gcd, isqrt
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from booker_sutherland import search  # noqa: E402
from elkies_jahnel import build_worker, iter_shell  # noqa: E402
from equation375 import points_from_cubes  # noqa: E402


def canonical(cubes):
    return tuple(sorted(cubes))


def primitive(cubes):
    return gcd(gcd(cubes[0], cubes[1]), cubes[2]) == 1


@lru_cache(maxsize=None)
def brute_box(target: int, height: int):
    """Every unordered integer triple with max absolute coordinate <= height."""
    cube_table = {coordinate ** 3: coordinate
                  for coordinate in range(-height, height + 1)}
    result = set()
    for a in range(-height, height + 1):
        for b in range(a, height + 1):
            c = cube_table.get(target - a ** 3 - b ** 3)
            if c is not None and c >= b:
                result.add((a, b, c))
    return frozenset(result)


def rectangle_oracle(target: int, D_min: int, D_max: int,
                     z_min: int, z_max: int):
    """Exhaust a provably sufficient cube box, then apply the rectangle.

    For S=u+v, |S|<=D_max and |u-v|²=(4Q-S²)/3<=4M/3,
    where M=|target|+max(|z_min|,|z_max|)^3. This only supplies
    an upper bound for the independent cube oracle; it does not find hits.
    """
    z_bound = max(abs(z_min), abs(z_max))
    M = abs(target) + z_bound ** 3
    difference_bound = isqrt(4 * M // 3) + 1
    height = max(z_bound, (D_max + difference_bound + 1) // 2)
    expected = set()
    for cubes in brute_box(target, height):
        total = sum(cubes)
        if any(z_min <= z <= z_max and D_min <= abs(total - z) <= D_max
               for z in cubes):
            expected.add(cubes)
    return expected


class BookerExhaustiveAgreement(unittest.TestCase):
    def test_rectangles_against_independent_cube_enumeration(self):
        cases = (
            (3, 1, 12, -5, 5),       # repeated coordinates are legitimate
            (6, 1, 30, -70, 70),    # nonempty primitive high-cancellation hit
            (7, 1, 8, -3, 4),       # zero coordinate
            (15, 1, 12, -5, 5),
            (375, 1, 40, -25, 25),  # both familiar nonprimitive triples
            (0, 1, 12, -8, 9),      # singular cube roots; D=0 stays excluded
            (8, 2, 15, -10, 10),    # a cube target with a zero-pair exception
            (-6, 1, 15, -8, 7),     # signed target and asymmetric z interval
            (3, 1, 1, 4, 4),        # inclusive endpoints, just (-5,4,4)
        )
        for target, D_min, D_max, z_min, z_max in cases:
            expected = rectangle_oracle(target, D_min, D_max, z_min, z_max)
            for primitive_only in (False, True):
                with self.subTest(target=target, region=(D_min, D_max, z_min, z_max),
                                  primitive=primitive_only):
                    results = list(search(target, D_min, D_max, z_min, z_max,
                                          primitive_only=primitive_only))
                    for u, v, w in results:
                        self.assertEqual(u ** 3 + v ** 3 + w ** 3, target)
                        self.assertGreaterEqual(u, v)
                        self.assertLessEqual(D_min, abs(u + v))
                        self.assertLessEqual(abs(u + v), D_max)
                        self.assertLessEqual(z_min, w)
                        self.assertLessEqual(w, z_max)
                    wanted = {t for t in expected if not primitive_only or primitive(t)}
                    self.assertEqual({canonical(t) for t in results}, wanted)

    def test_adjacent_inclusive_rectangles_partition_without_gaps(self):
        full = {canonical(t) for t in search(375, 1, 40, -25, 25)}
        left = {canonical(t) for t in search(375, 1, 40, -25, -1)}
        right = {canonical(t) for t in search(375, 1, 40, 0, 25)}
        self.assertEqual(left | right, full)
        low = {canonical(t) for t in search(375, 1, 9, -25, 25)}
        high = {canonical(t) for t in search(375, 10, 40, -25, 25)}
        self.assertEqual(low | high, full)
        self.assertEqual(full, {(5, 5, 5), (-25, 20, 20)})
        # Different pair choices may legitimately rediscover one cube triple.


class BothKernelsAgainstCubeOracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker = build_worker()

    def native_shell(self, height, target, primitive_only):
        records = list(iter_shell(height, target=target, primitive=primitive_only,
                                  progress_every=0, worker=self.worker))
        self.assertEqual(records[0]["type"], "start")
        self.assertEqual(records[-1]["type"], "end")
        self.assertIs(records[-1]["complete"], True)
        return {canonical(tuple(int(record[key]) for key in ("x", "y", "z")))
                for record in records if record["type"] == "hit"}

    def test_complete_small_shells_match_both_search_methods(self):
        for height, target in ((25, 375), (25, 15), (65, 6), (64, 7)):
            all_expected = {t for t in brute_box(target, 2 * height - 1)
                            if max(abs(v) for v in t) >= height}
            for primitive_only in (False, True):
                with self.subTest(height=height, target=target,
                                  primitive=primitive_only):
                    expected = {t for t in all_expected
                                if not primitive_only or primitive(t)}
                    native = self.native_shell(height, target, primitive_only)
                    modular = {
                        canonical(t)
                        for t in search(target, 1, 4 * height - 2,
                                        -2 * height + 1, 2 * height - 1,
                                        primitive_only=primitive_only)
                        if height <= max(abs(v) for v in t) < 2 * height
                    }
                    self.assertEqual(native, expected)
                    self.assertEqual(modular, expected)
                    if target == 6:
                        self.assertIn((-58, -43, 65), expected)
                    if target == 375:
                        self.assertEqual(expected, set() if primitive_only
                                         else {(-25, 20, 20)})

    def test_nonempty_end_to_end_half_integer_chart(self):
        cubes = self.native_shell(25, 15, True)
        self.assertIn((-46, 23, 44), cubes)
        points = {
            (p.n, p.X, p.Y, p.d)
            for triple in cubes
            for p in points_from_cubes(triple, target=15)
        }
        self.assertIn((3, -67, 21, Fraction(-2, 67)), points)
        # Independently substitute the known control in the original form.
        n, x, y, d = 3, Fraction(-67, 2), Fraction(21, 2), Fraction(-2, 67)
        A = Fraction((6 * n + 3) ** 3 - 15, 6)
        self.assertEqual(y * y, (x + 6 * n + 3) ** 2 + A / x)
        self.assertEqual(A, -2 * d * x * x * (y - (x + 6 * n + 3)))


if __name__ == "__main__":
    unittest.main()
