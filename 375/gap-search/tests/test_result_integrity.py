"""Finite positive controls for returned-hit integrity, audit identities and replay."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "bin" / "gap_worker"
sys.path.insert(0, str(ROOT))
from gap_common import COUNTERS  # noqa: E402


def run_script(name, *arguments):
    return subprocess.run([sys.executable, str(ROOT / name), *map(str, arguments)],
                          capture_output=True, text=True, timeout=20)


def write_json(path, value):
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


class ResultTools:
    def collect(self, *extra):
        result = run_script("collect_gap.py", "--page", self.page, "--results", self.result,
                            "--output-dir", self.tmp / "collected", "--expected-worker-sha256", self.digest, *extra)
        return result, json.loads((self.tmp / "collected" / "summary.json").read_text())

    def audit(self, worker=None, *extra):
        return run_script("audit_gap.py", "--page", self.page, "--results", self.result,
                          "--fraction", "1", "--seed", "1", "--worker", worker or self.worker, *extra)

    def assert_rejected(self):
        result, summary = self.collect()
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertTrue(summary["errors"])
        self.assertEqual(summary["covered_d"], [])
        self.assertEqual(summary["hits"], 0)
        self.assertEqual(summary["counters"]["d_total"], 0)
        audit = self.audit()
        self.assertEqual(audit.returncode, 1, audit.stderr + audit.stdout)


@unittest.skipUnless(WORKER.exists(), "build first: make")
class NativeResultIntegrity(ResultTools, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_context = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixture_context.cleanup)
        fixture = Path(cls.fixture_context.name)
        planned = run_script("gap_campaign.py", "--campaign-id", "hit-integrity", "--k", "7125",
                             "--d-start", "1", "--d-stop", "100", "--ratio-max", "64",
                             "--task-d-count", "99", "--frontier", "0", "--output-dir", fixture / "campaign")
        if planned.returncode:
            raise AssertionError(planned.stderr + planned.stdout)
        cls.fixture = fixture / "result"
        task = next((fixture / "campaign" / "tasks").glob("*.json"))
        native = run_script("run_gap_task.py", "--task", task, "--output-dir", cls.fixture, "--worker", WORKER)
        if native.returncode:
            raise AssertionError(native.stderr + native.stdout)
        cls.page = fixture / "campaign" / "page.json"
        cls.digest = hashlib.sha256(WORKER.read_bytes()).hexdigest()
        cls.worker = WORKER
        cls.original_hit = (cls.fixture / "hits.jsonl").read_text()
        hit = json.loads(cls.original_hit)
        if tuple(int(hit[key]) for key in ("x", "y", "z")) != (74, -67, -46):
            raise AssertionError("the native positive control did not return its known primitive hit")

    def setUp(self):
        self.tmp_context = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_context.cleanup)
        self.tmp = Path(self.tmp_context.name)
        self.result = self.tmp / "result"
        shutil.copytree(self.fixture, self.result)

    def test_native_positive_control_is_collected_and_audited(self):
        result, summary = self.collect("--require-complete")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual((summary["hits"], summary["primitive_hits"], summary["counters"]["hits"]), (1, 1, 1))
        audit = self.audit(None, "--expected-worker-sha256", self.digest)
        self.assertEqual(audit.returncode, 0, audit.stderr + audit.stdout)
        self.assertIn("1/1 sampled chunks agree in counters and exact solution identities", audit.stdout)

    def test_missing_empty_and_truncated_hits_are_rejected(self):
        path = self.result / "hits.jsonl"
        for content in (None, "", self.original_hit.rstrip("\n"), self.original_hit[:30] + "\n"):
            with self.subTest(content=content):
                if content is None:
                    path.unlink()
                else:
                    path.write_text(content)
                self.assert_rejected()

    def test_missing_status_or_chunk_log_is_rejected(self):
        for filename in ("status.json", "chunks.jsonl"):
            with self.subTest(filename=filename):
                path = self.result / filename
                content = path.read_bytes()
                path.unlink()
                self.assert_rejected()
                path.write_bytes(content)

    def test_status_hit_count_must_match_saved_identities(self):
        path = self.result / "status.json"
        status = json.loads(path.read_text())
        status["hits"] = 0
        write_json(path, status)
        self.assert_rejected()

    def test_hit_and_chunk_provenance_are_checked(self):
        for filename in ("hits.jsonl", "chunks.jsonl"):
            with self.subTest(filename=filename):
                path = self.result / filename
                content = path.read_text()
                record = json.loads(content)
                record["worker_sha256"] = "0" * 64
                write_json(path, record)
                self.assert_rejected()
                path.write_text(content)

    def test_hit_and_chunk_provenance_cannot_be_omitted(self):
        for filename in ("hits.jsonl", "chunks.jsonl"):
            with self.subTest(filename=filename):
                path = self.result / filename
                content = path.read_text()
                record = json.loads(content)
                del record["worker_sha256"]
                write_json(path, record)
                self.assert_rejected()
                path.write_text(content)

    def test_durable_hit_count_cannot_be_hidden_by_changing_status_total(self):
        (self.result / "hits.jsonl").write_text("")
        path = self.result / "status.json"
        status = json.loads(path.read_text())
        status["hits"] = 0
        write_json(path, status)
        self.assert_rejected()
        _, summary = self.collect()
        self.assertIn("durable interval", summary["errors"][0]["error"])

    def test_valid_but_altered_identity_fails_audit_with_unchanged_counts(self):
        hit = json.loads(self.original_hit)
        hit["x"], hit["y"] = hit["y"], hit["x"]
        write_json(self.result / "hits.jsonl", hit)
        collected, _ = self.collect("--require-complete")
        self.assertEqual(collected.returncode, 0, collected.stderr + collected.stdout)
        audited = self.audit()
        self.assertEqual(audited.returncode, 1, audited.stderr + audited.stdout)
        self.assertIn("missing returned identities [(74, -67, -46)]", audited.stdout)
        self.assertIn("unexpected returned identities [(-67, 74, -46)]", audited.stdout)

    def test_audit_detects_a_hit_removed_together_with_its_counts(self):
        (self.result / "hits.jsonl").write_text("")
        for filename in ("checkpoint.json", "status.json", "chunks.jsonl"):
            path = self.result / filename
            record = json.loads(path.read_text())
            record["counters"]["hits"] = record["counters"]["hits_primitive"] = 0
            if filename == "status.json":
                record["hits"] = 0
            write_json(path, record)
        collected, _ = self.collect("--require-complete")
        self.assertEqual(collected.returncode, 0, collected.stderr + collected.stdout)
        audited = self.audit()
        self.assertEqual(audited.returncode, 1, audited.stderr + audited.stdout)
        self.assertIn("missing returned identities [(74, -67, -46)]", audited.stdout)

    def test_duplicate_hit_and_replayed_chunk_do_not_inflate_counts(self):
        for filename in ("hits.jsonl", "chunks.jsonl"):
            path = self.result / filename
            content = path.read_text()
            path.write_text(content + content)
        collected, summary = self.collect("--require-complete")
        self.assertEqual(collected.returncode, 0, collected.stderr + collected.stdout)
        self.assertEqual((summary["hits"], summary["counters"]["hits"], summary["counters"]["d_total"]), (1, 1, 99))
        audited = self.audit()
        self.assertEqual(audited.returncode, 0, audited.stderr + audited.stdout)
        self.assertIn("1/1 sampled", audited.stdout)

    def test_audit_refuses_a_different_worker_release_before_execution(self):
        worker, marker = self.tmp / "different_worker.py", self.tmp / "executed"
        worker.write_text(f"#!/usr/bin/env python3\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n")
        worker.chmod(0o755)
        audited = self.audit(worker)
        self.assertEqual(audited.returncode, 1, audited.stderr + audited.stdout)
        self.assertIn("SHA-256", audited.stderr)
        self.assertFalse(marker.exists())


PARTIAL_WORKER = r'''#!/usr/bin/env python3
import argparse, json, pathlib
ap = argparse.ArgumentParser()
for name in ("k", "d-start", "d-stop", "ratio-max", "deadline-seconds", "chunk"):
    ap.add_argument("--" + name, type=int, required=True)
ap.add_argument("--primitive", action="store_true")
a = ap.parse_args()
partial = pathlib.Path(__file__).with_name("partial").exists() and a.d_start < 5 < a.d_stop
stop = 5 if partial else a.d_stop
print(json.dumps({"type": "start", "method": "booker-sutherland-gap-v1", "k": str(a.k),
                  "d_start": str(a.d_start), "d_stop": str(a.d_stop), "ratio_max": str(a.ratio_max),
                  "primitive": a.primitive}), flush=True)
counts = dict.fromkeys(COUNTER_NAMES, 0)
counts["d_total"] = stop - a.d_start
if a.d_start <= 7 < a.d_stop:
    print(json.dumps({"type": "hit", "k": "7125", "x": "74", "y": "-67", "z": "-46",
                      "d": "7", "primitive": True}), flush=True)
    if 7 < stop:
        counts["hits"] = counts["hits_primitive"] = 1
print(json.dumps({"type": "chunk", "d_start": str(a.d_start), "d_stop": str(stop), "counters": counts}), flush=True)
print(json.dumps({"type": "end", "state": "partial" if partial else "complete", "d_next": str(stop)}), flush=True)
'''.replace("COUNTER_NAMES", repr(list(COUNTERS)))


class PartialHitIntegrity(ResultTools, unittest.TestCase):
    def setUp(self):
        self.tmp_context = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_context.cleanup)
        self.tmp = Path(self.tmp_context.name)
        self.worker = self.tmp / "partial_worker.py"
        self.worker.write_text(PARTIAL_WORKER)
        self.worker.chmod(0o755)
        self.digest = hashlib.sha256(self.worker.read_bytes()).hexdigest()
        (self.tmp / "partial").touch()
        self.result = self.tmp / "result"
        planned = run_script("gap_campaign.py", "--campaign-id", "partial-hit", "--k", "7125",
                             "--d-start", "1", "--d-stop", "100", "--ratio-max", "64",
                             "--frontier", "0", "--output-dir", self.tmp / "campaign")
        self.assertEqual(planned.returncode, 0, planned.stderr)
        self.page = self.tmp / "campaign" / "page.json"
        task = next((self.tmp / "campaign" / "tasks").glob("*.json"))
        attempt = run_script("run_gap_task.py", "--task", task, "--output-dir", self.result, "--worker", self.worker)
        self.assertEqual(attempt.returncode, 0, attempt.stderr + attempt.stdout)

    def test_uncommitted_hit_is_preserved_then_deduplicated_on_resume(self):
        collected, summary = self.collect()
        self.assertEqual(collected.returncode, 0, collected.stderr + collected.stdout)
        self.assertEqual((summary["hits"], summary["counters"]["hits"]), (1, 0))
        self.assertEqual(summary["covered_d"], [["1", "5"]])
        audited = self.audit()
        self.assertEqual(audited.returncode, 0, audited.stderr + audited.stdout)
        (self.tmp / "partial").unlink()
        resumed = run_script("run_gap_task.py", "--task", self.result / "continuation.task.json",
                             "--output-dir", self.result, "--worker", self.worker)
        self.assertEqual(resumed.returncode, 0, resumed.stderr + resumed.stdout)
        collected, summary = self.collect("--require-complete")
        self.assertEqual(collected.returncode, 0, collected.stderr + collected.stdout)
        self.assertEqual((summary["hits"], summary["counters"]["hits"]), (1, 1))
        self.assertEqual(summary["covered_d"], [["1", "100"]])
        audited = self.audit()
        self.assertEqual(audited.returncode, 0, audited.stderr + audited.stdout)
        self.assertIn("2/2 sampled", audited.stdout)

    def test_truncated_uncommitted_hit_is_detected_by_terminal_status(self):
        (self.result / "hits.jsonl").write_text("")
        self.assert_rejected()

    def test_stale_running_status_does_not_discard_durable_partial_work(self):
        path = self.result / "status.json"
        status = json.loads(path.read_text())
        status.update({"state": "running", "d_next": "1", "hits": 0, "counters": dict.fromkeys(COUNTERS, 0)})
        write_json(path, status)
        collected, summary = self.collect()
        self.assertEqual(collected.returncode, 0, collected.stderr + collected.stdout)
        self.assertEqual((summary["covered_d"], summary["hits"]), ([["1", "5"]], 1))


if __name__ == "__main__":
    unittest.main()
