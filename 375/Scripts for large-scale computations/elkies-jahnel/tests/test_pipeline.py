"""Finite end-to-end and failure-contract tests for the separate EJ schema."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ej375 as ej


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, ok=True):
        p = subprocess.run([sys.executable, str(ROOT / "ej375.py"), *map(str, args)],
                           capture_output=True, text=True, timeout=60)
        if ok:
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        else:
            self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)
        return p

    def page(self, max_tiles=0, worker_sha=None):
        path = self.dir / "page"
        extra = [] if worker_sha is None else ["--worker-sha256", worker_sha]
        self.cli("plan", "--height", 64, "--k", 6, "--campaign-id", "test",
                 "--grid-span", 1000, "--page-size", 1, "--max-tiles", max_tiles,
                 "--output-dir", path, *extra)
        page = ej.load(path / "page.json")
        return path / "page.json", path / page["tasks"][0]["path"]

    def test_nonempty_plan_run_collect(self):
        page, task = self.page()
        out = self.dir / "results" / "one"
        self.cli("run", "--task", task, "--output-dir", out)
        status = ej.load(out / "status.json")
        self.assertEqual(status["state"], "complete")
        hits = [json.loads(s) for s in (out / "hits.jsonl").read_text().splitlines()]
        self.assertEqual([ej.verify_hit(h, ej.load(task)) for h in hits], [(-43, -58, 65)])
        hits[0]["original_points"] = ["untrusted altered metadata"]
        (out / "hits.jsonl").write_text(json.dumps(hits[0])+"\n")
        dest = self.dir / "collected"
        self.cli("collect", "--page", page, "--results", out.parent,
                 "--output-dir", dest, "--require-complete")
        summary = ej.load(dest / "summary.json")
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["hits"], 1)
        self.assertFalse(summary["gaps"])
        self.assertEqual(json.loads((dest / "hits.jsonl").read_text())["original_points"], [])

    def test_repeated_same_task_resumes_completed_tiles(self):
        _, task = self.page(max_tiles=1)
        out = self.dir / "result"
        cursors = []
        for _ in range(20):
            self.cli("run", "--task", task, "--output-dir", out)
            cp = ej.load(out / "checkpoint.json")
            cursors.append(int(cp["next_index"]))
            if cp["complete"]:
                break
        self.assertTrue(cp["complete"])
        self.assertTrue(all(a > b for a, b in zip(cursors, cursors[1:])))
        self.assertEqual(len((out / "hits.jsonl").read_text().splitlines()), 1)

    def test_separate_continuations_require_all_returned_intervals(self):
        page, task = self.page(max_tiles=1)
        root = self.dir / "results"
        for i in range(20):
            out = root / str(i)
            self.cli("run", "--task", task, "--output-dir", out)
            if ej.load(out / "checkpoint.json")["complete"]:
                break
            task = out / "continuation.task.json"
        self.assertLess(i, 19)
        self.cli("collect", "--page", page, "--results", root,
                 "--output-dir", self.dir / "all", "--require-complete")
        self.cli("collect", "--page", page, "--results", out,
                 "--output-dir", self.dir / "only_last", "--require-complete", ok=False)
        self.assertTrue(ej.load(self.dir / "only_last" / "summary.json")["gaps"])

    def test_invalid_hit_contributes_no_coverage(self):
        page, task = self.page()
        out = self.dir / "results" / "one"
        self.cli("run", "--task", task, "--output-dir", out)
        rec = json.loads((out / "hits.jsonl").read_text())
        rec["x"] = str(int(rec["x"])+1)
        (out / "hits.jsonl").write_text(json.dumps(rec)+"\n")
        dest = self.dir / "collected"
        self.cli("collect", "--page", page, "--results", out.parent,
                 "--output-dir", dest, ok=False)
        summary = ej.load(dest / "summary.json")
        self.assertFalse(summary["covered"])
        self.assertTrue(summary["errors"])

    def test_changed_binary_cannot_resume(self):
        _, task = self.page(max_tiles=1)
        out = self.dir / "result"
        self.cli("run", "--task", task, "--output-dir", out)
        old_status = (out / "status.json").read_bytes()
        copy = self.dir / "worker"
        shutil.copy2(ej.DEFAULT_WORKER, copy)
        with copy.open("ab") as f:
            f.write(b"\n")
        p = self.cli("run", "--task", task, "--output-dir", out, "--worker", copy, ok=False)
        self.assertIn("different task or worker binary", p.stderr)
        self.assertEqual((out / "status.json").read_bytes(), old_status)

    def test_missing_terminal_record_is_an_error(self):
        _, task = self.page()
        fake = self.dir / "fake_worker"
        fake.write_text(f"#!{sys.executable}\nimport json,sys\n"
            "a=dict(zip(sys.argv[1::2],sys.argv[2::2]))\n"
            "print(json.dumps({'type':'start','engine':'elkies-jahnel',"
            "'k':int(a['--target']),'height':a['--height'],"
            "'index_start':a['--index-start'],'index_stop':a['--index-stop'],'primitive':True}))\n")
        fake.chmod(0o755)
        out = self.dir / "result"
        self.cli("run", "--task", task, "--output-dir", out, "--worker", fake, ok=False)
        self.assertEqual(ej.load(out / "status.json")["state"], "error")
        self.assertFalse(ej.load(out / "checkpoint.json")["complete"])

    def test_terminal_batch_is_not_checkpointed_on_bad_end_or_failed_exit(self):
        _, task = self.page()
        for reason, rc in [("invalid", 0), ("tile_budget", 9)]:
            with self.subTest(reason=reason, exit_code=rc):
                fake = self.dir / f"worker_{reason}"
                fake.write_text(f"#!{sys.executable}\nimport json,sys\n"
                    "a=dict(zip(sys.argv[1::2],sys.argv[2::2]))\n"
                    "print(json.dumps({'type':'start','engine':'elkies-jahnel',"
                    "'k':int(a['--target']),'height':a['--height'],"
                    "'index_start':a['--index-start'],'index_stop':a['--index-stop'],'primitive':True}))\n"
                    "print(json.dumps({'type':'end','next_index':str(int(a['--index-stop'])-1),"
                    f"'tiles':1,'lattice_points':'1','complete':False,'reason':{reason!r}}}))\n"
                    f"sys.exit({rc})\n")
                fake.chmod(0o755)
                out = self.dir / reason
                self.cli("run", "--task", task, "--output-dir", out, "--worker", fake, ok=False)
                self.assertEqual(ej.load(out / "checkpoint.json")["next_index"], ej.load(task)["index_stop"])
                self.assertEqual(ej.load(out / "status.json")["state"], "error")

    def test_mixed_binaries_are_not_merged(self):
        page, task = self.page()
        results = self.dir / "results"
        self.cli("run", "--task", task, "--output-dir", results / "a")
        copy = self.dir / "worker"
        shutil.copy2(ej.DEFAULT_WORKER, copy)
        with copy.open("ab") as f:
            f.write(b"\n")
        self.cli("run", "--task", task, "--output-dir", results / "b", "--worker", copy)
        dest = self.dir / "collected"
        self.cli("collect", "--page", page, "--results", results,
                 "--output-dir", dest, ok=False)
        self.assertFalse(ej.load(dest / "summary.json")["covered"])

    def test_continuation_inherits_root_binary_pin(self):
        expected = ej.file_hash(ej.DEFAULT_WORKER)
        page, task = self.page(max_tiles=1, worker_sha=expected)
        first = self.dir / "first"
        self.cli("run", "--task", task, "--output-dir", first)
        cont = ej.load(first / "continuation.task.json")
        cont.pop("worker_sha256")
        continuation = self.dir / "continuation.json"
        ej.atomic_json(continuation, cont)
        copy = self.dir / "worker"
        shutil.copy2(ej.DEFAULT_WORKER, copy)
        with copy.open("ab") as f:
            f.write(b"\n")
        out = self.dir / "changed-child"
        self.cli("run", "--task", continuation, "--output-dir", out, "--worker", copy)
        dest = self.dir / "collected"
        self.cli("collect", "--page", page, "--results", out,
                 "--output-dir", dest, ok=False)
        self.assertFalse(ej.load(dest / "summary.json")["covered"])

    def test_cli_hash_cannot_override_task_pin(self):
        expected = ej.file_hash(ej.DEFAULT_WORKER)
        page, task = self.page(worker_sha=expected)
        out = self.dir / "result"
        self.cli("run", "--task", task, "--output-dir", out)
        self.cli("collect", "--page", page, "--results", out,
                 "--output-dir", self.dir / "collected",
                 "--expected-worker-sha256", "0"*64, ok=False)
        self.assertFalse(ej.load(self.dir / "collected" / "summary.json")["covered"])

    def test_planner_crosses_shells_without_final_upper_bound(self):
        page = self.dir / "first"
        self.cli("plan", "--height", 25, "--campaign-id", "shells", "--grid-span", 10000,
                 "--page-size", 2, "--output-dir", page)
        rows = [ej.load(page / p["path"]) for p in ej.load(page / "page.json")["tasks"]]
        self.assertEqual([r["height"] for r in rows], ["25", "50"])
        nxt = self.dir / "next"
        self.cli("plan", "--cursor", page / "next_plan.json", "--output-dir", nxt)
        first = ej.load(nxt / ej.load(nxt / "page.json")["tasks"][0]["path"])
        self.assertEqual(first["height"], "100")

    def test_schema_and_original_equation(self):
        with self.assertRaises(ValueError):
            ej.validate_task({"schema": "ce375-gap-task-v1"})
        with self.assertRaises(ValueError):
            ej.integer(2.0)
        self.cli("plan", "--height", 25, "--campaign-id", "bad-pin", "--worker-sha256", "",
                 "--output-dir", self.dir / "bad-pin", ok=False)
        pts = ej.original_points((20,20,-25), 375)
        half = [p for p in pts if p["chart"] == "half"]
        self.assertEqual(len(half), 1)
        self.assertEqual((half[0]["n"], half[0]["M"], half[0]["Y_abs"]), ("2", "5", "45"))


if __name__ == "__main__":
    unittest.main()
