"""General a/q campaign, supervisor and collection contracts.

Worker mocks deliberately return no discoveries.  The two synthetic-certificate
tests patch only the mathematical verifier to exercise collection/indexing; their
invented numbers are NOT equation solutions or positive discovery fixtures.
"""
import argparse
import copy
from fractions import Fraction
import json
from math import gcd
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import campaign
import collector
import run_task


class GeneralIntegrationTests(unittest.TestCase):
    Q_MIN = 10**12 + 1
    Q_MAX = 10**12 + 1001

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.worker = self.folder / "protocol_mock.py"
        self.marker = self.folder / "allow_completion"
        self.trace = self.folder / "submitted_pairs.jsonl"

    def tearDown(self):
        self.temp.cleanup()

    def generate(self, name="general", **overrides):
        values = dict(campaign_id="integration-" + name, a_values=None,
                      q_min=str(self.Q_MIN), q_max=str(self.Q_MAX), allow_q_window=True,
                      candidates_per_task="8", page_start="0", task_count=1,
                      seconds=10, precision_bits=512, max_precision_bits=16384,
                      checkpoint_seconds=1, n_min=str(10**43), n_max=str(10**45),
                      x_min=str(10**54), x_max=str(10**55),
                      signs="all", require_integer_sqrt=True,
                      output_dir=self.folder / name)
        values.update(overrides)
        args = argparse.Namespace(**values)
        page = campaign.generate(args)
        page_path = args.output_dir / f"page-{int(args.page_start):012d}.json"
        tasks = [json.loads((args.output_dir / entry["file"]).read_text())
                 for entry in page["tasks"]]
        paths = [args.output_dir / entry["file"] for entry in page["tasks"]]
        return page_path, page, tasks, paths

    @staticmethod
    def production_row(q):
        """Direct finite integer inequalities, independent of GeneralAQ ranking."""
        n_min, n_max, x_min, x_max = 10**43, 10**45, 10**54, 10**55
        k_max = (36*n_max**3 + 65) // (x_min*(x_min-6*n_max))
        m_min, m_max = 12*n_min + 1, 12*n_max + k_max
        low = (m_min*q + x_max-1) // x_max
        high = min(m_max*q // x_min, m_max)
        return [(a, q) for a in range(low, high+1) if gcd(a, 6) == 1]

    def make_worker(self, hang_pair=None):
        self.worker.write_text(
            "#!/usr/bin/env python3\n"
            "import json,sys,time\nfrom pathlib import Path\n"
            f"marker=Path({str(self.marker)!r})\n"
            f"trace=Path({str(self.trace)!r})\n"
            f"hang_pair={hang_pair!r}\n"
            "for line in sys.stdin:\n"
            " a,q=map(int,line.split())\n"
            " with trace.open('a') as log:\n"
            "  log.write(json.dumps([a,q])+'\\n'); log.flush()\n"
            " if (a,q)==hang_pair and not marker.exists(): time.sleep(3600)\n"
            " print(json.dumps({'a':str(a),'q':str(q),'status':'complete',"
            "'parameterization':'absolute-slope-a-over-q-v1','hits':[],"
            "'convergents':'1','congruences_enforced':True,"
            "'integer_sqrt_required':'--integer-sqrt' in sys.argv,"
            "'excluded_by_bounds':False,'excluded_by_congruence':False,"
            "'signs':sys.argv[sys.argv.index('--signs')+1]}),flush=True)\n",
            encoding="utf-8")
        self.worker.chmod(0o755)

    def run_supervisor(self, task_path, output):
        result = subprocess.run(
            [sys.executable, str(ROOT / "run_task.py"), "--task", str(task_path),
             "--worker", str(self.worker), "--output-dir", str(output)],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return json.loads((output / "status.json").read_text())

    def test_cli_default_is_general_with_complete_derived_q_window(self):
        output = self.folder / "cli"
        result = subprocess.run(
            [sys.executable, str(ROOT / "campaign.py"), "--campaign-id", "general-default",
             "--task-count", "1", "--candidates-per-task", "4",
             "--output-dir", str(output)],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        page = json.loads((output / "page-000000000000.json").read_text())
        task = json.loads((output / page["tasks"][0]["file"]).read_text())
        self.assertEqual(task["fibers"], {"mode": "general-aq-v1", "q_min": "1", "q_max": str(10**55)})
        self.assertIs(task["search"]["require_integer_sqrt"], True)
        self.assertEqual(task["search"]["signs"], "all")
        self.assertNotIn("a_values", task["fibers"])
        self.assertGreater(int(page["total_candidate_indices"]), 10**80)
        parsed = run_task.validate_task(task)
        self.assertEqual(len(list(run_task.iter_candidates(parsed, 0, 4))), 4)

    def test_wide_q_pages_cover_many_numerators_and_partition_exactly(self):
        _, first, tasks1, _ = self.generate("wide", candidates_per_task="4096", task_count=2)
        _, second, tasks2, _ = self.generate("wide", candidates_per_task="4096", task_count=2, page_start="2")
        tasks = tasks1 + tasks2
        self.assertEqual(first["next_page_start"], "2")
        self.assertEqual(second["page_start"], "2")
        self.assertEqual([task["slice"] for task in tasks],
                         [{"start": str(i*4096), "stop": str((i+1)*4096)} for i in range(4)])
        actual = []
        for task in tasks:
            parsed = run_task.validate_task(task)
            actual.extend(run_task.iter_candidates(parsed, parsed["start"], parsed["stop"]))
        expected = []
        for q in range(self.Q_MIN, self.Q_MAX+1):
            if gcd(q, 6) == 1:
                expected.extend(self.production_row(q))
            if len(expected) >= len(actual):
                break
        self.assertEqual(actual, expected[:len(actual)])
        self.assertEqual(len(set(actual)), len(actual))
        self.assertGreater(len({a for a, _ in actual}), 1000)
        self.assertGreater(len({q for _, q in actual}), 1)
        parsed = run_task.validate_task(tasks[0])
        for index in (0, 4095, 4096, 8191, len(actual)-1):
            self.assertEqual(run_task.candidate(parsed, index), actual[index])
            self.assertEqual(run_task.candidate_index(parsed, *actual[index]), index)

    def test_legacy_identity_and_index_order_are_unchanged(self):
        task = {"schema": "ce390-task-v2", "parameterization": "absolute-slope-a-over-q-v1",
                "campaign_id": "legacy-index-regression",
                "search": {"n_min": str(10**43), "n_max": str(10**45),
                           "x_min": str(10**54), "x_max": str(10**55),
                           "signs": "all", "require_integer_sqrt": True},
                "fibers": {"a_values": ["1", "5", "7"], "q_min": "11", "q_max": "17"},
                "slice": {"start": "0", "stop": "12"},
                "execution": {"time_limit_seconds": 10, "precision_bits": 512},
                "task_id": "67ad04a355d63a747a7a93e8f427d9d44f31ac5bd6074db54498ae2683974098"}
        self.assertEqual(run_task.task_identity(task), task["task_id"])
        parsed = run_task.validate_task(task)
        expected = [(a, q) for a in (1, 5, 7) for q in (11, 13, 15, 17)]
        self.assertEqual(list(run_task.iter_candidates(parsed, 0, 12)), expected)
        for index, pair in enumerate(expected):
            self.assertEqual(run_task.candidate(parsed, index), pair)
            self.assertEqual(run_task.candidate_index(parsed, *pair), index)
        with self.assertRaises(ValueError):
            run_task.candidate_index(parsed, 1, 19)

    def test_general_rejects_rational_missing_mixed_and_unsupported_scope(self):
        _, _, tasks, _ = self.generate()
        cases = [("rational", lambda t: t["search"].update(require_integer_sqrt=False)),
                 ("missing root policy", lambda t: t["search"].pop("require_integer_sqrt")),
                 ("mixed modes", lambda t: t["fibers"].update(a_values=["1"])),
                 ("unsupported n=1", lambda t: t["search"].update(n_min="1")),
                 ("unsupported mode", lambda t: t["fibers"].update(mode="general-aq-v999")),
                 ("unproved denominator ceiling", lambda t: t["fibers"].update(q_max=str(10**55+1)))]
        for label, change in cases:
            with self.subTest(case=label):
                altered = copy.deepcopy(tasks[0])
                change(altered)
                altered["task_id"] = run_task.task_identity(altered)
                with self.assertRaises(ValueError):
                    run_task.validate_task(altered)

    def test_cli_explicit_numerator_list_requires_denominator_bounds(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "campaign.py"), "--campaign-id", "legacy-needs-bounds",
             "--a-values", "1,5", "--output-dir", str(self.folder / "invalid")],
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires both --q-min and --q-max", result.stderr)

    def test_deadline_at_q_boundary_resumes_on_new_host_and_collects_without_gaps(self):
        first_row = self.production_row(self.Q_MIN)
        boundary = len(first_row)
        second_q = self.Q_MIN + 2
        second_row = self.production_row(second_q)
        hang_offset = next(i for i, (a, q) in enumerate(second_row) if gcd(a, q) == 1)
        hang_pair = second_row[hang_offset]
        cut = boundary + hang_offset
        page_path, _, tasks, paths = self.generate(
            "resume", candidates_per_task=str(boundary-2), page_start="1", seconds=1)
        task, task_path = tasks[0], paths[0]
        start, stop = int(task["slice"]["start"]), int(task["slice"]["stop"])
        self.assertLess(start, boundary)
        self.assertLess(cut, stop)
        self.make_worker(hang_pair)
        first_output = self.folder / "archived-first-host"
        first = self.run_supervisor(task_path, first_output)
        self.assertEqual(first["state"], "partial")
        self.assertEqual(first["reason"], "time_limit")
        self.assertEqual(first["next_index"], str(cut))
        self.assertEqual(first["output_coverage"], {"start": str(start), "stop": str(cut)})
        before = [tuple(json.loads(line)) for line in self.trace.read_text().splitlines()]
        self.assertEqual(before[-1], hang_pair)
        self.assertTrue(any(q == self.Q_MIN for _, q in before))
        continuation = json.loads((first_output / "continuation.task.json").read_text())
        self.assertEqual(continuation["task_id"], task["task_id"])
        self.assertEqual(continuation["resume_index"], str(cut))
        # Execution budget is mutable; the mathematical task identity is fixed.
        continuation["execution"]["time_limit_seconds"] = 10
        resumed_input = self.folder / "continuation-input.json"
        resumed_input.write_text(json.dumps(continuation), encoding="utf-8")
        self.marker.touch()
        returns = self.folder / "returns"
        second_output = returns / "second-host"
        second = self.run_supervisor(resumed_input, second_output)
        self.assertTrue(second["complete"])
        self.assertEqual(second["output_coverage"], {"start": str(cut), "stop": str(stop)})
        after = [tuple(json.loads(line)) for line in self.trace.read_text().splitlines()]
        self.assertEqual(after[len(before)], hang_pair, "the unfinished pair must be replayed")
        parsed = run_task.validate_task(task)
        expected = [pair for pair in run_task.iter_candidates(parsed, start, stop) if gcd(*pair) == 1]
        self.assertEqual(before[:-1] + after[len(before):], expected)
        suffix_only = collector.collect([page_path], returns, self.folder / "suffix-only")
        self.assertFalse(suffix_only["complete_selected_page"])
        self.assertEqual(suffix_only["tasks"][0]["gaps"], [{"start": str(start), "stop": str(cut)}])
        shutil.copytree(first_output, returns / "first-host")
        complete = collector.collect([page_path], returns, self.folder / "all-returns")
        self.assertTrue(complete["complete_selected_page"])
        self.assertEqual(complete["tasks"][0]["coverage"], [{"start": str(start), "stop": str(stop)}])
        self.assertEqual(complete["tasks"][0]["overlapping_returned_indices"], "0")

    def synthetic_collection_fixture(self):
        """Protocol data only: callers MUST mock the equation verifier explicitly."""
        page_path, _, tasks, paths = self.generate("synthetic", candidates_per_task="4")
        self.make_worker()
        returns = self.folder / "synthetic-returns"
        output = returns / "host"
        status = self.run_supervisor(paths[0], output)
        task = tasks[0]
        a, q = self.production_row(self.Q_MIN)[0]
        n = 10**43
        scale = 10**43 - 10**40 + 1
        x = q*scale
        y = x-6*n+a*scale
        d = -1-Fraction(a, 2*q)
        checked = {"n": str(n), "x": str(x), "y_num": str(y), "y_den": "1",
                   "d_num": str(d.numerator), "d_den": str(d.denominator), "sqrt_integer": True}
        row = dict(checked, a=str(a), q=str(q), candidate_index="0", task_id=task["task_id"],
                   certificate_sha256=run_task.certificate_key(checked))
        status["unique_hits_in_this_output"] = "1"
        status["counters_this_invocation"]["new_hits"] = "1"
        (output / "status.json").write_text(json.dumps(status), encoding="utf-8")
        (output / "hits.jsonl").write_text(json.dumps(row)+"\n", encoding="utf-8")
        return page_path, returns, output, checked, row

    def test_collector_general_inverse_protocol_with_explicit_math_mock(self):
        page, returns, _, checked, row = self.synthetic_collection_fixture()
        # This isolates index inversion; it does not claim this row is a solution.
        with patch.object(collector, "verify_record", return_value=checked) as math_verifier:
            result = collector.collect([page], returns, self.folder / "synthetic-collected")
        self.assertTrue(result["complete_selected_page"])
        self.assertEqual(result["unique_verified_solutions"], 1)
        self.assertIs(math_verifier.call_args.kwargs["require_integer_sqrt"], True)
        collected = json.loads((self.folder / "synthetic-collected" / "hits.jsonl").read_text())
        self.assertEqual((collected["a"], collected["q"]), (row["a"], row["q"]))
        self.assertEqual(collected["sources"][0]["candidate_index"], "0")

    def test_collector_rejects_wrong_general_index_even_with_math_mock(self):
        page, returns, output, checked, row = self.synthetic_collection_fixture()
        row["candidate_index"] = "1"
        (output / "hits.jsonl").write_text(json.dumps(row)+"\n", encoding="utf-8")
        with patch.object(collector, "verify_record", return_value=checked):
            with self.assertRaisesRegex(ValueError, "candidate_index"):
                collector.collect([page], returns, self.folder / "bad-index-collected")


if __name__ == "__main__":
    unittest.main()
