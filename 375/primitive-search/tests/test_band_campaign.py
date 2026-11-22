"""Planner tests for budget, disjoint coverage, and actual height geometry."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from band_campaign import lower_ratio, make_bands, optimize, planned_task_count, optimize_with_task_limit
from benchmark375 import fit_rows
from gap_common import expected_solutions, PRIMITIVE_RHO


class BandCampaignTests(unittest.TestCase):
    def test_height_geometry_against_integer_triple(self):
        # Independently known 2019 solution of k=3, with negative smallest
        # coordinate.  Its exact height relation includes the -3 term.
        a, b, t = 569936821221962380720, 569936821113563493509, 472715493453327032
        d = a-b
        self.assertEqual(t**3, a**3-b**3-3)
        self.assertAlmostEqual(lower_ratio(d, a) / (t/d), 1, places=13)

    def test_disjoint_bands_and_additive_yield(self):
        bands = make_bands(10**6, 10**10, 20, 10**16, 260, .025)
        self.assertEqual(int(bands[0]["d_start"]), 10**6)
        self.assertEqual(int(bands[-1]["d_stop"]), 10**10)
        for left, right in zip(bands, bands[1:]):
            self.assertEqual(left["d_stop"], right["d_start"])
        self.assertEqual(sum(int(b["d_stop"]) - int(b["d_start"]) for b in bands), 10**10-10**6)
        for b in bands:
            self.assertGreater(b["heuristic_expected_solutions"], 0)
            expected = expected_solutions(PRIMITIVE_RHO[375], int(b["d_start"]), int(b["d_stop"]), b["ratio_max"], 10**16)
            self.assertEqual(expected, b["heuristic_expected_solutions"])

    def test_actual_band_cost_respects_productive_budget(self):
        plan = optimize(1.0, 10**15, 260, .025, d_start=10**6, band_factor=1.5)
        self.assertLessEqual(plan["estimated_core_hours"], 1.0 + 1e-12)
        self.assertGreater(plan["estimated_core_hours"], .999)
        self.assertGreater(plan["heuristic_expected_solutions"], 0)

    def test_regression_recovers_known_cost_model(self):
        rows = []
        for i, x in enumerate((100, 200, 500, 1000, 2000, 5000)):
            rows.append({"d_start": str(10000+i), "ratio_max": x+10,
                         "completed_d": 1000, "search_seconds": 1,
                         "mean_scan_ratio": x, "ns_per_d": 200+.03*x})
        fit = fit_rows(rows)
        self.assertIsNotNone(fit)
        self.assertAlmostEqual(fit["base_ns"], 200)
        self.assertAlmostEqual(fit["ratio_ns"], .03)
        self.assertAlmostEqual(fit["r_squared"], 1)

    def test_invalid_cost_model_is_rejected(self):
        with self.assertRaises(ValueError):
            make_bands(10, 100, 10, 10**15, -1, .025)

    def test_task_rounding_never_overfills_a_task(self):
        # 10 integer d values at one hour each need four <=3-hour tasks,
        # even though round(10/3) would incorrectly request only three.
        band = {"d_start": "1", "d_stop": "11", "model_ns_per_d": 3.6e12}
        self.assertEqual(planned_task_count([band], 3.0), 4)

    def test_task_cap_reduces_productive_budget(self):
        plan = optimize_with_task_limit(1.0, 10**15, 260, .025, 10**8,
                                        2.0, .05, 20)
        self.assertLessEqual(plan["planned_task_count"], 20)
        self.assertLessEqual(plan["estimated_core_hours"], 1.0)


if __name__ == "__main__":
    unittest.main()
