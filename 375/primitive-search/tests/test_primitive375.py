"""Independent arithmetic and regression checks for the primitive-375 adaptation."""
from __future__ import annotations

import json
from math import gcd
from pathlib import Path
import subprocess
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "bin" / "gap_worker"


def run_worker(*args: object, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run([str(WORKER), *(str(a) for a in args)], capture_output=True,
                            text=True, timeout=120)
    if check and result.returncode:
        raise AssertionError(result.stderr)
    return result


def records(output: str, kind: str) -> list[dict]:
    return [r for line in output.splitlines() if line.startswith("{")
            if (r := json.loads(line)).get("type") == kind]


def root_set(k: int, d: int) -> tuple[int, list[int]]:
    text = run_worker("--k", k, "--d-start", d, "--d-stop", d + 1, "--dump-roots").stdout
    values = list(map(int, text.strip().split()))
    if not values or values[0] != d:
        raise AssertionError(text)
    return values[1], values[2:]


def hit_set(output: str) -> set[tuple[int, int, int]]:
    result = set()
    for r in records(output, "hit"):
        xyz = tuple(sorted(int(r[name]) for name in ("x", "y", "z")))
        if sum(a ** 3 for a in xyz) != int(r["k"]):
            raise AssertionError("invalid three-cubes identity")
        if r["primitive"] != (gcd(gcd(abs(xyz[0]), abs(xyz[1])), abs(xyz[2])) == 1):
            raise AssertionError("invalid primitive flag")
        if int(r["height"]) != max(map(abs, xyz)):
            raise AssertionError("invalid reported height")
        result.add(xyz)
    return result


@unittest.skipUnless(WORKER.exists(), "build first: make")
class SingularRoots(unittest.TestCase):
    def test_small_prime_power_sets_against_direct_enumeration(self):
        for k, p, exponents in ((375, 5, range(1, 7)), (-375, 5, range(1, 7)),
                                (192, 2, range(1, 11)), (600, 2, range(1, 9)),
                                (600, 5, range(1, 5)), (114, 19, range(1, 4))):
            for e in exponents:
                d = p ** e
                K, actual = root_set(k, d)
                expected = [z for z in range(d) if (z ** 3 - K) % d == 0]
                self.assertEqual(actual, expected, (k, p, e))

    def test_large_singular_roots_have_correct_complete_counts(self):
        # Counts follow p-adic valuations and bijectivity of cubing on units for p=2,5.
        # They do not depend on the worker's lifting algorithm.
        cases = [(k, 5 ** e, 25) for k in (375, -375) for e in (11, 17, 25)]
        cases += [(192, 2 ** e, 16) for e in (7, 30, 57)]
        cases += [(600, 2 ** 40, 4), (600, 5 ** 12, 0)]
        for k, d, count in cases:
            K, roots = root_set(k, d)
            self.assertEqual(len(roots), count, (k, d))
            self.assertEqual(roots, sorted(set(roots)))
            self.assertTrue(all(0 <= z < d and (z ** 3 - K) % d == 0 for z in roots))

    def test_mixed_modulus_retains_all_singular_lifts(self):
        # Cubing modulo 2 has exactly one root for the odd right-hand side.
        d = 2 * 5 ** 24
        K, roots = root_set(375, d)
        self.assertEqual(len(roots), 25)
        self.assertEqual(len(set(roots)), 25)
        self.assertTrue(all((z ** 3 - K) % d == 0 for z in roots))


@unittest.skipUnless(WORKER.exists(), "build first: make")
class PrimitiveFiltering(unittest.TestCase):
    def test_scaled_three_solution_is_rejected(self):
        # 3=(-5)^3+4^3+4^3; scaling by 5 produces an imprimitive 375 representation.
        args = ("--k", 375, "--d-start", 5, "--d-stop", 6, "--ratio-max", 4)
        self.assertEqual(hit_set(run_worker(*args).stdout), {(-25, 20, 20)})
        self.assertEqual(hit_set(run_worker(*args, "--primitive-only").stdout), set())

    def test_generic_gcd_filter_also_handles_other_cube_factors(self):
        # This exercises the exact gcd filter without the 375-specific 5-adic shortcut.
        args = ("--k", 192, "--d-start", 4, "--d-stop", 5, "--ratio-max", 4)
        self.assertEqual(hit_set(run_worker(*args).stdout), {(-20, 16, 16)})
        self.assertEqual(hit_set(run_worker(*args, "--primitive-only").stdout), set())

    def test_local_primitive_skip_count(self):
        for k in (375, -375):
            out = run_worker("--k", k, "--d-start", 1, "--d-stop", 1001,
                             "--ratio-max", 4, "--primitive-only").stdout
            counts = records(out, "chunk")[0]["counters"]
            expected = sum(d % 3 != 0 and d % 5 == 0 and d % 125 != 0 for d in range(1, 1001))
            self.assertEqual(counts["d_skipped_primitive"], expected)
            self.assertEqual(counts["d_total"], counts["d_skipped_mod3"] +
                             counts["d_skipped_primitive"] + counts["d_no_roots"] + counts["d_live"])

    def test_primitive_root_filter_matches_exact_discriminants(self):
        for k in (375, -375):
            for d in (125, 5 ** 11):
                out = run_worker("--k", k, "--d-start", d, "--d-stop", d + 1,
                                 "--ratio-max", 1024, "--primitive-only",
                                 "--dump-candidates", 1000000).stdout
                rows = [list(map(int, line.split())) for line in out.splitlines()
                        if line and not line.startswith("{")]
                self.assertGreater(len(rows), 0)
                for dd, z, K, _two, _res in rows:
                    numerator = 4 * (z ** 3 - K) - dd ** 3
                    self.assertEqual(numerator % (3 * dd), 0)
                    self.assertIn((numerator // (3 * dd)) % 5, (1, 4))
                # Raw algebraic roots stay available even in primitive dump mode.
                raw = run_worker("--k", k, "--d-start", d, "--d-stop", d + 1,
                                 "--primitive-only", "--dump-roots").stdout
                self.assertEqual(len(raw.split()) - 2, 25)

    def test_known_primitive_cube_factor_records(self):
        known = {
            192: (2642071652785051, -2641770614653715, -184725770857094),
            600: (358469562197, -248487937861, -313190404198),
        }
        for k, xyz in known.items():
            self.assertEqual(sum(a ** 3 for a in xyz), k)
            self.assertEqual(gcd(gcd(abs(xyz[0]), abs(xyz[1])), abs(xyz[2])), 1)
            z = min(xyz, key=abs)
            xy = [a for a in xyz if a != z]
            d = abs(sum(xy))
            ratio = -(-abs(z) // d) + 1
            args = ("--k", k, "--d-start", d - 2, "--d-stop", d + 3,
                    "--ratio-max", ratio, "--primitive-only")
            self.assertIn(tuple(sorted(xyz)), hit_set(run_worker(*args).stdout))
            H = max(map(abs, xyz))
            self.assertIn(tuple(sorted(xyz)), hit_set(run_worker(*args, "--height-min", H - 1).stdout))
            self.assertNotIn(tuple(sorted(xyz)), hit_set(run_worker(*args, "--height-min", H).stdout))


@unittest.skipUnless(WORKER.exists(), "build first: make")
class HeightBounds(unittest.TestCase):
    def test_block_pruning_agrees_with_postfiltering(self):
        for k in (3, -3, 24, -24, 192, 375, 600):
            args = ("--k", k, "--d-start", 1, "--d-stop", 200, "--ratio-max", 64)
            all_hits = hit_set(run_worker(*args).stdout)
            for H in (5, 20, 25, 80, 1000):
                expected = {s for s in all_hits if max(map(abs, s)) > H}
                self.assertEqual(hit_set(run_worker(*args, "--height-min", H).stdout), expected, (k, H))

    def test_height_boundary_is_strict(self):
        args = ("--k", 375, "--d-start", 5, "--d-stop", 6, "--ratio-max", 4)
        self.assertEqual(hit_set(run_worker(*args, "--height-min", 24).stdout), {(-25, 20, 20)})
        self.assertEqual(hit_set(run_worker(*args, "--height-min", 25).stdout), set())

    def test_height_pruning_above_64_bits(self):
        lo, H = 185185185185185186, 10 ** 22
        out = run_worker("--k", 375, "--d-start", lo, "--d-stop", lo + 1000,
                         "--ratio-max", 4096, "--height-min", H,
                         "--dump-candidates", 200).stdout
        rows = [list(map(int, line.split())) for line in out.splitlines()
                if line and not line.startswith("{")]
        self.assertEqual(len(rows), 200)
        self.assertTrue(all(z >= 2 ** 64 for _, z, _, _, _ in rows))
        bound = H ** 3 - (H - lo) ** 3 - 375
        primes = (5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61)
        squares = {p: {x * x % p for x in range(p)} for p in primes}
        for d, z, K, two, res in rows:
            self.assertGreater(z ** 3, bound)
            self.assertEqual((z ** 3 - K) % d, 0)
            numerator = 4 * (z ** 3 - K) - d ** 3
            self.assertEqual(numerator % (3 * d), 0)
            delta = numerator // (3 * d)
            self.assertEqual(two, int(d % 2 == 0 or delta % 8 == 1))
            self.assertEqual(res, int(all(d % p == 0 or delta % p in squares[p] for p in primes)))

    def test_metadata_defaults_and_height_input_limits(self):
        args = ("--d-start", 1, "--d-stop", 3, "--ratio-max", 4)
        start = records(run_worker(*args, "--primitive-only", "--height-min", 10 ** 15).stdout, "start")[0]
        self.assertEqual(start["k"], "375")
        self.assertEqual(start["method"], "booker-sutherland-primitive-v1")
        self.assertTrue(start["primitive_only"])
        self.assertEqual(start["height_min"], str(10 ** 15))
        self.assertEqual(run_worker(*args, "--height-min", 2 ** 128 - 1).returncode, 0)
        for bad in (-1, "1.5", 2 ** 128):
            self.assertNotEqual(run_worker(*args, "--height-min", bad, check=False).returncode, 0)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class CheckpointTiming(unittest.TestCase):
    def test_deadline_flushes_before_huge_count_based_chunk(self):
        # The count threshold cannot possibly be reached in this interval; only the deadline
        # can cause a partial checkpoint. Its counters must equal an independent complete rerun.
        lo, hi = 1, 10 ** 9
        args = ("--k", 375, "--d-start", lo, "--d-stop", hi, "--ratio-max", 1024,
                "--primitive-only", "--chunk", 2 ** 60)
        started = time.monotonic()
        out = run_worker(*args, "--deadline-seconds", 1).stdout
        self.assertLess(time.monotonic() - started, 10.0)
        chunks, ends = records(out, "chunk"), records(out, "end")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(ends), 1)
        self.assertEqual(ends[0]["state"], "partial")
        stop = int(ends[0]["d_next"])
        self.assertTrue(lo < stop < hi)
        self.assertEqual((stop - lo) % (1 << 16), 0)
        self.assertEqual(int(chunks[0]["d_start"]), lo)
        self.assertEqual(int(chunks[0]["d_stop"]), stop)
        self.assertEqual(chunks[0]["counters"]["d_total"], stop - lo)
        replay = run_worker("--k", 375, "--d-start", lo, "--d-stop", stop,
                            "--ratio-max", 1024, "--primitive-only", "--chunk", 2 ** 60).stdout
        self.assertEqual(records(replay, "end")[0]["state"], "complete")
        self.assertEqual(records(replay, "chunk")[0]["counters"], chunks[0]["counters"])
        self.assertEqual(hit_set(replay), hit_set(out))


if __name__ == "__main__":
    unittest.main()
