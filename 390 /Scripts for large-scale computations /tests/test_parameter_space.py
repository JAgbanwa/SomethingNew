"""Independent counting and resumability checks for the general a/q enclosure."""
import json
import math
from pathlib import Path
import random
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parameter_space import GeneralAQ, _floor_sum


PRODUCTION = dict(n_min=10**43, n_max=10**45, x_min=10**54, x_max=10**55)


def brute(bounds, q_min, q_max):
    """Deliberately scan integers and test cross-products, without prefix formulas."""
    k_max = ((36 * bounds["n_max"]**3 + 65)
             // (bounds["x_min"] * (bounds["x_min"] - 6 * bounds["n_max"])))
    if k_max == 0:
        return []
    low = 12 * bounds["n_min"] + 1
    high = 12 * bounds["n_max"] + k_max
    return [(a, q)
            for q in range(q_min, q_max + 1) if math.gcd(q, 6) == 1
            for a in range(1, high + 1) if math.gcd(a, 6) == 1
            and a * bounds["x_max"] >= low * q
            and a * bounds["x_min"] <= high * q]


class ParameterSpaceTests(unittest.TestCase):
    def test_floor_sum_matches_direct_signed_arithmetic(self):
        rng = random.Random(390)
        for _ in range(1500):
            n, modulus = rng.randrange(70), rng.randrange(1, 80)
            slope, intercept = rng.randrange(-120, 120), rng.randrange(-160, 160)
            self.assertEqual(_floor_sum(n, modulus, slope, intercept),
                             sum((slope * i + intercept) // modulus for i in range(n)))

    def test_differential_full_and_partial_windows(self):
        specifications = [
            dict(n_min=2, n_max=8, x_min=110, x_max=220),
            dict(n_min=7, n_max=12, x_min=160, x_max=450),
            dict(n_min=10, n_max=25, x_min=400, x_max=1100),
            dict(n_min=19, n_max=20, x_min=270, x_max=280),
        ]
        for bounds in specifications:
            for q_min, q_max in ((1, bounds["x_max"]),
                                 (bounds["x_min"] - 3, bounds["x_min"] + 3),
                                 (2, 31), (bounds["x_max"] - 7, bounds["x_max"])):
                with self.subTest(bounds=bounds, window=(q_min, q_max)):
                    space = GeneralAQ(bounds, q_min, q_max)
                    expected = brute(bounds, q_min, q_max)
                    self.assertEqual(space.count, len(expected))
                    self.assertEqual(list(space.iter_candidates()), expected)
                    sample_indices = sorted(set([0, len(expected) // 2, len(expected) - 1]))
                    for i in sample_indices:
                        if 0 <= i < len(expected):
                            self.assertEqual(space.candidate(i), expected[i])
                            self.assertEqual(space.index(*expected[i]), i)

    def test_every_small_index_roundtrips_and_reduced_filter_is_separate(self):
        bounds = dict(n_min=2, n_max=8, x_min=110, x_max=220)
        space = GeneralAQ(bounds, 1, 220)
        expected = brute(bounds, 1, 220)
        self.assertTrue(any(math.gcd(a, q) > 1 for a, q in expected))
        for i, pair in enumerate(expected):
            self.assertEqual(space.candidate(i), pair)
            self.assertEqual(space.index(*pair), i)

    def test_resumed_slices_partition_without_gaps_or_duplicates(self):
        bounds = dict(n_min=7, n_max=12, x_min=160, x_max=450)
        space = GeneralAQ(bounds, 6, 449)
        expected = brute(bounds, 6, 449)
        cuts = [0, 1, 23, space.count // 2, space.count - 1, space.count]
        cuts = sorted(set(i for i in cuts if 0 <= i <= space.count))
        actual = []
        for start, stop in zip(cuts, cuts[1:]):
            actual.extend(space.iter_candidates(start, stop))
        self.assertEqual(actual, expected)
        self.assertEqual(len(set(actual)), len(actual))

    def test_stream_unranks_only_once(self):
        space = GeneralAQ(PRODUCTION, 1, 10**55)
        with mock.patch.object(space, "candidate", wraps=space.candidate) as unrank:
            pairs = list(space.iter_candidates(1000, 6000))
        self.assertEqual(unrank.call_count, 1)
        self.assertEqual(len(pairs), 5000)
        self.assertEqual(space.index(*pairs[-1]), 5999)

    def test_production_window_derives_multiple_numerators_without_a_list(self):
        space = GeneralAQ(PRODUCTION, 1_000_000_000, 1_000_000_010)
        expected = [(a, q) for q in (1_000_000_001, 1_000_000_003,
                                     1_000_000_007, 1_000_000_009)
                    for a in (1, 5, 7, 11)]
        self.assertEqual(list(space.iter_candidates()), expected)
        self.assertEqual(space.count, 16)
        self.assertFalse(space.bounds_info()["full_denominator_window"])

    def test_large_integer_random_roundtrips_and_stream_edges(self):
        space = GeneralAQ({key: str(value) for key, value in PRODUCTION.items()},
                          1, 10**55)
        self.assertGreater(space.count, 10**99)
        self.assertGreaterEqual(space.k_max, 1)
        rng = random.Random(2026)
        indices = [0, 1, space.count - 1, space.count // 2]
        indices += [rng.randrange(space.count) for _ in range(18)]
        for i in indices:
            a, q = space.candidate(i)
            self.assertEqual(space.index(a, q), i)
            self.assertEqual(math.gcd(a, 6), 1)
            self.assertEqual(math.gcd(q, 6), 1)
            self.assertLess(a, q)
            self.assertLessEqual(q, PRODUCTION["x_max"])
            stop = min(i + 5, space.count)
            actual = list(space.iter_candidates(i, stop))
            self.assertEqual(actual, [space.candidate(j) for j in range(i, stop)])
        info = space.bounds_info()
        self.assertTrue(info["full_denominator_window"])
        self.assertEqual(info["total_candidate_indices"], str(space.count))
        json.dumps(info)

    def test_even_window_endpoints_and_adjacent_windows(self):
        bounds = dict(n_min=2, n_max=8, x_min=110, x_max=220)
        whole = GeneralAQ(bounds, 2, 220)
        first, last = GeneralAQ(bounds, 2, 110), GeneralAQ(bounds, 111, 220)
        self.assertEqual(whole.count, first.count + last.count)
        self.assertEqual(list(whole.iter_candidates()),
                         list(first.iter_candidates()) + list(last.iter_candidates()))

    def test_empty_windows_and_zero_k_enclosure(self):
        for bounds, q_min, q_max in ((PRODUCTION, 1, 10),
                                     (PRODUCTION, 6, 6),
                                     (dict(n_min=2, n_max=2, x_min=100, x_max=200), 1, 200)):
            with self.subTest(bounds=bounds, window=(q_min, q_max)):
                space = GeneralAQ(bounds, q_min, q_max)
                self.assertEqual(space.count, 0)
                self.assertEqual(list(space.iter_candidates()), [])
                with self.assertRaises(ValueError):
                    space.candidate(0)

    def test_invalid_bounds_and_unsupported_proof_domains(self):
        invalid = [
            dict(PRODUCTION, n_min=0), dict(PRODUCTION, n_min=1),
            dict(PRODUCTION, n_min=10**46),
            dict(n_min=2, n_max=20, x_min=100, x_max=300),
            dict(n_min=2, n_max=20, x_min=130, x_max=300),
            dict(PRODUCTION, require_integer_sqrt=False),
            dict(PRODUCTION, n_min=True), dict(PRODUCTION, n_min="2.5"),
        ]
        for bounds in invalid:
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                GeneralAQ(bounds, 1, bounds["x_max"])
        for q_min, q_max in ((0, 1), (10, 9), (1, 10**55 + 1), (True, 10)):
            with self.subTest(window=(q_min, q_max)), self.assertRaises(ValueError):
                GeneralAQ(PRODUCTION, q_min, q_max)

    def test_invalid_indices_and_pairs(self):
        space = GeneralAQ(PRODUCTION, 1, 10**55)
        a, q = space.candidate(0)
        for index in (-1, space.count, True, "-1"):
            with self.subTest(index=index), self.assertRaises(ValueError):
                space.candidate(index)
        for pair in ((a + 1, q), (a, q + 1), (0, q), (a, 10**55 + 1),
                     (a + 6 * 10**50, q), (True, q)):
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                space.index(*pair)
        for start, stop in ((-1, 0), (1, 0), (0, space.count + 1)):
            with self.subTest(slice=(start, stop)), self.assertRaises(ValueError):
                list(space.iter_candidates(start, stop))


if __name__ == "__main__":
    unittest.main()
