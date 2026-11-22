"""Tests for tools/rho.py: the point-count formula and the calibration of rho."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import rho  # noqa: E402


class PointCounts(unittest.TestCase):
    def test_jacobi_formula_against_brute_force(self):
        # N_p(k) = p^2 + 6p - L (k a cube mod p) or p^2 - 3p - L, p = 1 mod 3, p !| 3k.
        for p in (7, 13, 19, 31, 37, 43, 61, 67):
            h = Counter(pow(x, 3, p) for x in range(p))
            for k in range(1, p):
                n = sum(h[u] * h[v] * h[(k - u - v) % p] for u in h for v in h)
                cube = pow(k, (p - 1) // 3, p) == 1
                self.assertEqual(n, p * p + (6 * p if cube else -3 * p) - rho.L_of(p), (p, k))

    def test_local_densities_at_bad_primes(self):
        # Exact values, stable in e: sigma_3 = 1/3 for k = +-3 mod 9 with v_3 = 1; sigma_5 = 24/25 for
        # primitive solutions of 375 (the same as for 390, where 5 || k).
        self.assertAlmostEqual(rho.local_density(375, 3, 5)[-1], 1 / 3, places=12)
        self.assertAlmostEqual(rho.local_density(375, 5, 4)[-1], 0.96, places=12)
        self.assertAlmostEqual(rho.local_density(390, 5, 4)[-1], 0.96, places=12)
        # Non-primitive solutions would change the 5-adic factor for 375.
        self.assertNotAlmostEqual(rho.local_density(375, 5, 4, primitive=False)[-1], 0.96, places=6)


class Calibration(unittest.TestCase):
    def test_constant_is_the_same_for_all_cube_free_k_and_rho_375(self):
        P = 10 ** 6
        ps = rho.primes_1mod3(P)
        Lc = {int(p): rho.L_of(int(p)) for p in ps}
        def local(k):
            from math import exp, log
            bad = sum(log(rho.local_density(k, p)[-1]) for p in rho.bad_primes(k))
            return exp(rho.good_product(k, ps, Lc, P, P)[P] + bad)
        Cs = [r / local(k) for k, r in rho.BS_RHO.items()]
        self.assertLess((max(Cs) - min(Cs)) / min(Cs), 0.005)
        r375 = sum(Cs) / len(Cs) * local(375)
        self.assertTrue(0.0580 < r375 < 0.0592, r375)


if __name__ == "__main__":
    unittest.main()
