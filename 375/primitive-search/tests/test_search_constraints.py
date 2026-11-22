"""Coverage must remain bound to primitive and height constraints across lifecycle steps."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gap_common import METHOD, TASK_SCHEMA, expected_solutions, search_options, verify_hit


class ExactConstraints(unittest.TestCase):
    def test_primitive_and_height_are_verified_independently(self):
        # A known primitive600 triple, and its imprimitive scaling.
        a,b,c = 358469562197, -313190404198, -248487937861
        record = dict(k=600, x=str(a), y=str(b), z=str(c), d=str(abs(a+b)))
        verify_hit(record,600,primitive_only=True,height_min=10**11)
        with self.assertRaises(ValueError):
            verify_hit(record,600,primitive_only=True,height_min=abs(a))
        scaled = dict(k=4800,x=str(2*a),y=str(2*b),z=str(2*c),d=str(2*abs(a+b)))
        with self.assertRaises(ValueError):
            verify_hit(scaled,4800,primitive_only=True)

    def test_options_require_a_boolean(self):
        with self.assertRaises(ValueError):
            search_options(dict(primitive_only="false"))

    def test_heuristic_height_cut_reduces_mass(self):
        full = expected_solutions(.05861,10**10,2*10**10,32768)
        cut = expected_solutions(.05861,10**10,2*10**10,32768,10**15)
        self.assertGreater(cut,0)
        self.assertLess(cut,full)
        self.assertEqual(expected_solutions(.05861,10**10,2*10**10,4,10**15),0)

    @unittest.skipUnless((ROOT/'bin'/'gap_worker').exists(),'build first')
    def test_resume_rejects_changed_height_and_primitive_constraints(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            task = dict(schema=TASK_SCHEMA,method=METHOD,campaign_id='constraints',task_id='one',
                        k=375,d_start='48828125',d_stop='48828225',ratio_max=64,
                        primitive_only=True,height_min='0',deadline_seconds=0)
            taskfile=tmp/'task.json'; out=tmp/'out'
            taskfile.write_text(json.dumps(task))
            cmd=[sys.executable,str(ROOT/'run_gap_task.py'),'--task',str(taskfile),'--output-dir',str(out)]
            done=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(done.returncode,0,done.stderr)
            before=(out/'status.json').read_text()
            for extra in [dict(primitive_only=False),dict(height_min='1')]:
                taskfile.write_text(json.dumps({**task,**extra}))
                bad=subprocess.run(cmd,capture_output=True,text=True)
                self.assertNotEqual(bad.returncode,0)
                self.assertIn('constraints differ',bad.stderr)
                self.assertEqual((out/'status.json').read_text(),before)


if __name__ == '__main__':
    unittest.main()
