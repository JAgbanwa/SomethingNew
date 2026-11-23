"""Failure-injection and real-worker checks for durable fixed-g task results."""
from __future__ import annotations

import json
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
from common375 import (COUNTERS, PAGE_SCHEMA, PARAMETERIZATION, TASK_SCHEMA,  # noqa: E402
                       hit_key, pairs_in, sha256_file, verify_hit)

WORKER = ROOT / "bin" / "thue375_worker"
FAKE = '''#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import time
plan = json.loads(Path(__file__).with_suffix(".json").read_text())
for record in plan["records"]:
    print(json.dumps(record), flush=True)
if plan.get("wait"):
    while True:
        time.sleep(1)
sys.exit(plan.get("exit", 0))
'''


def start(first=1, stop=4, k=15, mode="xy"):
    return {"type": "start", "parameterization": PARAMETERIZATION, "g_values": [-1, 1],
            "k": str(k), "mode": mode, "h_start": first, "h_stop": stop}


def shell(h):
    return {"type": "shell", "h": h, **{c: 0 for c in COUNTERS}, "pairs": 4 * h - 1}


def end(state, nxt):
    return {"type": "end", "state": state, "next_h": nxt}


class RunnerReliability(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.task = {"schema": TASK_SCHEMA, "parameterization": PARAMETERIZATION, "g_values": [-1, 1],
                     "campaign_id": "reliability", "task_id": "task-0", "k": 15,
                     "mode": "xy", "h_start": 1, "h_stop": 4, "deadline_seconds": 0}
        self.task_path = self.root / "input.json"
        self.task_path.write_text(json.dumps(self.task))
        self.out = self.root / "result"
        self.fake = self.root / "fake_worker"
        self.fake.write_text(FAKE)
        self.fake.chmod(0o755)
        self.page_path = self.root / "page.json"
        self.page_path.write_text(json.dumps({**self.task, "schema": PAGE_SCHEMA}))

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, records, *, exit_code=0, wait=False):
        self.fake.with_suffix(".json").write_text(json.dumps({"records": records, "exit": exit_code, "wait": wait}))

    def command(self, *, worker=None, out=None, task=None, extra=()):
        return [sys.executable, str(ROOT / "run_task.py"), "--task", str(task or self.task_path),
                "--output-dir", str(out or self.out), "--worker", str(worker or self.fake), *extra]

    def run_task(self, **kwargs):
        return subprocess.run(self.command(**kwargs), capture_output=True, text=True, timeout=30)

    def status(self, out=None):
        return json.loads(((out or self.out) / "status.json").read_text())

    def cursor(self, out=None):
        cp = (out or self.out) / "checkpoint.json"
        return json.loads(cp.read_text())["next_h"] if cp.exists() else 1

    def collect(self, *results, extra=()):
        target = self.root / "collected"
        result = subprocess.run([sys.executable, str(ROOT / "collect.py"), "--page", str(self.page_path),
                                 "--results", *map(str, results or (self.out,)), "--output-dir", str(target),
                                 *extra], capture_output=True, text=True, timeout=30)
        return result, json.loads((target / "summary.json").read_text())

    def snapshot(self, out=None):
        return {str(p.relative_to(out or self.out)): p.read_bytes()
                for p in (out or self.out).rglob("*") if p.is_file()}

    def test_complete_requires_terminal_and_successful_exit(self):
        full = [start(), shell(1), shell(2), shell(3)]
        for label, records, code in (("missing end", full, 0),
                                     ("nonzero exit", full + [end("complete", 4)], 9),
                                     ("partial at endpoint", full + [end("partial", 4)], 0),
                                     ("post-terminal record", full + [end("complete", 4), shell(3)], 0),
                                     ("duplicate terminal", full + [end("complete", 4), end("complete", 4)], 0)):
            with self.subTest(label=label):
                out = self.root / label.replace(" ", "_")
                self.plan(records, exit_code=code)
                result = self.run_task(out=out)
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.status(out)["state"], "error")
                self.assertEqual(self.cursor(out), 3)  # last shell is not committed

    def test_start_and_order_are_required(self):
        cases = [[], [shell(1)], [start(k=57)], [start(first=2)],
                 [start(), start()], [start(), shell(2)],
                 [start(), shell(1), shell(1)], [start(), {"type": "unexpected"}],
                 [start(), shell(1) | {"h": 1.5}],
                 [start(), shell(1) | {"pairs": -1}],
                 [start(), shell(1) | {"pairs": 4}],
                 [start(), end("complete", 1)], [start(), end("partial", 2)],
                 [start(), end("unknown", 1)]]
        for i, records in enumerate(cases):
            with self.subTest(records=records):
                out = self.root / f"bad-{i}"
                self.plan(records)
                result = self.run_task(out=out)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.status(out)["state"], "error")
                self.assertEqual(self.cursor(out), 1)

    def test_partial_terminal_also_requires_successful_exit(self):
        for i, records in enumerate(([start(), shell(1), end("partial", 2)],
                                      [start(), shell(1), end("partial", 3)])):
            out = self.root / f"partial-fail-{i}"
            self.plan(records, exit_code=9 if i == 0 else 0)
            result = self.run_task(out=out)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.cursor(out), 1)

    def test_failed_final_shell_is_replayed_without_duplicate_counts(self):
        self.plan([start(), shell(1), shell(2), shell(3)])
        self.assertNotEqual(self.run_task().returncode, 0)
        self.assertEqual(self.cursor(), 3)
        # Reuse the same binary, now with a valid transcript for the pending shell.
        self.plan([start(first=3), shell(3), end("complete", 4)])
        result = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        cp = json.loads((self.out / "checkpoint.json").read_text())
        self.assertEqual(cp["terminal_state"], "complete")
        self.assertEqual(cp["worker_exit_code"], 0)
        self.assertEqual(cp["counters"]["pairs"], pairs_in(1, 4))
        self.assertEqual([json.loads(s)["h"] for s in (self.out / "shells.jsonl").read_text().splitlines()], [1, 2, 3])
        result, summary = self.collect(extra=("--require-complete",))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["covered_heights"], [[1, 4]])
        self.assertEqual(summary["errors"], [])

    def test_partial_continuation_in_new_directory_has_exact_union(self):
        self.plan([start(), shell(1), end("partial", 2)])
        result = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        continuation = self.out / "continuation.task.json"
        cont = json.loads(continuation.read_text())
        self.assertEqual(cont["h_start"], 2)
        self.assertEqual(cont["expected_worker_sha256"], sha256_file(self.fake))
        result, summary = self.collect(extra=("--require-complete",))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(summary["gaps"], [[2, 4]])
        other = self.root / "continuation-result"
        self.plan([start(first=2), shell(2), shell(3), end("complete", 4)])
        result = self.run_task(out=other, task=continuation)
        self.assertEqual(result.returncode, 0, result.stderr)
        result, summary = self.collect(self.out, other, extra=("--require-complete",))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["covered_heights"], [[1, 4]])
        self.assertEqual(summary["counters"]["pairs"], pairs_in(1, 4))
        before = self.snapshot(other)
        # This directory started at 2; it must never claim the original prefix.
        self.assertNotEqual(self.run_task(out=other).returncode, 0)
        self.assertEqual(self.snapshot(other), before)

    def test_same_directory_continuation_preserves_covered_start(self):
        self.plan([start(), shell(1), end("partial", 2)])
        self.assertEqual(self.run_task().returncode, 0)
        continuation = self.out / "continuation.task.json"
        self.plan([start(first=2), shell(2), shell(3), end("complete", 4)])
        result = self.run_task(task=continuation)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.status()["covered_h_start"], 1)
        result, summary = self.collect()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["covered_heights"], [[1, 4]])
        self.assertEqual(self.run_task().returncode, 0)  # original manifest remains a valid resume

    def test_signal_is_resumable_and_keeps_only_committed_prefix(self):
        self.plan([start(), shell(1), shell(2)], wait=True)
        proc = subprocess.Popen(self.command(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not (self.out / "checkpoint.json").exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertIsNone(proc.poll())
            self.assertTrue((self.out / "checkpoint.json").exists())
            proc.send_signal(signal.SIGTERM)
            _, stderr = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 0, stderr)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
        self.assertEqual(self.status()["state"], "partial")
        self.assertEqual(self.cursor(), 2)
        self.plan([start(first=2), shell(2), shell(3), end("complete", 4)])
        self.assertEqual(self.run_task().returncode, 0)

    def test_changed_binary_resume_and_wrong_pin_do_not_modify_results(self):
        self.plan([start(), shell(1), end("partial", 2)])
        self.assertEqual(self.run_task().returncode, 0)
        before = self.snapshot()
        other = self.root / "different_worker"
        other.write_text(FAKE + "\n# different release\n")
        other.chmod(0o755)
        result = self.run_task(worker=other)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.snapshot(), before)
        result = self.run_task(extra=("--expected-worker-sha256", "0" * 64))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.snapshot(), before)
        fresh = self.root / "refused-fresh"
        self.assertNotEqual(self.run_task(worker=other, out=fresh, task=self.out / "continuation.task.json").returncode, 0)
        self.assertFalse(fresh.exists())

    def test_collection_rejects_mixed_or_unexpected_binary_hashes(self):
        self.plan([start(), shell(1), shell(2), shell(3), end("complete", 4)])
        self.assertEqual(self.run_task().returncode, 0)
        other = self.root / "other-result"
        shutil.copytree(self.out, other)
        digest = "0" * 64
        for name in ("task.json", "checkpoint.json", "status.json"):
            path = other / name
            record = json.loads(path.read_text())
            record["expected_worker_sha256" if name == "task.json" else "worker_sha256"] = digest
            path.write_text(json.dumps(record))
        shells = [json.loads(line) | {"worker_sha256": digest} for line in (other / "shells.jsonl").read_text().splitlines()]
        (other / "shells.jsonl").write_text("".join(json.dumps(r) + "\n" for r in shells))
        for results, extra in (((self.out, other), ()),
                               ((self.out,), ("--expected-worker-sha256", digest))):
            result, summary = self.collect(*results, extra=extra)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(summary["covered_heights"], [])
            self.assertEqual(summary["hits"], 0)
            self.assertTrue(summary["errors"])

    def test_collection_requires_committed_contiguous_shells_and_terminal_proof(self):
        self.plan([start(), shell(1), shell(2), shell(3), end("complete", 4)])
        self.assertEqual(self.run_task().returncode, 0)
        for label in ("missing-shell", "missing-terminal", "counter-mismatch", "missing-hash"):
            with self.subTest(label=label):
                out = self.root / label
                shutil.copytree(self.out, out)
                cp_path = out / "checkpoint.json"
                cp = json.loads(cp_path.read_text())
                if label == "missing-shell":
                    lines = (out / "shells.jsonl").read_text().splitlines()
                    (out / "shells.jsonl").write_text("\n".join(lines[1:]) + "\n")
                elif label == "missing-terminal":
                    del cp["terminal_state"]
                elif label == "counter-mismatch":
                    cp["counters"]["pairs"] += 1
                else:
                    del cp["worker_sha256"]
                cp_path.write_text(json.dumps(cp))
                result, summary = self.collect(out)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(summary["covered_heights"], [])
                before = self.snapshot(out)
                self.assertNotEqual(self.run_task(out=out).returncode, 0)
                self.assertEqual(self.snapshot(out), before)

    def test_uncommitted_shell_log_tail_is_replayed(self):
        self.plan([start(), shell(1), end("partial", 2)])
        self.assertEqual(self.run_task().returncode, 0)
        # Model a host crash after log append but before checkpoint replacement.
        with (self.out / "shells.jsonl").open("a") as handle:
            handle.write(json.dumps(shell(2) | {"worker_sha256": sha256_file(self.fake)}) + "\n")
            handle.write('{"unfinished":')
        self.plan([start(first=2), shell(2), shell(3), end("complete", 4)])
        result = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([json.loads(line)["h"] for line in (self.out / "shells.jsonl").read_text().splitlines()], [1, 2, 3])

    def test_partial_results_require_their_hit_file_and_unique_count(self):
        self.plan([start(), shell(1), end("partial", 2)])
        self.assertEqual(self.run_task().returncode, 0)
        for label in ("missing-hits", "wrong-count", "missing-status"):
            with self.subTest(label=label):
                out = self.root / label
                shutil.copytree(self.out, out)
                if label == "missing-hits":
                    (out / "hits.jsonl").unlink()
                elif label == "missing-status":
                    (out / "status.json").unlink()
                else:
                    path = out / "status.json"
                    status = json.loads(path.read_text()) | {"hits": 1}
                    path.write_text(json.dumps(status))
                before = self.snapshot(out)
                result, summary = self.collect(out)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(summary["covered_heights"], [])
                self.assertNotEqual(self.run_task(out=out).returncode, 0)
                self.assertEqual(self.snapshot(out), before)

    def test_zero_hit_endpoint_requires_empty_hit_artifact_with_stale_status(self):
        self.plan([start(), shell(1), shell(2), shell(3), end("complete", 4)])
        self.assertEqual(self.run_task().returncode, 0)
        status = self.status() | {"state": "running", "next_h": 1, "hits": 0}
        (self.out / "status.json").write_text(json.dumps(status))
        (self.out / "hits.jsonl").unlink()
        before = self.snapshot()
        result, summary = self.collect()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(summary["covered_heights"], [])
        self.assertNotEqual(self.run_task().returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def prepare_real_positive(self):
        self.task["k"], self.task["h_stop"] = 57, 20
        self.task_path.write_text(json.dumps(self.task))
        self.page_path.write_text(json.dumps({**self.task, "schema": PAGE_SCHEMA}))
        result = self.run_task(worker=WORKER)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = (self.out / "hits.jsonl").read_text().splitlines()
        self.assertTrue(lines, "K=57 is a real positive control")
        return lines

    @unittest.skipUnless(WORKER.exists(), "build first: make")
    def test_real_successful_hit_loss_is_rejected_by_collection_and_resume(self):
        lines = self.prepare_real_positive()
        for label in ("missing-hits", "empty-hits", "lost-hit", "cut-json", "wrong-count", "missing-status", "lost-markers"):
            with self.subTest(label=label):
                out = self.root / label
                shutil.copytree(self.out, out)
                if label == "missing-hits":
                    (out / "hits.jsonl").unlink()
                elif label == "empty-hits":
                    (out / "hits.jsonl").write_text("")
                elif label == "lost-hit":
                    (out / "hits.jsonl").write_text("".join(line + "\n" for line in lines[:-1]))
                elif label == "cut-json":
                    (out / "hits.jsonl").write_text("\n".join(lines)[:-5])
                elif label == "wrong-count":
                    path = out / "status.json"
                    status = json.loads(path.read_text()) | {"hits": 0}
                    path.write_text(json.dumps(status))
                else:
                    (out / "status.json").unlink()
                    if label == "lost-markers":
                        (out / "checkpoint.json").unlink()
                before = self.snapshot(out)
                result, summary = self.collect(out)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(summary["covered_heights"], [])
                self.assertEqual(summary["hits"], 0)
                self.assertTrue(summary["errors"])
                self.assertNotEqual(self.run_task(out=out, worker=WORKER).returncode, 0)
                self.assertEqual(self.snapshot(out), before)

    @unittest.skipUnless(WORKER.exists(), "build first: make")
    def test_checkpoint_hit_count_protects_the_stale_running_status_window(self):
        self.prepare_real_positive()
        for label in ("missing-hits", "truncated-hits"):
            with self.subTest(label=label):
                out = self.root / label
                shutil.copytree(self.out, out)
                path = out / "status.json"
                status = json.loads(path.read_text()) | {"state": "running", "hits": 0, "next_h": 1}
                path.write_text(json.dumps(status))
                if label == "missing-hits":
                    (out / "hits.jsonl").unlink()
                else:
                    (out / "hits.jsonl").write_text("")
                before = self.snapshot(out)
                result, summary = self.collect(out)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(summary["covered_heights"], [])
                self.assertNotEqual(self.run_task(out=out, worker=WORKER).returncode, 0)
                self.assertEqual(self.snapshot(out), before)

    @unittest.skipUnless(WORKER.exists(), "build first: make")
    def test_stale_running_error_counts_and_duplicate_records_remain_resumable(self):
        lines = self.prepare_real_positive()
        for state in ("running", "error", "complete"):
            with self.subTest(state=state):
                out = self.root / state
                shutil.copytree(self.out, out)
                path = out / "status.json"
                status = json.loads(path.read_text())
                if state != "complete":
                    status.update(state=state, hits=0, next_h=1)
                path.write_text(json.dumps(status))
                # Count unique hit_key values, not raw records or worker hits.
                with (out / "hits.jsonl").open("a") as handle:
                    handle.write(lines[0] + "\n")
                expected = (out / "hits.jsonl").read_bytes()
                result = self.run_task(out=out, worker=WORKER)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((out / "hits.jsonl").read_bytes(), expected)
                result, summary = self.collect(out, extra=("--require-complete",))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(summary["hits"], len({hit_key(json.loads(line)) for line in lines}))

    @unittest.skipUnless(WORKER.exists(), "build first: make")
    def test_real_positive_hits_keep_binary_and_search_certificates(self):
        self.task["k"], self.task["h_stop"] = 57, 20
        self.task_path.write_text(json.dumps(self.task))
        self.page_path.write_text(json.dumps({**self.task, "schema": PAGE_SCHEMA}))
        digest = sha256_file(WORKER)
        result = self.run_task(worker=WORKER, extra=("--expected-worker-sha256", digest))
        self.assertEqual(result.returncode, 0, result.stderr)
        hits = [json.loads(line) for line in (self.out / "hits.jsonl").read_text().splitlines()]
        self.assertTrue(hits)
        self.assertTrue(any(verify_hit(hit, 57)["desired"] for hit in hits))
        self.assertEqual({hit["worker_sha256"] for hit in hits}, {digest})
        before = (self.out / "hits.jsonl").read_bytes()
        self.assertEqual(self.run_task(worker=WORKER).returncode, 0)
        self.assertEqual((self.out / "hits.jsonl").read_bytes(), before)
        result, summary = self.collect(extra=("--expected-worker-sha256", digest, "--require-complete"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["hits"], len({hit_key(hit) for hit in hits}))
        self.assertEqual(summary["gaps"], [])


if __name__ == "__main__":
    unittest.main()
