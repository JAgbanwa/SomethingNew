"""Independent variable-a/q traversal, parity and actual-worker coverage checks."""
from copy import deepcopy
from fractions import Fraction as F
import json
from math import gcd
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aq_traversal import InterleavedAQ, interleaved_rank, traversal_index
from xy_common import XYAQ, parameter_space, validate_task, reject_xy_parity, reject_xy_q, rational
from xy_campaign import argument_parser, generate
from cube_campaign import generate_components
from run_task import load_json, task_identity, atomic_json
from collect_xy import collect
from test_xy_target import search, task, FIXTURES, fixture_search

class TraversalTests(unittest.TestCase):
    def test_exhaustive_permutation_and_inverse(self):
        for C in range(1,258):
            ranks=[interleaved_rank(i,C) for i in range(C)]
            self.assertEqual(sorted(ranks),list(range(C)))
            self.assertEqual([traversal_index(r,C) for r in ranks],list(range(C)))
    def test_independent_binary_string_sort_oracle(self):
        for C in range(1,200):
            expected=sorted(range(C),key=lambda r:format(r,f'0{(C-1).bit_length()}b')[::-1])
            self.assertEqual([interleaved_rank(i,C) for i in range(C)],expected)
    def test_huge_edge_and_random_roundtrips(self):
        rng=random.Random(390)
        for C in (1,2,3,2**338-1,2**338,2**338+1,10**102+12345):
            for i in [0,C-1,C//2]+[rng.randrange(C) for _ in range(50)]:
                r=interleaved_rank(i,C);self.assertTrue(0<=r<C);self.assertEqual(traversal_index(r,C),i)
    def test_invalid_arguments(self):
        for f in (interleaved_rank,traversal_index):
            for i,C in ((0,0),(0,-1),(-1,3),(3,3),(True,3),(0,True),(0.0,2)):
                with self.assertRaises(ValueError):f(i,C)
    def test_exact_set_equivalence_small_enclosures(self):
        for b in (1,2,6,8):
            base=XYAQ(search(b));sp=InterleavedAQ(base)
            old=list(base.iter_candidates(0,base.count));new=list(sp.iter_candidates(0,sp.count))
            self.assertEqual(len(new),len(set(new)));self.assertEqual(set(new),set(old))
            for i,p in enumerate(new):self.assertEqual(sp.index(*p),i)
    def test_slices_window_and_empty(self):
        base=XYAQ(search(2),12,40);sp=InterleavedAQ(base);cut=sp.count//2
        whole=list(sp.iter_candidates(0,sp.count))
        self.assertEqual(whole,list(sp.iter_candidates(0,cut))+list(sp.iter_candidates(cut,sp.count)))
        self.assertEqual(set(whole),set(base.iter_candidates(0,base.count)))
        self.assertEqual(list(InterleavedAQ(XYAQ(search(2),1,1)).iter_candidates(0,0)),[])
        for lo,hi in ((-1,0),(0,sp.count+1),(True,1)):
            with self.assertRaises(ValueError):list(sp.iter_candidates(lo,hi))
    def test_mode_part_of_identity_old_not_reindexed(self):
        old=task(search(2));new=deepcopy(old);new['fibers']['mode']=InterleavedAQ.MODE
        with self.assertRaisesRegex(ValueError,'identity'):validate_task(new)
        new['task_id']=task_identity(new)
        self.assertIsInstance(validate_task(new)['parameter_space'],InterleavedAQ)
        self.assertIsInstance(validate_task(old)['parameter_space'],XYAQ)
        new['fibers']['mode']='unsupported';new['task_id']=task_identity(new)
        with self.assertRaisesRegex(ValueError,'fiber mode'):validate_task(new)
    def test_production_first_256_vary_both_parameters(self):
        for b in (1,2):
            s=search(b,n_min=str(10**43),n_max=str(10**45),x_min=str(10**54),x_max=str(10**55),require_integer_components=True)
            sp=parameter_space(s,mode=InterleavedAQ.MODE);pairs=list(sp.iter_candidates(0,256))
            good=[(a,q) for a,q in pairs if gcd(a,q)==gcd(q,b)==1 and not reject_xy_q(q) and not reject_xy_parity(a,q,b)]
            self.assertEqual(len({a for a,q in pairs}),256);self.assertEqual(len({q for a,q in pairs}),256)
            self.assertGreater(len({a for a,q in good}),10);self.assertGreater(len({q for a,q in good}),10)
            for i,p in enumerate(pairs):self.assertEqual(sp.index(*p),i)
            if b==2:
                self.assertEqual(len(good),31)
                self.assertEqual(XYAQ(s).candidate(1_000_000),(1,84_333_334))
    def test_parity_independently_from_all_small_sixths_odd_xy(self):
        for k in range(-18,19):
            for X in range(-21,22,2):
                for Y in range(1,22,2):
                    n,x,y=F(k,6),F(X,2),F(Y,2);s=abs(y/abs(x)-1+6*n/x)
                    if s:self.assertFalse(reject_xy_parity(s.numerator,s.denominator,2))
    def test_parity_not_fixed_a_or_other_b(self):
        for a in range(2,102,2):
            self.assertFalse(reject_xy_parity(a,101,2));self.assertTrue(reject_xy_parity(a-1,101,2))
        for b in (1,3,6,8,84):
            self.assertFalse(reject_xy_parity(1,5,b));self.assertFalse(reject_xy_parity(3,8,b))
        for a,q,b in ((0,1,2),(1,-1,2),(1,1,0),(True,1,2)):
            with self.assertRaises(ValueError):reject_xy_parity(a,q,b)

class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r=subprocess.run(['make','bin/xy_cf_worker'],cwd=ROOT,text=True,capture_output=True)
        if r.returncode:raise RuntimeError(r.stderr)
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def make_task(self,**kw):
        args=argument_parser(integer_components=True).parse_args(['--campaign-id','variable-test','--xy-denominator','2',
            '--n-min','2','--n-max','3','--x-min','24','--x-max','30','--candidates-per-task','100','--output-dir',str(self.root/'tasks')])
        for k,v in kw.items():setattr(args,k,v)
        plan=generate_components(args);p=plan['pages'][0]
        return self.root/'tasks'/p['page'],self.root/'tasks'/p['task_files'][0]
    def run_job(self,path,out,worker=None):
        return subprocess.run([sys.executable,str(ROOT/'run_xy_task.py'),'--task',str(path),'--output-dir',str(out),
            '--worker',str(worker or ROOT/'bin/xy_cf_worker')],capture_output=True,text=True,timeout=20)
    def test_default_and_explicit_legacy_order(self):
        _,p=self.make_task();self.assertEqual(load_json(p)['fibers']['mode'],InterleavedAQ.MODE)
        _,p=self.make_task(parameter_order='q-major');self.assertEqual(load_json(p)['fibers']['mode'],XYAQ.MODE)
        self.assertEqual(argument_parser().parse_args(['--campaign-id','b','--xy-denominator','2']).parameter_order,'q-major')
    def test_actual_worker_collector_and_checkpoint_identity(self):
        page,path=self.make_task();out=self.root/'out';r=self.run_job(path,out)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        st=load_json(out/'status.json');self.assertTrue(st['complete']);self.assertEqual(st['next_index'],'100')
        self.assertIn(InterleavedAQ.MODE,st['coverage_note']);self.assertIn('Dispatch candidate',r.stdout)
        self.assertTrue(collect([page],out,self.root/'collected')['complete_selected_page'])
        t=load_json(path);t['fibers']['mode']=XYAQ.MODE;t['task_id']=task_identity(t)
        p=self.root/'other.json';atomic_json(p,t);self.assertNotEqual(self.run_job(p,out).returncode,0)
    def test_nonempty_broad_fixture_index_inverse(self):
        f=FIXTURES[1];s=fixture_search(f);sp=parameter_space(s,mode=InterleavedAQ.MODE)
        _,n,x,y,_=f;aq=abs(y/abs(x)-1+6*n/x);i=sp.index(aq.numerator,aq.denominator)
        bounds=[]
        for k in ('n_min','n_max','x_min','x_max'):bounds+=['--'+k.replace('_','-'),s[k]]
        args=argument_parser().parse_args(['--campaign-id','fixture','--xy-denominator',str(f[0]),'--parameter-order','interleaved',
             '--candidates-per-task','1','--page-start',str(i),'--output-dir',str(self.root/'fixture'),*bounds])
        page=generate(args);path=args.output_dir/page['tasks'][0]['file'];out=self.root/'out'
        r=self.run_job(path,out);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        rows=[json.loads(l) for l in (out/'hits.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['candidate_index'],str(i))
        self.assertEqual(tuple(rational(rows[0],k) for k in ('n','x','y')),(n,x,y))
        summary=collect([args.output_dir/f'page-{i:012d}.json'],out,self.root/'collected')
        self.assertTrue(summary['complete_selected_page']);self.assertEqual(summary['unique_verified_solutions'],1)
    def test_deadline_continuation_keeps_mapping(self):
        page,path=self.make_task(seconds=1);worker=self.root/'worker'
        worker.write_text('#!/bin/sh\nif [ ! -f "'+str(worker)+'.ready" ]; then touch "'+str(worker)+'.ready"; sleep 3; fi\nexec "'+str(ROOT/'bin/xy_cf_worker')+'" "$@"\n');worker.chmod(0o755)
        out=self.root/'returns'/'one';r=self.run_job(path,out,worker)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertEqual(load_json(out/'status.json')['state'],'partial')
        c=out/'continuation.task.json';self.assertEqual(load_json(c)['fibers']['mode'],InterleavedAQ.MODE)
        r=self.run_job(c,self.root/'returns'/'two',worker);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertTrue(collect([page],self.root/'returns',self.root/'collected')['complete_selected_page'])
    def test_odd_a_is_completed_without_worker_query(self):
        t=task(search(2));sp=validate_task(t)['parameter_space']
        a,q=next((a,q) for a,q in sp.iter_candidates(0,sp.count) if a%2 and q%2 and gcd(a,q)==1 and not reject_xy_q(q))
        i=sp.index(a,q);t['slice']={'start':str(i),'stop':str(i+1)};t['task_id']=task_identity(t)
        path=self.root/'one.json';atomic_json(path,t);worker=self.root/'empty'
        worker.write_text('#!/bin/sh\nexit 0\n');worker.chmod(0o755);out=self.root/'out'
        r=self.run_job(path,out,worker);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        st=load_json(out/'status.json');self.assertEqual(st['next_index'],str(i+1))
        self.assertEqual(st['counters_this_invocation']['fibers_completed'],'0')
        self.assertEqual(st['counters_this_invocation']['denominator_excluded'],'1')
    def test_native_validation_then_parity(self):
        r=subprocess.run([str(ROOT/'bin/xy_cf_worker'),'--xy-denominator','2','--require-integer-components'],
            input='0 5\n1 5\n2 5\n4 5\n',text=True,capture_output=True,timeout=20)
        rows=[json.loads(l) for l in r.stdout.splitlines()];self.assertEqual(rows[0]['status'],'error')
        self.assertTrue(rows[1]['excluded_by_denominator']);self.assertEqual(rows[1]['convergents'],0)
        for row in rows[2:]:self.assertFalse(row['excluded_by_denominator'])
    def test_packaging_and_source_pin(self):
        self.assertIn('aq_traversal.py',(ROOT/'Dockerfile').read_text())
        self.assertIn('aq_traversal.py',(ROOT/'run_xy_task.py').read_text())

if __name__=='__main__':unittest.main()
