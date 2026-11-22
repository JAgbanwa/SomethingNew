"""CE375 test suite: run with  python3 -m unittest discover -s tests -v  (after make)."""
from __future__ import annotations

from fractions import Fraction
import json
from math import isqrt
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common375 import N_of, n_mod3, ns_in, primitivity, verify_hit  # noqa: E402

WORKER = ROOT / "bin" / "xy375_worker"
# odd k = +-3 (mod 9) with small known representations; 1875 = 3*5^4 and
# 7125 = 57*5^3 are not cube-free, like 375 = 3*5^3.
KS = (375, 15, 57, 1875, 7125)
NB = 300   # brute force over -NB <= n < NB


def run_worker(k: int, a: int, b: int, *extra: str) -> list[dict]:
    out = subprocess.run([str(WORKER), "--k", str(k), "--n-start", str(a), "--n-stop", str(b), *extra],
                         check=True, capture_output=True, text=True).stdout
    return [json.loads(line) for line in out.splitlines()]


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


def brute(k: int, a: int, b: int) -> dict[tuple[int, int, int], bool]:
    """Every point with a <= n < b on the ORIGINAL equation, straight from the
    definition: x | N(n) (integer form) or x = X/2 with X odd, X | N(n) (half
    form), and y^2 a rational square. No use of the n (mod 3) filter."""
    out = {}
    for n in range(a, b):
        N, S = N_of(n, k), 6 * n + 3
        for D in divisors(N):
            for sx in (D, -D):
                for x in [Fraction(sx)] + ([Fraction(sx, 2)] if D % 2 else []):
                    v = (x + S) ** 2 + N / x
                    if v < 0:
                        continue
                    rn, rd = isqrt(v.numerator), isqrt(v.denominator)
                    if rn * rn != v.numerator or rd * rd != v.denominator:
                        continue
                    y = Fraction(rn, rd)
                    if y.denominator != x.denominator:
                        continue   # x integer needs y integer; x = X/2 needs y = Y/2, Y odd
                    form = "integer" if x.denominator == 1 else "half"
                    cubes = (int(-x + y), int(-x - y), int(2 * x + S))
                    out[(n, int(2 * x), int(2 * y))] = primitivity(form, n, x, y, cubes)["desired"]
    return out


def points(records: list[dict]) -> dict[tuple[int, int, int], bool]:
    return {(int(r["n"]), int(r["X"]), int(r["Y"])): r["desired"] for r in records if r["type"] == "hit"}


@unittest.skipUnless(WORKER.exists(), "build first: make")
class AgainstBruteForce(unittest.TestCase):
    """The worker must find exactly the points a direct search finds."""

    @classmethod
    def setUpClass(cls):
        cls.records = {k: run_worker(k, -NB, NB, "--block", "97") for k in KS}

    def test_exact_agreement(self):
        total = 0
        for k in KS:
            expected = brute(k, -NB, NB)
            self.assertEqual(points(self.records[k]), expected, f"k={k}")
            total += len(expected)
        self.assertGreater(total, 10)

    def test_every_hit_verifies_independently(self):
        for k in KS:
            for r in self.records[k]:
                if r["type"] == "hit":
                    verify_hit(r, k)

    def test_both_forms_and_desired_points_occur(self):
        forms, desired = set(), 0
        for k in KS:
            for r in self.records[k]:
                if r["type"] == "hit":
                    forms.add(r["form"])
                    desired += r["desired"]
        self.assertEqual(forms, {"integer", "half"})
        self.assertGreater(desired, 3)

    def test_no_incomplete_and_counts(self):
        for k in KS:
            blocks = [r for r in self.records[k] if r["type"] == "block"]
            self.assertEqual(sum(b["incomplete"] for b in blocks), 0)
            self.assertEqual(sum(b["ns"] for b in blocks), ns_in(-NB, NB, k))
            self.assertEqual(self.records[k][-1], {"type": "end", "state": "complete", "next_n": str(NB)})

    def test_n_mod_3_invariant(self):
        self.assertEqual(n_mod3(375), 2)
        for k in KS:
            for (n, _, _) in brute(k, -60, 60):
                self.assertEqual(n % 3, n_mod3(k))

    def test_k375_known_points(self):
        """5*(1,1,1) and 5*(4,4,-5) give the only points with |n| < 300, all non-primitive."""
        self.assertEqual(points(self.records[375]),
                         {(2, -10, 0): False, (2, -40, 0): False, (2, 5, 45): False})

    def test_known_primitive_points(self):
        p15 = points(self.records[15])
        self.assertTrue(p15[(0, -1, 3)])                       # 2^3 + (-1)^3 + 2^3 = 15, half form
        p1875 = points(self.records[1875])
        self.assertTrue(p1875[(-4, 58, 0)])                    # (-29)^3 + (-29)^3 + 37^3: x = 29, y = 0
        p7125 = points(self.records[7125])
        self.assertTrue(p7125[(-7, -7, 141)])                  # (-67)^3 + (-46)^3 + 74^3: x = -7/2, y = 141/2
        self.assertTrue(p7125[(-7, 113, 21)])                  # and x = 113/2, y = 21/2


@unittest.skipUnless(WORKER.exists() and shutil.which("gp"), "needs the worker and PARI/GP")
class LargeNFactorisation(unittest.TestCase):
    """At large n the divisor count of every N(n) must equal PARI's numdiv."""

    def check(self, a: int, count: int) -> None:
        recs = run_worker(375, a, a + count, "--block", "1")
        blocks = [r for r in recs if r["type"] == "block" and r["ns"] == 1]
        ns = [int(r["n_start"]) for r in blocks]
        self.assertEqual(len(ns), ns_in(a, a + count))
        script = "\n".join(f"print(numdiv({N_of(n)}))" for n in ns)
        pari = [int(v) for v in subprocess.run(["gp", "-q", "-f"], input=script, check=True,
                                               capture_output=True, text=True, timeout=600).stdout.split()]
        self.assertEqual([r["divisors"] for r in blocks], pari)
        self.assertEqual(sum(r["incomplete"] for r in recs if r["type"] == "block"), 0)

    def test_near_1e9(self):
        self.check(1_000_000_000, 450)

    def test_near_minus_1e10(self):
        self.check(-10_000_000_000, 150)

    def test_near_1e11(self):
        self.check(100_000_000_000, 90)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Lifecycle(unittest.TestCase):
    def test_campaign_interrupt_resume_collect(self):
        py = sys.executable
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            subprocess.run([py, str(ROOT / "make_campaign.py"), "--campaign-id", "t57", "--k", "57",
                            "--n-start", "-3000", "--n-stop", "3000", "--us-per-n", "20", "--task-hours", "0.000005",
                            "--output-dir", str(tmp / "camp")], check=True, capture_output=True)
            page = json.loads((tmp / "camp" / "page.json").read_text())
            spans = [(t["n_start"], t["n_stop"]) for t in page["tasks"]]
            self.assertGreater(len(spans), 1)
            self.assertEqual((spans[0][0], spans[-1][1]), (-3000, 3000))
            self.assertTrue(all(a[1] == b[0] for a, b in zip(spans, spans[1:])))
            last = page["tasks"][-1]
            outdir = tmp / "res" / last["task_id"]
            proc = subprocess.Popen([py, str(ROOT / "run_task.py"), "--task", str(tmp / "camp" / last["file"]),
                                     "--output-dir", str(outdir), "--block", "7"])
            deadline = time.time() + 30
            while not (outdir / "checkpoint.json").exists() and time.time() < deadline:
                time.sleep(0.01)
            proc.send_signal(signal.SIGTERM)
            self.assertEqual(proc.wait(timeout=60), 0)
            for t in page["tasks"]:
                subprocess.run([py, str(ROOT / "run_task.py"), "--task", str(tmp / "camp" / t["file"]),
                                "--output-dir", str(tmp / "res" / t["task_id"]), "--block", "50"],
                               check=True, capture_output=True)
            self.assertEqual(json.loads((outdir / "status.json").read_text())["state"], "complete")
            subprocess.run([py, str(ROOT / "collect.py"), "--results", str(tmp / "res"), "--page",
                            str(tmp / "camp" / "page.json"), "--output-dir", str(tmp / "col")],
                           check=True, capture_output=True)
            summary = json.loads((tmp / "col" / "summary.json").read_text())
            self.assertEqual(summary["gaps"], [])
            self.assertEqual(summary["covered_n"], [[-3000, 3000]])
            self.assertEqual(summary["counters"]["ns"], ns_in(-3000, 3000, 57))
            direct = points(run_worker(57, -3000, 3000))
            collected = points([json.loads(l) for l in (tmp / "col" / "hits.jsonl").read_text().splitlines()])
            self.assertEqual(direct, collected)
            self.assertTrue(direct)
            subprocess.run([py, str(ROOT / "verify_hits.py"), "--k", "57", str(tmp / "col" / "hits.jsonl")],
                           check=True, capture_output=True)

    def test_deadline_gives_continuation(self):
        py = sys.executable
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            task = {"schema": "ce375-xy-task-v1", "campaign_id": "d", "task_id": "d-0", "k": 375,
                    "n_start": 100_000_000, "n_stop": 100_600_000, "deadline_seconds": 1}
            (tmp / "task.json").write_text(json.dumps(task))
            subprocess.run([py, str(ROOT / "run_task.py"), "--task", str(tmp / "task.json"), "--output-dir",
                            str(tmp / "out"), "--block", "300"], check=True, capture_output=True)
            status = json.loads((tmp / "out" / "status.json").read_text())
            self.assertEqual(status["state"], "partial")
            cont = json.loads((tmp / "out" / "continuation.task.json").read_text())
            self.assertEqual(cont["n_start"], status["next_n"])
            self.assertGreater(cont["n_start"], task["n_start"])


if __name__ == "__main__":
    unittest.main()
