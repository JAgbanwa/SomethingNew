"""Task partition tests: pages cover each selected candidate exactly once."""
import argparse
import json
from pathlib import Path
import sys
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
                 require_integer_sqrt=False,signs="all",output_dir=output_dir)
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
            rational=campaign.generate(arguments(folder/"rational",task_count=1))
            integer=campaign.generate(arguments(folder/"integer",task_count=1,require_integer_sqrt=True))
            self.assertNotEqual(rational["tasks"][0]["task_id"],integer["tasks"][0]["task_id"])

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
