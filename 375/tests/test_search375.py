"""Finite positive controls, interruption, and validated-history regressions."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "search375.py"
WORKER = ROOT / "Scripts for large-scale computations" / "elkies-jahnel" / "bin" / "elkies375_worker"
spec = importlib.util.spec_from_file_location("search375", SCRIPT)
search = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search)


@unittest.skipUnless(WORKER.exists(), "build the EJ worker first")
class ContinuingSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.out = self.base / "search"

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, command, *args, ok=True):
        result = subprocess.run([sys.executable, str(SCRIPT), command,
            "--output-dir", str(self.out), *map(str, args)], capture_output=True, text=True, timeout=60)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
        return result

    def state(self):
        return json.loads((self.out / "state.json").read_text())

    def receipt(self, job):
        return json.loads((self.out / "jobs" / f"{job:012d}" / "receipt.json").read_text())

    def test_stops_on_exact_primitive_half_chart_positive_control(self):
        self.cli("start", "--k", 7125, "--height", 70, "--grid-span", 1000)
        state = self.state()
        self.assertEqual(state["state"], "found")
        self.assertTrue(any(set(map(int, r["cubes"])) == {-67,-46,74} for r in state["solutions"]))
        self.assertEqual(len(state["solutions"]), 1)  # the two y signs are one triple
        for point in state["solutions"][0]["original_points"]:
            self.assertEqual(point["chart"], "half")
            self.assertEqual(int(point["M"]) % 2, 1)
            self.assertEqual(int(point["Y_abs"]) % 2, 1)
        before = state["attempts"]
        self.cli("resume")
        self.assertEqual(self.state()["attempts"], before)

    def test_partial_attempts_resume_automatically_before_credit(self):
        self.cli("start", "--k", 7125, "--height", 70, "--grid-span", 1000,
                 "--task-max-tiles", 1, "--solutions", 0, "--max-attempts", 1)
        first = self.state()
        self.assertEqual(first["state"], "paused")
        self.assertEqual(first["progress"]["completed_tasks"], 0)
        self.assertIsNotNone(first["pending"])
        self.cli("resume", "--max-tasks", 1)
        done = self.state()
        self.assertEqual(done["state"], "paused")
        self.assertEqual(done["progress"]["completed_tasks"], 1)
        self.assertGreater(done["attempts"], first["attempts"])
        self.assertIsNone(done["pending"])
        self.assertTrue(self.receipt(0)["checkpoint"]["complete"])
        self.assertEqual(len(done["solutions"]), 1)

    def test_diagonal_schedule_revisits_unfinished_shells_and_reaches_higher_ones(self):
        self.cli("start", "--height", 1000, "--grid-span", 1,
                 "--solutions", 0, "--max-tasks", 6)
        receipts = [self.receipt(i) for i in range(6)]
        self.assertEqual([int(r["task"]["height"]) for r in receipts], [1000,2000,1000,4000,2000,1000])
        first_shell = [r["task"] for r in receipts if r["level"] == 0]
        self.assertTrue(all(a["index_start"] == b["index_stop"] for a,b in zip(first_shell, first_shell[1:])))
        self.cli("resume", "--max-tasks", 1)
        self.assertEqual(int(self.receipt(6)["task"]["height"]), 8000)
        self.assertEqual(self.state()["progress"]["completed_tasks"], 7)
        self.assertIsNone(self.state()["final_height_bound"])

    def test_sweep_advances_only_after_validated_full_shell(self):
        self.cli("start", "--height", 25, "--grid-span", 10000,
                 "--schedule", "sweep", "--solutions", 0, "--max-tasks", 2)
        self.assertEqual([int(self.receipt(i)["task"]["height"]) for i in range(2)], [25,50])
        for r in (self.receipt(0), self.receipt(1)):
            self.assertEqual(r["task"]["index_start"], str(search.ej.lower_index(int(r["task"]["height"]),375)))

    def test_rejects_changed_worker_without_overwriting_saved_state(self):
        self.cli("start", "--height", 1000, "--grid-span", 1, "--solutions", 0, "--max-tasks", 1)
        before = (self.out / "state.json").read_bytes()
        altered = self.base / "different-worker"
        shutil.copy2(WORKER, altered)
        with altered.open("ab") as f:
            f.write(b"changed")
        self.cli("resume", "--worker", altered, "--max-tasks", 1, ok=False)
        self.assertEqual((self.out / "state.json").read_bytes(), before)

    def test_tampered_receipt_cannot_advance_coverage(self):
        self.cli("start", "--height", 1000, "--grid-span", 1, "--solutions", 0, "--max-tasks", 1)
        before = (self.out / "state.json").read_bytes()
        path = self.out / "jobs" / "000000000000" / "receipt.json"
        receipt = json.loads(path.read_text())
        receipt["checkpoint"]["next_index"] = str(int(receipt["checkpoint"]["next_index"])+1)
        path.write_text(json.dumps(receipt))
        self.cli("resume", "--max-tasks", 1, ok=False)
        self.assertEqual((self.out / "state.json").read_bytes(), before)

    def test_missing_pending_hits_refuses_completion(self):
        self.cli("start", "--k", 7125, "--height", 70, "--grid-span", 1000)
        # Reproduce a crash after the completed receipt was prepared but before
        # the continuing controller committed that receipt into its state.
        state = self.state()
        state["progress"] = search.initial_progress()
        level = search.choose_level(state["progress"], state["config"])
        state["pending"] = {"job": 0, "level": level}
        state["solutions"] = []
        state["state"] = "running"
        (self.out / "state.json").write_text(json.dumps(state))
        (self.out / "jobs" / "000000000000" / "result" / "hits.jsonl").unlink()
        self.cli("resume", "--max-tasks", 1, ok=False)
        self.assertEqual(self.state()["progress"]["completed_tasks"], 0)

    def test_prepared_receipt_is_recovered_once_after_controller_crash(self):
        self.cli("start", "--height", 1000, "--grid-span", 1, "--solutions", 0, "--max-tasks", 1)
        state = self.state()
        state["progress"] = search.initial_progress()
        level = search.choose_level(state["progress"], state["config"])
        state["pending"] = {"job": 0, "level": level}
        (self.out / "state.json").write_text(json.dumps(state))
        attempts = state["attempts"]
        self.cli("resume", "--max-tasks", 1)
        self.assertEqual(self.state()["progress"]["completed_tasks"], 1)
        self.assertEqual(self.state()["attempts"], attempts)  # no repeated worker execution

    def test_sigterm_pauses_then_resume_advances_same_task(self):
        log = self.base / "signal.log"
        with log.open("w") as output:
            p = subprocess.Popen([sys.executable, str(SCRIPT), "start", "--output-dir", str(self.out),
                "--height", str(10**12), "--grid-span", "1000000", "--task-max-tiles", "100",
                "--solutions", "0"], stdout=output, stderr=output)
            try:
                raw = self.out / "jobs" / "000000000000" / "result" / "worker.jsonl"
                deadline = time.monotonic()+15
                while time.monotonic() < deadline:
                    if raw.exists() and '"progress"' in raw.read_text():
                        break
                    if p.poll() is not None:
                        self.fail(log.read_text())
                    time.sleep(0.02)
                else:
                    self.fail("worker did not start")
                p.send_signal(signal.SIGTERM)
                self.assertEqual(p.wait(timeout=20), 0, log.read_text())
            finally:
                if p.poll() is None:
                    p.terminate()
                    p.wait(timeout=20)
        self.assertEqual(self.state()["state"], "paused")
        cp_path = self.out / "jobs" / "000000000000" / "result" / "checkpoint.json"
        old = int(json.loads(cp_path.read_text())["next_index"])
        self.cli("resume", "--max-attempts", 1)
        self.assertLess(int(json.loads(cp_path.read_text())["next_index"]), old)
        self.assertEqual(self.state()["progress"]["completed_tasks"], 0)

    def test_killed_controller_adopts_existing_runner_without_overlapping_it(self):
        gate, marker = self.base / "gate", self.base / "launches"
        wrapper = self.base / "gated-worker"
        wrapper.write_text("#!/usr/bin/env python3\nimport os,sys,time\nfrom pathlib import Path\n"
            +f"with Path({str(marker)!r}).open('a') as f: f.write('launch\\n')\n"
            +f"while not Path({str(gate)!r}).exists(): time.sleep(0.02)\n"
            +f"os.execv({str(WORKER)!r}, [{str(WORKER)!r}]+sys.argv[1:])\n")
        wrapper.chmod(0o755)
        with (self.base / "orphan.log").open("w") as log:
            p = subprocess.Popen([sys.executable, str(SCRIPT), "start", "--output-dir", str(self.out),
                "--worker", str(wrapper), "--k", "7125", "--height", "70"], stdout=log, stderr=log)
            try:
                deadline = time.monotonic()+10
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(marker.exists())
                p.kill()  # its backend runner survives and still owns runner.lock
                p.wait(timeout=10)
                self.cli("resume", "--max-seconds", 0.3)
                self.assertEqual(self.state()["state"], "paused")
                self.assertEqual(self.state()["attempts"], 0)
                self.assertEqual(marker.read_text().splitlines(), ["launch"])
                gate.touch()
                result = self.out / "jobs" / "000000000000" / "result"
                deadline = time.monotonic()+10
                while search.runner_active(result) and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertFalse(search.runner_active(result))
                self.cli("resume")
                self.assertEqual(self.state()["state"], "found")
                self.assertEqual(marker.read_text().splitlines(), ["launch"])
            finally:
                gate.touch()
                if p.poll() is None:
                    p.terminate()
                    p.wait(timeout=10)


class Acceptance(unittest.TestCase):
    def test_point_primitivity_is_optional_and_y_signs_do_not_duplicate_triples(self):
        # Primitive cubes can yield a half chart with a nontrivial point gcd.
        hit = {"k": 12195, "x": 11, "y": 22, "z": 6}
        cfg = {"k": 12195, "chart": "half", "primitive_point": False}
        all_half = search.selected_solution(hit, cfg)
        self.assertTrue(any(int(p["point_gcd"]) == 11 for p in all_half["original_points"]))
        strict = search.selected_solution(hit, {**cfg, "primitive_point": True})
        self.assertTrue(all(p["primitive_point"] for p in strict["original_points"]))
        self.assertLess(len(strict["original_points"]), len(all_half["original_points"]))

    def test_all_primitive_cube_discoveries_are_retained_even_outside_selected_chart(self):
        hit = {"k": 3, "x": 1, "y": 1, "z": 1}
        state = {"config": {"k": 3, "chart": "half", "primitive_point": False},
                 "solutions": [], "cube_solutions": []}
        search.add_solutions(state, [hit])
        self.assertEqual(state["solutions"], [])
        self.assertEqual(len(state["cube_solutions"]), 1)

    def test_finite_small_height_exception_contains_no_primitive_375_triple(self):
        self.assertEqual(search.small_375_check()["triples"], [[5,5,5]])


if __name__ == "__main__":
    unittest.main()
