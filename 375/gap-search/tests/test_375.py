"""Tests specific to k with cube factors and to primitive mode (k = 375 = 3*5^3). Run after `make`."""
from __future__ import annotations

import json
from math import gcd
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
WORKER = ROOT / "bin" / "gap_worker"
D375 = ROOT.parent / "Scripts for large-scale computations"

from gap_common import (coverage_fraction, cube_primes, expected_solutions, is_prime, primitive_d_ok,  # noqa: E402
                        verify_hit, z_frontier)
import to_points375  # noqa: E402

# k = 3 m^3 (or with several cube primes), all cube primes == 2 (mod 3), k == +-3 (mod 9).
CUBE_KS = (24, 375, 1875, 3000, 7125)


def worker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run([str(WORKER), *args], capture_output=True, text=True, timeout=1200)
    if check and r.returncode:
        raise AssertionError(r.stderr)
    return r


def hits(out: str) -> list[dict]:
    return [json.loads(line) for line in out.splitlines() if '"hit"' in line]


def chunk_counters(out: str) -> dict:
    tot: dict = {}
    for line in out.splitlines():
        if '"chunk"' in line:
            for key, v in json.loads(line)["counters"].items():
                tot[key] = tot.get(key, 0) + v
    return tot


def eps3(k: int) -> int:
    return 1 if k % 9 == 3 else 2


def solutions(k: int, B: int) -> set[tuple[int, int, int]]:
    """Every solution of x^3 + y^3 + z^3 = k with max |coordinate| <= B (sorted triples)."""
    import numpy as np
    v = np.arange(-B, B + 1, dtype=np.int64)
    cubes = v ** 3
    out = set()
    for x in range(-B, B + 1):
        r = k - x ** 3 - cubes
        for i in np.nonzero(np.isin(r, cubes))[0]:
            y, zc = int(v[i]), int(r[i])
            z = round(abs(zc) ** (1 / 3)) * (1 if zc >= 0 else -1)
            for zz in (z - 1, z, z + 1):
                if zz ** 3 == zc:
                    out.add(tuple(sorted((x, y, zz))))
    return out


def in_region(sol, dmax: int, ratio: int):
    """(sorted pair, Z) labellings of a solution that the worker's region contains."""
    for i in range(3):
        Z = sol[i]
        x, y = sol[(i + 1) % 3], sol[(i + 2) % 3]
        d, z = abs(x + y), abs(Z)
        if not 1 <= d < dmax or d % 3 == 0 or not 3847 * d // 1000 <= z <= ratio * d:
            continue
        if Z == 0 or (x + y) != (-d if Z > 0 else d):
            continue
        yield (tuple(sorted((x, y))), Z)


def factor(n: int) -> dict[int, int]:
    out, p = {}, 2
    while p * p <= n:
        while n % p == 0:
            out[p] = out.get(p, 0) + 1
            n //= p
        p += 1 if p == 2 else 2
    if n > 1:
        out[n] = out.get(n, 0) + 1
    return out


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Roots(unittest.TestCase):
    def test_roots_brute_force_cube_factor_k(self):
        for k in CUBE_KS + (-375,):
            out = worker("--k", str(k), "--d-start", "1", "--d-stop", "2500", "--dump-roots").stdout
            seen = 0
            for line in out.splitlines():
                parts = list(map(int, line.split()))
                d, K, roots = parts[0], parts[1], parts[2:]
                self.assertEqual(K, k if d % 3 == eps3(k) else -k)
                self.assertEqual(roots, [z for z in range(d) if (z ** 3 - K) % d == 0], f"k={k} d={d}")
                seen += 1
            self.assertEqual(seen, sum(1 for d in range(1, 2500) if d % 3))

    def test_roots_high_powers_of_5_at_production_size(self):
        # d divisible by 5^e for e up to 17 (the old brute force refused e >= 11). Each root must cube
        # to K mod d, and the count must be multiplicative: at p = 5 (v = 3) there are
        # 5^(e - ceil(e/3)) roots for e <= 3 and 25 for e > 3.
        rng = random.Random(375)
        for e in (3, 4, 7, 11, 14, 17):
            q = 5 ** e
            start = (10 ** 13 // q + rng.randrange(1, 50)) * q - 300
            out = worker("--d-start", str(start), "--d-stop", str(start + 600), "--dump-roots").stdout
            n_checked = 0
            for line in out.splitlines():
                parts = list(map(int, line.split()))
                d, K, roots = parts[0], parts[1], parts[2:]
                self.assertTrue(all((r ** 3 - K) % d == 0 for r in roots))
                self.assertEqual(len(set(roots)), len(roots))
                expected = 1
                for p, ee in factor(d).items():
                    if p == 5:
                        expected *= 5 ** (ee - -(-ee // 3)) if ee <= 3 else 25
                    elif p % 3 == 2:
                        expected *= 1
                    else:
                        expected *= 3 if pow(K % p, (p - 1) // 3, p) == 1 else 0
                self.assertEqual(len(roots), expected, f"d={d}")
                n_checked += 1
            self.assertEqual(n_checked, sum(1 for d in range(start, start + 600) if d % 3))


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Primitive(unittest.TestCase):
    B, DMAX, RATIO = 1500, 700, 3000

    def test_primitive_d_rule(self):
        # The necessary condition used by --primitive, checked on every solution found by brute force.
        n_prim = 0
        for k in CUBE_KS:
            for sol in solutions(k, 600):
                if gcd(gcd(*sol[:2]), sol[2]) != 1:
                    continue
                for i in range(3):
                    x, y = sol[(i + 1) % 3], sol[(i + 2) % 3]
                    if x + y:
                        self.assertTrue(primitive_d_ok(k, abs(x + y)), (k, sol))
                        n_prim += 1
        self.assertGreater(n_prim, 5)

    def test_agrees_with_brute_force(self):
        """Without --primitive: exactly the solutions in the region, with correct primitive flags.
        With --primitive: every primitive solution in the region, nothing outside it."""
        n_prim_total = 0
        for k in CUBE_KS + (48, 750, 6000):        # 48 = 6*2^3, 750 = 6*5^3, 6000 = 6*10^3
            sols = solutions(k, self.B)
            exp_all, exp_prim = {}, set()
            for s in sols:
                prim = gcd(gcd(s[0], s[1]), s[2]) == 1
                for key in in_region(s, self.DMAX, self.RATIO):
                    exp_all[key] = prim
                    if prim:
                        exp_prim.add(key)
            args = ["--k", str(k), "--d-start", "1", "--d-stop", str(self.DMAX), "--ratio-max", str(self.RATIO)]
            got_all = {}
            for h in hits(worker(*args).stdout):
                verify_hit(h, k)
                x, y, Z = int(h["x"]), int(h["y"]), int(h["z"])
                if max(abs(x), abs(y), abs(Z)) <= self.B:
                    got_all[(tuple(sorted((x, y))), Z)] = h["primitive"]
            self.assertEqual(got_all, exp_all, f"k={k}")
            r = worker(*args, "--primitive")
            got_prim = set()
            for h in hits(r.stdout):
                verify_hit(h, k)
                key = (tuple(sorted((int(h["x"]), int(h["y"])))), int(h["z"]))
                if h["primitive"] and max(abs(int(h["x"])), abs(int(h["y"])), abs(int(h["z"]))) <= self.B:
                    got_prim.add(key)
            self.assertEqual(got_prim, exp_prim, f"k={k}")
            self.assertGreater(chunk_counters(r.stdout)["d_skipped_prim"], 0)
            n_prim_total += len(exp_prim)
        self.assertGreaterEqual(n_prim_total, 4)   # 48, 3000, 6000, 7125 each have one in the region

    def test_filters_never_change_the_answer(self):
        for k in (7125, 3000):
            args = ["--k", str(k), "--d-start", "1", "--d-stop", "400", "--ratio-max", "2000", "--primitive"]
            a = {(h["x"], h["y"], h["z"]) for h in hits(worker(*args).stdout)}
            b = {(h["x"], h["y"], h["z"]) for h in hits(worker(*args, "--no-filter").stdout)}
            self.assertEqual(a, b)
            self.assertTrue(a, k)

    def test_scaled_k3_record_is_skipped_only_in_primitive_mode(self):
        # 5 * (569936821221962380720, -569936821113563493509, -472715493453327032): d = 5 * 108398887211.
        d = 5 * 108398887211
        args = ["--d-start", str(d - 30), "--d-stop", str(d + 30), "--ratio-max", "5000000"]
        found = hits(worker(*args).stdout)
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]["primitive"])
        self.assertEqual(int(found[0]["x"]) % 5, 0)
        r = worker(*args, "--primitive")
        self.assertEqual(hits(r.stdout), [])
        self.assertGreater(chunk_counters(r.stdout)["d_skipped_prim"], 0)

    def test_cube_free_k_unaffected(self):
        # No cube primes: --primitive changes nothing, records are still found.
        k, sol = 42, (-80538738812075974, 80435758145817515, 12602123297335631)
        d = abs(sol[0] + sol[1])
        args = ["--k", "42", "--d-start", str(d - 20), "--d-stop", str(d + 20), "--ratio-max", "2"]
        args[-1] = str(-(-abs(sol[2]) // d) + 1)
        a, b = worker(*args).stdout, worker(*args, "--primitive").stdout
        self.assertEqual(chunk_counters(a), chunk_counters(b))
        self.assertEqual(len(hits(b)), 1)
        self.assertTrue(hits(b)[0]["primitive"])

    def test_counters_do_not_depend_on_how_a_range_is_split(self):
        # The audit re-runs single chunks with their own d_stop (hence a different sieve limit); every
        # counter, including the primitive skip, must be identical. (Regression: an early version read
        # the skip from sieve factor lists and split it differently from d_no_roots.)
        lo, mid, hi = 5908625924, 5908625924 + 3 * 2 ** 16 + 777, 5908625924 + 2 ** 20
        args = ["--ratio-max", "4096", "--primitive", "--chunk", str(10 ** 12)]
        a = chunk_counters(worker("--d-start", str(lo), "--d-stop", str(hi), *args).stdout)
        b1 = chunk_counters(worker("--d-start", str(lo), "--d-stop", str(mid), *args).stdout)
        b2 = chunk_counters(worker("--d-start", str(mid), "--d-stop", str(hi), *args).stdout)
        self.assertEqual(a, {key: b1[key] + b2[key] for key in a})
        big = worker("--d-start", str(lo), "--d-stop", str(10 ** 11), "--ratio-max", "4096", "--primitive",
                     "--chunk", str(hi - lo), "--deadline-seconds", "1").stdout
        first = [json.loads(l) for l in big.splitlines() if '"chunk"' in l][0]
        self.assertEqual((int(first["d_start"]), int(first["d_stop"])), (lo, hi))
        self.assertEqual(first["counters"], a)
        self.assertGreater(a["d_skipped_prim"], 0)

    def test_rejects_cube_prime_1_mod_3(self):
        r = worker("--k", str(3 * 7 ** 3), "--d-start", "1", "--d-stop", "100", "--primitive", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(cube_primes(375), [5])
        self.assertEqual(cube_primes(3000), [2, 5])


class Converter(unittest.TestCase):
    def test_flags_and_points(self):
        p = to_points375.points(5, 5, 5, 375)
        self.assertEqual(len(p), 1)
        self.assertFalse(p[0]["desired"])
        pts = to_points375.points(-67, -46, 74, 7125)
        self.assertEqual(sorted(q["chart"] for q in pts), ["half", "half", "integer"])
        self.assertEqual(sum(q["desired"] for q in pts), 3)
        with self.assertRaises(ValueError):
            to_points375.points(1, 2, 3, 375)

    @unittest.skipUnless((D375 / "common375.py").exists(), "375 d-first folder not present")
    def test_agrees_with_dfirst_folder(self):
        sys.path.insert(0, str(D375))
        import common375
        for t, k in (((-67, -46, 74), 7125), ((5, 5, 5), 375), ((20, 20, -25), 375), ((-29, -29, 37), 1875)):
            primitive_cubes = gcd(gcd(t[0], t[1]), t[2]) == 1
            mine = {(q["chart"], q["d"], q["n"], q["x"], q["y"], q["desired"]) for q in to_points375.points(*t, k)}
            theirs = {(q["chart"], q["d"], q["n"], q["x"], q["s"],
                       common375.primitivity(q["chart"], q["n"], q["x"], q["s"], t)["desired"] and primitive_cubes)
                      for q in common375.d_values_from_cubes(*t, k)}
            self.assertEqual(mine, theirs, (t, k))

    def test_every_primitive_representation_gives_desired_points(self):
        # On the CE375 equation (generalised to k), desired points come exactly from primitive representations.
        for k in (7125, 1875, 3000):
            for sol in solutions(k, 300):
                if sum(sol) % 6 != 3 % 6 or (sum(sol) - 3) % 6:
                    continue
                pts = to_points375.points(*sol, k)
                prim = gcd(gcd(sol[0], sol[1]), sol[2]) == 1
                if not prim:
                    self.assertFalse(any(q["desired"] for q in pts))
                for q in pts:
                    self.assertEqual(q["primitive_cubes"], prim)


class YieldModel(unittest.TestCase):
    def test_no_frontier_matches_closed_form(self):
        a = expected_solutions(1.0, 10 ** 9, 10 ** 12, 4096, 0)
        b = expected_solutions(1.0, 10 ** 9, 10 ** 12, 4096, 1e-9)   # numerical path, frontier ~ 0
        self.assertAlmostEqual(a, coverage_fraction(4096) * 6.907755278982137, places=6)
        self.assertAlmostEqual(a, b, places=3)

    def test_frontier_only_removes(self):
        for N in (1e12, 1e14, 1e16):
            self.assertLessEqual(expected_solutions(1.0, 10 ** 9, 10 ** 13, 4096, N),
                                 expected_solutions(1.0, 10 ** 9, 10 ** 13, 4096, 0))
        # A solution of max coordinate M has z <= z_frontier(d, M) exactly at the boundary.
        for d in (10, 10 ** 6, 10 ** 10):
            M = 10 ** 15
            z = z_frontier(d, M)
            delta = (4 * z ** 3 / d - d ** 2) / 3
            self.assertAlmostEqual((d + delta ** 0.5) / 2 / M, 1.0, places=6)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Pipeline(unittest.TestCase):
    def test_plan_run_collect_audit_convert(self):
        # k = 7125 has a primitive solution at d = 7 (|z| = 46), so a tiny campaign must report it.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            run = lambda *a: subprocess.run([sys.executable, *map(str, a)], check=True, capture_output=True, text=True)
            run(ROOT / "gap_campaign.py", "--campaign-id", "t7125", "--k", "7125", "--d-start", "1", "--d-stop", "2000",
                "--ratio-max", "500", "--task-d-count", "1000", "--frontier", "0", "--output-dir", tmp / "camp")
            for tj in sorted((tmp / "camp" / "tasks").glob("*.json")):
                run(ROOT / "run_gap_task.py", "--task", tj, "--output-dir", tmp / "res" / tj.stem)
            out = run(ROOT / "collect_gap.py", "--page", tmp / "camp" / "page.json", "--results", tmp / "res",
                      "--output-dir", tmp / "col", "--require-complete").stdout
            summary = json.loads((tmp / "col" / "summary.json").read_text())
            self.assertEqual(summary["gaps"], [])
            self.assertGreaterEqual(summary["primitive_hits"], 1)
            self.assertIn("PRIMITIVE", out)
            self.assertTrue(summary["primitive"])
            run(ROOT / "audit_gap.py", "--page", tmp / "camp" / "page.json", "--results", tmp / "res", "--fraction", "1")
            conv = run(ROOT / "to_points375.py", tmp / "col" / "hits.jsonl").stdout
            self.assertIn("DESIRED", conv)
            self.assertIn("-46^3", conv.replace("+ -", "+ -"))


if __name__ == "__main__":
    unittest.main()
