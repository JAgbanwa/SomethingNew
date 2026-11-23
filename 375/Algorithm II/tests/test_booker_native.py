"""Native gap arithmetic, bounded coverage, interruption and protocol checks."""
from __future__ import annotations

import json
from math import gcd, isqrt
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from booker_native import (BSWorkerError, COUNTERS, D_STOP_MAX, METHOD, RATIO_MAX,
                          WORKER_VERSION, build_worker, iter_gap, validate_gap)
from booker_sutherland import search


def hits(records):
    return {tuple(int(r[name]) for name in ("x", "y", "z"))
            for r in records if r["type"] == "hit"}


def counts(records):
    result = {key: 0 for key in COUNTERS}
    for record in records:
        if record["type"] == "chunk":
            for key in COUNTERS:
                result[key] += int(record["counters"][key])
    return result


def native_region(triple, lower, upper, ratio):
    x, y, z = triple
    gap = abs(x + y)
    return (x >= y and lower <= gap < upper and (x + y) * z < 0
            and 3847 * gap // 1000 <= abs(z) <= ratio * gap)


class NativeArithmetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker = build_worker()

    def test_full_native_region_matches_python_reference(self):
        lower, upper, ratio = 1, 61, 16
        for target in (-375, 3, 6, 15, 24, 375, 7125):
            for primitive in (False, True):
                with self.subTest(target=target, primitive=primitive):
                    expected = {triple for triple in search(
                        target, lower, upper - 1, -ratio * (upper - 1),
                        ratio * (upper - 1), primitive_only=primitive)
                        if native_region(triple, lower, upper, ratio)}
                    actual = list(iter_gap(lower, upper, ratio, primitive=primitive,
                                           target=target, worker=self.worker))
                    self.assertEqual(hits(actual), expected)
                    self.assertEqual(actual[-1]["state"], "complete")

    def test_independent_coordinate_enumeration(self):
        bound, lower, upper, ratio = 70, 1, 141, 40
        cube_to_integer = {a ** 3: a for a in range(-bound, bound + 1)}
        for target in (6, 15, 375):
            expected = set()
            for x in range(-bound, bound + 1):
                for y in range(-bound, x + 1):
                    z = cube_to_integer.get(target - x ** 3 - y ** 3)
                    if z is not None and native_region((x, y, z), lower, upper, ratio):
                        expected.add((x, y, z))
            rows = list(iter_gap(lower, upper, ratio, target=target,
                                 primitive=False, worker=self.worker))
            actual = {xyz for xyz in hits(rows) if max(map(abs, xyz)) <= bound}
            self.assertEqual(actual, expected)
            self.assertTrue(actual, "independent comparison must include positive controls")

    def test_375_tie_and_strict_primitive_output(self):
        rows = list(iter_gap(1, 100, 16, primitive=False, worker=self.worker))
        self.assertIn((20, -25, 20), hits(rows))
        self.assertEqual(hits(iter_gap(1, 100, 16, worker=self.worker)), set())
        # Here v_2(D)=4, so the primitive gap filter does not discard the gap.
        # The exact hit gcd must still remove this nonprimitive representation.
        target = 44 ** 3 + (-28) ** 3 + (-64) ** 3
        self.assertEqual(hits(iter_gap(16, 17, 4, target=target, primitive=False,
                                      worker=self.worker)), {(44, -28, -64)})
        self.assertEqual(hits(iter_gap(16, 17, 4, target=target,
                                      worker=self.worker)), set())

    def test_large_known_target_three_representation(self):
        triple = (569936821221962380720, -569936821113563493509,
                  -472715493453327032)
        gap = abs(triple[0] + triple[1])
        ratio = (abs(triple[2]) + gap - 1) // gap
        rows = list(iter_gap(gap, gap + 1, ratio, target=3, worker=self.worker))
        self.assertIn(triple, hits(rows))
        self.assertGreater(max(map(abs, triple)), 2 ** 64)

    def test_prime_power_roots_against_residue_enumeration(self):
        # The native diagnostic uses the sign K fixed by D modulo three.
        process = subprocess.run([str(self.worker), "--d-start", "1", "--d-stop", "1001",
                                  "--k", "375", "--dump-roots"],
                                 capture_output=True, text=True, check=True)
        observed = {}
        for line in process.stdout.splitlines():
            gap, target, *roots = map(int, line.split())
            expected = [r for r in range(gap) if (r ** 3 - target) % gap == 0]
            self.assertEqual(roots, expected, gap)
            observed[gap] = roots
        self.assertEqual(set(observed), {d for d in range(1, 1001) if d % 3})
        self.assertEqual(len(observed[125]), 25)
        self.assertEqual(len(observed[625]), 25)

    def test_adjacent_tasks_preserve_hits_and_counters(self):
        options = {"target": 6, "primitive": True, "worker": self.worker}
        full = list(iter_gap(1, 20_001, 32, **options))
        left = list(iter_gap(1, 7777, 32, **options))
        right = list(iter_gap(7777, 20_001, 32, **options))
        self.assertEqual(hits(full), hits(left) | hits(right))
        self.assertFalse(hits(left) & hits(right))
        self.assertEqual(counts(full), {k: counts(left)[k] + counts(right)[k] for k in COUNTERS})

    def test_actual_deadline_returns_only_a_completed_prefix(self):
        rows = list(iter_gap(1, 100_000_001, 1024, deadline_seconds=1, worker=self.worker))
        self.assertEqual(rows[-1]["state"], "partial")
        self.assertEqual(rows[-1]["reason"], "deadline")
        next_gap = int(rows[-1]["d_next"])
        self.assertLess(next_gap, 100_000_001)
        self.assertEqual(counts(rows)["d_total"], next_gap - 1)

    def test_actual_signal_prefix_and_resume_equal_uninterrupted_run(self):
        start, stop, ratio = 1, 1_048_577, 1024
        command = [str(self.worker), "--d-start", str(start), "--d-stop", str(stop),
                   "--ratio-max", str(ratio), "--chunk", "65536", "--primitive"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8")
        prefix = []
        try:
            assert process.stdout is not None
            for line in process.stdout:
                record = json.loads(line)
                prefix.append(record)
                if record["type"] == "chunk":
                    process.send_signal(signal.SIGINT)
                    break
            # Continue through the same TextIOWrapper: communicate() can use
            # the raw descriptor and lose lines already buffered by readline.
            output = process.stdout.read()
            process.wait(timeout=10)
            assert process.stderr is not None
            errors = process.stderr.read()
            prefix.extend(json.loads(line) for line in output.splitlines())
            self.assertEqual(process.returncode, 0, errors)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
        self.assertEqual(prefix[-1]["state"], "partial")
        self.assertEqual(prefix[-1]["reason"], "signal")
        next_gap = int(prefix[-1]["d_next"])
        self.assertEqual(counts(prefix)["d_total"], next_gap - start)
        tail = list(iter_gap(next_gap, stop, ratio, worker=self.worker))
        full = list(iter_gap(start, stop, ratio, worker=self.worker))
        self.assertEqual(hits(full), hits(prefix) | hits(tail))
        self.assertEqual(counts(full), {k: counts(prefix)[k] + counts(tail)[k] for k in COUNTERS})
        # Replay the real signal stream through the strict interface as well.
        with tempfile.TemporaryDirectory(prefix="bs-signal-", dir=ROOT / "build") as directory:
            fake = Path(directory) / "worker"
            fake.write_text("#!/usr/bin/env python3\nimport json\n"
                            + f"rows = {prefix!r}\n"
                            + "for row in rows: print(json.dumps(row), flush=True)\n",
                            encoding="utf-8")
            fake.chmod(0o755)
            self.assertEqual(list(iter_gap(start, stop, ratio, worker=fake)), prefix)


class NativeContract(unittest.TestCase):
    def records(self):
        counters = {key: 0 for key in COUNTERS}
        counters.update(d_total=3, d_skipped_mod3=1, d_live=2, roots=2)
        return [{"type": "start", "engine": "booker-sutherland", "version": WORKER_VERSION,
                 "method": METHOD, "k": "375", "d_start": "1", "d_stop": "4",
                 "ratio_max": "4", "chunk": "65536", "deadline_seconds": "0",
                 "primitive": True, "square_sieve": True,
                 "z_lo": "floor(3847*d/1000)", "pair_sum_sign": "opposite_z",
                 "sieve_limit": "1", "setup_seconds": 0.1},
                {"type": "chunk", "d_start": "1", "d_stop": "4", "seconds": 0.1,
                 "counters": counters},
                {"type": "end", "state": "complete", "d_next": "4", "reason": "complete"}]

    def run_fake(self, rows, exit_code=0):
        (ROOT / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="bs-contract-", dir=ROOT / "build") as directory:
            worker = Path(directory) / "worker"
            worker.write_text("#!/usr/bin/env python3\nimport json\n"
                              + f"rows = {rows!r}\n"
                              + "for row in rows: print(json.dumps(row), flush=True)\n"
                              + f"raise SystemExit({exit_code})\n", encoding="utf-8")
            worker.chmod(0o755)
            return list(iter_gap(1, 4, 4, worker=worker))

    def test_valid_contract_and_missing_terminal(self):
        self.assertEqual(self.run_fake(self.records())[-1]["state"], "complete")
        with self.assertRaises(BSWorkerError):
            self.run_fake(self.records()[:-1])

    def test_wrong_scope_gaps_counters_and_terminal_rejected(self):
        for index, key, value in ((0, "k", "3"), (0, "ratio_max", "5"),
                                  (1, "d_start", "2"), (2, "d_next", "3"),
                                  (2, "state", "partial")):
            rows = self.records()
            rows[index][key] = value
            with self.subTest(key=key), self.assertRaises(BSWorkerError):
                self.run_fake(rows)
        rows = self.records()
        rows[1]["counters"]["d_total"] = 4
        with self.assertRaises(BSWorkerError):
            self.run_fake(rows)
        rows = self.records()
        rows[1]["counters"]["hits"] = 1
        with self.assertRaises(BSWorkerError):
            self.run_fake(rows)

    def test_nonzero_exit_trailing_record_and_forged_hit_rejected(self):
        with self.assertRaises(BSWorkerError):
            self.run_fake(self.records(), exit_code=2)
        with self.assertRaises(BSWorkerError):
            self.run_fake(self.records() + [{"type": "surprise"}])
        rows = self.records()
        rows.insert(1, {"type": "hit", "k": "375", "method": METHOD,
                        "x": "20", "y": "-25", "z": "20", "d": "5", "primitive": True})
        with self.assertRaises(BSWorkerError):
            self.run_fake(rows)

    def test_limits_and_invalid_inputs_before_launch(self):
        self.assertEqual(validate_gap(10 ** 12, 10 ** 12 + 65536)["d_start"], 10 ** 12)
        for args in ((0, 1, 4), (1, 1, 4), (1, D_STOP_MAX + 1, 4),
                     (1, 2, 3), (1, 2, RATIO_MAX + 1), (True, 2, 4),
                     (1, D_STOP_MAX, RATIO_MAX)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                validate_gap(*args)
        for options in ({"primitive": 1}, {"deadline_seconds": -1}, {"chunk": 0},
                        {"target": 42.0}, {"target": 0}, {"target": 1029}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                list(iter_gap(1, 2, 4, worker="/does/not/exist", **options))


if __name__ == "__main__":
    unittest.main()
