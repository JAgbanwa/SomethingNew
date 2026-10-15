"""Full lifecycle for the corrected schema; old integer jobs stay unchanged."""
from copy import deepcopy
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from test_xy_target import fixture_search, FIXTURES, search, task
from xy_common import validate_task, XYAQ
from run_task import load_json, atomic_json, task_identity
from collect_xy import collect, checked_status

# Lifecycle-only fixture. Not evidence of mathematical search.
MOCK='''#!/usr/bin/env python3
import json,os,sys,time
args=sys.argv[1:]
def arg(k):return args[args.index(k)+1]
for line in sys.stdin:
 a,q=line.split()
 if os.environ.get('XY_TEST_SLOW')=='1':time.sleep(3)
 out=dict(a=a,q=q,status='complete',parameterization='n-sixths-equal-xy-denominators-v1',
          xy_denominator=arg('--xy-denominator'),n_denominators=[int(d) for d in arg('--n-denominators').split(',')],
          signs=arg('--signs'),congruence_policy=arg('--congruence-policy'),
          noninteger_d_required='--noninteger-d' in args,excluded_by_denominator=False,
          excluded_by_congruence=False,excluded_by_q_sieve=False,excluded_by_bounds=False,
          precision_bits=0,convergents=0,hits=[])
 if os.environ.get('XY_TEST_WRONG')=='1':out['n_denominators']=[1]
 print(json.dumps(out),flush=True)
'''

class XYIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        r=subprocess.run(['make','bin/xy_cf_worker'],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.worker=ROOT/'bin/xy_cf_worker'

    def tearDown(self):self.tmp.cleanup()

    def generate(self,*extra):
        out=self.root/'tasks'
        r=subprocess.run([sys.executable,str(ROOT/'xy_campaign.py'),'--campaign-id','xy-integration',
              '--xy-denominator','6','--n-min','65','--n-max','65','--x-min','964','--x-max','965',
              '--q-min','5785','--q-max','5785','--allow-q-window','--candidates-per-task','10000',
              '--output-dir',str(out),*extra],text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        return next(out.glob('task-*.json')),out/'page-000000000000.json'

    def run_task(self,path,out,extra=(),env=None):
        return subprocess.run([sys.executable,str(ROOT/'run_xy_task.py'),'--task',str(path),
                          '--output-dir',str(out),'--worker',str(self.worker),*extra],
                         env=env,text=True,capture_output=True,timeout=20)

    def mock(self):
        p=self.root/'mock-worker';p.write_text(MOCK);p.chmod(0o755);self.worker=p

    def test_generated_task_explicitly_selects_all_n_denominators(self):
        p,_=self.generate();t=load_json(p)
        self.assertEqual(t['search']['n_denominators'],[1,2,3,6])
        self.assertEqual(t['search']['xy_denominator'],'6')
        self.assertNotIn('require_integer_sqrt',t['search'])
        self.assertEqual(t['search']['congruence_policy'],'none')

    def test_real_nonempty_job_collects_and_independently_verifies(self):
        p,page=self.generate();out=self.root/'run'
        r=self.run_task(p,out);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        s=load_json(out/'status.json');self.assertEqual(s['state'],'complete')
        self.assertEqual(s['output_coverage'],{'start':'0','stop':'111'})
        self.assertEqual(s['unique_hits_in_this_output'],'1')
        result=collect([page],out,self.root/'collected')
        self.assertTrue(result['complete_selected_page']);self.assertEqual(result['unique_verified_solutions'],1)
        r=subprocess.run([sys.executable,str(ROOT/'verify_xy.py'),str(self.root/'collected/hits.jsonl'),
                          '--task',str(p)],text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_in_place_restart_preserves_hits_and_coverage(self):
        p,page=self.generate();out=self.root/'run'
        self.assertEqual(self.run_task(p,out).returncode,0)
        hits=(out/'hits.jsonl').read_bytes()
        self.assertEqual(self.run_task(p,out).returncode,0)
        self.assertEqual((out/'hits.jsonl').read_bytes(),hits)
        s=load_json(out/'status.json')
        self.assertEqual(s['invocation_coverage'],{'start':'111','stop':'111'})
        self.assertEqual(s['output_coverage'],{'start':'0','stop':'111'})
        self.assertTrue(collect([page],out,self.root/'collected')['complete_selected_page'])

    def test_lost_hit_records_are_not_silently_accepted(self):
        p,_=self.generate();out=self.root/'run';self.run_task(p,out)
        (out/'hits.jsonl').write_text('')
        r=self.run_task(p,out);self.assertEqual(r.returncode,2)
        self.assertIn('lost',r.stderr)

    def test_deadline_continuation_new_host_and_collection(self):
        p,page=self.generate('--seconds','1');self.mock()
        env=dict(os.environ,XY_TEST_SLOW='1');out=self.root/'returns'/'first'
        r=self.run_task(p,out,env=env);self.assertEqual(r.returncode,0,r.stderr)
        s=load_json(out/'status.json');self.assertEqual(s['state'],'partial')
        self.assertEqual(s['reason'],'time_limit');self.assertEqual(s['unique_hits_in_this_output'],'0')
        ct=out/'continuation.task.json';t=load_json(ct)
        self.assertIn('expected_implementation_sha256',t);self.assertIn('expected_worker_sha256',t)
        new=self.root/'returns'/'second';r=self.run_task(ct,new)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        result=collect([page],self.root/'returns',self.root/'collected')
        self.assertTrue(result['complete_selected_page'])

    def test_wrong_worker_policy_leaves_current_fiber_uncompleted(self):
        p,_=self.generate();self.mock();out=self.root/'run'
        r=self.run_task(p,out,env=dict(os.environ,XY_TEST_WRONG='1'))
        self.assertEqual(r.returncode,2)
        s=load_json(out/'status.json');self.assertEqual(s['state'],'error')
        self.assertLess(int(s['next_index']),111)

    def test_continuation_pins_both_worker_and_source(self):
        p,_=self.generate();t=load_json(p)
        for key in ('expected_worker_sha256','expected_implementation_sha256'):
            tt=deepcopy(t);tt[key]='0'*64;other=self.root/(key+'.json');atomic_json(other,tt)
            r=self.run_task(other,self.root/key);self.assertEqual(r.returncode,2)
            self.assertTrue(list((self.root/key).glob('startup-error-*')))

    def test_collector_detects_bad_counters_and_changed_policy(self):
        p,_=self.generate();out=self.root/'run';self.run_task(p,out)
        original=load_json(p);s=load_json(out/'status.json')
        for mutate in ('counter','subset','identity'):
            ss=deepcopy(s);tt=deepcopy(original)
            if mutate=='counter':ss['counters_this_invocation']['denominator_excluded']='999'
            elif mutate=='subset':ss['counters_this_invocation']['q_sieve_excluded']='999'
            else:tt['search']['n_denominators']=[2];tt['task_id']=task_identity(tt)
            with self.assertRaises(ValueError):checked_status(ss,original,tt)

    def test_original_integer_task_not_reinterpreted(self):
        p=next((ROOT/'examples/general-pilot').glob('task-*.json'))
        r=self.run_task(p,self.root/'out')
        self.assertEqual(r.returncode,2)
        self.assertIn('not a corrected',r.stderr)

    def test_restricted_q_window_needs_explicit_opt_in(self):
        r=subprocess.run([sys.executable,str(ROOT/'xy_campaign.py'),'--campaign-id','xy',
                          '--xy-denominator','84','--q-min','5','--q-max','1000','--output-dir',str(self.root/'bad')],
                         text=True,capture_output=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('allow-q-window',r.stderr)

    def test_packaging_has_both_workers_and_corrected_tools(self):
        text=(ROOT/'Dockerfile').read_text()
        self.assertIn('COPY xy_campaign.py xy_common.py run_xy_task.py collect_xy.py verify_xy.py /app/',text)
        self.assertIn('COPY --from=build /build/bin/ /app/bin/',text)
        make=(ROOT/'Makefile').read_text();self.assertIn('all: bin/cf_worker bin/xy_cf_worker',make)
        self.assertIn('bin/xy_cf_worker: src/xy_cf_worker.cpp src/q_sieve.hpp',make)

if __name__=='__main__':unittest.main()
