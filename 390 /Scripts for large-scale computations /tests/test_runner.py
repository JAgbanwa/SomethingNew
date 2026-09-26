"""Supervisor fault-injection checks: deadlines, resume and failed fibers."""
import copy
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import run_task


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.folder=Path(self.temp.name)
        self.task_path=self.folder/"task.json"
        self.output=self.folder/"out"
        self.worker=self.folder/"mock_worker.py"
        self.marker=self.folder/"continue"
        self.task={"schema":run_task.SCHEMA,"parameterization":run_task.PARAMETERIZATION,
                   "campaign_id":"test-supervisor", "search":{
                       "n_min":str(10**43),"n_max":str(10**45),
                       "x_min":str(10**54),"x_max":str(10**55)},
                   "fibers":{"a_values":["1"],"q_min":"5","q_max":"17"},
                   "slice":{"start":"0","stop":"7"},
                   "execution":{"time_limit_seconds":1,"precision_bits":512}}
        self.task["task_id"]=run_task.task_identity(self.task)
        self.write_task()

    def tearDown(self):
        self.temp.cleanup()

    def write_task(self):
        self.task_path.write_text(json.dumps(self.task),encoding="utf-8")

    def mock(self, mode="complete"):
        self.worker.write_text(
            "#!/usr/bin/env python3\nimport json,sys,time\nfrom pathlib import Path\n"
            f"mode={mode!r}\nmarker=Path({str(self.marker)!r})\n"
            "for line in sys.stdin:\n"
            " a,q=line.split()\n"
            " if mode=='hang' or (mode=='partial' and q=='11' and not marker.exists()): time.sleep(3600)\n"
            " row={'a':a,'q':q,'status':'error' if mode=='error' else 'complete','hits':[],'convergents':'1','congruences_enforced':mode!='relaxed','integer_sqrt_required':'--integer-sqrt' in sys.argv,'excluded_by_bounds':False,'excluded_by_congruence':False}\n"
            " if mode=='wrong': row['q']='999'\n"
            " print(json.dumps(row),flush=True)\n",encoding="utf-8")
        self.worker.chmod(0o755)

    def argv(self):
        return [sys.executable,str(ROOT/"run_task.py"),"--task",str(self.task_path),
                "--worker",str(self.worker),"--output-dir",str(self.output)]

    def run_supervisor(self):
        return subprocess.run(self.argv(),text=True,capture_output=True,timeout=10)

    def status(self):
        return json.loads((self.output/"status.json").read_text())

    def test_complete_empty_task_records_exact_selected_coverage(self):
        self.mock()
        run=self.run_supervisor()
        self.assertEqual(run.returncode,0,run.stderr+run.stdout)
        status=self.status()
        self.assertTrue(status["complete"])
        self.assertEqual(status["next_index"],"7")
        self.assertEqual(status["unique_hits_in_this_output"],"0")
        self.assertIn("not an exhaustive",status["coverage_note"])
        self.assertFalse((self.output/"continuation.task.json").exists())
        self.assertTrue((self.output/"hits.jsonl").exists())

    def test_soft_deadline_replays_incomplete_fiber_and_resumes(self):
        self.mock("partial")
        started=time.monotonic()
        run=self.run_supervisor()
        self.assertEqual(run.returncode,0,run.stderr+run.stdout)
        self.assertLess(time.monotonic()-started,6)
        status=self.status()
        self.assertFalse(status["complete"])
        self.assertEqual(status["reason"],"time_limit")
        self.assertEqual(status["next_index"],"3")
        continuation=json.loads((self.output/"continuation.task.json").read_text())
        self.assertEqual(continuation["resume_index"],"3")
        self.assertEqual(continuation["task_id"],self.task["task_id"])
        self.marker.touch()  # Same executable bytes; resume will now complete.
        run=self.run_supervisor()
        self.assertEqual(run.returncode,0,run.stderr+run.stdout)
        status=self.status()
        self.assertTrue(status["complete"])
        self.assertEqual(status["invocation_coverage"],{"start":"3","stop":"7"})
        self.assertEqual(status["output_coverage"],{"start":"0","stop":"7"})
        self.assertFalse((self.output/"continuation.task.json").exists())

    def test_worker_error_never_advances_cursor(self):
        self.mock("error")
        run=self.run_supervisor()
        self.assertEqual(run.returncode,2,run.stderr+run.stdout)
        self.assertEqual(self.status()["state"],"error")
        self.assertEqual(self.status()["next_index"],"0")
        self.assertTrue((self.output/"worker_error.json").exists())

    def test_continuation_on_new_host_does_not_claim_unreturned_prefix(self):
        self.mock()
        self.task["resume_index"]="3"
        self.write_task()
        run=self.run_supervisor()
        self.assertEqual(run.returncode,0,run.stderr+run.stdout)
        status=self.status()
        self.assertTrue(status["complete"])
        self.assertEqual(status["output_coverage"],{"start":"3","stop":"7"})
        self.assertEqual(status["invocation_coverage"],{"start":"3","stop":"7"})

    def test_mismatched_worker_response_is_not_accepted(self):
        self.mock("wrong")
        run=self.run_supervisor()
        self.assertEqual(run.returncode,2,run.stderr+run.stdout)
        self.assertEqual(self.status()["next_index"],"0")

    def test_relaxed_worker_mode_cannot_certify_production_coverage(self):
        self.mock("relaxed")
        run=self.run_supervisor()
        self.assertEqual(run.returncode,2,run.stderr+run.stdout)
        self.assertEqual(self.status()["next_index"],"0")

    def test_signal_saves_checkpoint_without_advancing_current_fiber(self):
        self.mock("hang")
        process=subprocess.Popen(self.argv(),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+3
            while not (self.output/"checkpoint.json").exists() and process.poll() is None:
                if time.monotonic()>deadline:
                    self.fail("supervisor did not create initial checkpoint")
                time.sleep(0.01)
            process.send_signal(signal.SIGTERM)
            out,err=process.communicate(timeout=6)
            self.assertEqual(process.returncode,0,err+out)
            status=self.status()
            self.assertEqual(status["state"],"partial")
            self.assertEqual(status["reason"],"signal")
            self.assertEqual(status["next_index"],"0")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_binary_change_invalidates_checkpoint(self):
        self.mock()
        self.assertEqual(self.run_supervisor().returncode,0)
        with self.worker.open("a") as stream:
            stream.write("# changed binary identity\n")
        run=self.run_supervisor()
        self.assertEqual(run.returncode,2)
        self.assertIn("hash differs",run.stderr)

    def test_lost_whole_hit_records_in_prior_output_are_detected(self):
        self.mock()
        self.assertEqual(self.run_supervisor().returncode,0)
        status=self.status()
        status["unique_hits_in_this_output"]="1"
        (self.output/"status.json").write_text(json.dumps(status))
        run=self.run_supervisor()
        self.assertEqual(run.returncode,2)
        self.assertIn("hit",run.stderr.lower())

    def test_immutable_task_definition_cannot_be_silently_changed(self):
        altered=copy.deepcopy(self.task)
        altered["search"]["n_max"]=str(10**44)
        with self.assertRaisesRegex(ValueError,"task_id"):
            run_task.validate_task(altered)
        altered=copy.deepcopy(self.task)
        altered["fibers"]["q_min"]="2"
        altered["task_id"]=run_task.task_identity(altered)
        with self.assertRaisesRegex(ValueError,"odd"):
            run_task.validate_task(altered)

    def test_interrupted_trailing_append_is_recovered(self):
        path=self.folder/"hits.jsonl"
        path.write_bytes(b'{"n":"incomplete')
        bounds=run_task.validate_task(self.task)["bounds"]
        self.assertEqual(run_task.recover_hits(path,bounds,self.task["task_id"]),set())
        self.assertEqual(path.read_bytes(),b"")
        path.write_bytes(b'{"n":"bad complete record"}\n')
        with self.assertRaises((ValueError,KeyError)):
            run_task.recover_hits(path,bounds,self.task["task_id"])

    def test_duplicate_json_keys_are_rejected(self):
        self.task_path.write_text('{"schema":"one","schema":"two"}')
        with self.assertRaisesRegex(ValueError,"duplicate"):
            run_task.load_json(self.task_path)


if __name__=="__main__":
    unittest.main()
