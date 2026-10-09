"""Task partition tests: pages cover each selected candidate exactly once."""
import argparse
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import campaign
import run_task


def arguments(output_dir, **changes):
    options=dict(campaign_id="partition-test",a_values="1,3",q_min="5",q_max="17",
                 candidates_per_task="4",page_start="0",task_count=2,
                 seconds=3000,precision_bits=512,max_precision_bits=16384,checkpoint_seconds=5,
                 n_min=str(10**43),n_max=str(10**45),x_min=str(10**54),x_max=str(10**55),
                 require_integer_sqrt=True,signs="all",output_dir=output_dir)
    options.update(changes)
    return argparse.Namespace(**options)


class CampaignTests(unittest.TestCase):
    def test_page_boundaries_are_gap_free_nonoverlapping_and_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            first=campaign.generate(arguments(folder))
            self.assertEqual(first["next_page_start"],"2")
            second=campaign.generate(arguments(folder,page_start="2"))
            self.assertIsNone(second["next_page_start"])
            entries=first["tasks"]+second["tasks"]
            intervals=[(int(e["slice"]["start"]),int(e["slice"]["stop"])) for e in entries]
            self.assertEqual(intervals,[(0,4),(4,8),(8,12),(12,14)])
            self.assertEqual(campaign.generate(arguments(folder)),first)
            pairs=[]
            for entry in entries:
                task=json.loads((folder/entry["file"]).read_text())
                parsed=run_task.validate_task(task)
                pairs.extend(run_task.candidate(parsed,i) for i in range(parsed["start"],parsed["stop"]))
            self.assertEqual(pairs,[(a,q) for a in (1,3) for q in range(5,18,2)])
            self.assertEqual(len(set(pairs)),14)

    def test_integer_radical_campaign_has_distinct_task_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            rational=campaign.generate(arguments(folder/"rational",task_count=1,require_integer_sqrt=False))
            integer=campaign.generate(arguments(folder/"integer",task_count=1,require_integer_sqrt=True))
            self.assertNotEqual(rational["tasks"][0]["task_id"],integer["tasks"][0]["task_id"])

    def test_cli_defaults_to_explicit_integer_roots_and_opt_out_is_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            tasks=[]
            for label,flags,expected in (("default",[],True),
                                         ("integer",["--require-integer-sqrt"],True),
                                         ("rational",["--allow-rational-sqrt"],False)):
                output=folder/label
                run=subprocess.run([sys.executable,str(ROOT/"campaign.py"),
                     "--campaign-id","cli-default-policy","--a-values","1","--q-min","5","--q-max","17",
                     "--task-count","1","--output-dir",str(output),*flags],
                     text=True,capture_output=True,timeout=10)
                self.assertEqual(run.returncode,0,run.stderr)
                task=json.loads(next(output.glob("task-*.json")).read_text())
                self.assertIs(task["search"]["require_integer_sqrt"],expected)
                self.assertEqual(task["search"]["signs"],"all")
                tasks.append(task)
            self.assertEqual(tasks[0]["task_id"],tasks[1]["task_id"])
            self.assertNotEqual(tasks[0]["task_id"],tasks[2]["task_id"])
            conflicting=subprocess.run([sys.executable,str(ROOT/"campaign.py"),
                "--campaign-id","conflicting-policy","--a-values","1","--q-min","5","--q-max","17",
                "--require-integer-sqrt","--allow-rational-sqrt", "--output-dir",str(folder/"invalid")],
                text=True,capture_output=True,timeout=10)
            self.assertNotEqual(conflicting.returncode,0)
            self.assertFalse((folder/"invalid").exists())

    def test_sign_policy_is_explicit_and_part_of_task_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            identifiers=[]
            for signs in ("all","pp","pn","np","nn"):
                page=campaign.generate(arguments(folder/signs,task_count=1,signs=signs))
                task=json.loads((folder/signs/page["tasks"][0]["file"]).read_text())
                self.assertEqual(task["schema"],"ce390-task-v2")
                self.assertEqual(task["search"]["signs"],signs)
                self.assertEqual(run_task.validate_task(task)["signs"],signs)
                identifiers.append(task["task_id"])
            self.assertEqual(len(set(identifiers)),5)

    def test_auxiliary_slope_domain_and_positive_magnitudes_are_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            with self.assertRaisesRegex(ValueError,"smaller than q_min"):
                campaign.generate(arguments(folder,a_values="5",q_min="5"))
            with self.assertRaises(ValueError):
                campaign.generate(arguments(folder,n_min="-100"))
            with self.assertRaisesRegex(ValueError,"search.signs"):
                campaign.generate(arguments(folder,signs="both"))

    def test_general_mode_defaults_to_full_derived_denominator_enclosure(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            args = arguments(folder, a_values=None, q_min=None, q_max=None, task_count=1)
            page = campaign.generate(args)
            task = json.loads((folder / page["tasks"][0]["file"]).read_text())
            self.assertEqual(task["fibers"]["q_min"], "1")
            self.assertEqual(task["fibers"]["q_max"], str(10**55))
            self.assertEqual(page["total_candidate_indices"],
                             "12600000000000000038000000228000001368000008207444444443124444444444426662666666642666666522666665816")

    def test_restricted_general_q_window_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            args = arguments(folder, a_values=None, q_min="1000000000001",
                             q_max="1000000001001", task_count=1)
            with self.assertRaisesRegex(ValueError, "restricted denominator window is opt-in"):
                campaign.generate(args)
            args.allow_q_window = True
            page = campaign.generate(args)
            task = json.loads((folder / page["tasks"][0]["file"]).read_text())
            self.assertEqual(task["fibers"]["q_min"], "1000000000001")
            self.assertEqual(task["fibers"]["q_max"], "1000000001001")
            self.assertFalse(GeneralAQ({
                "n_min": args.n_min, "n_max": args.n_max,
                "x_min": args.x_min, "x_max": args.x_max
            }, int(task["fibers"]["q_min"]), int(task["fibers"]["q_max"])).bounds_info()["full_denominator_window"])

    def test_invalid_page_and_conflicting_task_file_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            with self.assertRaisesRegex(ValueError,"beyond"):
                campaign.generate(arguments(folder,page_start="4"))
            page=campaign.generate(arguments(folder))
            path=folder/page["tasks"][0]["file"]
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError,"overwrite"):
                campaign.generate(arguments(folder))


if __name__=="__main__":
    unittest.main()
