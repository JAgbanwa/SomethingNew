"""Independent campaign coverage, continuation, corruption and locking checks.

The deliberately tiny integration job verifies the checkpoint protocol. Its
coordinates and duration are not represented as a large mathematical search.
Large arithmetic task partitions are checked without expanding their task lists.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import campaign375 as campaign  # noqa: E402
import search375  # noqa: E402
from equation375 import RationalDFilter, validate_point  # noqa: E402
from elkies_jahnel import minimum_index  # noqa: E402


def fixture_plan(families=None):
    if families is None:
        families = [{"engine": "elkies", "height": "25", "start": "30",
                     "stop": "100", "task_width": "70", "tile_scale": "11/2"}]
    return {
        "schema": campaign.SCHEMA, "target": "375", "name": "protocol-control",
        "created_utc": "2026-11-23T00:00:00+00:00",
        "status": "planned_only_no_completed_search_implied",
        "optional_filters": "none", "families": families,
        "task_count": str(sum(campaign.family_count(f) for f in families)),
        "source_sha256": {"search375.py": "test-source-fingerprint",
                          "campaign375.py": "test-campaign-fingerprint"},
    }


def fixture_records(plan, task, *, complete=True, next_value=None):
    """A valid zero-hit protocol fixture, not evidence of executed computation."""
    scope = campaign.expected_scope(task)
    is_bs = task["engine"] == "booker"
    if next_value is None:
        next_value = task["stop"] if is_bs else task["start"]
    terminal = ({"state": "complete" if complete else "partial", "d_next": str(next_value)}
                if is_bs else {"type": "end", "complete": complete,
                               "next_index": str(next_value)})
    start = {
        "type": "start", "schema": "algorithm-ii-375-v1", "version": search375.VERSION,
        "command": "booker-gap" if is_bs else "elkies-shell", "target": 375,
        "scope": scope,
        "source_sha256": {k: v for k, v in plan["source_sha256"].items()
                          if k != "campaign375.py"},
        "required": {"integer_n": True, "odd_X_Y": True, "gcd_X_Y": 1, "positive_Y": True},
        "n_filter": {"minimum": None, "maximum": None},
        "rational_d_filter": RationalDFilter().as_dict(),
    }
    end = {"type": "end", "scope": scope, "complete": complete,
           "status": "complete" if complete else "partial", "solutions": 0,
           "backend_terminal": terminal}
    return [start, end]


def write_records(path, records):
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records),
                    encoding="utf-8")


def save_checkpoint(plan, original, directory, records, returncode):
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "attempt-control.jsonl"
    write_records(output, records)
    remaining, complete, sha = campaign.read_attempt(output, original, plan, returncode)
    state = {"plan_sha256": campaign.plan_hash(plan), "task": original,
             "remaining": remaining, "complete": complete,
             "attempts": [{"output": output.name, "sha256": sha,
                           "returncode": returncode}]}
    campaign.atomic_json(directory / "state.json", state)
    return state


class ArithmeticTaskPartitions(unittest.TestCase):
    def test_plan_pins_the_exact_current_search_sources(self):
        plan = fixture_plan()
        plan["source_sha256"] = campaign.source_hashes()
        campaign.validate_plan(plan)
        changed = deepcopy(plan)
        changed["source_sha256"]["search375.py"] = "0" * 64
        with self.assertRaises(ValueError):
            campaign.validate_plan(changed)

    def test_partitions_have_no_gaps_overlaps_or_expanded_final_endpoint(self):
        plan = fixture_plan([
            {"engine": "booker", "start": "1", "stop": "12", "task_width": "4",
             "ratio_max": "1024"},
            {"engine": "elkies", "height": "25", "start": "30", "stop": "100",
             "task_width": "23", "tile_scale": "11/2"},
        ])
        tasks = [campaign.get_task(plan, i) for i in range(int(plan["task_count"]))]
        self.assertEqual([(int(t["start"]), int(t["stop"])) for t in tasks],
                         [(1, 5), (5, 9), (9, 12), (30, 53), (53, 76), (76, 99), (99, 100)])
        for engine, expected in (("booker", set(range(1, 12))),
                                 ("elkies", set(range(30, 100)))):
            visited = []
            for task in tasks:
                if task["engine"] == engine:
                    visited.extend(range(int(task["start"]), int(task["stop"])))
            self.assertEqual(set(visited), expected)
            self.assertEqual(len(visited), len(set(visited)))

    def test_large_family_selection_uses_arithmetic_worker_strides(self):
        offset = 10 ** 12
        plan = fixture_plan([
            {"engine": "booker", "start": "1", "stop": str(offset + 1),
             "task_width": "1", "ratio_max": "1024"},
            {"engine": "elkies", "height": "25", "start": "30", "stop": "100",
             "task_width": "7", "tile_scale": "11/2"},
        ])
        all_ids = []
        for worker in range(3):
            ids = list(campaign.assigned_ids(plan, "elkies", 3, worker))
            self.assertEqual(ids, [i for i in range(offset, offset + 10) if i % 3 == worker])
            all_ids.extend(ids)
        self.assertEqual(sorted(all_ids), list(range(offset, offset + 10)))
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertEqual(campaign.get_task(plan, offset + 9)["stop"], "100")

    def test_task_membership_respects_ratio_and_gap_boundaries(self):
        cubes = (20, 20, -25)
        ej = {"engine": "elkies", "height": "25", "start": "99", "stop": "100"}
        self.assertTrue(campaign.point_in_task(cubes, ej))  # global right endpoint included
        self.assertFalse(campaign.point_in_task(cubes, {**ej, "start": "98", "stop": "99"}))
        self.assertFalse(campaign.point_in_task(cubes, {**ej, "height": "26"}))
        bs = {"engine": "booker", "start": "5", "stop": "6", "ratio_max": "4"}
        self.assertTrue(campaign.point_in_task(cubes, bs))
        self.assertFalse(campaign.point_in_task(cubes, {**bs, "start": "4", "stop": "5"}))


class AttemptAndCheckpointAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="campaign375-control-")
        self.directory = Path(self.tmp.name)
        self.plan = fixture_plan()
        self.task = campaign.get_task(self.plan, 0)
        self.path = self.directory / "output.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_empty_attempt_and_partial_suffix_are_accepted_exactly(self):
        write_records(self.path, fixture_records(self.plan, self.task))
        remaining, complete, sha = campaign.read_attempt(self.path, self.task, self.plan, 0)
        self.assertTrue(complete)
        self.assertEqual(remaining["stop"], self.task["start"])
        self.assertEqual(sha, campaign.digest(self.path.read_bytes()))
        write_records(self.path, fixture_records(self.plan, self.task, complete=False, next_value=80))
        remaining, complete, _ = campaign.read_attempt(self.path, self.task, self.plan, 3)
        self.assertFalse(complete)
        self.assertEqual(remaining["start"], "30")
        self.assertEqual(remaining["stop"], "80")
        self.assertEqual(remaining["height"], self.task["height"])

    def test_failed_missing_trailing_and_corrupt_attempts_cannot_advance(self):
        good = fixture_records(self.plan, self.task)
        mutations = []
        changed = deepcopy(good); changed[0]["source_sha256"]["search375.py"] = "different"
        mutations.append(changed)
        changed = deepcopy(good); changed[0]["scope"]["index_start"] = "29"
        mutations.append(changed)
        changed = deepcopy(good); changed[0]["rational_d_filter"]["height"] = "1"
        mutations.append(changed)
        changed = deepcopy(good); changed[0]["command"] = "booker-gap"
        mutations.append(changed)
        changed = deepcopy(good); changed[-1]["solutions"] = 1
        mutations.append(changed)
        mutations.extend((good[:-1], good + [good[0]], [good[0], good[0], good[-1]]))
        for rows in mutations:
            write_records(self.path, rows)
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                campaign.read_attempt(self.path, self.task, self.plan, 0)
        write_records(self.path, good)
        for returncode in (1, 2, 130, -9):
            with self.subTest(returncode=returncode), self.assertRaises(ValueError):
                campaign.read_attempt(self.path, self.task, self.plan, returncode)
        self.path.write_text('{"type":"start"}\n{"type":', encoding="utf-8")
        with self.assertRaises(ValueError):
            campaign.read_attempt(self.path, self.task, self.plan, 0)

    def test_scaled375_hit_cannot_pass_campaign_strict_verification(self):
        rows = fixture_records(self.plan, self.task)
        point = validate_point(2, 5, 45, Fraction(-8), require_coprime=False)
        rows.insert(1, {"type": "solution", "verified_original_equation": True,
                        **point.as_dict()})
        rows[-1]["solutions"] = 1
        write_records(self.path, rows)
        with self.assertRaises(ValueError):
            campaign.read_attempt(self.path, self.task, self.plan, 0)

    def test_partial_boundaries_cannot_expand_or_pretend_to_complete(self):
        for next_value in (29, 101, 30):
            rows = fixture_records(self.plan, self.task, complete=False, next_value=next_value)
            write_records(self.path, rows)
            with self.subTest(next_value=next_value), self.assertRaises(ValueError):
                campaign.read_attempt(self.path, self.task, self.plan, 3)
        write_records(self.path, fixture_records(self.plan, self.task, next_value=31))
        with self.assertRaises(ValueError):
            campaign.read_attempt(self.path, self.task, self.plan, 0)

    def test_checkpoint_reaudits_output_digest_and_remaining_boundary(self):
        task_dir = self.directory / "task-0"
        state = save_checkpoint(self.plan, self.task, task_dir,
                                fixture_records(self.plan, self.task, complete=False, next_value=80), 3)
        remaining, complete, attempts = campaign.audit_task(self.plan, self.task, task_dir)
        self.assertEqual(remaining["stop"], "80")
        self.assertFalse(complete)
        self.assertEqual(len(attempts), 1)
        bad = deepcopy(state); bad["remaining"]["stop"] = "79"
        campaign.atomic_json(task_dir / "state.json", bad)
        with self.assertRaises(ValueError):
            campaign.audit_task(self.plan, self.task, task_dir)
        campaign.atomic_json(task_dir / "state.json", state)
        output = task_dir / state["attempts"][0]["output"]
        # Semantics still valid; changed byte encoding must fail the saved digest.
        rows = [json.loads(line) for line in output.read_text().splitlines()]
        output.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n")
        with self.assertRaises(ValueError):
            campaign.audit_task(self.plan, self.task, task_dir)

    def test_alias_task_directory_cannot_double_count_completed_coverage(self):
        plan = fixture_plan([{**self.plan["families"][0], "task_width": "35"}])
        task = campaign.get_task(plan, 0)
        task_dir = self.directory / "task-0"
        save_checkpoint(plan, task, task_dir, fixture_records(plan, task), 0)
        status = campaign.campaign_status(plan, self.directory)
        self.assertEqual(status["complete_tasks"], "1")
        self.assertFalse(status["entire_campaign_complete"])
        shutil.copytree(task_dir, self.directory / "task-00")
        with self.assertRaises(ValueError):
            campaign.campaign_status(plan, self.directory)

    def test_uncheckpointed_output_is_not_completed_coverage(self):
        task_dir = self.directory / "task-0"
        task_dir.mkdir()
        write_records(task_dir / "attempt-orphan.jsonl", fixture_records(self.plan, self.task))
        status = campaign.campaign_status(self.plan, self.directory)
        self.assertEqual(status["complete_tasks"], "0")
        self.assertEqual(status["certified_EJ_ratio_index_width_across_shells"], "0")
        self.assertFalse(status["entire_campaign_complete"])

    def test_task_lock_excludes_a_second_process_and_releases(self):
        task_dir = self.directory / "locked-task"
        code = ("from pathlib import Path; import sys; from campaign375 import task_lock; "
                "lock=task_lock(Path(sys.argv[1])); acquired=lock.__enter__(); "
                "print(acquired); lock.__exit__(None,None,None)")
        with campaign.task_lock(task_dir) as acquired:
            self.assertTrue(acquired)
            run = subprocess.run([sys.executable, "-c", code, str(task_dir)], cwd=ROOT,
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout.strip(), "False")
        run = subprocess.run([sys.executable, "-c", code, str(task_dir)], cwd=ROOT,
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "True")


class ActualLatticeCampaignContinuation(unittest.TestCase):
    def test_partial_native_job_resumes_and_completes_the_original_band(self):
        with tempfile.TemporaryDirectory(prefix="campaign375-integration-") as temporary:
            directory = Path(temporary)
            args = campaign.parser().parse_args([
                "plan", "--engine", "elkies", "--ej-height", "25", "--ej-stop", "50",
                "--ej-width", "1000", "--output", str(directory / "plan.json")])
            plan = campaign.make_plan(args)
            self.assertEqual(plan["task_count"], "1")
            task = campaign.get_task(plan, 0)
            state_dir = directory / "state"
            campaign.state_directory(plan, state_dir)
            task_dir = state_dir / "task-0"
            options = argparse.Namespace(bs_seconds=0, ej_max_tiles=1)
            with redirect_stdout(io.StringIO()):
                first = campaign.run_one(plan, task, task_dir, options)
            self.assertEqual(first, "partial")
            remaining, complete, attempts = campaign.audit_task(plan, task, task_dir)
            self.assertFalse(complete)
            self.assertEqual(remaining["start"], task["start"])
            self.assertLess(int(remaining["stop"]), int(task["stop"]))
            self.assertGreater(int(remaining["stop"]), int(task["start"]))
            self.assertEqual(len(attempts), 1)
            status = campaign.campaign_status(plan, state_dir)
            self.assertFalse(status["entire_campaign_complete"])
            self.assertEqual(status["partial_tasks"], "1")
            options.ej_max_tiles = 0
            with redirect_stdout(io.StringIO()):
                second = campaign.run_one(plan, task, task_dir, options)
            self.assertEqual(second, "complete")
            final_remaining, complete, attempts = campaign.audit_task(plan, task, task_dir)
            self.assertTrue(complete)
            self.assertEqual(final_remaining["stop"], task["start"])
            self.assertEqual(len(attempts), 2)
            second_rows = [json.loads(line) for line in
                           (task_dir / attempts[1]["output"]).read_text().splitlines()]
            self.assertEqual(second_rows[0]["scope"]["index_start"], remaining["start"])
            self.assertEqual(second_rows[0]["scope"]["index_stop"], remaining["stop"])
            status = campaign.campaign_status(plan, state_dir)
            self.assertTrue(status["entire_campaign_complete"])
            self.assertEqual(status["certified_EJ_ratio_index_width_across_shells"],
                             str(int(task["stop"]) - int(task["start"])))
            with redirect_stdout(io.StringIO()):
                again = campaign.run_one(plan, task, task_dir, options)
            self.assertEqual(again, "already_complete")
            self.assertEqual(len(list(task_dir.glob("attempt-*.jsonl"))), 2)
            self.assertEqual(int(task["start"]), minimum_index(25))


if __name__ == "__main__":
    unittest.main()
