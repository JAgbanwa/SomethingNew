"""Tests of the d-first half-chart engine (src/dthue_worker.cpp, D_FIRST.md).

The decisive test is the first one: for m = 1 (k = 6) half-chart points are
KNOWN, and the unchanged campaign code must report each of them. The others
check the Thue solver against an independent brute force, plant large
solutions that only the continued-fraction path can find, compare the
admissibility filter with an independent factorisation-based implementation
and with the repository's 733-prime sieve, and exercise the task lifecycle.
"""
from fractions import Fraction
import json
from math import gcd, isqrt
import os
from pathlib import Path
import random
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfirst_common import admissible, prime_cap, shell_pairs, thue_form, verify_hit, pairs_in_shells  # noqa: E402
from q_sieve import forbidden_primes  # noqa: E402


def brute_solutions(p, q, T, gmax):
    """Independent oracle: all (n, g), 1 <= |g| <= gmax, with F_d(n, g) = T."""
    out = set()
    for g in range(-gmax, gmax + 1):
        if g == 0:
            continue
        k1, k0 = -12 * p * q * g * g, p * q * (p + q) * g ** 3 - T  # 72 n^3 + k1 n + k0 = 0
        def h(n):
            return 72 * n ** 3 + k1 * n + k0
        bound = 2 + (abs(k1) + abs(k0)) // 72
        pieces = [(-bound, bound, 1)]
        if k1 < 0:
            r = isqrt(-k1 // 216)
            pieces = [(-bound, -r - 1, 1), (-r, r, -1), (r + 1, bound, 1)]
        for lo, hi, sign in pieces:
            # first n in [lo, hi] with sign*h(n) >= 0
            a, b = lo, hi + 1
            while a < b:
                mid = (a + b) // 2
                if sign * h(mid) >= 0:
                    b = mid
                else:
                    a = mid + 1
            if a <= hi and h(a) == 0:
                out.add((a, g))
    return out


def real_root_cf(p, q, terms=60, bits=1200):
    """Partial quotients of the real root of 72t^3 - 12pq t + pq(p+q), exactly."""
    def side(num, den):
        return 72 * num ** 3 - 12 * p * q * num * den * den + p * q * (p + q) * den ** 3
    D = 1 << bits
    bound = (2 + (12 * abs(p * q) + abs(p * q * (p + q))) // 72) * D
    lo, hi = -bound, bound
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if side(mid, D) < 0:
            lo = mid
        else:
            hi = mid
    a_lo, a_hi = Fraction(lo, D), Fraction(hi, D)
    quotients = []
    for _ in range(terms):
        c0, c1 = a_lo.numerator // a_lo.denominator, a_hi.numerator // a_hi.denominator
        if c0 != c1:
            break
        quotients.append(c0)
        if a_lo == c0:
            break
        a_lo, a_hi = 1 / (a_hi - c0), 1 / (a_lo - c0)
    return quotients


class DFirstTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shlex.split(os.environ.get("CXX", "g++"))
        if not compiler or not shutil.which(compiler[0]):
            raise unittest.SkipTest("a C++17 compiler is required")
        cls.temp = tempfile.TemporaryDirectory()
        cls.worker = Path(cls.temp.name) / "dthue_worker"
        build = subprocess.run([*compiler, *shlex.split(os.environ.get("CXXFLAGS", "-O2 -Wall -Wextra")),
                                "-std=c++17", str(ROOT / "src/dthue_worker.cpp"), "-o", str(cls.worker),
                                *shlex.split(os.environ.get("LDLIBS", "-lgmpxx -lgmp"))],
                               text=True, capture_output=True)
        if build.returncode:
            raise RuntimeError(build.stdout + build.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def campaign(self, m, start, stop, digits=100):
        run = subprocess.run([str(self.worker), "--m", str(m), "--h-start", str(start), "--h-stop", str(stop),
                              "--g-max-digits", str(digits)], text=True, capture_output=True, timeout=600)
        self.assertEqual(run.returncode, 0, run.stderr)
        return [json.loads(line) for line in run.stdout.splitlines()]

    def raw(self, pairs, target, gmax):
        run = subprocess.run([str(self.worker), "--raw", "--target", str(target), "--g-max", str(gmax)],
                             input="".join(f"{p} {q}\n" for p, q in pairs), text=True,
                             capture_output=True, timeout=600)
        self.assertEqual(run.returncode, 0, run.stderr)
        return [json.loads(line) for line in run.stdout.splitlines()]

    # -- the decisive end-to-end check -------------------------------------------------
    def test_known_half_chart_points_for_k6_are_all_reported(self):
        rows = self.campaign(1, 1, 450)
        hits = [r for r in rows if r["type"] == "hit"]
        found = {(Fraction(int(h["d_num"]), int(h["d_den"])), int(h["n_num"]), Fraction(int(h["x_num"]), 2))
                 for h in hits}
        expected = {(Fraction(-22, 101), -6, Fraction(101, 2)), (Fraction(1, 181), -9, Fraction(-181, 2)),
                    (Fraction(7, 439), -33, Fraction(-439, 2)), (Fraction(22, 7), -6, Fraction(-7, 2)),
                    (Fraction(1), 0, Fraction(-1, 2)), (Fraction(181), -9, Fraction(-1, 2)),
                    (Fraction(439, 7), -33, Fraction(-7, 2))}
        self.assertEqual(found, expected)
        self.assertEqual(len(hits), 7)
        for h in hits:
            verify_hit(h, 1, (1, 450))
        self.assertEqual(rows[-1], {"type": "end", "state": "complete", "next_h": 450})

    def test_k390_low_shells_complete_and_counts_match_independent_filter(self):
        rows = self.campaign(65, 1, 121)
        shells = [r for r in rows if r["type"] == "shell"]
        self.assertEqual([r["h"] for r in shells], list(range(1, 121)))
        for r in shells:
            pairs = list(shell_pairs(r["h"]))
            self.assertEqual(r["pairs"], len(pairs))
            self.assertEqual(r["admissible"], sum(admissible(p, q, 65) for p, q in pairs), r["h"])
        self.assertEqual(sum(r["pairs"] for r in shells), pairs_in_shells(1, 121))
        self.assertEqual(sum(r["admissible"] for r in shells), 517)
        self.assertFalse([r for r in rows if r["type"] == "hit"])

    def test_k6_filter_counts_match(self):
        for r in [r for r in self.campaign(1, 1, 80) if r["type"] == "shell"]:
            self.assertEqual(r["admissible"], sum(admissible(p, q, 1) for p, q in shell_pairs(r["h"])))

    def test_even_and_negative_targets_filter_counts_match(self):
        # The extra mod-4 filter is conditional on m being odd. Signed p is
        # enumerated in every shell, and negative m has the same parity rule.
        for m in (-65, -2, 2):
            for row in [r for r in self.campaign(m, 1, 31, digits=10) if r["type"] == "shell"]:
                self.assertEqual(row["admissible"],
                                 sum(admissible(p, q, m) for p, q in shell_pairs(row["h"])),
                                 (m, row["h"]))

    def test_prime_conditions_agree_with_repository_733_prime_sieve(self):
        primes = [p for p in range(5, 20000) if all(p % d for d in range(2, isqrt(p) + 1))]
        ours = tuple(p for p in primes if prime_cap(p, 65) == 0)
        self.assertEqual(ours, forbidden_primes())
        self.assertEqual(prime_cap(5, 65), 1)   # 25 can never divide p or q
        self.assertEqual(prime_cap(13, 65), 1)  # nor 169
        self.assertEqual(prime_cap(2, 65), 1)   # nor 4

    # -- Thue solver core ----------------------------------------------------------------
    def test_raw_solver_matches_brute_force_on_planted_small_solutions(self):
        rng = random.Random(390)
        cases = [(1, 1), (5, 7), (-11, 13), (7, 8), (-2, 5), (13, 11), (3, 2), (1, 7), (-25, 1)]
        for p, q in cases:
            for _ in range(3):
                n0, g0 = rng.randint(-40, 40), rng.choice([-1, 1]) * rng.randint(1, 30)
                T = thue_form(p, q, n0, g0)
                if T == 0:
                    continue
                gmax = 120
                (row,) = self.raw([(p, q)], T, gmax)
                got = {(int(n), int(g)) for n, g, _ in row["solutions"]}
                self.assertEqual(got, brute_solutions(p, q, T, gmax), (p, q, T))
                self.assertIn((n0, g0), got)

    def test_raw_solver_finds_planted_large_solutions_through_convergents(self):
        found = 0
        for p, q in [(p, q) for p in range(-60, 61) for q in range(1, 61) if p and gcd(p, q) == 1][::7]:
            if found >= 4:
                break
            cf = real_root_cf(p, q, terms=40, bits=600)
            pk, qk, pm, qm = 1, 0, 0, 1
            for i, c in enumerate(cf[:-1]):
                pk, qk, pm, qm = c * pk + pm, c * qk + qm, pk, qk
                # A large next partial quotient makes |F(pk, qk)| small relative to qk,
                # so qk lies beyond the exhaustive range g0 and only a convergent can find it.
                if qk >= 10**4 and cf[i + 1] >= 100:
                    T = thue_form(p, q, pk, qk)
                    alpha = pk / qk
                    g0_estimate = abs(T) / (27 * alpha * alpha - 6 * p * q)  # = |T|/(36 eta^2)
                    if g0_estimate > min(qk / 4, 20000):
                        continue  # keep the exhaustive part of this test short
                    (row,) = self.raw([(p, q)], T, 10**40)
                    self.assertLess(int(row["g0"]), qk)
                    sols = {(int(n), int(g)): src for n, g, src in row["solutions"]}
                    self.assertIn((pk, qk), sols, (p, q, i))
                    self.assertEqual(sols[(pk, qk)], "convergent")
                    found += 1
                    break
        self.assertGreaterEqual(found, 2)

    def test_eta_small_case_uses_exhaustive_range(self):
        # d = 1: eta^2 = 3 alpha^2/4 - 1/6 is tiny, so g0 is large; still exact.
        (row,) = self.raw([(1, 1)], 130, 3000)
        self.assertGreater(int(row["g0"]), 1000)
        got = {(int(n), int(g)) for n, g, _ in row["solutions"]}
        self.assertEqual(got, brute_solutions(1, 1, 130, 3000))

    # -- verifier and lifecycle ----------------------------------------------------------
    def test_verifier_rejects_tampering(self):
        hit = [r for r in self.campaign(1, 101, 102) if r["type"] == "hit"][0]
        verify_hit(hit, 1)
        for key, value in [("y_num", str(int(hit["y_num"]) + 2)), ("d_num", "23"), ("m", "65"), ("x_den", "1")]:
            bad = dict(hit, **{key: value})
            with self.assertRaises(ValueError):
                verify_hit(bad, 1)
        with self.assertRaises(ValueError):
            verify_hit(hit, 1, (1, 101))

    def test_packaging_builds_and_ships_the_engine(self):
        self.assertIn("bin/dthue_worker: src/dthue_worker.cpp", (ROOT / "Makefile").read_text())
        self.assertIn("all: bin/cf_worker bin/xy_cf_worker bin/dthue_worker", (ROOT / "Makefile").read_text())
        docker = (ROOT / "Dockerfile").read_text()
        app_sources = {source for line in docker.splitlines()
                       if line.startswith("COPY ") and line.split()[-1] == "/app/"
                       for source in line.split()[1:-1]}
        self.assertTrue({"dfirst_common.py", "d_campaign.py", "run_d_task.py",
                         "run_d_campaign.py", "collect_d.py", "verify_d.py"} <= app_sources)
        self.assertIn("/app/bin/dthue_worker", docker)

    def test_rejects_m_divisible_by_three(self):
        run = subprocess.run([str(self.worker), "--m", "3", "--h-start", "1", "--h-stop", "5"],
                             text=True, capture_output=True)
        self.assertEqual(run.returncode, 2)

    def test_task_lifecycle_partial_resume_collect(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            subprocess.run([sys.executable, str(ROOT / "d_campaign.py"), "--campaign-id", "t", "--m", "1",
                            "--h-start", "1", "--h-stop", "450", "--target-seconds", "100",
                            "--output-dir", str(tmp / "tasks")], check=True, capture_output=True, env=env)
            page = json.loads((tmp / "tasks/page.json").read_text())
            self.assertEqual(len(page["tasks"]), 1)
            task_file = tmp / "tasks" / page["tasks"][0]["file"]
            task = json.loads(task_file.read_text())
            task["seconds"] = 1  # not part of the task identity
            task_file.write_text(json.dumps(task))
            def run(task_path, out):
                r = subprocess.run([sys.executable, str(ROOT / "run_d_task.py"), "--task", str(task_path),
                                    "--output-dir", str(out), "--worker", str(self.worker),
                                    "--reserve-seconds", "0"], capture_output=True, text=True, env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                return json.loads((out / "status.json").read_text())
            first = run(task_file, tmp / "out/a")
            self.assertEqual(first["state"], "partial")
            cont = tmp / "out/a/continuation.task.json"
            current, i = cont, 0
            while True:
                c = json.loads(current.read_text())
                c["seconds"] = 3600
                current.write_text(json.dumps(c))
                i += 1
                status = run(current, tmp / f"out/b{i}")
                if status["state"] == "complete":
                    break
                current = tmp / f"out/b{i}/continuation.task.json"
            r = subprocess.run([sys.executable, str(ROOT / "collect_d.py"), "--page", str(tmp / "tasks/page.json"),
                                "--results-dir", str(tmp / "out"), "--output-dir", str(tmp / "col")],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            summary = json.loads((tmp / "col/summary.json").read_text())
            self.assertTrue(summary["all_tasks_complete"])
            self.assertEqual(summary["covered_shells"], [{"start": "1", "stop": "450"}])
            self.assertEqual(summary["verified_hits"], 7)
            # A continuation is refused by a different worker binary.
            other = tmp / "other_worker"
            shutil.copy(self.worker, other)
            with other.open("ab") as fh:
                fh.write(b"\0")
            r = subprocess.run([sys.executable, str(ROOT / "run_d_task.py"), "--task", str(cont),
                                "--output-dir", str(tmp / "out/z"), "--worker", str(other)],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 2)
            self.assertIn("pinned", r.stderr)


if __name__ == "__main__":
    unittest.main()
