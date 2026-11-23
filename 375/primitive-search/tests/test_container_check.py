"""Offline Docker command/cleanup guards. Real image execution is a separate CI gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from container_check import Harness  # noqa: E402


class ContainerGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        args = argparse.Namespace(image="primitive375:local", output_dir=self.root / "check", docker="docker", timeout=30)
        with patch("container_check.shutil.which", return_value="/mock/docker"):
            self.harness = Harness(args)

    def test_container_is_offline_uses_absolute_mounts_and_is_cleaned_up(self):
        self.harness.execute = Mock(return_value="ok")
        input_dir = self.root / "input with spaces"
        input_dir.mkdir()
        output_dir = self.root / "output with spaces"
        with patch("container_check.subprocess.run") as cleanup:
            result = self.harness.container("bundle", input_dir=input_dir, output_dir=output_dir, copy_index=0)
        self.assertEqual(result, "ok")
        command = self.harness.execute.call_args.args[1]
        self.assertIn("--pull=never", command)
        self.assertEqual(command[command.index("--network") + 1], "none")
        self.assertIn(f"type=bind,source={input_dir.resolve()},target=/local/input,readonly", command)
        self.assertIn(f"type=bind,source={output_dir.resolve()},target=/local/output", command)
        self.assertEqual(command[command.index("--env") + 1], "CE_JOB_COPY=0")
        self.assertEqual(command[-1], "primitive375:local")  # Deliberately exercises the default entrypoint.
        name = command[command.index("--name") + 1]
        self.assertEqual(cleanup.call_args.args[0], ["/mock/docker", "rm", "--force", name])

    def test_failed_or_timed_out_client_still_removes_daemon_container(self):
        self.harness.execute = Mock(side_effect=RuntimeError("timed out"))
        with patch("container_check.subprocess.run") as cleanup:
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                self.harness.container("timeout")
        self.assertEqual(cleanup.call_count, 1)
        self.assertEqual(cleanup.call_args.args[0][1:3], ["rm", "--force"])

    def test_stale_image_source_is_rejected_before_search(self):
        self.harness.execute = Mock(return_value="sha256:" + "1" * 64)
        self.harness.container = Mock(return_value=json.dumps({"source_sha256": "0" * 64, "worker_sha256": "2" * 64}))
        with self.assertRaisesRegex(ValueError, "source SHA-256 differs"):
            self.harness.run()
        self.assertEqual(self.harness.container.call_count, 1)
        report = json.loads((self.harness.out / "report.json").read_text())
        self.assertEqual(report["state"], "failed")
        self.assertFalse((self.harness.out / "fixtures").exists())


if __name__ == "__main__":
    unittest.main()
