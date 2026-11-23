"""Malformed returned work must never become credited search coverage."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gap_common import CHECKPOINT_SCHEMA, COUNTERS, METHOD, PAGE_SCHEMA, TASK_SCHEMA, registered_tasks


def task():
    return dict(schema=TASK_SCHEMA, method=METHOD, campaign_id="coverage", task_id="coverage-0",
                k=375, d_start="1000000", d_stop="1000100", ratio_max=16,
                primitive_only=True, height_min="0", deadline_seconds=10)


class ReturnedCoverage(unittest.TestCase):
    def test_runner_rejects_outside_or_miscounted_chunks(self):
        for stop, total in [(1000101, 101), (1000100, 99), (1000000, 0)]:
            with self.subTest(stop=stop, total=total), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                t = task()
                (root / "task.json").write_text(json.dumps(t))
                counters = dict.fromkeys(COUNTERS, 0)
                counters["d_total"] = total
                records = [dict(type="start", **{k: t[k] for k in ("k", "ratio_max", "primitive_only", "height_min")}),
                           dict(type="chunk", d_start=t["d_start"], d_stop=str(stop), counters=counters)]
                worker = root / "worker"
                worker.write_text("#!/usr/bin/env python3\nimport json\nfor r in " + repr(records) + ": print(json.dumps(r), flush=True)\n")
                worker.chmod(0o755)
                run = subprocess.run([sys.executable, str(ROOT / "run_gap_task.py"), "--task", str(root / "task.json"),
                                      "--output-dir", str(root / "out"), "--worker", str(worker)],
                                     text=True, capture_output=True)
                self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                self.assertFalse((root / "out" / "checkpoint.json").exists())

    def test_collector_rejects_checkpoint_beyond_registered_task(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            t = task()
            entries = [dict(task_id="coverage-0", d_start="1000000", d_stop="1000100"),
                       dict(task_id="coverage-1", d_start="1000100", d_stop="1000200")]
            page = dict(t, schema=PAGE_SCHEMA, d_stop="1000200", tasks=entries)
            (root / "page.json").write_text(json.dumps(page))
            output = root / "results"
            output.mkdir()
            (output / "task.json").write_text(json.dumps(t))
            counters = dict.fromkeys(COUNTERS, 0)
            counters["d_total"] = 200
            checkpoint = dict(t, schema=CHECKPOINT_SCHEMA, covered_start=t["d_start"], d_next="1000200",
                              counters=counters, worker_sha256="0" * 64)
            (output / "checkpoint.json").write_text(json.dumps(checkpoint))
            run = subprocess.run([sys.executable, str(ROOT / "collect_gap.py"), "--page", str(root / "page.json"),
                                  "--results", str(output), "--output-dir", str(root / "collected")],
                                 text=True, capture_output=True)
            self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
            summary = json.loads((root / "collected" / "summary.json").read_text())
            self.assertEqual(summary["d_values_covered"], 0)
            self.assertTrue(summary["errors"])

    def test_page_rejects_overlapping_registered_tasks(self):
        with self.assertRaises(ValueError):
            registered_tasks(dict(d_start="1", d_stop="100", tasks=[
                dict(task_id="a", d_start="1", d_stop="60"),
                dict(task_id="b", d_start="50", d_stop="100")]))


if __name__ == "__main__":
    unittest.main()
