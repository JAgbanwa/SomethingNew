"""End-to-end regression checks for the integrated runner and native q sieve."""
from __future__ import annotations

import json
import math
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
from q_sieve import forbidden_primes, reject_q
from run_task import (PARAMETERIZATION, SCHEMA, candidate_index, iter_candidates,
                      task_identity, validate_task)
from parameter_space import GeneralAQ


class QSieveIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shlex.split(os.environ.get("CXX", "g++"))
        if not compiler or not shutil.which(compiler[0]):
            raise unittest.SkipTest("a C++17 compiler is required")
        cls.build = tempfile.TemporaryDirectory()
        cls.worker = Path(cls.build.name) / "cf_worker"
        subprocess.run([
            *compiler, *shlex.split(os.environ.get("CPPFLAGS", "")),
            *shlex.split(os.environ.get("CXXFLAGS", "-O2 -Wall -Wextra")),
            "-std=c++17", str(ROOT / "src/cf_worker.cpp"), "-o", str(cls.worker),
            *shlex.split(os.environ.get("LDFLAGS", "")),
            *shlex.split(os.environ.get("LDLIBS", "-lgmpxx -lgmp")),
        ], check=True, capture_output=True, text=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def invoke(self, pairs, *options):
        proc = subprocess.run([str(self.worker), *options],
                              input="".join(f"{a} {q}\n" for a, q in pairs),
                              text=True, capture_output=True, check=True, timeout=20)
        rows = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(len(rows), len(pairs))
        return rows

    def task(self, q_min=7, q_max=7, policy=True):
        search = dict(n_min="1", n_max="80", x_min="1", x_max="120", signs="all")
        if policy is not None:
            search["require_integer_sqrt"] = policy
        task = dict(schema=SCHEMA, parameterization=PARAMETERIZATION,
                    campaign_id="q-sieve-regression", search=search,
                    fibers=dict(a_values=["1"], q_min=str(q_min), q_max=str(q_max)),
                    slice=dict(start="0", stop=str((q_max-q_min)//2+1)),
                    execution=dict(time_limit_seconds=20, precision_bits=512,
                                   checkpoint_seconds=1))
        task["task_id"] = task_identity(task)
        return task

    def run_task(self, directory, task, worker=None):
        root = Path(directory)
        path = root / "task.json"
        path.write_text(json.dumps(task))
        proc = subprocess.run([sys.executable, str(ROOT / "run_task.py"),
                               "--task", str(path), "--output-dir", str(root / "output"),
                               "--worker", str(worker or self.worker)],
                              text=True, capture_output=True, timeout=30)
        status_path = root / "output/status.json"
        status = json.loads(status_path.read_text()) if status_path.exists() else None
        return proc, status

    def fake_worker(self, directory, fail_once=False):
        path = Path(directory) / "fake_worker.py"
        marker = str(Path(directory) / "already_failed")
        path.write_text("#!" + sys.executable + "\n" +
            "import json, pathlib, sys\n" +
            f"marker = pathlib.Path({marker!r})\n" +
            f"fail_once = {fail_once!r}\n" +
            "for line in sys.stdin:\n"
            "    a, q = line.split()\n"
            "    fail = not fail_once or not marker.exists()\n"
            "    marker.touch()\n"
            "    row = dict(a=a, q=q, status='error' if fail else 'complete',\n"
            "               parameterization='absolute-slope-a-over-q-v1',\n"
            "               signs='all', congruences_enforced=True,\n"
            "               integer_sqrt_required=True, excluded_by_congruence=False,\n"
            "               excluded_by_bounds=False, convergents=0, hits=[])\n"
            "    print(json.dumps(row), flush=True)\n")
        path.chmod(0o755)
        return path

    def test_every_obstructing_prime_returns_certified_empty(self):
        pairs = [(1, p) for p in forbidden_primes()]
        for signs in ("all", "pp", "pn", "np", "nn"):
            for row in self.invoke(pairs, "--signs", signs):
                self.assertEqual(row["status"], "complete", row)
                self.assertTrue(row["excluded_by_q_sieve"], row)
                self.assertTrue(row["excluded_by_congruence"], row)
                self.assertFalse(row["excluded_by_bounds"], row)
                self.assertEqual(row["hits"], [])
                self.assertEqual(row["convergents"], 0)
                self.assertEqual(row["precision_bits"], 0)

    def test_input_validation_precedes_sieve(self):
        rows = self.invoke([(7, 7), (7, 49), (0, 7), (2, 7), (-1, 7), (1, 7)])
        self.assertEqual([r["status"] for r in rows], ["error"] * 5 + ["complete"])

    def test_exceptional_primes_not_sieved(self):
        for row in self.invoke([(1, q) for q in (5, 13, 25, 65, 169, 5**10 * 13**7)]):
            self.assertEqual(row["status"], "complete", row)
            self.assertFalse(row["excluded_by_q_sieve"], row)

    def test_large_denominator_and_relaxed_congruences(self):
        q = 7 * (10**54 + 1)
        row = self.invoke([(1, q)], "--relax-congruences")[0]
        self.assertEqual(row["status"], "complete", row)
        self.assertTrue(row["excluded_by_q_sieve"])
        self.assertFalse(row["congruences_enforced"])
        self.assertEqual(row["q"], str(q))

    def test_actual_rational_solution_with_obstructing_prime_79_survives(self):
        pair = (7438954542449, 1173073086419625)
        self.assertEqual(pair[1] % 79, 0)
        options = ("--n-min", "5877899", "--n-max", "5877899",
                   "--x-min", "11122866225", "--x-max", "11122866225",
                   "--relax-congruences")
        rational = self.invoke([pair], *options, "--allow-rational-sqrt")[0]
        self.assertEqual(rational["status"], "complete", rational)
        self.assertFalse(rational["excluded_by_q_sieve"])
        self.assertEqual([(h["n"], h["x"]) for h in rational["hits"]],
                         [("-5877899", "11122866225")])
        integral = self.invoke([pair], *options, "--integer-sqrt")[0]
        self.assertEqual(integral["status"], "complete")
        self.assertTrue(integral["excluded_by_q_sieve"])
        self.assertEqual(integral["hits"], [])

    def test_obstructed_old_precision_fixture_is_proven_empty(self):
        row = self.invoke([(1, 10000000001)], "--precision-bits", "64",
                          "--max-precision-bits", "64", "--relax-congruences")[0]
        self.assertEqual(10000000001 % 3541, 0)
        self.assertEqual(row["status"], "complete")
        self.assertTrue(row["excluded_by_q_sieve"])
        self.assertEqual(row["convergents"], 0)

    def test_surviving_precision_fixture_still_errors_and_refines(self):
        pairs = [(1, 10000000009)]
        low = self.invoke(pairs, "--precision-bits", "64", "--max-precision-bits", "64",
                          "--relax-congruences")[0]
        self.assertEqual(low["status"], "error", low)
        self.assertIn("precision cap", low["error"])
        high = self.invoke(pairs, "--precision-bits", "64", "--relax-congruences")[0]
        self.assertEqual(high["status"], "complete", high)
        self.assertFalse(high["excluded_by_q_sieve"])
        self.assertGreater(high["precision_bits"], 64)

    def test_runner_sieves_before_dispatch_and_completes_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            proc, status = self.run_task(directory, self.task(), self.fake_worker(directory))
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue(status["complete"])
            self.assertEqual(status["output_coverage"], dict(start="0", stop="1"))
            counters = status["counters_this_invocation"]
            self.assertEqual(counters["q_sieve_excluded"], "1")
            self.assertEqual(counters["congruence_excluded"], "1")
            self.assertEqual(counters["fibers_completed"], "0")
            self.assertFalse((Path(directory) / "already_failed").exists())
            checkpoint = json.loads((Path(directory) / "output/checkpoint.json").read_text())
            self.assertEqual(checkpoint["next_index"], "1")
            self.assertFalse((Path(directory) / "output/continuation.task.json").exists())

    def test_explicit_and_legacy_rational_tasks_are_not_sieved(self):
        for policy in (False, None):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as directory:
                proc, status = self.run_task(directory, self.task(policy=policy), self.fake_worker(directory))
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(status["state"], "error")
                self.assertEqual(status["next_index"], "0")
                self.assertEqual(status["counters_this_invocation"]["q_sieve_excluded"], "0")
                self.assertTrue((Path(directory) / "already_failed").exists())

    def test_mixed_denominators_keep_original_indices(self):
        task = self.task(5, 45)
        expected = sum(q % 3 != 0 and reject_q(q, require_integer_sqrt=True)
                       for q in range(5, 46, 2))
        with tempfile.TemporaryDirectory() as directory:
            proc, status = self.run_task(directory, task)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue(status["complete"])
            self.assertEqual(status["next_index"], "21")
            self.assertEqual(status["output_coverage"], dict(start="0", stop="21"))
            self.assertEqual(status["counters_this_invocation"]["q_sieve_excluded"], str(expected))

    def test_general_aq_retains_rank_and_coverage(self):
        task = self.task()
        task["search"].update(n_min="2", n_max="10", x_min="130", x_max="500")
        task["fibers"] = dict(mode="general-aq-v1", q_min="1", q_max="100")
        space = GeneralAQ(task["search"], 1, 100)
        task["slice"]["stop"] = str(space.count)
        task["task_id"] = task_identity(task)
        parsed = validate_task(task)
        pairs = list(iter_candidates(parsed, 0, space.count))
        self.assertEqual(pairs[:3], [(1, 5), (1, 7), (5, 7)])
        self.assertEqual([candidate_index(parsed, a, q) for a, q in pairs], list(range(space.count)))
        expected = sum(math.gcd(a, q) == 1 and reject_q(q, require_integer_sqrt=True)
                       for a, q in pairs)
        with tempfile.TemporaryDirectory() as directory:
            proc, status = self.run_task(directory, task)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue(status["complete"])
            self.assertEqual(status["next_index"], str(space.count))
            self.assertEqual(status["counters_this_invocation"]["q_sieve_excluded"], str(expected))

    def test_resume_keeps_coverage_of_already_sieved_indices(self):
        task = self.task(7, 13)
        with tempfile.TemporaryDirectory() as directory:
            worker = self.fake_worker(directory, fail_once=True)
            proc, first = self.run_task(directory, task, worker)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(first["next_index"], "2")  # q=7 sieved, q=9 pre-existing exclusion.
            continuation = json.loads((Path(directory) / "output/continuation.task.json").read_text())
            self.assertEqual(continuation["resume_index"], "2")
            proc, second = self.run_task(directory, continuation, worker)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue(second["complete"])
            self.assertEqual(second["invocation_coverage"], dict(start="2", stop="4"))
            self.assertEqual(second["output_coverage"], dict(start="0", stop="4"))
            self.assertFalse((Path(directory) / "output/continuation.task.json").exists())

    def test_non_coprime_filter_keeps_precedence(self):
        task = self.task(49, 49)
        task["fibers"]["a_values"] = ["7"]
        task["task_id"] = task_identity(task)
        with tempfile.TemporaryDirectory() as directory:
            proc, status = self.run_task(directory, task)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertEqual(status["counters_this_invocation"]["non_coprime_skipped"], "1")
            self.assertEqual(status["counters_this_invocation"]["q_sieve_excluded"], "0")

    def test_worker_hash_pin_still_rejects_changed_binary(self):
        task = self.task()
        task["expected_worker_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            proc, status = self.run_task(directory, task)
            self.assertEqual(proc.returncode, 2)
            self.assertIsNone(status)
            self.assertIn("binary pinned", proc.stderr)

    def test_collector_accepts_sieve_subset_without_double_counting(self):
        from collector import checked_status
        task = self.task()
        with tempfile.TemporaryDirectory() as directory:
            proc, status = self.run_task(directory, task)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertEqual(checked_status(status, task, task), ((0, 1), (0, 1)))
            del status["counters_this_invocation"]["q_sieve_excluded"]
            self.assertEqual(checked_status(status, task, task), ((0, 1), (0, 1)))

    def test_collector_rejects_sieve_count_exceeding_parent_category(self):
        from collector import checked_status
        task = self.task()
        with tempfile.TemporaryDirectory() as directory:
            _, status = self.run_task(directory, task)
            status["counters_this_invocation"]["q_sieve_excluded"] = "2"
            with self.assertRaisesRegex(ValueError, "exceeds congruence"):
                checked_status(status, task, task)

    def test_collector_rejects_sieve_claim_for_rational_task(self):
        from collector import checked_status
        task = self.task(policy=False)
        with tempfile.TemporaryDirectory() as directory:
            proc, status = self.run_task(directory, task)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            status["counters_this_invocation"]["q_sieve_excluded"] = "1"
            status["counters_this_invocation"]["congruence_excluded"] = "1"
            with self.assertRaisesRegex(ValueError, "rational-square-root"):
                checked_status(status, task, task)

    def test_build_and_runtime_packaging_include_sieve(self):
        self.assertIn("bin/cf_worker: src/cf_worker.cpp src/q_sieve.hpp", (ROOT / "Makefile").read_text())
        runtime_copy = [line for line in (ROOT / "Dockerfile").read_text().splitlines()
                        if line.startswith("COPY campaign.py ")]
        self.assertEqual(len(runtime_copy), 1)
        self.assertIn("q_sieve.py", runtime_copy[0])


if __name__ == "__main__":
    unittest.main()
