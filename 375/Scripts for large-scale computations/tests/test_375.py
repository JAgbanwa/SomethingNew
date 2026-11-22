"""CE375 test suite: run with  python3 -m unittest discover -s tests -v  (after make)."""
from __future__ import annotations

from fractions import Fraction
import json
from math import gcd, isqrt
import os
from pathlib import Path
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common375 import (Admissibility, d_values_from_cubes, n_mod3, pairs_in, primitivity,  # noqa: E402
                       shell, verify_hit)

WORKER = ROOT / "bin" / "thue375_worker"
TEST_KS = (3, 15, 21, 57)   # odd, +-3 mod 9, with small known representations
HMAX = 70                   # heights 1..HMAX-1 in the known-answer runs
CUBE_BOUND = 400


def icbrt(v: int) -> int:
    r = round(abs(v) ** (1 / 3)) if v else 0
    for c in (r - 1, r, r + 1):
        if c ** 3 == abs(v):
            return c if v >= 0 else -c
    raise ValueError


def representations(k: int, bound: int) -> set[tuple[int, int, int]]:
    reps = set()
    for a in range(-bound, bound + 1):
        for b in range(a, bound + 1):
            r = k - a ** 3 - b ** 3
            c = round(abs(r) ** (1 / 3)) * (1 if r >= 0 else -1)
            for cc in (c - 1, c, c + 1):
                if cc ** 3 == r and abs(cc) <= bound:
                    reps.add(tuple(sorted((a, b, cc))))
    return reps


def run_worker(k: int, h_stop: int, digits: int = 40, mode: str = "both") -> list[dict]:
    out = subprocess.run([str(WORKER), "--k", str(k), "--mode", mode, "--h-start", "1", "--h-stop", str(h_stop),
                          "--g-max-digits", str(digits)], check=True, capture_output=True, text=True).stdout
    return [json.loads(line) for line in out.splitlines()]


def as_point(rec: dict) -> tuple:
    return (Fraction(int(rec["d_num"]), int(rec["d_den"])), rec["chart"],
            Fraction(int(rec["x_num"]), int(rec["x_den"])), Fraction(int(rec["s_num"]), int(rec["s_den"])))


def height(d: Fraction) -> int:
    return max(abs(d.numerator), d.denominator)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class KnownAnswers(unittest.TestCase):
    """For k with known representations the worker must recover every predicted d."""

    @classmethod
    def setUpClass(cls):
        cls.records = {k: run_worker(k, HMAX) for k in TEST_KS}
        cls.reps = {k: representations(k, CUBE_BOUND) for k in TEST_KS}

    def test_every_hit_verifies(self):
        for k, recs in self.records.items():
            for rec in recs:
                if rec["type"] == "hit":
                    verify_hit(rec, k)

    def test_all_predicted_points_found_and_nothing_spurious(self):
        total_int = total_half = 0
        sources = set()
        for k in TEST_KS:
            expected = set()
            for rep in self.reps[k]:
                for v in d_values_from_cubes(*rep, k):
                    if height(v["d"]) < HMAX:
                        expected.add((v["d"], v["chart"], v["x"], v["s"]))
            found = {as_point(r) for r in self.records[k] if r["type"] == "hit"}
            sources |= {r["source"] for r in self.records[k] if r["type"] == "hit"}
            self.assertTrue(expected, f"k={k}: test needs predicted points")
            self.assertLessEqual(expected, found, f"k={k}: missed {expected - found}")
            # Conversely, every hit whose cube components lie inside the brute-force box
            # must come from a brute-force representation: nothing spurious.
            small = {as_point(r) for r in self.records[k] if r["type"] == "hit"
                     and max(abs(int(r[c])) for c in ("cube_a", "cube_b", "cube_c")) <= CUBE_BOUND}
            self.assertLessEqual(small, expected)
            total_int += sum(1 for p in found if p[1] == "integer")
            total_half += sum(1 for p in found if p[1] == "half")
        self.assertGreater(total_int, 0)
        self.assertGreater(total_half, 0)
        self.assertIn("convergent", sources, "known answers must also exercise the CF path")

    def test_k15_exact(self):
        found = {as_point(r) for r in self.records[15] if r["type"] == "hit"}
        self.assertIn((Fraction(1, 4), "integer", Fraction(-2), Fraction(0)), found)
        self.assertIn((Fraction(4), "half", Fraction(-1, 2), Fraction(3, 2)), found)

    def test_x_first_brute_force_agrees(self):
        """Independent of the cube identity: enumerate (n, x) on the ORIGINAL equation."""
        for k in (15, 57):
            found = {as_point(r) for r in self.records[k] if r["type"] == "hit"}
            for n in range(-25, 26):
                N = 36 * n ** 3 + 54 * n ** 2 + 27 * n + (27 - k) // 6
                if N == 0:
                    continue
                m = 6 * n + 3
                for X in range(1, abs(N) + 1):
                    if N % X:
                        continue
                    for sx in (X, -X):
                        for x in ([Fraction(sx)] + ([Fraction(sx, 2)] if X % 2 else [])):
                            v = (x + m) ** 2 + N / x
                            if v < 0:
                                continue
                            num, den = v.numerator, v.denominator
                            rn, rd = isqrt(num), isqrt(den)
                            if rn * rn != num or rd * rd != den:
                                continue
                            s = Fraction(rn, rd)
                            if x.denominator == 1 and s.denominator != 1:
                                continue
                            if x.denominator == 2 and s.denominator != 2:
                                continue
                            if s + x + m == 0:
                                continue
                            d = -(s + x + m) / (2 * x)
                            self.assertEqual(Fraction(N), -2 * d * x * x * (-(x + m) + s))
                            chart = "integer" if x.denominator == 1 else "half"
                            if height(d) < HMAX:
                                self.assertIn((d, chart, x, s), found, f"k={k} n={n} x={x}")


def divisors(m: int) -> list[int]:
    m, out, f = abs(m), [1], 2
    while f * f <= m:
        e = 0
        while m % f == 0:
            m //= f
            e += 1
        if e:
            out = [d * f ** i for d in out for i in range(e + 1)]
        f += 1
    if m > 1:
        out = out + [d * m for d in out]
    return out


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Production375(unittest.TestCase):
    """K = 375 = 3 * 5^3 itself: invariants, non-primitive points, primitivity flags."""

    K = 375

    @classmethod
    def setUpClass(cls):
        cls.records = run_worker(cls.K, HMAX)
        cls.hits = [r for r in cls.records if r["type"] == "hit"]

    def test_invariant_n_mod_3(self):
        self.assertEqual(n_mod3(375), 2)
        self.assertEqual(n_mod3(627), 1)      # matches the CE627 derivation
        for r in self.hits:
            self.assertEqual(int(r["n"]) % 3, 2)

    def test_every_hit_verifies_with_independent_primitivity(self):
        self.assertTrue(self.hits)
        for r in self.hits:
            v = verify_hit(r, self.K)        # raises if the worker's flags disagree
            self.assertEqual(r["desired"], v["desired"])

    def test_scaled_k3_representations_found_and_flagged_non_primitive(self):
        """5*(1,1,1) and 5*(4,4,-5) represent 375; all their d must appear, never as desired."""
        expected = set()
        for rep in ((5, 5, 5), (20, 20, -25)):
            for v in d_values_from_cubes(*rep, self.K):
                if height(v["d"]) < HMAX:
                    expected.add((v["d"], v["chart"], v["x"], v["s"]))
        found = {as_point(r): r for r in self.hits}
        self.assertLessEqual(expected, set(found), f"missed {expected - set(found)}")
        for pt in expected:
            self.assertFalse(found[pt]["desired"])
            self.assertFalse(found[pt]["primitive_cubes"])
        # (5,5,5) gives (n, x) = (2, -5): gcd(n, x) = 1 but the cubes share 5.
        pt = (Fraction(1), "integer", Fraction(-5), Fraction(0))
        self.assertTrue(found[pt]["primitive_point"])
        self.assertFalse(found[pt]["desired"])

    def test_nothing_spurious_in_small_box(self):
        reps = representations(self.K, CUBE_BOUND)
        expected = {(v["d"], v["chart"], v["x"], v["s"]) for rep in reps
                    for v in d_values_from_cubes(*rep, self.K)}
        small = {as_point(r) for r in self.hits
                 if max(abs(int(r[c])) for c in ("cube_a", "cube_b", "cube_c")) <= CUBE_BOUND}
        self.assertLessEqual(small, expected)

    def test_x_first_brute_force_on_original_equation(self):
        """Every (n, x) point with |n| <= 60 found by divisors of N(n), with d of small height,
        must be among the worker's hits, with the same primitivity verdict."""
        found = {as_point(r): r for r in self.hits}
        checked = 0
        for n in range(-60, 61):
            N = 36 * n ** 3 + 54 * n ** 2 + 27 * n + (27 - self.K) // 6
            m = 6 * n + 3
            for X in divisors(N):
                for sx in (X, -X):
                    for x in ([Fraction(sx)] + ([Fraction(sx, 2)] if X % 2 else [])):
                        v = (x + m) ** 2 + N / x
                        if v < 0:
                            continue
                        rn, rd = isqrt(v.numerator), isqrt(v.denominator)
                        if rn * rn != v.numerator or rd * rd != v.denominator:
                            continue
                        s = Fraction(rn, rd)
                        if s.denominator != x.denominator:
                            continue
                        d = -(s + x + m) / (2 * x)
                        self.assertEqual(Fraction(N), -2 * d * x * x * (-(x + m) + s))
                        chart = "integer" if x.denominator == 1 else "half"
                        checked += 1
                        if height(d) < HMAX:
                            rec = found.get((d, chart, x, s))
                            self.assertIsNotNone(rec, f"n={n} x={x}")
                            cubes = (int(-x + s), int(-x - s), int(2 * x + m))
                            self.assertEqual(rec["desired"], primitivity(chart, n, x, s, cubes)["desired"])
        self.assertGreater(checked, 0)


def xy_point(rec: dict) -> tuple[int, int, int]:
    return int(rec["n"]), int(rec["X"]), int(rec["Y"])


def xy_brute(k: int, nmax: int) -> set[tuple[int, int, int]]:
    """Every (n, X, |Y|) with |n| <= nmax, X, Y odd, gcd(X, Y) = 1, primitive cubes, on
    y^2 = (x+6n+3)^2 + N/x with x = X/2: X must divide N (X odd, 8N/X = Y^2 - (X+2S)^2)."""
    out = set()
    for n in range(-nmax, nmax + 1):
        N = 36 * n ** 3 + 54 * n ** 2 + 27 * n + (27 - k) // 6
        S = 6 * n + 3
        for X0 in divisors(N):
            if X0 % 2 == 0:
                continue
            for X in (X0, -X0):
                v = (X + 2 * S) ** 2 + 8 * N // X
                Y = isqrt(v) if v >= 0 else -1
                if Y < 0 or Y * Y != v or Y % 2 == 0 or gcd(X, Y) != 1:
                    continue
                x, y = Fraction(X, 2), Fraction(Y, 2)
                cubes = (int(-x + y), int(-x - y), int(2 * x + S))
                if primitivity("half", n, x, y, cubes)["desired"]:
                    out.add((n, X, Y))
    return out


@unittest.skipUnless(WORKER.exists(), "build first: make")
class XYHalf(unittest.TestCase):
    """--mode xy-half: rational x = X/2, y = Y/2 (X, Y odd, gcd(X, Y) = 1), both signs of y."""

    H = 130
    KS = (15, 21, 57, 7125)   # 7125 = 57 * 5^3 exercises the mod-125 filter

    @classmethod
    def setUpClass(cls):
        cls.xy = {k: [r for r in run_worker(k, cls.H, mode="xy-half") if r["type"] == "hit"] for k in cls.KS + (375,)}
        cls.both = {k: [r for r in run_worker(k, cls.H) if r["type"] == "hit"] for k in cls.KS}

    def test_every_xy_hit_verifies(self):
        for k, recs in self.xy.items():
            for r in recs:
                v = verify_hit(r, k)
                self.assertEqual(v["mode"], "xy-half")
                self.assertEqual(r["chart"], "half")

    def test_contains_every_desired_half_point_of_the_full_search(self):
        for k in self.KS:
            full = {(int(r["n"]), 2 * int(r["x_num"]) // int(r["x_den"]), 2 * int(r["s_num"]) // int(r["s_den"]))
                    for r in self.both[k] if r["chart"] == "half" and r["desired"]}
            got = {xy_point(r) for r in self.xy[k] if r["desired"]}
            self.assertTrue(full or k == 21, f"k={k} needs half points")
            self.assertLessEqual(full, got, f"k={k}: missed {full - got}")

    def test_k7125_known_points(self):
        """(-67)^3 + (-46)^3 + 74^3 = 7125: half points x = -7/2, y = 141/2 and x = 113/2, y = 21/2."""
        got = {xy_point(r) for r in self.xy[7125] if r["desired"]}
        n = (-67 - 46 + 74 - 3) // 6
        self.assertIn((n, -7, 141), got)
        self.assertIn((n, 113, 21), got)

    def test_x_first_brute_force(self):
        """Independent of the Thue reduction: points with |n| <= 40 and principal d of small height."""
        for k in (15, 57, 7125):
            got = {xy_point(r) for r in self.xy[k]}
            for n, X, Y in xy_brute(k, 40):
                x, y, S = Fraction(X, 2), Fraction(Y, 2), 6 * n + 3
                d = -(x + S + y) / (2 * x)
                if height(d) < self.H:
                    self.assertIn((n, X, Y), got, f"k={k} n={n} X={X} Y={Y}")

    def test_k375_small_heights_have_no_desired_point(self):
        self.assertFalse([r for r in self.xy[375] if r["desired"]])

    def test_python_mirror_matches_worker_counts(self):
        for k in (375, 7125, 15):
            adm = Admissibility(k, "xy-half")
            recs = run_worker(k, 160, digits=20, mode="xy-half")
            worker = {r["h"]: (r["pairs"], r["admissible"]) for r in recs if r["type"] == "shell"}
            for h in range(1, 160):
                pairs = list(shell(h))
                self.assertEqual(worker[h], (len(pairs), sum(adm(p, q) for p, q in pairs)), f"k={k} h={h}")

    def test_mod125_filter_keeps_principal_and_conjugate_d(self):
        adm = Admissibility(7125, "xy-half")
        for r in self.xy[7125]:
            if r["desired"]:
                self.assertTrue(adm(int(r["thue_p"]), int(r["thue_q"])))

    def test_campaign_lifecycle(self):
        py = sys.executable
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            subprocess.run([py, str(ROOT / "make_campaign.py"), "--campaign-id", "xy", "--k", "7125", "--mode",
                            "xy-half", "--h-stop", str(self.H), "--task-hours", "0.0005", "--us-per-pair", "9",
                            "--g-max-digits", "40", "--output-dir", str(tmp / "camp")], check=True, capture_output=True)
            page = json.loads((tmp / "camp" / "page.json").read_text())
            self.assertEqual(page["mode"], "xy-half")
            for t in page["tasks"]:
                subprocess.run([py, str(ROOT / "run_task.py"), "--task", str(tmp / "camp" / t["file"]),
                                "--output-dir", str(tmp / "res" / t["task_id"])], check=True, capture_output=True)
            subprocess.run([py, str(ROOT / "collect.py"), "--results", str(tmp / "res"), "--page",
                            str(tmp / "camp" / "page.json"), "--output-dir", str(tmp / "col")],
                           check=True, capture_output=True)
            collected = {xy_point(json.loads(line)) for line in (tmp / "col" / "hits.jsonl").read_text().splitlines()}
            self.assertEqual(collected, {xy_point(r) for r in self.xy[7125]})
            self.assertIn("y=+-141/2", (tmp / "col" / "desired_d_values.txt").read_text())


def xy_brute_both(k: int, nmax: int) -> set[tuple[int, int, int]]:
    """Desired (n, X, |Y|) of BOTH charts on y^2 = (x+6n+3)^2 + N/x, |n| <= nmax, X = 2x, Y = 2y:
    integer chart x | N, y integer; half chart x = X/2 with X odd, X | N, Y odd."""
    out = set()
    for n in range(-nmax, nmax + 1):
        N = 36 * n ** 3 + 54 * n ** 2 + 27 * n + (27 - k) // 6
        S = 6 * n + 3
        for D in divisors(N):
            for sx in (D, -D):
                cands = [Fraction(sx)] + ([Fraction(sx, 2)] if D % 2 else [])
                for x in cands:
                    v = (x + S) ** 2 + N / x
                    if v < 0:
                        continue
                    rn, rd = isqrt(v.numerator), isqrt(v.denominator)
                    if rn * rn != v.numerator or rd * rd != v.denominator:
                        continue
                    y = Fraction(rn, rd)
                    if y.denominator != x.denominator:
                        continue
                    chart = "integer" if x.denominator == 1 else "half"
                    cubes = (int(-x + y), int(-x - y), int(2 * x + S))
                    if primitivity(chart, n, x, y, cubes)["desired"]:
                        out.add((n, int(2 * x), int(2 * y)))
    return out


@unittest.skipUnless(WORKER.exists(), "build first: make")
class XYBoth(unittest.TestCase):
    """--mode xy (production): desired points of both charts on the y^2 equation, both signs of y."""

    H = 130
    KS = (15, 57, 1875, 7125)   # 1875 = 3*5^4 and 7125 = 57*5^3 exercise the mod-125 filter

    @classmethod
    def setUpClass(cls):
        cls.xy = {k: [r for r in run_worker(k, cls.H, mode="xy") if r["type"] == "hit"] for k in cls.KS + (375,)}
        cls.both = {k: [r for r in run_worker(k, cls.H) if r["type"] == "hit"] for k in cls.KS}

    def test_every_hit_verifies(self):
        for k, recs in self.xy.items():
            for r in recs:
                self.assertEqual(verify_hit(r, k)["mode"], "xy")

    def test_contains_every_desired_point_of_the_full_search(self):
        charts = set()
        for k in self.KS:
            full = {(int(r["n"]), 2 * int(r["x_num"]) // int(r["x_den"]), 2 * int(r["s_num"]) // int(r["s_den"]))
                    for r in self.both[k] if r["desired"]}
            got = {xy_point(r) for r in self.xy[k] if r["desired"]}
            self.assertLessEqual(full, got, f"k={k}: missed {full - got}")
            charts |= {r["chart"] for r in self.xy[k] if r["desired"]}
        self.assertEqual(charts, {"integer", "half"})

    def test_k1875_integer_point(self):
        """(-29)^3 + (-29)^3 + 37^3 = 1875: x = 29, y = 0, n = -4 (gcd(n, x) = 1), d = -4/29."""
        hits = {xy_point(r): r for r in self.xy[1875]}
        rec = hits[(-4, 58, 0)]
        self.assertTrue(rec["desired"])
        self.assertEqual((rec["chart"], rec["d_num"], rec["d_den"]), ("integer", "-4", "29"))

    def test_x_first_brute_force_both_charts(self):
        checked = 0
        for k in (15, 57, 1875, 7125):
            got = {xy_point(r) for r in self.xy[k]}
            for n, X, Y in xy_brute_both(k, 40):
                x, y, S = Fraction(X, 2), Fraction(Y, 2), 6 * n + 3
                if height(-(x + S + y) / (2 * x)) < self.H:
                    checked += 1
                    self.assertIn((n, X, Y), got, f"k={k} n={n} X={X} Y={Y}")
        self.assertGreater(checked, 3)

    def test_k375_small_heights_have_no_desired_point(self):
        self.assertFalse([r for r in self.xy[375] if r["desired"]])

    def test_python_mirror_matches_worker_counts(self):
        for k in (375, 1875, 15):
            adm = Admissibility(k, "xy")
            recs = run_worker(k, 160, digits=20, mode="xy")
            worker = {r["h"]: (r["pairs"], r["admissible"]) for r in recs if r["type"] == "shell"}
            for h in range(1, 160):
                pairs = list(shell(h))
                self.assertEqual(worker[h], (len(pairs), sum(adm(p, q) for p, q in pairs)), f"k={k} h={h}")

    def test_default_campaign_is_xy(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, str(ROOT / "make_campaign.py"), "--campaign-id", "c", "--h-stop", "50",
                            "--output-dir", tmp], check=True, capture_output=True)
            self.assertEqual(json.loads((Path(tmp) / "page.json").read_text())["mode"], "xy")


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Filters(unittest.TestCase):
    def test_filter_keeps_every_known_d(self):
        for k in TEST_KS:
            adm = Admissibility(k)
            for rep in representations(k, 300):
                for v in d_values_from_cubes(*rep, k):
                    self.assertTrue(adm(v["d"].numerator, v["d"].denominator), f"k={k} rep={rep} d={v['d']}")

    def test_python_mirror_matches_worker_counts(self):
        for k in (375,) + TEST_KS:
            adm = Admissibility(k)
            recs = run_worker(k, 160, digits=20)
            worker = {r["h"]: (r["pairs"], r["admissible"]) for r in recs if r["type"] == "shell"}
            for h in range(1, 160):
                pairs = list(shell(h))
                self.assertEqual(worker[h], (len(pairs), sum(adm(p, q) for p, q in pairs)), f"k={k} h={h}")

    def test_pair_count_formula(self):
        self.assertEqual(pairs_in(1, 101), sum(4 * h - 1 for h in range(1, 101)))


@unittest.skipUnless(WORKER.exists() and shutil.which("gp"), "needs the worker and PARI/GP")
class PariCrossCheck(unittest.TestCase):
    """Raw Thue solutions with |g| <= G must equal PARI's unconditional solution set."""

    def test_raw_mode_equals_pari(self):
        rng = random.Random(375)
        cases = []
        for k in (375, 15, 57):
            for rep in sorted(representations(k, 60))[:6]:
                for v in d_values_from_cubes(*rep, k):
                    cases.append((k, v["d"].numerator, v["d"].denominator))
            while len([c for c in cases if c[0] == k]) < 20:
                p, q = rng.randint(-40, 40), rng.randint(1, 40)
                if p and gcd(p, q) == 1:
                    cases.append((k, p, q))
        G = 10 ** 60
        script = ["default(parisize, 64000000);"]
        for k, p, q in cases:
            script.append(f"print(thue(thueinit(x^3 - 6*{p}*{q}*x + 3*{p}*{q}*({p}+{q}), 1), {k}));")
        pari = subprocess.run(["gp", "-q", "-f"], input="\n".join(script), check=True,
                              capture_output=True, text=True, timeout=1200).stdout.split("\n")
        pari = [line for line in pari if line.strip()]
        self.assertEqual(len(pari), len(cases))
        for (k, p, q), line in zip(cases, pari):
            nums = [int(t) for t in line.replace("[", " ").replace("]", " ").replace(",", " ").replace(";", " ").split()]
            psol = {(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)}
            psol = {(S, g) for S, g in psol if g != 0 and abs(g) <= G}
            out = subprocess.run([str(WORKER), "--raw", "--target", str(k), "--g-max", str(G)],
                                 input=f"{p} {q}\n", check=True, capture_output=True, text=True).stdout
            wsol = {(int(a), int(b)) for a, b, _ in json.loads(out)["solutions"]}
            self.assertEqual(wsol, psol, f"k={k} d={p}/{q}")


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Lifecycle(unittest.TestCase):
    def test_campaign_interrupt_resume_collect(self):
        py = sys.executable
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            subprocess.run([py, str(ROOT / "make_campaign.py"), "--campaign-id", "t15", "--k", "15", "--mode", "both",
                            "--h-stop", "900", "--task-hours", "0.004", "--us-per-pair", "9",
                            "--g-max-digits", "40", "--output-dir", str(tmp / "camp")],
                           check=True, capture_output=True)
            page = json.loads((tmp / "camp" / "page.json").read_text())
            self.assertGreater(len(page["tasks"]), 1)
            spans = [(t["h_start"], t["h_stop"]) for t in page["tasks"]]
            self.assertEqual(spans[0][0], 1)
            self.assertEqual(spans[-1][1], 900)
            self.assertTrue(all(a[1] == b[0] for a, b in zip(spans, spans[1:])))
            # Interrupt the last (largest-height) task, then resume it in place.
            last = page["tasks"][-1]
            outdir = tmp / "res" / last["task_id"]
            proc = subprocess.Popen([py, str(ROOT / "run_task.py"), "--task", str(tmp / "camp" / last["file"]),
                                     "--output-dir", str(outdir)])
            deadline = time.time() + 30
            while not (outdir / "checkpoint.json").exists() and time.time() < deadline:
                time.sleep(0.05)
            proc.send_signal(signal.SIGTERM)
            self.assertEqual(proc.wait(timeout=60), 0)
            status = json.loads((outdir / "status.json").read_text())
            if status["state"] == "partial":
                self.assertTrue((outdir / "continuation.task.json").exists())
            for t in page["tasks"]:
                subprocess.run([py, str(ROOT / "run_task.py"), "--task", str(tmp / "camp" / t["file"]),
                                "--output-dir", str(tmp / "res" / t["task_id"])], check=True, capture_output=True)
            self.assertEqual(json.loads((outdir / "status.json").read_text())["state"], "complete")
            subprocess.run([py, str(ROOT / "collect.py"), "--results", str(tmp / "res"), "--page",
                            str(tmp / "camp" / "page.json"), "--output-dir", str(tmp / "col")],
                           check=True, capture_output=True)
            summary = json.loads((tmp / "col" / "summary.json").read_text())
            self.assertEqual(summary["gaps"], [])
            self.assertEqual(summary["covered_heights"], [[1, 900]])
            # Same hits as one uninterrupted worker run.
            direct = {as_point(r) for r in run_worker(15, 900) if r["type"] == "hit"}
            collected = {as_point(json.loads(line)) for line in (tmp / "col" / "hits.jsonl").read_text().splitlines()}
            self.assertEqual(direct, collected)
            subprocess.run([py, str(ROOT / "verify_hits.py"), "--k", "15", str(tmp / "col" / "hits.jsonl")],
                           check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
