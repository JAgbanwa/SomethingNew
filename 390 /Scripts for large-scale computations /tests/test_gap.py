"""Tests for the gap-search engine (src/gap_worker.cpp, gap_*.py). Run after `make`."""
from __future__ import annotations

import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
WORKER = ROOT / "bin" / "gap_worker"

from gap_common import is_prime, verify_hit  # noqa: E402

# Record solutions (Booker 2019; Booker-Sutherland 2021). Each must be rediscovered.
RECORDS = {
    33: (8866128975287528, -8778405442862239, -2736111468807040),
    42: (-80538738812075974, 80435758145817515, 12602123297335631),
    3: (569936821221962380720, -569936821113563493509, -472715493453327032),
    165: (-385495523231271884, 383344975542639445, 98422560467622814),
    579: (143075750505019222645, -143070303858622169975, -6941531883806363291),
    795: (-14219049725358227, 14197965759741571, 2337348783323923),
    906: (-74924259395610397, 72054089679353378, 35961979615356503),
}


def worker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run([str(WORKER), *args], capture_output=True, text=True, timeout=1200)
    if check and r.returncode:
        raise AssertionError(r.stderr)
    return r


def hits(out: str) -> list[dict]:
    return [json.loads(line) for line in out.splitlines() if '"hit"' in line]


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


def eps3(k: int) -> int:
    return 1 if k % 9 == 3 else 2


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Records(unittest.TestCase):
    def test_rediscovers_every_record_solution(self):
        for k, sol in RECORDS.items():
            Z = min(sol, key=abs)
            x, y = [v for v in sol if v != Z]
            d, z = abs(x + y), abs(Z)
            ratio = -(-z // d) + 1
            r = worker("--k", str(k), "--d-start", str(d - 25), "--d-stop", str(d + 25), "--ratio-max", str(ratio))
            found = [h for h in hits(r.stdout) if {int(h["x"]), int(h["y"]), int(h["z"])} == set(sol)]
            self.assertEqual(len(found), 1, f"k={k}")
            verify_hit(found[0], k)

    def test_record_lost_when_window_excludes_it(self):
        k, sol = 33, RECORDS[33]
        d, z = abs(sol[0] + sol[1]), abs(sol[2])
        r = worker("--k", "33", "--d-start", str(d - 25), "--d-stop", str(d + 25), "--ratio-max", str(z // d - 1))
        self.assertEqual(hits(r.stdout), [])

    def test_filters_never_change_the_answer(self):
        # Same windows with every residue filter disabled: identical hits.
        for k in (33, 906, 165):
            sol = RECORDS[k]
            Z = min(sol, key=abs)
            x, y = [v for v in sol if v != Z]
            d, z = abs(x + y), abs(Z)
            args = ["--k", str(k), "--d-start", str(d - 3), "--d-stop", str(d + 3), "--ratio-max", str(-(-z // d) + 1)]
            a = {(h["x"], h["y"], h["z"]) for h in hits(worker(*args).stdout)}
            b = {(h["x"], h["y"], h["z"]) for h in hits(worker(*args, "--no-filter").stdout)}
            self.assertEqual(a, b)
            self.assertTrue(a)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Arithmetic(unittest.TestCase):
    def test_factorizations_near_production_start(self):
        for start in (185185185185185186, 185185185185185186 + 3 * 2 ** 18 - 500, 2 ** 58 - 1000):
            out = worker("--d-start", str(start), "--d-stop", str(start + 1000), "--dump-factors").stdout.split("\n")
            lines = [line for line in out if line]
            self.assertEqual(len(lines), 1000)
            for line in lines:
                parts = line.split()
                d, prod = int(parts[0]), 1
                for f in parts[1:]:
                    p, e = map(int, f.split("^"))
                    self.assertTrue(is_prime(p), f"{d}: {p} not prime")
                    prod *= p ** e
                self.assertEqual(prod, d)

    def test_roots_small_d_brute_force(self):
        for k in (390, 627, 33, -390):
            if k % 9 not in (3, 6):
                continue
            out = worker("--k", str(k), "--d-start", "1", "--d-stop", "1500", "--dump-roots").stdout
            seen = set()
            for line in out.splitlines():
                parts = list(map(int, line.split()))
                d, K, roots = parts[0], parts[1], parts[2:]
                seen.add(d)
                self.assertEqual(K, k if d % 3 == eps3(k) else -k)
                self.assertEqual(roots, [z for z in range(d) if (z ** 3 - K) % d == 0], f"k={k} d={d}")
            self.assertEqual(seen, {d for d in range(1, 1500) if d % 3})

    def test_roots_large_d(self):
        rng = random.Random(390)
        base = 185185185185185186
        # random production d, and windows containing multiples of 2^25, 5^14, 13^10, 7^12 (prime powers of p | k and p !| k)
        starts = [base + rng.randrange(10 ** 12)] + [(base // q + 1) * q - 1500 for q in (2 ** 25, 5 ** 14, 13 ** 10, 7 ** 12)]
        for start in starts:
            self._roots_window(start)

    def _roots_window(self, start):
        out = worker("--k", "390", "--d-start", str(start), "--d-stop", str(start + 3000), "--dump-roots").stdout
        # Factorizations from --dump-factors, checked here (product and primality) independently.
        facs = {}
        for line in worker("--d-start", str(start), "--d-stop", str(start + 3000), "--dump-factors").stdout.splitlines():
            parts = line.split()
            f = {int(a): int(b) for a, b in (t.split("^") for t in parts[1:])}
            self.assertTrue(all(is_prime(q) for q in f))
            prod = 1
            for q, e in f.items():
                prod *= q ** e
            self.assertEqual(prod, int(parts[0]))
            facs[int(parts[0])] = f
        n_live = 0
        for line in out.splitlines():
            parts = list(map(int, line.split()))
            d, K, roots = parts[0], parts[1], parts[2:]
            self.assertTrue(all((r ** 3 - K) % d == 0 for r in roots))
            self.assertEqual(len(set(roots)), len(roots))
            expected = 1
            for p, e in facs[d].items():   # local counts are multiplicative
                if 390 % p == 0:   # v_p(390) = 1: z^3 == K (mod p^e) solvable only for e = 1 (z == 0)
                    cnt = sum(1 for z in range(p ** e) if (z ** 3 - K) % p ** e == 0) if e == 1 else 0
                elif p % 3 == 2:
                    cnt = 1
                else:
                    cnt = 3 if pow(K % p, (p - 1) // 3, p) == 1 else 0
                expected *= cnt
            self.assertEqual(len(roots), expected, f"d={d}")
            n_live += bool(roots)
        self.assertGreater(n_live, 100)


    def test_filter_verdicts_match_exact_arithmetic(self):
        """Each residue filter must say exactly what exact integer arithmetic says."""
        from math import isqrt
        qr = {p: {x * x % p for x in range(p)} for p in (5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61)}
        for k, start in ((390, 185185185185185186 + 7 * 10 ** 9), (627, 185185185185185186), (33, 10 ** 12)):
            out = worker("--k", str(k), "--d-start", str(start), "--d-stop", str(start + 10 ** 7), "--ratio-max", "40",
                         "--dump-candidates", "4000").stdout
            n_int = 0
            for line in out.splitlines():
                if line.startswith("{"):
                    continue   # start record
                d, z, K, two, res = map(int, line.split())
                self.assertEqual((z ** 3 - K) % d, 0)
                self.assertEqual(z % 3, d % 3)
                self.assertTrue(3847 * d // 1000 <= z <= 40 * d)
                N = 4 * (z ** 3 - K) - d ** 3
                if N % (3 * d):
                    continue           # Delta not an integer: never a solution, verdict irrelevant
                n_int += 1
                delta = N // (3 * d)
                self.assertEqual(two, int(d % 2 == 0 or delta % 8 == 1), (d, z))
                self.assertEqual(res, int(all(d % p == 0 or delta % p in qr[p] for p in qr)), (d, z))
                if delta >= 0 and isqrt(delta) ** 2 == delta:
                    self.assertTrue(two and res)
            self.assertGreater(n_int, 1000, k)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class BruteForce(unittest.TestCase):
    """All solutions with max |coordinate| <= B must be found inside the searched (d, z) region."""
    B = 2000

    @staticmethod
    def solutions(k: int, B: int) -> set[tuple[int, int, int]]:
        import numpy as np
        v = np.arange(-B, B + 1, dtype=np.int64)
        cubes = v ** 3
        out = set()
        for x in range(-B, B + 1):
            r = k - x ** 3 - cubes                      # = z^3 for a solution
            idx = np.nonzero(np.isin(r, cubes, assume_unique=False))[0]
            for i in idx:
                y = int(v[i]); zc = int(r[i])
                z = round(abs(zc) ** (1 / 3)) * (1 if zc >= 0 else -1)
                for zz in (z - 1, z, z + 1):
                    if zz ** 3 == zc:
                        out.add(tuple(sorted((x, y, zz))))
        return out

    def test_agrees_with_brute_force(self):
        total = 0
        for k in [k for k in range(1, 101) if k % 9 in (3, 6)]:
            sols = self.solutions(k, self.B)
            ratio, dmax = 2000, 800
            expected = set()
            for s in sols:
                for i in range(3):
                    Z = s[i]
                    x, y = s[(i + 1) % 3], s[(i + 2) % 3]
                    d, z = abs(x + y), abs(Z)
                    if not 1 <= d < dmax or d % 3 == 0 or not 3847 * d // 1000 <= z <= ratio * d:
                        continue
                    if Z == 0 or (x + y) != (-d if Z > 0 else d):
                        continue
                    expected.add((tuple(sorted((x, y))), Z))
            r = worker("--k", str(k), "--d-start", "1", "--d-stop", str(dmax), "--ratio-max", str(ratio))
            got = set()
            for h in hits(r.stdout):
                verify_hit(h, k)
                x, y, Z = int(h["x"]), int(h["y"]), int(h["z"])
                if max(abs(x), abs(y), abs(Z)) <= self.B:
                    got.add((tuple(sorted((x, y))), Z))
            self.assertEqual(got, expected, f"k={k}")
            total += len(expected)
        self.assertGreater(total, 30)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Lifecycle(unittest.TestCase):
    def test_plan_run_interrupt_resume_collect(self):
        py = sys.executable
        k, sol = 906, RECORDS[906]
        Z = min(sol, key=abs)
        x, y = [v for v in sol if v != Z]
        d0 = abs(x + y)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            subprocess.run([py, str(ROOT / "gap_campaign.py"), "--campaign-id", "t906", "--k", "906",
                            "--d-start", str(d0 - 3_000_000), "--d-stop", str(d0 + 1_000_000), "--ratio-max", "14",
                            "--task-d-count", "1500000", "--output-dir", str(tmp / "camp")],
                           check=True, capture_output=True)
            page = json.loads((tmp / "camp" / "page.json").read_text())
            self.assertEqual(len(page["tasks"]), 3)
            for t in page["tasks"]:
                out = tmp / "res" / t["task_id"]
                cmd = [py, str(ROOT / "run_gap_task.py"), "--task", str(tmp / "camp" / t["file"]), "--output-dir", str(out),
                       "--chunk", "262144"]
                proc = subprocess.Popen(cmd)
                deadline = time.time() + 60
                while not (out / "checkpoint.json").exists() and time.time() < deadline and proc.poll() is None:
                    time.sleep(0.02)
                if proc.poll() is None:
                    proc.send_signal(signal.SIGTERM)
                self.assertEqual(proc.wait(timeout=120), 0)
                subprocess.run(cmd, check=True, capture_output=True)   # resume in place
                self.assertEqual(json.loads((out / "status.json").read_text())["state"], "complete")
            r = subprocess.run([py, str(ROOT / "collect_gap.py"), "--page", str(tmp / "camp" / "page.json"),
                                "--results", str(tmp / "res"), "--output-dir", str(tmp / "col")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            summary = json.loads((tmp / "col" / "summary.json").read_text())
            self.assertEqual(summary["gaps"], [])
            found = [json.loads(line) for line in (tmp / "col" / "hits.jsonl").read_text().splitlines()]
            self.assertIn(set(sol), [{int(h["x"]), int(h["y"]), int(h["z"])} for h in found])


@unittest.skipUnless(WORKER.exists(), "build first: make")
class CoverageAccounting(unittest.TestCase):
    """Coverage must only ever be credited for d values actually searched in that directory."""

    def _plan(self, tmp):
        py = sys.executable
        subprocess.run([py, str(ROOT / "gap_campaign.py"), "--campaign-id", "cov", "--k", "390",
                        "--d-start", "1000000000000", "--d-stop", "1000040000000", "--ratio-max", "40",
                        "--task-d-count", "40000000", "--output-dir", str(tmp / "camp")], check=True, capture_output=True)
        return tmp / "camp" / "tasks" / "cov-0.json"

    def _run(self, task, out, interrupt=False):
        cmd = [sys.executable, str(ROOT / "run_gap_task.py"), "--task", str(task), "--output-dir", str(out),
               "--chunk", "1048576"]
        if not interrupt:
            return subprocess.run(cmd, capture_output=True, text=True).returncode
        proc = subprocess.Popen(cmd)
        deadline = time.time() + 60
        while not (out / "checkpoint.json").exists() and time.time() < deadline and proc.poll() is None:
            time.sleep(0.01)
        proc.send_signal(signal.SIGTERM)
        return proc.wait(timeout=120)

    def _collect(self, tmp, *dirs):
        r = subprocess.run([sys.executable, str(ROOT / "collect_gap.py"), "--page", str(tmp / "camp" / "page.json"),
                            "--results", *map(str, dirs), "--output-dir", str(tmp / "col")], capture_output=True, text=True)
        return r.returncode, json.loads((tmp / "col" / "summary.json").read_text())

    def test_original_rerun_into_continuation_dir_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            task = self._plan(tmp)
            self.assertEqual(self._run(task, tmp / "A", interrupt=True), 0)
            cont = tmp / "A" / "continuation.task.json"
            self.assertTrue(cont.exists())
            a_next = int(json.loads((tmp / "A" / "checkpoint.json").read_text())["d_next"])
            self.assertEqual(self._run(cont, tmp / "B"), 0)
            before = (tmp / "B" / "status.json").read_text()
            self.assertEqual(self._run(task, tmp / "B"), 1)            # refused ...
            self.assertEqual((tmp / "B" / "status.json").read_text(), before)   # ... and nothing changed
            rc, summary = self._collect(tmp, tmp / "B")                 # directory A lost
            self.assertEqual(rc, 0)
            self.assertEqual(summary["gaps"], [["1000000000000", str(a_next)]])

    def test_continuation_in_same_dir_has_no_false_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            task = self._plan(tmp)
            self.assertEqual(self._run(task, tmp / "A", interrupt=True), 0)
            self.assertEqual(self._run(tmp / "A" / "continuation.task.json", tmp / "A"), 0)
            rc, summary = self._collect(tmp, tmp / "A")
            self.assertEqual((rc, summary["gaps"]), (0, []))
            self.assertEqual(summary["d_values_covered"], 40_000_000)

    def test_audit_detects_altered_counters(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            task = self._plan(tmp)
            self.assertEqual(self._run(task, tmp / "A"), 0)
            audit = [sys.executable, str(ROOT / "audit_gap.py"), "--page", str(tmp / "camp" / "page.json"),
                     "--results", str(tmp / "A"), "--fraction", "1", "--seed", "1"]
            self.assertEqual(subprocess.run(audit, capture_output=True).returncode, 0)
            chunks = tmp / "A" / "chunks.jsonl"
            recs = [json.loads(line) for line in chunks.read_text().splitlines()]
            recs[3]["counters"]["candidates"] -= 1                     # a host that skipped one candidate
            chunks.write_text("".join(json.dumps(r) + "\n" for r in recs))
            self.assertEqual(subprocess.run(audit, capture_output=True).returncode, 1)


if __name__ == "__main__":
    unittest.main()
