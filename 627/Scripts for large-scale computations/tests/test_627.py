"""CE627 test suite: run with  python3 -m unittest discover -s tests -v  (after make)."""
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

from common627 import (Admissibility, d_values_from_cubes, pairs_in, shell,  # noqa: E402
                       verify_hit)

WORKER = ROOT / "bin" / "thue627_worker"
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


def run_worker(k: int, h_stop: int, digits: int = 40) -> list[dict]:
    out = subprocess.run([str(WORKER), "--k", str(k), "--h-start", "1", "--h-stop", str(h_stop),
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


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Filters(unittest.TestCase):
    def test_filter_keeps_every_known_d(self):
        for k in TEST_KS:
            adm = Admissibility(k)
            for rep in representations(k, 300):
                for v in d_values_from_cubes(*rep, k):
                    self.assertTrue(adm(v["d"].numerator, v["d"].denominator), f"k={k} rep={rep} d={v['d']}")

    def test_python_mirror_matches_worker_counts(self):
        for k in (627,) + TEST_KS:
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
        rng = random.Random(627)
        cases = []
        for k in (627, 15, 57):
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
            subprocess.run([py, str(ROOT / "make_campaign.py"), "--campaign-id", "t15", "--k", "15",
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
