"""Independent mathematical controls for the native exact lattice worker.

Run ``make test`` from the elkies-jahnel directory.  These tests need only
Python's standard library and the already-built GMP worker.  A small optional
C++ harness checks the private integer polynomial-root utility against an
independent exhaustive oracle; it introduces no production CLI test hooks.
"""
from __future__ import annotations

import json
from math import gcd
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ej375 as ej

WORKER = ROOT / "bin" / "elkies375_worker"
SOURCE = ROOT / "src" / "elkies375_worker.cpp"


def floor_cube_root(n: int) -> int:
    """Integer binary search, independent of GMP's root implementation."""
    if n < 0:
        raise ValueError("nonnegative root argument required")
    lo, hi, answer = 0, 1 << ((n.bit_length() + 2) // 3), 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if mid ** 3 <= n:
            answer, lo = mid, mid + 1
        else:
            hi = mid - 1
    return answer


def low_index(height: int, target: int) -> int:
    n = 3 * height * height - 3 * height + 1 - target
    a = floor_cube_root(n)
    a += a ** 3 != n
    return 5 * a // 2


def brute_shell(height: int, target: int, primitive: bool = False) -> set[tuple[int, int, int]]:
    """Exhaust all integer magnitudes, with no tangent, lattice, or residue filters."""
    found = set()
    for c in range(height, 2 * height):
        cube_to_b = {b ** 3: b for b in range(c)}
        for a in range(c):
            for residual_sign in (-1, 1):
                b = cube_to_b.get(c ** 3 + residual_sign * target - a ** 3)
                if b is None or a > b:
                    continue
                if primitive and gcd(gcd(a, b), c) != 1:
                    continue
                found.add((a, b, -c) if residual_sign == 1 else (-a, -b, c))
    return found


def triples(records: list[dict]) -> set[tuple[int, int, int]]:
    return {tuple(int(r[k]) for k in ("x", "y", "z"))
            for r in records if r["type"] == "hit"}


@unittest.skipUnless(WORKER.exists(), "build the native worker first: make")
class ExactLatticeMath(unittest.TestCase):
    def worker(self, height: int, target: int = 375, *, left: int | None = None,
               right: int | None = None, primitive: bool = True,
               scale: str = "11/2", extra: tuple[str, ...] = ()) -> list[dict]:
        left = low_index(height, target) if left is None else left
        right = 4 * height if right is None else right
        command = [str(WORKER), "--height", str(height), "--target", str(target),
                   "--index-start", str(left), "--index-stop", str(right),
                   "--tile-scale", scale, "--progress-every", "0", *extra]
        if not primitive:
            command.append("--include-nonprimitive")
        run = subprocess.run(command, capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        records = [json.loads(line) for line in run.stdout.splitlines()]
        self.assertEqual(records[0]["type"], "start")
        self.assertEqual(records[-1]["type"], "end")
        hit_records = [r for r in records if r["type"] == "hit"]
        self.assertEqual(len(hit_records), len(triples(records)), "duplicate canonical hit")
        for hit in hit_records:
            x, y, z = (int(hit[key]) for key in ("x", "y", "z"))
            self.assertEqual(x ** 3 + y ** 3 + z ** 3, target)
            self.assertEqual(hit["primitive"], gcd(gcd(x, y), z) == 1)
            self.assertEqual(int(hit["height"]), max(abs(x), abs(y), abs(z)))
            self.assertGreaterEqual(int(hit["height"]), height)
            self.assertLess(int(hit["height"]), 2 * height)
        return records

    def test_full_small_shells_against_independent_brute_force(self):
        # K=7 exercises the full coordinate lattice rather than the index-9
        # sublattice. K=7125 supplies additional signed and primitive controls.
        for height, target in ((25, 375), (64, 6), (128, 6), (128, 375),
                               (64, 7), (64, 24), (128, 7125)):
            with self.subTest(height=height, target=target):
                records = self.worker(height, target, primitive=False)
                self.assertEqual(triples(records), brute_shell(height, target))
                self.assertTrue(records[-1]["complete"])
                self.assertEqual(int(records[-1]["next_index"]), low_index(height, target))

    def test_primitive_negative_and_positive_controls(self):
        # The familiar 375 point must never be reported as a primitive discovery.
        all375 = self.worker(25, 375, primitive=False)
        self.assertEqual(triples(all375), {(20, 20, -25)})
        self.assertEqual(triples(self.worker(25, 375)), set())
        # A nonempty independent positive control prevents an empty search from
        # passing the primitive375 negative control accidentally.
        records = self.worker(64, 6)
        self.assertIn((-43, -58, 65), triples(records))
        self.assertEqual(triples(records), brute_shell(64, 6, primitive=True))

    def test_planner_upper_bound_preserves_full_small_shell_coverage(self):
        # Compare the tightened planning region with an independent exhaustive
        # search, not only with another invocation of the same lattice worker.
        for height, target in ((25, 375), (64, 6), (128, 6), (128, 375),
                               (64, 7), (64, 24), (128, 7125), (73, 1207)):
            with self.subTest(height=height, target=target):
                right = ej.upper_index(height, target)
                records = self.worker(height, target, right=right, primitive=False)
                self.assertTrue(records[-1]["complete"])
                self.assertEqual(triples(records), brute_shell(height, target))
                if (height, target) == (73, 1207):
                    # The exact rational endpoint j=(5H)*a/c=290 must be
                    # retained although the task's upper endpoint is excluded.
                    self.assertEqual(right, 291)
                    self.assertIn((58, 58, -73), triples(records))

    def test_global_top_endpoint_and_adjacent_ratio_partition(self):
        # At H=25, (20,20,25) lies exactly at a/c=4/5. Only the global
        # upper endpoint is included; the adjacent task must not duplicate it.
        lo = low_index(25, 375)
        top = self.worker(25, 375, left=99, right=100, primitive=False)
        below = self.worker(25, 375, left=lo, right=99, primitive=False)
        self.assertEqual(triples(top), {(20, 20, -25)})
        self.assertFalse(triples(top) & triples(below))
        self.assertEqual(triples(top) | triples(below), brute_shell(25, 375))

        # For H=65, the primitive6 control has the exact grid index
        # (5H)*43/65=215, an internal boundary owned by the task on its right.
        lo, mid, hi = low_index(65, 6), 215, 260
        full = self.worker(65, 6)
        left = self.worker(65, 6, left=lo, right=mid)
        right = self.worker(65, 6, left=mid, right=hi)
        self.assertNotIn((-43, -58, 65), triples(left))
        self.assertIn((-43, -58, 65), triples(right))
        self.assertFalse(triples(left) & triples(right))
        self.assertEqual(triples(left) | triples(right), triples(full))
        # Arbitrary partitions change enclosures: their lattice-point counts
        # are intentionally not required to be additive.

    def test_height_shell_endpoints(self):
        control = (-55, -235, 236)
        self.assertEqual(sum(x ** 3 for x in control), 6)
        self.assertNotIn(control, triples(self.worker(118, 6)))  # excluded 2H
        self.assertIn(control, triples(self.worker(236, 6)))     # included H

    def test_true_tile_boundary_continuation(self):
        height, target = 65, 6
        full = self.worker(height, target)
        first = self.worker(height, target, extra=("--max-tiles", "2"))
        end1 = first[-1]
        self.assertFalse(end1["complete"])
        self.assertEqual(end1["reason"], "tile_budget")
        self.assertEqual(end1["tiles"], 2)
        rest = self.worker(height, target, right=int(end1["next_index"]))
        self.assertTrue(rest[-1]["complete"])
        self.assertFalse(triples(first) & triples(rest))
        self.assertEqual(triples(first) | triples(rest), triples(full))
        self.assertEqual(int(end1["lattice_points"]) + int(rest[-1]["lattice_points"]),
                         int(full[-1]["lattice_points"]))
        self.assertEqual(end1["tiles"] + rest[-1]["tiles"], full[-1]["tiles"])

    def test_known_huge_scaled375_solution_is_not_primitive(self):
        # Five times Booker--Sutherland's known representation of 3. The
        # identity itself and the gcd are rechecked here with Python integers.
        a = 2363577467266635160
        b = 2849684105567817467545
        c = 2849684106109811903600
        expected = (-a, -b, c)
        self.assertEqual(sum(x ** 3 for x in expected), 375)
        self.assertEqual(gcd(gcd(a, b), c), 5)
        height = 2 * 10 ** 21
        index = 5 * height * a // c
        all_hits = self.worker(height, left=index, right=index + 1, primitive=False)
        self.assertEqual(triples(all_hits), {expected})
        primitive = self.worker(height, left=index, right=index + 1)
        self.assertEqual(triples(primitive), set())
        self.assertEqual(primitive[-1]["lattice_points"], all_hits[-1]["lattice_points"])

    def test_width_invariance_and_long_inner_interval_shortcut(self):
        for height, target in ((64, 6), (128, 6), (64, 7), (128, 7125)):
            expected = brute_shell(height, target)
            with self.subTest(height=height, target=target):
                for scale in ("1/2", "11/2", "1000"):
                    records = self.worker(height, target, primitive=False, scale=scale)
                    self.assertEqual(triples(records), expected)
                    if scale == "1000":
                        self.assertEqual(records[-1]["tiles"], 1)
                        self.assertGreater(int(records[-1]["lattice_points"]), 10000)

    def test_arbitrary_precision_height(self):
        height = 10 ** 40  # beyond 64- and 128-bit coordinate/index arguments
        records = self.worker(height, extra=("--max-tiles", "1"))
        end = records[-1]
        self.assertFalse(end["complete"])
        self.assertEqual(end["reason"], "tile_budget")
        self.assertEqual(end["tiles"], 1)
        self.assertGreaterEqual(int(end["next_index"]), low_index(height, 375))
        self.assertLess(int(end["next_index"]), 4 * height)

    def test_empty_completed_interval(self):
        lo = low_index(64, 6)
        records = self.worker(64, 6, left=lo, right=lo)
        self.assertTrue(records[-1]["complete"])
        self.assertEqual(records[-1]["tiles"], 0)
        self.assertEqual(records[-1]["lattice_points"], "0")

    def test_invalid_scope_is_rejected(self):
        valid_lo = low_index(25, 375)
        cases = [
            ("--height", "24", "--index-start", "1", "--index-stop", "2"),
            ("--height", "25", "--target", "0", "--index-start", "1", "--index-stop", "2"),
            ("--height", "25", "--target", "8", "--index-start", "1", "--index-stop", "2"),
            ("--height", "25", "--target", "380", "--index-start", "1", "--index-stop", "2"),
            ("--height", "1000", "--target", "3000001", "--index-start", "1", "--index-stop", "2"),
            ("--height", "25", "--index-start", str(valid_lo - 1), "--index-stop", "100"),
            ("--height", "25", "--index-start", str(valid_lo), "--index-stop", "101"),
            ("--height", "25", "--index-start", "99", "--index-stop", "98"),
            ("--height", "25", "--index-start", str(valid_lo), "--index-stop", "100", "--tile-scale", "0"),
            ("--height", "25", "--index-start", str(valid_lo), "--index-stop", "100", "--tile-scale", "1/0"),
            ("--height", "-25", "--index-start", "1", "--index-stop", "2"),
        ]
        for args in cases:
            with self.subTest(args=args):
                result = subprocess.run([str(WORKER), *args], capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(result.stderr.strip())
                self.assertNotIn('"complete":true', result.stdout)


class IntegerPolynomialRoots(unittest.TestCase):
    def test_small_exhaustive_and_large_constructed_roots(self):
        compiler = shlex.split(os.environ.get("CXX", "c++"))
        if not compiler or not shutil.which(compiler[0]):
            self.skipTest("C++ compiler unavailable for the private math harness")
        source_name = json.dumps(str(SOURCE))
        harness = r'''
#define main elkies_worker_cli_main
#include SOURCE_NAME
#undef main
#include <random>
int main() {
    std::mt19937 rng(375);
    for (int i=0; i<96; ++i) {
        Poly p;
        for (int j=0; j<4; ++j) p[j]=static_cast<long>(rng()%2001)-1000;
        if (i%4==0) p[3]=0;
        if (i%9==0) p[2]=0;
        if (i%13==0) p[1]=0;
        std::set<Z> got, expected;
        bool finite=integer_polynomial_roots(p,Z(200),got);
        if (!finite) {
            if (p[0]!=0 || p[1]!=0 || p[2]!=0 || p[3]!=0) return 1;
            continue;
        }
        for (Z n=0; n<=200; ++n) if(evaluate(p,n)==0) expected.insert(n);
        if (got!=expected) return 2;
    }
    for (int i=0; i<48; ++i) {
        Z a=static_cast<long>(rng()%250)-25;
        Z b=static_cast<long>(rng()%250)-25;
        Z c=static_cast<long>(rng()%250)-25;
        if(i%3==0) b=a;
        if(i%5==0) c=b;
        Poly p={-a*b*c,a*b+a*c+b*c,-a-b-c,Z(1)};
        if(i%2==0) for(Z& coefficient:p) coefficient=-coefficient;
        std::set<Z> got,expected;
        integer_polynomial_roots(p,Z(200),got);
        for(const Z& z:{a,b,c}) if(0<=z && z<=200) expected.insert(z);
        if(got!=expected) return 3;
    }
    Z a("100000000000000000000000000000000000000000000000000000001"),b=a+17,c=a+1000;
    Poly p={-a*b*c,a*b+a*c+b*c,-a-b-c,Z(1)};
    std::set<Z> roots; integer_polynomial_roots(p,2*c,roots);
    if(roots!=std::set<Z>{a,b,c}) return 4;
    Poly zero{};
    roots.clear();
    if(integer_polynomial_roots(zero,Z(1000),roots)) return 5;
    std::cout << "exact polynomial controls passed\n";
}
'''.replace("SOURCE_NAME", source_name)
        with tempfile.TemporaryDirectory(prefix="ej375-math-") as td:
            directory = Path(td)
            source, executable = directory / "root_check.cpp", directory / "root_check"
            source.write_text(harness, encoding="utf-8")
            compile_run = subprocess.run([*compiler, "-O2", "-std=c++17", str(source),
                                          "-lgmpxx", "-lgmp", "-o", str(executable)],
                                         capture_output=True, text=True, timeout=90)
            self.assertEqual(compile_run.returncode, 0, compile_run.stderr)
            run = subprocess.run([str(executable)], capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, f"math harness exit {run.returncode}: {run.stderr}")
            self.assertIn("exact polynomial controls passed", run.stdout)


if __name__ == "__main__":
    unittest.main()
