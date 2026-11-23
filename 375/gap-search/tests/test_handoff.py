"""Bounded deployment-contract tests; fake workers never perform a search."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gap_common import COUNTERS, METHOD, PAGE_SCHEMA, TASK_SCHEMA  # noqa: E402


FAKE_WORKER = r'''#!/usr/bin/env python3
import argparse, json, pathlib, sys, time
ap = argparse.ArgumentParser()
for name in ("k", "d-start", "d-stop", "ratio-max", "deadline-seconds", "chunk"):
    ap.add_argument("--" + name, type=int, required=True)
ap.add_argument("--primitive", action="store_true")
a = ap.parse_args()
control = json.loads(pathlib.Path(__file__).with_name("control.json").read_text())
mode = control["mode"]
if mode == "no_output":
    sys.exit(0)
start = {"type": "start", "method": "booker-sutherland-gap-v1", "k": str(a.k),
         "d_start": str(a.d_start), "d_stop": str(a.d_stop),
         "ratio_max": str(a.ratio_max), "primitive": a.primitive}
if mode == "wrong_start":
    start["ratio_max"] = str(a.ratio_max + 1)
print(json.dumps(start), flush=True)
if mode == "start_only":
    sys.exit(0)
endpoint = ((a.d_start + a.d_stop) // 2
            if mode in ("partial", "early_complete", "pause") else a.d_stop)
counters = dict.fromkeys(COUNTER_NAMES, 0)
counters["d_total"] = endpoint - a.d_start
print(json.dumps({"type": "chunk", "d_start": str(a.d_start),
                  "d_stop": str(endpoint), "counters": counters}), flush=True)
if mode == "pause":
    time.sleep(30)
if mode == "missing_end":
    sys.exit(0)
end = {"type": "end", "state": "partial" if mode in ("partial", "bad_partial") else "complete",
       "d_next": str(endpoint + (1 if mode == "bad_cursor" else 0))}
print(json.dumps(end), flush=True)
if mode == "duplicate_end":
    print(json.dumps(end), flush=True)
sys.exit(7 if mode == "nonzero_exit" else 0)
'''.replace("COUNTER_NAMES", repr(list(COUNTERS)))


class Handoff(unittest.TestCase):
    def setUp(self):
        self.tmp_context = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_context.cleanup)
        self.tmp = Path(self.tmp_context.name)
        self.worker = self.tmp / "fake_worker.py"
        self.worker.write_text(FAKE_WORKER)
        self.worker.chmod(0o755)
        self.mode("complete")

    def mode(self, value):
        (self.tmp / "control.json").write_text(json.dumps({"mode": value}))

    def digest(self):
        return hashlib.sha256(self.worker.read_bytes()).hexdigest()

    def task(self, name="task", lo=1, hi=11):
        data = {"schema": TASK_SCHEMA, "campaign_id": "handoff", "task_id": name,
                "method": METHOD, "k": 7125, "d_start": str(lo), "d_stop": str(hi),
                "ratio_max": 16, "primitive": True, "deadline_seconds": 0}
        path = self.tmp / f"{name}.json"
        path.write_text(json.dumps(data))
        return path

    def command(self, task, out, *extra):
        return [sys.executable, str(ROOT / "run_gap_task.py"), "--task", str(task),
                "--output-dir", str(out), "--worker", str(self.worker), *extra]

    def run_task(self, task, out, *extra):
        return subprocess.run(self.command(task, out, *extra), capture_output=True, text=True, timeout=10)

    def snapshot(self, out):
        return {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}

    def complete(self, name="task", lo=1, hi=11):
        task, out = self.task(name, lo, hi), self.tmp / name
        result = self.run_task(task, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((out / "status.json").read_text())["state"], "complete")
        return task, out

    def collect(self, results, *extra):
        page = {"schema": PAGE_SCHEMA, "method": METHOD, "campaign_id": "handoff", "k": 7125,
                "d_start": "1", "d_stop": "11", "ratio_max": 16, "primitive": True, "frontier": 0}
        page_path = self.tmp / "page.json"
        page_path.write_text(json.dumps(page))
        out = self.tmp / "collected"
        result = subprocess.run([sys.executable, str(ROOT / "collect_gap.py"), "--page", str(page_path),
                                 "--results", *map(str, results), "--output-dir", str(out), *extra],
                                capture_output=True, text=True, timeout=10)
        return result, json.loads((out / "summary.json").read_text())

    def hit(self):
        # The actual primitive k=7125 representation used by the native pipeline test.
        return {"type": "hit", "k": "7125", "x": "74", "y": "-67", "z": "-46", "d": "7",
                "primitive": True, "worker_sha256": self.digest()}

    def test_normal_completion_and_pinned_collection(self):
        task, out = self.complete()
        cp = json.loads((out / "checkpoint.json").read_text())
        self.assertEqual(cp["terminal_state"], "complete")
        self.assertEqual(cp["worker_sha256"], self.digest())
        self.assertEqual(self.run_task(task, out, "--expected-worker-sha256", self.digest()).returncode, 0)
        result, summary = self.collect([out], "--require-complete", "--expected-worker-sha256", self.digest())
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(summary["covered_d"], [["1", "11"]])
        self.assertEqual(summary["counters"]["d_total"], 10)

    def test_pin_rejects_worker_before_creating_output(self):
        task, out = self.task(), self.tmp / "output"
        for expected in ("0" * 64, ""):
            with self.subTest(expected=expected):
                result = self.run_task(task, out, "--expected-worker-sha256", expected)
                self.assertEqual(result.returncode, 1)
                self.assertIn("differs from expected" if expected else "64 hexadecimal", result.stderr)
                self.assertFalse(out.exists())

    def test_changed_binary_cannot_resume_and_leaves_output_unchanged(self):
        task, out = self.complete()
        before = self.snapshot(out)
        self.worker.write_text(FAKE_WORKER + "\n# different binary release\n")
        result = self.run_task(task, out)
        self.assertEqual(result.returncode, 1)
        self.assertIn("different worker SHA-256", result.stderr)
        self.assertEqual(self.snapshot(out), before)

    def test_changed_binary_is_rejected_before_first_checkpoint_too(self):
        self.mode("start_only")
        task, out = self.task(), self.tmp / "output"
        self.assertEqual(self.run_task(task, out).returncode, 1)
        self.assertFalse((out / "checkpoint.json").exists())
        before = self.snapshot(out)
        self.worker.write_text(FAKE_WORKER + "\n# changed after early exit\n")
        self.assertEqual(self.run_task(task, out).returncode, 1)
        self.assertEqual(self.snapshot(out), before)

    def test_resume_reverifies_saved_hits_and_their_provenance(self):
        for mutation in ({"worker_sha256": "0" * 64}, {"x": "75"}):
            with self.subTest(mutation=mutation):
                name = "hash_hit" if "worker_sha256" in mutation else "invalid_hit"
                task, out = self.complete(name)
                (out / "hits.jsonl").write_text(json.dumps(self.hit() | mutation) + "\n")
                before = self.snapshot(out)
                result = self.run_task(task, out)
                self.assertEqual(result.returncode, 1)
                self.assertIn("saved hit cannot be reused", result.stderr)
                self.assertEqual(self.snapshot(out), before)

    def test_premature_or_malformed_terminal_records_fail(self):
        for mode in ("no_output", "start_only", "missing_end", "early_complete", "bad_partial",
                     "bad_cursor", "duplicate_end", "nonzero_exit", "wrong_start"):
            with self.subTest(mode=mode):
                self.mode(mode)
                task, out = self.task(mode), self.tmp / mode
                result = self.run_task(task, out)
                self.assertEqual(result.returncode, 1, result.stderr)
                status = json.loads((out / "status.json").read_text())
                self.assertEqual(status["state"], "error")
                self.assertLess(int(status["d_next"]), 11)

    def test_unconfirmed_final_chunk_is_replayed_on_retry(self):
        self.mode("missing_end")
        task, out = self.task(), self.tmp / "output"
        self.assertEqual(self.run_task(task, out).returncode, 1)
        self.assertFalse((out / "checkpoint.json").exists())
        self.mode("complete")
        result = self.run_task(task, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        result, summary = self.collect([out], "--require-complete")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(summary["counters"]["d_total"], 10)

    def test_explicit_partial_preserves_exit_code_and_can_resume(self):
        self.mode("partial")
        task, out = self.task(), self.tmp / "output"
        result = self.run_task(task, out, "--partial-exit-code", "75")
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertEqual(json.loads((out / "status.json").read_text())["state"], "partial")
        self.mode("complete")
        result = self.run_task(out / "continuation.task.json", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((out / "continuation.task.json").exists())
        result, summary = self.collect([out], "--require-complete")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(summary["covered_d"], [["1", "11"]])

    def test_real_sigterm_is_a_resumable_partial(self):
        self.mode("pause")
        task, out = self.task(), self.tmp / "output"
        proc = subprocess.Popen(self.command(task, out), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            until = time.monotonic() + 5
            while not (out / "checkpoint.json").exists() and proc.poll() is None and time.monotonic() < until:
                time.sleep(0.01)
            self.assertTrue((out / "checkpoint.json").exists())
            proc.send_signal(signal.SIGTERM)
            _, stderr = proc.communicate(timeout=5)
            self.assertEqual(proc.returncode, 0, stderr)
            self.assertEqual(json.loads((out / "status.json").read_text())["state"], "partial")
            self.assertTrue((out / "continuation.task.json").exists())
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def test_collection_rejects_mixed_binary_releases_without_coverage(self):
        _, first = self.complete("first", 1, 6)
        self.worker.write_text(FAKE_WORKER + "\n# a second release\n")
        _, second = self.complete("second", 6, 11)
        result, summary = self.collect([first, second], "--require-complete")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(summary["covered_d"], [])
        self.assertEqual(summary["counters"]["d_total"], 0)
        self.assertEqual(len(summary["worker_sha256"]), 2)
        self.assertTrue(any("mixed worker" in e["error"] for e in summary["errors"]))

    def test_collection_rejects_unexpected_hash_without_coverage(self):
        _, out = self.complete()
        result, summary = self.collect([out], "--expected-worker-sha256", "0" * 64)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(summary["covered_d"], [])
        self.assertEqual(summary["expected_worker_sha256"], "0" * 64)

    def test_invalid_hit_does_not_contribute_coverage(self):
        _, out = self.complete()
        (out / "hits.jsonl").write_text(json.dumps(self.hit() | {"x": "75"}) + "\n")
        result, summary = self.collect([out])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(summary["covered_d"], [])
        self.assertEqual(summary["hits"], 0)
        self.assertEqual(summary["counters"]["d_total"], 0)

    def test_collection_rejects_checkpoint_status_hash_conflict(self):
        _, out = self.complete()
        cp_path = out / "checkpoint.json"
        cp = json.loads(cp_path.read_text())
        cp["worker_sha256"] = "0" * 64
        cp_path.write_text(json.dumps(cp))
        result, summary = self.collect([out])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(summary["covered_d"], [])
        self.assertEqual(len(summary["worker_sha256"]), 2)

    def test_collection_rejects_missing_checkpoint_provenance(self):
        _, out = self.complete()
        cp_path = out / "checkpoint.json"
        cp = json.loads(cp_path.read_text())
        del cp["worker_sha256"]
        cp_path.write_text(json.dumps(cp))
        result, summary = self.collect([out])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(summary["covered_d"], [])


if __name__ == "__main__":
    unittest.main()
