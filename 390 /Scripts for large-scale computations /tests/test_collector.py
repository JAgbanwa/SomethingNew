"""Returned-job collection must distinguish coverage from a final cursor."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import campaign
import collector


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.folder=Path(self.temp.name)
        self.pages=self.folder/"pages"
        self.results=self.folder/"returns"
        self.first=self.results/"first"
        self.destination=self.folder/"collected"
        args=argparse.Namespace(campaign_id="collector-test",a_values="1",q_min="5",q_max="17",
             candidates_per_task="7",page_start="0",task_count=1,seconds=10,
             precision_bits=512,max_precision_bits=16384,checkpoint_seconds=5,
             n_min=str(10**43),n_max=str(10**45),x_min=str(10**54),x_max=str(10**55),
             require_integer_sqrt=False,output_dir=self.pages)
        page=campaign.generate(args)
        self.page=self.pages/"page-000000000000.json"
        task_path=self.pages/page["tasks"][0]["file"]
        worker=self.folder/"mock.py"
        worker.write_text("#!/usr/bin/env python3\nimport sys,json\nfor line in sys.stdin:\n"
             " a,q=line.split()\n print(json.dumps({'a':a,'q':q,'status':'complete','hits':[],'convergents':'1','congruences_enforced':True,'integer_sqrt_required':'--integer-sqrt' in sys.argv,'excluded_by_bounds':False,'excluded_by_congruence':False}),flush=True)\n")
        worker.chmod(0o755)
        run=subprocess.run([sys.executable,str(ROOT/"run_task.py"),"--task",str(task_path),
                            "--output-dir",str(self.first),"--worker",str(worker)],
                           text=True,capture_output=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr+run.stdout)

    def tearDown(self):
        self.temp.cleanup()

    def status(self,path=None):
        return json.loads(((path or self.first)/"status.json").read_text())

    def write_status(self,status,path=None):
        ((path or self.first)/"status.json").write_text(json.dumps(status))

    def set_coverage(self,path,start,stop,retained_start=None):
        status=self.status(path)
        status.update(invocation_coverage={"start":str(start),"stop":str(stop)},
                      output_coverage={"start":str(start if retained_start is None else retained_start),"stop":str(stop)},
                      next_index=str(stop),remaining_indices=str(7-stop),
                      complete=(stop==7),state="complete" if stop==7 else "partial")
        real=sum((1+(5+2*i))%3==0 for i in range(start,stop))
        status["counters_this_invocation"].update(fibers_completed=str(real),
                cf_fibers_completed=str(real),bounds_excluded="0",non_coprime_skipped="0",
                congruence_excluded=str(stop-start-real),new_hits="0",convergents=str(real))
        self.write_status(status,path)

    def collect(self):
        return collector.collect([self.page],self.results,self.destination)

    def test_real_runner_complete_output_collects(self):
        summary=self.collect()
        self.assertTrue(summary["complete_selected_page"])
        self.assertEqual(summary["unique_verified_solutions"],0)
        self.assertEqual(summary["tasks"][0]["coverage"],[{"start":"0","stop":"7"}])

    def test_disjoint_host_returns_union_to_full_selected_coverage(self):
        second=self.results/"second"
        shutil.copytree(self.first,second)
        self.set_coverage(self.first,0,3)
        self.set_coverage(second,3,7)
        summary=self.collect()
        self.assertTrue(summary["complete_selected_page"])
        self.assertEqual(summary["tasks"][0]["gaps"],[])

    def test_resumed_final_output_alone_reports_missing_prefix(self):
        self.set_coverage(self.first,3,7)
        summary=self.collect()
        self.assertFalse(summary["complete_selected_page"])
        self.assertEqual(summary["tasks"][0]["gaps"],[{"start":"0","stop":"3"}])

    def test_locally_retained_prefix_counts_when_explicitly_recorded(self):
        self.set_coverage(self.first,3,7,retained_start=0)
        self.assertTrue(self.collect()["complete_selected_page"])

    def test_different_binary_hashes_for_one_task_are_rejected(self):
        second=self.results/"second"
        shutil.copytree(self.first,second)
        status=self.status(second)
        status["worker_sha256"]="0"*64
        self.write_status(status,second)
        with self.assertRaisesRegex(ValueError,"worker hashes"):
            self.collect()

    def test_unselected_or_tampered_identity_is_rejected(self):
        status=self.status()
        status["task_id"]="0"*64
        self.write_status(status)
        with self.assertRaisesRegex(ValueError,"unselected"):
            self.collect()

    def test_hit_file_loss_cannot_be_silently_counted_as_complete(self):
        status=self.status()
        status["unique_hits_in_this_output"]="1"
        self.write_status(status)
        with self.assertRaises(ValueError):
            self.collect()

    def test_missing_returned_task_has_a_full_gap(self):
        shutil.rmtree(self.first)
        summary=self.collect()
        self.assertFalse(summary["complete_selected_page"])
        self.assertEqual(len(summary["missing_tasks"]),1)
        self.assertEqual(summary["tasks"][0]["gaps"],[{"start":"0","stop":"7"}])


if __name__=="__main__":
    unittest.main()
