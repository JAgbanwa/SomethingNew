"""CE allocation/duplicate guards and the two-worker container runtime; no remote jobs."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ce_submit  # noqa: E402
from gap_common import METHOD, TASK_SCHEMA  # noqa: E402
from run_ce_bundle import validate_bundle  # noqa: E402


def manifest(groups=1):
    tasks = [{"schema": TASK_SCHEMA, "method": METHOD, "campaign_id": "test375", "task_id": f"task-{i:04d}",
              "k": 375, "d_start": str(10000 + i * 100), "d_stop": str(10100 + i * 100),
              "ratio_max": 64, "primitive_only": True, "height_min": "1000000000000000",
              "deadline_seconds": 10} for i in range(groups * 2)]
    return {"schema": "ce375-bundle-v1", "campaign_id": "test375", "groups": [tasks[i:i + 2] for i in range(0, len(tasks), 2)],
            "max_instance_hours": 1, "cores_per_instance": 2, "total_reserved_core_hours": groups * 2}


class Launcher(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle_path = self.root / "manifest.json"
        self.state = self.root / "state"
        self.bundle = manifest()
        self.write_bundle()
        self.base = ["--manifest", str(self.bundle_path), "--image", "docker:example/ce375:test-v1",
                     "--ce-cli", sys.executable, "--workdir", str(self.state)]
        self.secret = "SECRET_TEST_CE_AUTH_TOKEN_MUST_STAY_PRIVATE"

    def write_bundle(self):
        self.bundle_path.write_text(json.dumps(self.bundle), encoding="utf-8")

    def main(self, *options, token=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        environment = dict(os.environ)
        environment.pop("CE_AUTH_TOKEN", None)
        if token is not None:
            environment["CE_AUTH_TOKEN"] = token
        with patch.dict(os.environ, environment, clear=True), redirect_stdout(stdout), redirect_stderr(stderr):
            rc = ce_submit.main([*self.base, *options])
        return rc, stdout.getvalue(), stderr.getvalue()

    def ledger(self):
        return json.loads((self.state / "submission-ledger.json").read_text())

    def good_ce(self, command, **kwargs):
        # The reservation must already be durable when anything external runs.
        record = self.ledger()["batches"]["0"]
        self.assertIn(record["state"], {"reserved", "submitted", "unknown"})
        self.assertEqual(self.ledger()["reserved_core_hours"], "2")
        self.assertEqual(command[command.index("--auth") + 1], self.secret)
        self.assertNotIn("CE_AUTH_TOKEN", kwargs["env"])
        checkpoint = Path(command[command.index("--checkpointfile") + 1])
        checkpoint.write_text("test checkpoint with known jobs", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, f"submitted; diagnostic {self.secret}\n", "")

    def test_default_is_offline_dry_run_without_auth_or_cli(self):
        with patch("ce_submit.invoke") as invoke:
            rc, stdout, stderr = self.main("--ce-cli", str(self.root / "not-installed"))
        self.assertEqual((rc, stderr), (0, ""))
        invoke.assert_not_called()
        review = json.loads(stdout)
        self.assertEqual(review["mode"], "dry-run")
        self.assertEqual(review["total_reserved_core_hours"], "2")
        self.assertTrue((self.state / "batch-0000" / "bundle.json").is_file())
        self.assertFalse((self.state / "submission-ledger.json").exists())

    def test_public_container_archive_is_one_app_argument(self):
        url = "https://github.com/example/search/releases/download/v1/ce375-image.tar"
        rc, stdout, stderr = self.main("--image-tar-url", url)
        self.assertEqual((rc, stderr), (0, ""))
        command = json.loads(stdout)["batches"][0]["command"]
        self.assertEqual(command[command.index("--app") + 1], "docker:example/ce375:test-v1 " + url)
        self.assertNotIn(url, command)
        self.assertIn("--batch", command)
        self.assertNotIn("--batchlabel", command)

    def test_archive_url_cannot_persist_credentials_or_secret_queries(self):
        urls = ("http://example.com/image.tar", "https://user:password@example.com/image.tar",
                "https://example.com/image.tar?token=secret", "https://example.com/image.tar#secret",
                "https://example.com/ima\nge.tar", "file:///tmp/image.tar")
        for url in urls:
            with self.subTest(url=url), patch("ce_submit.invoke") as invoke:
                rc, _stdout, stderr = self.main("--image-tar-url", url)
                self.assertEqual(rc, 2)
                self.assertIn("public HTTPS URL", stderr)
                invoke.assert_not_called()
                self.assertFalse(self.state.exists())

    def test_splits_501_instances_into_independent_copy_indices(self):
        self.bundle = manifest(501)
        self.write_bundle()
        rc, stdout, stderr = self.main()
        self.assertEqual((rc, stderr), (0, ""))
        review = json.loads(stdout)
        self.assertEqual([batch["copies"] for batch in review["batches"]], [500, 1])
        first = json.loads((self.state / "batch-0000" / "bundle.json").read_text())
        last = json.loads((self.state / "batch-0001" / "bundle.json").read_text())
        self.assertEqual((first["group_offset"], last["group_offset"]), (0, 500))
        self.assertEqual(last["groups"][0], self.bundle["groups"][500])
        self.assertEqual(last["total_reserved_core_hours"], 2)
        validate_bundle(first)
        validate_bundle(last)

    def test_budget_uses_reserved_two_core_instance_time(self):
        self.bundle = manifest(901)
        self.write_bundle()
        with patch("ce_submit.invoke") as invoke:
            rc, _stdout, stderr = self.main()
        self.assertEqual(rc, 2)
        self.assertIn("1802", stderr)
        invoke.assert_not_called()
        self.assertFalse(self.state.exists())
        self.bundle["total_reserved_core_hours"] = 1  # Underreporting does not bypass the allocation limit.
        self.write_bundle()
        rc, _stdout, stderr = self.main()
        self.assertEqual(rc, 2)
        self.assertIn("declared core-hour total", stderr)

    def test_missing_auth_blocks_before_any_reservation(self):
        with patch("ce_submit.invoke") as invoke:
            rc, stdout, stderr = self.main("--submit")
        self.assertEqual(rc, 2)
        self.assertIn("blocked: CE_AUTH_TOKEN", stderr)
        self.assertEqual(stdout, "")
        invoke.assert_not_called()
        self.assertFalse((self.state / "submission-ledger.json").exists())

    def test_submit_is_once_retrieve_is_identical_and_never_double_charged(self):
        with patch("ce_submit.subprocess.run", side_effect=self.good_ce) as execute:
            rc, stdout, stderr = self.main("--submit", token=self.secret)
            self.assertEqual((rc, stderr), (0, ""))
            first_command = execute.call_args.args[0]
            self.assertEqual(self.ledger()["batches"]["0"]["state"], "submitted")
            self.assertNotIn(self.secret, stdout)
            self.assertEqual(self.main("--submit", token=self.secret)[0], 0)
            self.assertEqual(execute.call_count, 1)
            self.assertEqual(self.main("--retrieve", token=self.secret)[0], 0)
            self.assertEqual(execute.call_count, 2)
            self.assertEqual(first_command, execute.call_args.args[0])
        self.assertEqual(self.ledger()["reserved_core_hours"], "2")
        for path in self.state.rglob("*"):
            if path.is_file():
                self.assertNotIn(self.secret.encode(), path.read_bytes(), str(path))

    def test_failure_is_unknown_and_never_automatically_resubmitted(self):
        def failed(command, **kwargs):
            self.assertEqual(self.ledger()["batches"]["0"]["state"], "reserved")
            return subprocess.CompletedProcess(command, 3, "", self.secret)
        with patch("ce_submit.subprocess.run", side_effect=failed) as execute:
            rc, stdout, stderr = self.main("--submit", token=self.secret)
            self.assertEqual(rc, 1)
            self.assertNotIn(self.secret, stdout + stderr)
            self.assertEqual(self.ledger()["batches"]["0"]["state"], "unknown")
            self.assertEqual(self.main("--submit", token=self.secret)[0], 2)
            rc, _stdout, stderr = self.main("--retrieve", token=self.secret)
            self.assertEqual(rc, 2)
            self.assertIn("checkpoint is absent", stderr)
            self.assertEqual(execute.call_count, 1)
        self.assertEqual(self.ledger()["reserved_core_hours"], "2")

    def test_missing_checkpoint_never_creates_jobs_during_retrieval(self):
        with patch("ce_submit.subprocess.run", side_effect=self.good_ce) as execute:
            self.assertEqual(self.main("--submit", token=self.secret)[0], 0)
            (self.state / "batch-0000" / "ce-checkpoint.sqlite").unlink()
            rc, _stdout, stderr = self.main("--retrieve", token=self.secret)
            self.assertEqual(rc, 2)
            self.assertIn("refusing retrieval", stderr)
            self.assertEqual(execute.call_count, 1)

    def test_retrieval_without_ledger_and_zero_checkpoint_is_blocked(self):
        with patch("ce_submit.invoke") as invoke:
            rc, _stdout, stderr = self.main("--retrieve", token=self.secret)
            self.assertEqual(rc, 2)
            self.assertIn("no submission ledger", stderr)
            invoke.assert_not_called()
        with patch("ce_submit.subprocess.run", side_effect=self.good_ce):
            self.assertEqual(self.main("--submit", token=self.secret)[0], 0)
        (self.state / "batch-0000" / "ce-checkpoint.sqlite").write_bytes(b"")
        with patch("ce_submit.invoke") as invoke:
            self.assertEqual(self.main("--retrieve", token=self.secret)[0], 2)
            invoke.assert_not_called()

    def test_external_exception_reservation_is_kept_without_leaking_arguments(self):
        with patch("ce_submit.invoke", side_effect=OSError(self.secret)):
            rc, stdout, stderr = self.main("--submit", token=self.secret)
        self.assertEqual(rc, 1)
        self.assertNotIn(self.secret, stdout + stderr)
        self.assertEqual(self.ledger()["reserved_core_hours"], "2")
        self.assertEqual(self.ledger()["batches"]["0"]["state"], "unknown")

    def test_mutated_plan_or_staged_input_is_not_silently_replaced(self):
        self.assertEqual(self.main()[0], 0)
        self.bundle["groups"][0][0]["ratio_max"] = 128
        self.write_bundle()
        rc, _stdout, stderr = self.main()
        self.assertEqual(rc, 2)
        self.assertIn("different plan", stderr)
        self.bundle["groups"][0][0]["ratio_max"] = 64
        self.write_bundle()
        staged = self.state / "batch-0000" / "bundle.json"
        staged.write_text("{}", encoding="utf-8")
        rc, _stdout, stderr = self.main()
        self.assertEqual(rc, 2)
        self.assertIn("staged batch input changed", stderr)

    def test_rejects_unsafe_ids_duplicates_missing_deadlines_and_nonprimitive_tasks(self):
        for field, value in (("task_id", "../escape"), ("deadline_seconds", 0),
                             ("deadline_seconds", 3550), ("primitive_only", False)):
            with self.subTest(field=field, value=value):
                bad = manifest()
                bad["groups"][0][0][field] = value
                with self.assertRaises(ValueError):
                    validate_bundle(bad)
        bad = manifest()
        bad["groups"][0][1]["task_id"] = bad["groups"][0][0]["task_id"]
        with self.assertRaises(ValueError):
            validate_bundle(bad)

    def test_multiband_task_campaigns_require_an_explicit_allowlist(self):
        bundle = manifest()
        bundle["groups"][0][0]["campaign_id"] = "test375-b000"
        bundle["groups"][0][1]["campaign_id"] = "test375-b001"
        with self.assertRaisesRegex(ValueError, "unlisted campaign"):
            validate_bundle(bundle)
        bundle["task_campaign_ids"] = ["test375-b000", "test375-b001"]
        validate_bundle(bundle)
        bundle["task_campaign_ids"].append("test375-b001")
        with self.assertRaisesRegex(ValueError, "unique safe"):
            validate_bundle(bundle)


FAKE_RUNNER = r'''
import argparse, json, os, pathlib, signal, sys, time
p = argparse.ArgumentParser()
p.add_argument('--task'); p.add_argument('--output-dir'); p.add_argument('--worker'); p.add_argument('--deadline-seconds')
a = p.parse_args()
task = json.loads(pathlib.Path(a.task).read_text())
out = pathlib.Path(a.output_dir)
def finish(state):
    (out / 'status.json').write_text(json.dumps({'campaign_id': task['campaign_id'], 'task_id': task['task_id'],
        'state': state, 'credential_present': 'CE_AUTH_TOKEN' in os.environ}))
def stop(sig, frame):
    time.sleep(.05)
    finish('partial')
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
(out.parent / (task['task_id'] + '.started')).write_text(str(os.getpid()))
limit = time.monotonic() + 5
while len(list(out.parent.glob('*.started'))) < 2:
    if time.monotonic() > limit:
        sys.exit(7)
    time.sleep(.01)
if os.environ.get('WAIT_FOR_SIGNAL') == '1':
    while True: time.sleep(.05)
time.sleep(.05)
finish('complete')
'''


class BundleRuntime(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = manifest(2)
        self.manifest_path = self.root / "bundle.json"
        self.manifest_path.write_text(json.dumps(self.bundle))
        self.fake = self.root / "fake_runner.py"
        self.fake.write_text(FAKE_RUNNER)
        self.out = self.root / "output"
        self.command = [sys.executable, str(ROOT / "run_ce_bundle.py"), "--manifest", str(self.manifest_path),
                        "--output-dir", str(self.out), "--runner", str(self.fake), "--grace-seconds", "2"]
        self.environment = dict(os.environ, CE_JOB_COPY="1", CE_AUTH_TOKEN="SECRET_NOT_FOR_COMPUTE")

    def test_copy_selects_exactly_two_concurrent_tasks_and_strips_auth(self):
        self.bundle["task_campaign_ids"] = ["test375", "test375-b001"]
        self.bundle["groups"][1][1]["campaign_id"] = "test375-b001"
        self.manifest_path.write_text(json.dumps(self.bundle))
        result = subprocess.run(self.command, env=self.environment, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        status = json.loads((self.out / "bundle.status.json").read_text())
        self.assertEqual(status["state"], "complete")
        self.assertEqual([task["task_id"] for task in status["tasks"]], ["task-0002", "task-0003"])
        self.assertFalse((self.out / "task-0000").exists())
        for name in ("task-0002", "task-0003"):
            task_status = json.loads((self.out / name / "status.json").read_text())
            self.assertFalse(task_status["credential_present"])

    def test_signal_is_forwarded_and_both_checkpoints_are_drained(self):
        environment = dict(self.environment, WAIT_FOR_SIGNAL="1")
        process = subprocess.Popen(self.command, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            until = time.monotonic() + 10
            while len(list(self.out.glob("*.started"))) < 2 and time.monotonic() < until:
                self.assertIsNone(process.poll(), "bundle exited before both tasks started")
                time.sleep(.02)
            self.assertEqual(len(list(self.out.glob("*.started"))), 2)
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            status = json.loads((self.out / "bundle.status.json").read_text())
            self.assertEqual(status["state"], "partial")
            self.assertTrue(all(task["state"] == "partial" for task in status["tasks"]))
            self.assertIn("signal", status["stop_reason"])
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()

    def test_invalid_copy_index_and_source_binding_fail_before_launch(self):
        result = subprocess.run(self.command, env=dict(self.environment, CE_JOB_COPY="2"),
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.out.exists())
        self.bundle["worker_source_sha256"] = "0" * 64
        self.manifest_path.write_text(json.dumps(self.bundle))
        result = subprocess.run(self.command, env=self.environment, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("source SHA-256 differs", result.stderr)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
