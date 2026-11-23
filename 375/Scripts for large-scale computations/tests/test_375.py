"""CE375 tests: production is the unit-g subsearch; --raw remains a general solver."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
import json
from math import gcd, isqrt
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

from common375 import (  # noqa: E402
    Admissibility, CHECKPOINT_SCHEMA, PAGE_SCHEMA, PARAMETERIZATION, STATUS_SCHEMA,
    TASK_SCHEMA, d_values_from_cubes, n_mod3, pairs_in, primitivity, shell,
    validate_task, verify_hit,
)

WORKER = ROOT / "bin" / "thue375_worker"
TEST_KS = (3, 15, 21, 57)
HMAX = 70
CUBE_BOUND = 400


def icbrt_floor(v: int) -> int:
    """Exact nonnegative integer cube root, used only for bounded test oracles."""
    if not v:
        return 0
    r = 1 << ((v.bit_length() + 2) // 3)
    while True:
        nxt = (2 * r + v // (r * r)) // 3
        if nxt >= r:
            return r
        r = nxt


@lru_cache(maxsize=None)
def representations(k: int, bound: int) -> frozenset[tuple[int, int, int]]:
    reps = set()
    for a in range(-bound, bound + 1):
        for b in range(a, bound + 1):
            r = k - a ** 3 - b ** 3
            c = icbrt_floor(abs(r)) * (1 if r >= 0 else -1)
            if c ** 3 == r and abs(c) <= bound:
                reps.add(tuple(sorted((a, b, c))))
    return frozenset(reps)


def run_worker(k: int, h_stop: int, mode: str = "both", h_start: int = 1) -> list[dict]:
    out = subprocess.run(
        [str(WORKER), "--k", str(k), "--mode", mode, "--h-start", str(h_start), "--h-stop", str(h_stop)],
        check=True, capture_output=True, text=True,
    ).stdout
    return [json.loads(line) for line in out.splitlines()]


def as_point(rec: dict) -> tuple:
    return (Fraction(int(rec["d_num"]), int(rec["d_den"])), rec["chart"],
            Fraction(int(rec["x_num"]), int(rec["x_den"])),
            Fraction(int(rec["s_num"]), int(rec["s_den"])))


def xy_point(rec: dict) -> tuple[int, int, int]:
    if "X" in rec:
        return int(rec["n"]), int(rec["X"]), int(rec["Y"])
    return (int(rec["n"]), int(2 * Fraction(int(rec["x_num"]), int(rec["x_den"]))),
            int(2 * Fraction(int(rec["s_num"]), int(rec["s_den"]))))


def height(d: Fraction) -> int:
    return max(abs(d.numerator), d.denominator)


def branch_certificates(n: int, X: int, Y: int) -> list[tuple[Fraction, int, str]]:
    """Derive each actual signed-y certificate from the original point, independently."""
    x, y, S = Fraction(X, 2), Fraction(Y, 2), 6 * n + 3
    out = []
    for signed_y, branch in ((y, "principal"), (-y, "conjugate")):
        d = -(x + S + signed_y) / (2 * x)
        assert X % d.denominator == 0
        out.append((d, -X // d.denominator, branch))
    return out


def in_unit_scope(point: tuple[int, int, int], h_stop: int, *, principal_only: bool = False) -> bool:
    certs = branch_certificates(*point)
    return any(abs(g) == 1 and height(d) < h_stop for d, g, _ in (certs[:1] if principal_only else certs))


def point_primitive(n: int, X: int, Y: int) -> bool:
    """The user's two alternative definitions, not the implementation under test."""
    return gcd(X, Y) == 1 if X % 2 else gcd(gcd(n, X // 2), Y // 2) == 1


def divisors(m: int) -> list[int]:
    m, out, f = abs(m), [1], 2
    if not m:
        raise ValueError("zero has no finite divisor list")
    while f * f <= m:
        e = 0
        while m % f == 0:
            m //= f
            e += 1
        if e:
            out = [d * f ** i for d in out for i in range(e + 1)]
        f += 1
    if m > 1:
        out += [d * m for d in out]
    return out


@lru_cache(maxsize=None)
def original_points(k: int, nmax: int) -> frozenset[tuple[int, int, int]]:
    """Independent original-equation oracle, including nonprimitive points in both charts.

    Integer x divides N(n). Odd half-chart X also divides N(n), since the
    difference of the two odd squares is divisible by 8. Bounds here describe
    test coverage only and do not become campaign/search restrictions.
    """
    out = set()
    for n in range(-nmax, nmax + 1):
        N = 36 * n ** 3 + 54 * n ** 2 + 27 * n + (27 - k) // 6
        if not N:
            continue
        S = 6 * n + 3
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
                    if y.denominator == x.denominator:
                        out.add((n, int(2 * x), int(2 * y)))
    return frozenset(out)


def xy_record(k: int, point: tuple[int, int, int], branch: str = "principal") -> dict:
    """Build a mathematically valid certificate, including nonunit ones for rejection tests."""
    n, X, Y = point
    certs = branch_certificates(n, X, Y)
    d = certs[0][0]
    td, g, _ = next(c for c in certs if c[2] == branch)
    x, y, S = Fraction(X, 2), Fraction(Y, 2), 6 * n + 3
    cubes = tuple(int(c) for c in (-x + y, -x - y, 2 * x + S))
    pg = gcd(X, Y) if X % 2 else gcd(gcd(n, X // 2), Y // 2)
    cg = gcd(gcd(cubes[0], cubes[1]), cubes[2])
    return {
        "type": "hit", "mode": "xy", "chart": "half" if X % 2 else "integer", "source": "unit_g",
        "branch": branch, "k": str(k), "n": str(n), "X": str(X), "Y": str(Y),
        "x_num": str(X), "x_den": "2", "y_num": str(Y), "y_den": "2",
        "d_num": str(d.numerator), "d_den": str(d.denominator),
        "thue_p": str(td.numerator), "thue_q": str(td.denominator), "g": str(g),
        "cube_a": str(cubes[0]), "cube_b": str(cubes[1]), "cube_c": str(cubes[2]),
        "primitive_point": pg == 1, "primitive_cubes": cg == 1, "desired": pg == 1,
        "point_gcd": str(pg), "cube_gcd": str(cg),
    }


class PrimitivityRules(unittest.TestCase):
    def test_integer_definition_includes_y(self):
        # 8^3 + 2^3 + 23^3 = 12687, g=1, d=31/10.
        flags = primitivity("integer", 5, Fraction(-5), Fraction(3), (8, 2, 23))
        self.assertEqual(gcd(5, -5), 5)
        self.assertTrue(flags["primitive_point"])
        self.assertTrue(flags["desired"])
        self.assertEqual(flags["point_gcd"], "1")

    def test_cube_primitivity_is_informational(self):
        # This known375 point is chart-primitive but has g=10, so its flags
        # and its exclusion from the unit-g production scope are separate facts.
        flags = primitivity("integer", 2, Fraction(-5), Fraction(0), (5, 5, 5))
        self.assertTrue(flags["desired"])
        self.assertFalse(flags["primitive_cubes"])
        self.assertEqual(flags["cube_gcd"], "5")
        with self.assertRaises(ValueError):
            verify_hit(xy_record(375, (2, -10, 0)), 375)

    def test_half_and_integer_are_alternative_acceptance_rules(self):
        self.assertTrue(primitivity("half", 0, Fraction(-1, 2), Fraction(3, 2), (2, -1, 2))["desired"])
        self.assertTrue(primitivity("integer", 0, Fraction(-1), Fraction(3), (4, -2, 1))["desired"])
        self.assertFalse(primitivity("half", 2, Fraction(5, 2), Fraction(45, 2), (20, -25, 20))["desired"])
        self.assertFalse(primitivity("integer", 0, Fraction(-2), Fraction(0), (2, 2, -1))["desired"])

    def test_actual_certificate_controls_unit_scope(self):
        # The principal d=4 has g=7, but the conjugate d=-113/7 has g=1.
        record = xy_record(7125, (-7, -7, 141), "conjugate")
        self.assertEqual((record["d_num"], record["d_den"]), ("4", "1"))
        self.assertEqual((record["thue_p"], record["thue_q"], record["g"]), ("-113", "7", "1"))
        self.assertTrue(verify_hit(record, 7125)["desired"])
        with self.assertRaises(ValueError):
            verify_hit(xy_record(7125, (-7, -7, 141), "principal"), 7125)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class KnownAnswers(unittest.TestCase):
    """Diagnostic both mode returns precisely the principal-branch unit-g points."""

    @classmethod
    def setUpClass(cls):
        cls.records = {k: run_worker(k, HMAX) for k in TEST_KS}

    def test_every_hit_verifies_and_production_never_runs_the_cf_search(self):
        signs, charts = set(), set()
        for k, recs in self.records.items():
            start = recs[0]
            self.assertEqual(start["g_values"], [-1, 1])
            self.assertEqual(start["parameterization"], PARAMETERIZATION)
            self.assertNotIn("g_max_digits", start)
            for r in recs:
                if r["type"] == "hit":
                    verify_hit(r, k)
                    signs.add(int(r["g"]))
                    charts.add(r["chart"])
                    self.assertEqual(r["source"], "unit_g")
                elif r["type"] == "shell":
                    self.assertEqual(r["small_g_values"], 2 * r["admissible"])
                    self.assertEqual(r["convergents"], 0)
                    self.assertEqual(r["refinements"], 0)
        self.assertEqual(signs, {-1, 1})
        self.assertEqual(charts, {"integer", "half"})

    def test_all_predicted_unit_points_found_and_nothing_spurious(self):
        for k in TEST_KS:
            expected = set()
            for rep in representations(k, CUBE_BOUND):
                for v in d_values_from_cubes(*rep, k):
                    g = -int(2 * v["x"]) // v["d"].denominator
                    if height(v["d"]) < HMAX and abs(g) == 1:
                        expected.add((v["d"], v["chart"], v["x"], v["s"]))
            found = {as_point(r) for r in self.records[k] if r["type"] == "hit"}
            self.assertLessEqual(expected, found, f"k={k}: missed {expected - found}")
            small = {as_point(r) for r in self.records[k] if r["type"] == "hit"
                     and max(abs(int(r[c])) for c in ("cube_a", "cube_b", "cube_c")) <= CUBE_BOUND}
            self.assertEqual(small, expected)

    def test_original_equation_oracle_filtered_by_actual_unit_g(self):
        for k in TEST_KS:
            expected = {pt for pt in original_points(k, 30) if in_unit_scope(pt, HMAX, principal_only=True)}
            found = {xy_point(r) for r in self.records[k] if r["type"] == "hit" and abs(int(r["n"])) <= 30}
            self.assertEqual(found, expected, f"k={k}")

    def test_k15_preserves_both_diagnostic_charts(self):
        found = {as_point(r) for r in self.records[15] if r["type"] == "hit"}
        self.assertIn((Fraction(1, 4), "integer", Fraction(-2), Fraction(0)), found)
        self.assertIn((Fraction(4), "half", Fraction(-1, 2), Fraction(3, 2)), found)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class ProductionScope(unittest.TestCase):
    def test_default_worker_is_xy_and_old_production_bound_is_rejected(self):
        proc = subprocess.run([str(WORKER), "--h-start", "1", "--h-stop", "2"], check=True, capture_output=True, text=True)
        start = json.loads(proc.stdout.splitlines()[0])
        self.assertEqual(start["mode"], "xy")
        self.assertEqual(start["g_values"], [-1, 1])
        old = subprocess.run([str(WORKER), "--h-start", "1", "--h-stop", "2", "--g-max-digits", "100"], capture_output=True, text=True)
        self.assertNotEqual(old.returncode, 0)

    def test_known_nonunit375_points_are_out_of_scope(self):
        recs = run_worker(375, HMAX)
        found = {as_point(r) for r in recs if r["type"] == "hit"}
        excluded = set()
        for rep in ((5, 5, 5), (20, 20, -25)):
            for v in d_values_from_cubes(*rep, 375):
                g = -int(2 * v["x"]) // v["d"].denominator
                self.assertNotEqual(abs(g), 1)
                excluded.add((v["d"], v["chart"], v["x"], v["s"]))
        self.assertTrue(excluded.isdisjoint(found))
        expected = {pt for pt in original_points(375, 60) if in_unit_scope(pt, HMAX, principal_only=True)}
        got = {xy_point(r) for r in recs if r["type"] == "hit" and abs(int(r["n"])) <= 60}
        self.assertEqual(got, expected)
        self.assertEqual(n_mod3(375), 2)
        self.assertEqual(n_mod3(627), 1)

    def test_general_raw_solver_still_exercises_nonunit_g_and_continued_fractions(self):
        out = subprocess.run([str(WORKER), "--raw", "--target", "375", "--g-max", str(10 ** 30)],
                             input="1 1\n", check=True, capture_output=True, text=True).stdout
        r = json.loads(out)
        self.assertGreater(r["convergents"], 0)
        self.assertEqual({(int(S), int(g)) for S, g, _ in r["solutions"]}, {(15, -5), (15, 10)})


@unittest.skipUnless(WORKER.exists(), "build first: make")
class XYModes(unittest.TestCase):
    H = 130
    KS = (15, 57, 1875, 7125, 12687)

    @classmethod
    def setUpClass(cls):
        cls.records = {(k, mode): run_worker(k, cls.H, mode=mode)
                       for k in cls.KS for mode in ("xy", "xy-half")}

    def test_original_equation_brute_force_agrees_in_both_modes(self):
        charts, signs, count = set(), set(), 0
        for (k, mode), records in self.records.items():
            expected = {pt for pt in original_points(k, 40)
                        if point_primitive(*pt) and in_unit_scope(pt, self.H)
                        and (mode != "xy-half" or pt[1] % 2)}
            hits = [r for r in records if r["type"] == "hit"]
            got = {xy_point(r) for r in hits if r["desired"] and abs(int(r["n"])) <= 40}
            self.assertEqual(got, expected, f"k={k} mode={mode}, missing={expected-got}, extra={got-expected}")
            count += len(expected)
            for r in hits:
                self.assertEqual(verify_hit(r, k)["mode"], mode)
                self.assertEqual(r["desired"], point_primitive(*xy_point(r)))
                self.assertEqual(abs(int(r["g"])), 1)
                if mode == "xy-half":
                    self.assertEqual(r["chart"], "half")
                    self.assertEqual(int(r["thue_q"]) % 2, 1)
                charts.add(r["chart"])
                signs.add(int(r["g"]))
        self.assertGreater(count, 5)
        self.assertEqual(charts, {"integer", "half"})
        self.assertEqual(signs, {-1, 1})

    def test_corrected_integer_primitivity_is_reported(self):
        hits = {xy_point(r): r for r in self.records[12687, "xy"] if r["type"] == "hit"}
        r = hits[(5, -10, 6)]
        self.assertEqual((r["d_num"], r["d_den"]), ("31", "10"))
        self.assertEqual(r["point_gcd"], "1")
        self.assertTrue(r["desired"])

    def test_conjugate_unit_certificate_not_principal_height_controls_inclusion(self):
        point = (-7, -7, 141)
        short = {xy_point(r) for r in run_worker(7125, 10, mode="xy-half") if r["type"] == "hit"}
        self.assertNotIn(point, short)  # displayed d=4 is small but its g is 7
        hits = [r for r in self.records[7125, "xy-half"] if r["type"] == "hit" and xy_point(r) == point]
        self.assertTrue(hits)
        for r in hits:
            self.assertEqual((r["d_num"], r["d_den"]), ("4", "1"))
            self.assertEqual((r["thue_p"], r["thue_q"], r["g"]), ("-113", "7", "1"))
            self.assertEqual(r["branch"], "conjugate")

    def test_previously_expected_nonunit1875_point_is_excluded(self):
        # (-29,-29,37) gives (n,x,y)=(-4,29,0), but its actual g=-2.
        self.assertFalse(in_unit_scope((-4, 58, 0), self.H))
        got = {xy_point(r) for r in self.records[1875, "xy"] if r["type"] == "hit"}
        self.assertNotIn((-4, 58, 0), got)

    def test_either_chart_is_sufficient(self):
        half = {xy_point(r) for r in self.records[15, "xy-half"] if r["type"] == "hit"}
        integer = {xy_point(r) for r in self.records[57, "xy"] if r["type"] == "hit" and r["chart"] == "integer"}
        self.assertIn((0, -1, 3), half)
        self.assertIn((0, -2, 6), integer)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Filters(unittest.TestCase):
    def test_filter_keeps_every_in_scope_known_d(self):
        for k in TEST_KS:
            for mode in ("both", "xy", "xy-half"):
                adm = Admissibility(k, mode)
                for rep in representations(k, 300):
                    for v in d_values_from_cubes(*rep, k):
                        pt = (v["n"], int(2 * v["x"]), int(2 * v["s"]))
                        if mode != "both" and not point_primitive(*pt):
                            continue
                        if mode == "xy-half" and pt[1] % 2 == 0:
                            continue
                        certs = branch_certificates(*pt)
                        for d, g, _ in (certs[:1] if mode == "both" else certs):
                            if abs(g) == 1:
                                self.assertTrue(adm(d.numerator, d.denominator), f"k={k} mode={mode} d={d}")

    def test_python_mirror_matches_worker_counts(self):
        for k, mode in ((375, "both"), (15, "both"), (375, "xy"), (12687, "xy"), (375, "xy-half"), (7125, "xy-half")):
            adm = Admissibility(k, mode)
            recs = run_worker(k, 100, mode=mode)
            counts = {r["h"]: (r["pairs"], r["admissible"]) for r in recs if r["type"] == "shell"}
            for h in range(1, 100):
                pairs = list(shell(h))
                self.assertEqual(counts[h], (len(pairs), sum(adm(p, q) for p, q in pairs)), f"k={k} mode={mode} h={h}")

    def test_pair_count_formula(self):
        self.assertEqual(pairs_in(1, 101), sum(4 * h - 1 for h in range(1, 101)))


@unittest.skipUnless(WORKER.exists() and shutil.which("gp"), "needs the worker and PARI/GP")
class PariCrossCheck(unittest.TestCase):
    """The untouched GENERAL raw solver must still match PARI, including nonunit g."""

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
        saw_nonunit = False
        for (k, p, q), line in zip(cases, pari):
            nums = [int(t) for t in line.replace("[", " ").replace("]", " ").replace(",", " ").replace(";", " ").split()]
            psol = {(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)}
            psol = {(S, g) for S, g in psol if g != 0 and abs(g) <= G}
            out = subprocess.run([str(WORKER), "--raw", "--target", str(k), "--g-max", str(G)],
                                 input=f"{p} {q}\n", check=True, capture_output=True, text=True).stdout
            wsol = {(int(a), int(b)) for a, b, _ in json.loads(out)["solutions"]}
            self.assertEqual(wsol, psol, f"k={k} d={p}/{q}")
            saw_nonunit |= any(abs(g) > 1 for _, g in wsol)
        self.assertTrue(saw_nonunit)


class TaskScope(unittest.TestCase):
    def task(self) -> dict:
        return {"schema": TASK_SCHEMA, "parameterization": PARAMETERIZATION, "g_values": [-1, 1],
                "campaign_id": "test", "task_id": "test-0", "k": 375, "h_start": 1, "h_stop": 10}

    def test_v2_scope_is_explicit_and_defaults_to_xy(self):
        self.assertEqual(PARAMETERIZATION, "ce375-dfirst-unit-g-both-charts-v2")
        for schema in (TASK_SCHEMA, PAGE_SCHEMA, STATUS_SCHEMA, CHECKPOINT_SCHEMA):
            self.assertTrue(schema.endswith("-v2"))
        self.assertEqual(validate_task(self.task())["mode"], "xy")

    def test_nonunit_legacy_and_missing_scopes_are_rejected(self):
        changes = ({"schema": "ce375-dfirst-task-v1"},
                   {"parameterization": "ce375-dfirst-thue-both-charts-v1"},
                   {"g_values": [1]}, {"g_values": [-5, 1]}, {"g_values": [1, -1]},
                   {"g_values": [-1, True]}, {"g_max_digits": 100})
        for change in changes:
            task = self.task() | change
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_task(task)
        for key in ("g_values", "parameterization"):
            task = self.task()
            del task[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                validate_task(task)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class Lifecycle(unittest.TestCase):
    def generate(self, root: Path, *, mode: str = "xy", k: int = 57, h_stop: int = 15,
                 task_hours: str = "1") -> dict:
        subprocess.run([sys.executable, str(ROOT / "make_campaign.py"), "--campaign-id", "test", "--k", str(k),
                        "--mode", mode, "--h-stop", str(h_stop), "--task-hours", task_hours,
                        "--output-dir", str(root / "camp")], check=True, capture_output=True, text=True)
        return json.loads((root / "camp" / "page.json").read_text())

    def run_task(self, root: Path, entry: dict, *, output: Path | None = None, check: bool = True):
        return subprocess.run([sys.executable, str(ROOT / "run_task.py"), "--task", str(root / "camp" / entry["file"]),
                               "--output-dir", str(output or root / "res" / entry["task_id"])],
                              check=check, capture_output=True, text=True)

    def collect(self, root: Path, results: Path, output: Path, *, check: bool = True):
        return subprocess.run([sys.executable, str(ROOT / "collect.py"), "--results", str(results),
                               "--page", str(root / "camp" / "page.json"), "--output-dir", str(output)],
                              check=check, capture_output=True, text=True)

    def test_default_campaign_scope_and_obsolete_cli_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            cmd = [sys.executable, str(ROOT / "make_campaign.py"), "--campaign-id", "c", "--h-stop", "3",
                   "--output-dir", str(tmp)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            page = json.loads((tmp / "page.json").read_text())
            self.assertEqual(page["mode"], "xy")
            self.assertEqual(page["g_values"], [-1, 1])
            self.assertEqual(page["schema"], PAGE_SCHEMA)
            self.assertNotIn("g_max_digits", page)
            old = subprocess.run(cmd + ["--g-max-digits", "100"], capture_output=True, text=True)
            self.assertNotEqual(old.returncode, 0)

    def test_unit_campaign_end_to_end_and_completed_resume(self):
        for mode in ("xy", "xy-half", "both"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                page = self.generate(tmp, mode=mode, k=7125, h_stop=130)
                for entry in page["tasks"]:
                    self.run_task(tmp, entry)
                    out = tmp / "res" / entry["task_id"]
                    for name, schema in (("task.json", TASK_SCHEMA), ("checkpoint.json", CHECKPOINT_SCHEMA), ("status.json", STATUS_SCHEMA)):
                        rec = json.loads((out / name).read_text())
                        self.assertEqual(rec["schema"], schema)
                        self.assertEqual(rec["g_values"], [-1, 1])
                        self.assertEqual(rec["parameterization"], PARAMETERIZATION)
                        self.assertNotIn("g_max_digits", rec)
                    before = (out / "hits.jsonl").read_text()
                    self.run_task(tmp, entry)
                    self.assertEqual((out / "hits.jsonl").read_text(), before)
                self.collect(tmp, tmp / "res", tmp / "col")
                summary = json.loads((tmp / "col" / "summary.json").read_text())
                self.assertEqual(summary["gaps"], [])
                self.assertEqual(summary["covered_heights"], [[1, 130]])
                self.assertEqual(summary["g_values"], [-1, 1])
                collected = [json.loads(line) for line in (tmp / "col" / "hits.jsonl").read_text().splitlines()]
                direct = [r for r in run_worker(7125, 130, mode=mode) if r["type"] == "hit"]
                key = as_point if mode == "both" else xy_point
                self.assertEqual({key(r) for r in collected}, {key(r) for r in direct})
                subprocess.run([sys.executable, str(ROOT / "verify_hits.py"), "--k", "7125", str(tmp / "col" / "hits.jsonl")],
                               check=True, capture_output=True, text=True)

    def test_interrupt_resume_then_collect_has_no_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            page = self.generate(tmp, mode="both", k=15, h_stop=900, task_hours="0.001")
            self.assertGreater(len(page["tasks"]), 1)
            entry = max(page["tasks"], key=lambda t: t["pairs"])
            out = tmp / "res" / entry["task_id"]
            proc = subprocess.Popen([sys.executable, str(ROOT / "run_task.py"), "--task", str(tmp / "camp" / entry["file"]),
                                     "--output-dir", str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            deadline = time.monotonic() + 30
            while not (out / "checkpoint.json").exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
            _, stderr = proc.communicate(timeout=60)
            self.assertEqual(proc.returncode, 0, stderr)
            status = json.loads((out / "status.json").read_text())
            if status["state"] == "partial":
                self.assertTrue((out / "continuation.task.json").exists())
            for task in page["tasks"]:
                self.run_task(tmp, task)
            self.collect(tmp, tmp / "res", tmp / "col")
            summary = json.loads((tmp / "col" / "summary.json").read_text())
            self.assertEqual(summary["covered_heights"], [[1, 900]])
            self.assertEqual(summary["gaps"], [])
            direct = {as_point(r) for r in run_worker(15, 900) if r["type"] == "hit"}
            collected = {as_point(json.loads(s)) for s in (tmp / "col" / "hits.jsonl").read_text().splitlines()}
            self.assertEqual(collected, direct)

    def test_resume_and_collector_reject_legacy_or_mixed_scope_without_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            page = self.generate(tmp)
            entry = page["tasks"][0]
            self.run_task(tmp, entry)
            source = tmp / "res" / entry["task_id"]
            mutations = (("checkpoint.json", {"schema": "ce375-dfirst-checkpoint-v1"}),
                         ("checkpoint.json", {"g_values": [-1, 1, 5]}),
                         ("task.json", {"g_max_digits": 100}),
                         ("task.json", {"mode": "xy-half"}),
                         ("status.json", {"parameterization": "ce375-dfirst-thue-both-charts-v1"}))
            for i, (filename, change) in enumerate(mutations):
                with self.subTest(filename=filename, change=change):
                    bad = tmp / f"bad{i}"
                    shutil.copytree(source, bad)
                    path = bad / filename
                    rec = json.loads(path.read_text()) | change
                    path.write_text(json.dumps(rec))
                    result = self.collect(tmp, bad, tmp / f"badcol{i}", check=False)
                    self.assertNotEqual(result.returncode, 0)
                    summary = json.loads((tmp / f"badcol{i}" / "summary.json").read_text())
                    self.assertEqual(summary["covered_heights"], [])
                    self.assertEqual(summary["gaps"], [[1, 15]])
                    self.assertEqual(summary["hits"], 0)
                    self.assertTrue(summary["errors"])
                    if filename in ("checkpoint.json", "task.json"):
                        self.assertNotEqual(self.run_task(tmp, entry, output=bad, check=False).returncode, 0)


if __name__ == "__main__":
    unittest.main()
