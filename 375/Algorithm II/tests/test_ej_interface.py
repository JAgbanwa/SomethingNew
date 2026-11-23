"""Independent worker-contract checks; incomplete output is never coverage."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elkies_jahnel import (EJWorkerError, WORKER_VERSION, build_worker,
                          iter_shell, minimum_index)


class NativeInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker = build_worker()

    def test_nonempty_control_and_partial_resume(self):
        options = {"target": 6, "worker": self.worker, "progress_every": 1}
        full = list(iter_shell(65, **options))
        first = list(iter_shell(65, max_tiles=2, **options))
        self.assertFalse(first[-1]["complete"])
        tail = list(iter_shell(65, index_stop=int(first[-1]["next_index"]), **options))
        hits = lambda rows: {tuple(int(r[k]) for k in ("x", "y", "z"))
                             for r in rows if r["type"] == "hit"}
        self.assertIn((-43, -58, 65), hits(full))
        self.assertEqual(hits(full), hits(first) | hits(tail))
        self.assertFalse(hits(first) & hits(tail))
        self.assertTrue(full[-1]["complete"])
        self.assertTrue(tail[-1]["complete"])

    def test_nonprimitive_375_never_passes_primitive_worker(self):
        all_rows = list(iter_shell(25, primitive=False, worker=self.worker))
        hits = [r for r in all_rows if r["type"] == "hit"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(tuple(int(hits[0][k]) for k in ("x", "y", "z")), (20, 20, -25))
        self.assertFalse(hits[0]["primitive"])
        self.assertFalse(any(r["type"] == "hit" for r in iter_shell(25, worker=self.worker)))

    def test_empty_band_is_complete_without_work(self):
        low = minimum_index(25)
        rows = list(iter_shell(25, index_start=low, index_stop=low, worker=self.worker))
        self.assertTrue(rows[-1]["complete"])
        self.assertEqual(rows[-1]["tiles"], 0)

    def test_invalid_inputs_are_rejected_before_worker_launch(self):
        invalid = [dict(height=24), dict(height=25, target=380),
                   dict(height=25, target=8), dict(height=True),
                   dict(height=25, index_start=0), dict(height=25, index_stop=101),
                   dict(height=25, max_tiles=-1), dict(height=25, primitive=1),
                   dict(height=25, tile_scale="0"), dict(height=25, tile_scale=0.5)]
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(ValueError):
                list(iter_shell(worker="/does/not/exist", **options))


class InvalidNativeOutput(unittest.TestCase):
    def records(self):
        return [{"type": "start", "engine": "elkies-jahnel", "version": WORKER_VERSION,
                 "k": 375, "height": "25", "index_start": str(minimum_index(25)),
                 "index_stop": "100", "primitive": True},
                {"type": "end", "complete": True, "next_index": str(minimum_index(25)),
                 "tiles": 1, "lattice_points": "10", "reason": "complete"}]

    def run_fake(self, records, code=0):
        (ROOT / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ej-contract-", dir=ROOT / "build") as directory:
            worker = Path(directory) / "worker"
            worker.write_text("#!/usr/bin/env python3\nimport json\n"
                              + f"records = {records!r}\n"
                              + "for record in records: print(json.dumps(record), flush=True)\n"
                              + f"raise SystemExit({code})\n", encoding="utf-8")
            worker.chmod(0o755)
            return list(iter_shell(25, worker=worker))

    def test_missing_terminal_and_wrong_scope_are_errors(self):
        with self.assertRaises(EJWorkerError):
            self.run_fake(self.records()[:1])
        rows = self.records()
        rows[0]["height"] = "50"
        with self.assertRaises(EJWorkerError):
            self.run_fake(rows)

    def test_wrong_hit_is_rejected(self):
        rows = self.records()
        rows.insert(1, {"type": "hit", "k": 375, "x": "20", "y": "20", "z": "-25",
                        "height": "25", "primitive": True})
        with self.assertRaises(EJWorkerError):
            self.run_fake(rows)

    def test_no_completion_on_nonzero_exit_or_trailing_output(self):
        with self.assertRaises(EJWorkerError):
            self.run_fake(self.records(), code=2)
        with self.assertRaises(EJWorkerError):
            self.run_fake(self.records() + [{"type": "surprise"}])

    def test_contradictory_completion_is_rejected(self):
        rows = self.records()
        rows[-1]["next_index"] = "99"
        with self.assertRaises(EJWorkerError):
            self.run_fake(rows)
        rows = self.records()
        rows[-1]["tiles"] = 0
        with self.assertRaises(EJWorkerError):
            self.run_fake(rows)


if __name__ == "__main__":
    unittest.main()
