"""Budget boundaries, restart accounting, and real process-tree termination."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import d_campaign
from d_budget import Ledger, NANOSECONDS, limit_nanoseconds, locked_ledger
from dfirst_common import pairs_in_shells
from run_d_campaign import execute_attempt, load_page, run
from run_task import load_json


class BudgetPlanningTests(unittest.TestCase):
    def generate(self, directory, *options):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            d_campaign.main(["--campaign-id", "budget-test", "--output-dir", str(directory), *options])
        return json.loads(output.getvalue())

    def test_default_plan_has_no_coordinate_rectangle_and_reserves_other_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "tasks"
            plan = self.generate(directory, "--plan-only")
            self.assertFalse(directory.exists())
            self.assertEqual(plan["budget"]["core_hours"], "1800")
            self.assertEqual(plan["budget"]["planned_core_hours"], "1600")
            self.assertEqual(plan["shells"], {"start": "1", "stop": "800000"})
            self.assertLessEqual(plan["predicted_core_hours"], 1600)
            self.assertNotIn("n_min", json.dumps(plan))
            self.assertEqual(plan["budget"]["limit_ns"], 1800 * 3600 * NANOSECONDS)

    def test_pair_budget_inversion_does_not_round_past_boundary(self):
        for start in (1, 3, 1000):
            for end in (start + 1, start + 10, start + 100):
                count = pairs_in_shells(start, end)
                self.assertEqual(d_campaign.stop_for_pairs(start, count), end)
                self.assertEqual(d_campaign.stop_for_pairs(start, count - 1), end - 1)

    def test_rejects_excess_height_and_budget_and_nonfinite_rates(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            for options in (("--h-stop", "950001"), ("--budget-core-hours", "2000"),
                            ("--us-per-pair", "nan"), ("--planned-core-hours", "Infinity"),
                            ("--budget-core-hours", "-1")):
                with self.assertRaises(SystemExit):
                    self.generate(Path(tmp) / "tasks", *options)
            self.assertFalse((Path(tmp) / "tasks").exists())

    def test_generated_tasks_are_pinned_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "tasks"
            self.generate(directory, "--h-stop", "20")
            page, tasks, limit = load_page(directory / "page.json")
            self.assertEqual(limit, 1800 * 3600 * NANOSECONDS)
            self.assertEqual(len(tasks), 1)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.generate(directory, "--h-stop", "20")
            path, task = tasks[0]
            task["seconds"] -= 1
            path.write_text(json.dumps(task))
            with self.assertRaisesRegex(ValueError, "hashes"):
                load_page(directory / "page.json")


class BudgetLedgerTests(unittest.TestCase):
    def test_failed_attempts_charge_and_reservations_cannot_exceed_remaining(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with locked_ledger(output, "page-a", 100 * NANOSECONDS) as ledger:
                first = ledger.reserve(70, "t", "task.json", "attempt-0")
                self.assertIsNotNone(first)
                self.assertIsNone(ledger.reserve(31, "t", "task.json", "attempt-1"))
                ledger.settle(first, 25 * NANOSECONDS, returncode=1, task_state="error")
                self.assertEqual(ledger.remaining_ns, 75 * NANOSECONDS)
                with self.assertRaises(ValueError):
                    ledger.settle(first, 0)
            with locked_ledger(output, "page-a", 100 * NANOSECONDS) as ledger:
                self.assertEqual(ledger.data["charged_ns"], 25 * NANOSECONDS)
                self.assertIsNone(ledger.reserve(76, "t", "task.json", "attempt-1"))

    def test_restart_does_not_refund_unknown_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with locked_ledger(output, "page-a", 100 * NANOSECONDS) as ledger:
                ledger.reserve(70, "t", "task.json", "attempt-0")
            with self.assertRaisesRegex(ValueError, "unsettled"):
                with locked_ledger(output, "page-a", 100 * NANOSECONDS):
                    pass
            recorded = load_json(output / "budget.json")
            self.assertEqual(recorded["attempts"][0]["reserved_ns"], 70 * NANOSECONDS)
            self.assertEqual(recorded["attempts"][0]["state"], "reserved")

    def test_changed_scope_and_concurrent_controllers_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with locked_ledger(output, "page-a", 100 * NANOSECONDS):
                with self.assertRaisesRegex(ValueError, "lock"):
                    with locked_ledger(output, "page-a", 100 * NANOSECONDS):
                        pass
            with self.assertRaisesRegex(ValueError, "another page"):
                with locked_ledger(output, "page-b", 100 * NANOSECONDS):
                    pass

    def test_deleted_ledger_does_not_reset_used_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "attempt-000000").mkdir()
            with self.assertRaisesRegex(ValueError, "refusing to reset"):
                with locked_ledger(output, "page-a", 100 * NANOSECONDS):
                    pass


@unittest.skipUnless(hasattr(os, "sched_setaffinity"), "Linux CPU affinity required")
class BudgetExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def fake_worker(self, mode="complete"):
        path = self.base / f"worker-{mode}"
        path.write_text(f"#!{sys.executable}\n" + r'''
import argparse, json, os, sys
from pathlib import Path
Path(__file__).with_suffix('.group').write_text(json.dumps(
    [os.getpgrp(), os.getpgid(os.getppid()), len(os.sched_getaffinity(0))]))
parser = argparse.ArgumentParser()
parser.add_argument('--h-start', type=int)
parser.add_argument('--h-stop', type=int)
a, _ = parser.parse_known_args()
''' + ("sys.exit(3)\n" if mode == "error" else "") + r'''
stop = a.h_stop
''' + ("if a.h_start == 1: stop = 2\n" if mode == "partial" else "") + r'''
keys = ('pairs','admissible','convergents','small_g_values','thue_solutions',
        'other_chart','other_branch','refinements','exact_roots')
for h in range(a.h_start, stop):
    print(json.dumps(dict(type='shell', h=h, **{k:0 for k in keys})), flush=True)
print(json.dumps(dict(type='end', state='complete' if stop==a.h_stop else 'partial', next_h=stop)), flush=True)
''')
        path.chmod(0o755)
        return path

    def arguments(self, worker, budget="1800", seconds="1"):
        directory = self.base / "tasks"
        if not directory.exists():
            with contextlib.redirect_stdout(io.StringIO()):
                d_campaign.main(["--campaign-id", "execution", "--output-dir", str(directory),
                                 "--h-stop", "4", "--budget-core-hours", budget,
                                 "--seconds", seconds, "--target-seconds", seconds])
        return argparse.Namespace(page=directory / "page.json", output_dir=self.base / "results",
                                  worker=worker, max_attempts=None)

    def test_continuations_are_new_charged_attempts_and_restart_skips_complete(self):
        args = self.arguments(self.fake_worker("partial"))
        result = run(args)
        self.assertTrue(result["complete"])
        self.assertEqual(result["total_attempts"], 2)
        ledger = load_json(args.output_dir / "budget.json")
        self.assertEqual([a["task_state"] for a in ledger["attempts"]], ["partial", "complete"])
        self.assertTrue(all(a["charged_ns"] > 0 for a in ledger["attempts"]))
        again = run(args)
        self.assertEqual(again["attempts_this_invocation"], 0)
        self.assertEqual(again["charged_core_hours"], result["charged_core_hours"])
        worker_group, runner_group, cpus = load_json(args.worker.with_suffix(".group"))
        self.assertEqual(worker_group, runner_group)
        self.assertEqual(cpus, 1)

    def test_one_attempt_pilot_resumes_the_same_charged_ledger(self):
        args = self.arguments(self.fake_worker("partial"))
        args.max_attempts = 1
        first = run(args)
        self.assertFalse(first["complete"])
        self.assertEqual(first["reason"], "attempt_limit")
        self.assertEqual(first["total_attempts"], 1)
        second = run(args)
        self.assertTrue(second["complete"])
        self.assertEqual(second["total_attempts"], 2)
        self.assertGreater(second["charged_core_hours"], first["charged_core_hours"])

    def test_errors_are_charged_and_further_invocation_does_not_reset_budget(self):
        args = self.arguments(self.fake_worker("error"))
        first = run(args)
        self.assertEqual(first["reason"], "task_error")
        self.assertGreater(first["charged_core_hours"], 0)
        second = run(args)
        self.assertEqual(second["total_attempts"], 2)
        self.assertGreater(second["charged_core_hours"], first["charged_core_hours"])

    def test_insufficient_reservation_starts_no_process(self):
        args = self.arguments(self.fake_worker(), budget="0.03")
        result = run(args)
        self.assertEqual(result["reason"], "budget_exhausted")
        self.assertEqual(result["total_attempts"], 0)
        self.assertEqual(result["charged_core_hours"], 0)

    def test_watchdog_kills_hung_worker_grandchild(self):
        child_pid_file = self.base / "child.pid"
        child_code = "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)"
        parent_code = ("import subprocess,sys,time,signal,pathlib; "
                       "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                       f"p=subprocess.Popen([sys.executable,'-c',{child_code!r}]); "
                       f"pathlib.Path({str(child_pid_file)!r}).write_text(str(p.pid)); time.sleep(60)")
        result = execute_attempt([sys.executable, "-c", parent_code], self.base / "hung",
                                 timeout=0.5, cleanup_seconds=0.2)
        self.assertTrue(result["timed_out"])
        self.assertLess(result["elapsed_ns"], 3 * NANOSECONDS)
        pid = int(child_pid_file.read_text())
        state = Path(f"/proc/{pid}/stat")
        for _ in range(100):
            if not state.exists() or state.read_text().split()[2] == "Z":
                break
            time.sleep(0.01)
        self.assertTrue(not state.exists() or state.read_text().split()[2] == "Z",
                        "worker grandchild is still executing after the budget deadline")


if __name__ == "__main__":
    unittest.main()
