"""Independent arithmetic/partition checks for the n-strip planning layer."""
import importlib.util
from fractions import Fraction
from pathlib import Path
import sys
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "region.py"
SPEC = importlib.util.spec_from_file_location("ej_region_tested", SOURCE)
region = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = region
SPEC.loader.exec_module(region)


class RegionTests(unittest.TestCase):
    def test_integer_roots_at_large_boundaries(self):
        for k in (1, 2, 9, 10**20 + 123, 10**60 + 17):
            for value in (k**3 - 1, k**3, k**3 + 1):
                lower = region.floor_cuberoot(value)
                upper = region.ceil_cuberoot(value)
                self.assertLessEqual(lower**3, value)
                self.assertGreater((lower + 1)**3, value)
                self.assertGreaterEqual(upper**3, value)
                self.assertLess((upper - 1)**3, value)

    def test_interval_modular_count_without_enumeration(self):
        for low, high in ((1, 200), (2, 2), (11, 11), (50, 300)):
            expected = sum(n % 27 in region.N_RESIDUES for n in range(low, high + 1))
            self.assertEqual(region.admissible_n_count(low, high), expected)
        self.assertEqual(region.admissible_n_count(10**17, 10**20),
                         18_500_000_000_000_000_000)

    def test_ratio_root_rounding_near_huge_integer_boundaries(self):
        # delta=1 makes F(u)=6*(u-1)^2+1-epsilon.  These expected roots
        # follow directly, independently of the discriminant implementation.
        self.assertEqual(region._ratio_root_floors(Fraction(1), Fraction(1), 7), (7, 7))
        self.assertEqual(region._ratio_root_floors(Fraction(1),
                         1 + 6*Fraction(3, 7)**2, 7), (4, 10))
        grid, q = 10**40 + 7, 10**60 + 19
        self.assertEqual(region._ratio_root_floors(Fraction(1),
                         1 + Fraction(6, q*q), grid), (grid-1, grid))
        self.assertEqual(region._ratio_root_floors(Fraction(1),
                         1 + Fraction(12, q*q), grid), (grid-1, grid))
        self.assertIsNone(region._ratio_root_floors(Fraction(1),
                          1 - Fraction(1, q*q), grid))

    def test_known_375_control_included_on_global_ratio_boundary(self):
        # 20^3+20^3-25^3=375 and S=15, n=2.  Its ratio index is exactly
        # the one included native upper endpoint 4H=100.
        plan = region.make_region(2, 2, height_min=25, height_max=25)
        tasks = list(region.iter_tasks(plan, band_width=7))
        selected = [t for t in tasks if t.height == 25
                    and t.index_start <= 100
                    and (100 < t.index_stop or t.include_right_endpoint and 100 == t.index_stop)]
        self.assertEqual(len(selected), 1)
        self.assertTrue(selected[0].include_right_endpoint)
        self.assertEqual((selected[0].c_min, selected[0].c_max), (25, 25))
        self.assertFalse(plan.complete_height_scope)
        self.assertFalse(plan.small_height_required)
        self.assertLessEqual(25, plan.canonical_height_max)
        self.assertEqual(region.canonical_height_lower(15), 25)

    def test_height_lower_bound_is_the_first_permitted_integer(self):
        for n in (1, 2, 3, 100, 10**20):
            total = 6*n+3
            c = region.canonical_height_lower(total)
            self.assertEqual(c % 3, 1)
            self.assertGreaterEqual(c, total+4)
            self.assertLessEqual((total+c)**3, 4*(c**3+375))
            if c-3 >= total+4:
                self.assertGreater((total+c-3)**3, 4*((c-3)**3+375))

    def test_small_height_fallback_is_explicit(self):
        plan = region.make_region(2, 2)
        self.assertTrue(plan.small_height_required)
        self.assertEqual((plan.small_height_min, plan.small_height_max), (0, 24))
        self.assertTrue(plan.complete_height_scope)
        # The low control (5,5,5), height5, cannot be found by a native H>=25 task.
        self.assertLessEqual(plan.small_height_min, 5)
        self.assertGreaterEqual(plan.small_height_max, 5)
        self.assertFalse(region.make_region(100, 200).small_height_required)

    def test_partition_and_resume_pages_are_exact(self):
        plan = region.make_region(2, 100, height_min=25, height_max=200)
        tasks = list(region.iter_tasks(plan, band_width=37))
        self.assertEqual(len(tasks), region.task_count(plan, 37))
        self.assertEqual([t.logical_index for t in tasks], list(range(len(tasks))))
        self.assertEqual(list(region.iter_tasks(plan, 37, start=7, limit=11)), tasks[7:18])
        self.assertEqual(list(region.iter_tasks(plan, 37, start=len(tasks), limit=3)), [])
        self.assertEqual(list(region.iter_tasks(plan, 37, limit=0)), [])
        for shell in region.iter_shells(plan):
            parts = [t for t in tasks if t.height == shell.height]
            self.assertEqual(parts[0].index_start, shell.index_start)
            self.assertEqual(parts[-1].index_stop, shell.index_stop)
            for left, right in zip(parts, parts[1:]):
                self.assertEqual(left.index_stop, right.index_start)

    def test_bruteforce_native_control_coverage(self):
        # This oracle knows nothing about the height proof, tangent curve, LLL
        # or sampling.  Enumerate native signed cube solutions at small heights
        # and check every positive-n control falls in precisely one planned band.
        limit = 160
        cubes = {a**3: a for a in range(1, limit)}
        hits = []
        for c in range(25, limit):
            for a in range(1, c):
                b = cubes.get(c**3 + 375 - a**3)
                if b is not None and a <= b < c:
                    total = a + b - c
                    if total >= 9 and total % 6 == 3:
                        hits.append((a, b, c, (total - 3)//6))
        self.assertIn((20, 20, 25, 2), hits)
        for a, b, c, n in hits:
            plan = region.make_region(n, n)
            self.assertLessEqual(c, plan.canonical_height_max)
            containing = []
            for task in region.iter_tasks(plan, band_width=11):
                if not task.c_min <= c <= task.c_max:
                    continue
                index_numerator = 5 * task.height * a
                if task.index_start*c <= index_numerator and (
                    index_numerator < task.index_stop*c or
                    task.include_right_endpoint and index_numerator == task.index_stop*c
                ):
                    containing.append(task)
            self.assertEqual(len(containing), 1, (a, b, c, n))

    def test_large_region_stays_compact_and_exact(self):
        plan = region.make_region(10**17, 10**20)
        description = region.describe_region(plan, band_width=1000)
        self.assertTrue(plan.complete_height_scope)
        self.assertFalse(plan.small_height_required)
        self.assertGreater(plan.canonical_height_max, 10**30)
        self.assertLess(plan.canonical_height_max, 10**31)
        self.assertEqual(plan.canonical_height_max % 3, 1)
        self.assertLess(description["native_shell_count"], 100)
        count = region.task_count(plan, 1000)
        self.assertGreater(count, 10**18)
        last = list(region.iter_tasks(plan, 1000, start=count - 1, limit=1))
        self.assertEqual(len(last), 1)
        self.assertEqual(last[0].logical_index, count - 1)
        self.assertIsInstance(last[0].to_dict()["height"], str)
        self.assertEqual(list(region.iter_tasks(plan, 1000, start=count, limit=1)), [])
        self.assertEqual(description["coverage_status"], "planned; no search is established by this descriptor")

    def test_invalid_and_empty_scopes(self):
        for args in ((0, 2), (3, 2), (1.0, 2)):
            with self.assertRaises((ValueError, TypeError)):
                region.make_region(*args)
        with self.assertRaises(ValueError):
            region.make_region(2, 2, height_min=30, height_max=20)
        excluded = region.make_region(11, 11)
        self.assertEqual(region.task_count(excluded), 0)
        self.assertEqual(region.describe_region(excluded)["admissible_n_count"], "0")
        empty = region.make_region(2, 2, height_min=1000)
        self.assertFalse(empty.complete_height_scope)
        self.assertEqual(region.task_count(empty), 0)


if __name__ == "__main__":
    unittest.main()
