"""The FINAL target: both -x +/- y and 2*x+6*n are integral.

Synthetic structural examples are NOT claimed solutions of the 390 equation.
Existing nonempty broad-rational fixtures are deliberately rejected here.
"""
from copy import deepcopy
from fractions import Fraction as F
import itertools
import json
from math import gcd, isqrt
import os
from pathlib import Path
import random
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from xy_common import (integer_components, verify_record, validate_search, validate_task,
                       XYAQ, reject_xy_q, rational)
from xy_campaign import argument_parser
from cube_campaign import generate_components
from run_task import load_json, atomic_json, task_identity
from collect_xy import collect, checked_status
from test_xy_target import search, task, FIXTURES, fixture_search, record


def cube_search(b=1, **kwargs):
    return search(b, require_integer_components=True, **kwargs)


class ComponentArithmeticTests(unittest.TestCase):
    def test_integers_and_half_integers_with_both_signs(self):
        self.assertEqual(integer_components(F(2), F(1,2), F(3,2)), (1,-2,13))
        self.assertEqual(integer_components(F(-2), F(-1,2), F(3,2)), (2,-1,-13))
        self.assertEqual(integer_components(F(2), F(1), F(3)), (2,-4,14))

    def test_one_sign_does_not_suffice(self):
        # Actual old broad-rational fixture: -x+y is integral; -x-y is not.
        f=FIXTURES[0]; _,n,x,y,_=f
        self.assertEqual((-x+y).denominator,1)
        self.assertNotEqual((-x-y).denominator,1)
        with self.assertRaisesRegex(ValueError,'ALL'):
            integer_components(n,x,y)

    def test_third_component_is_checked_separately(self):
        with self.assertRaisesRegex(ValueError,'ALL'):
            integer_components(F(1,5),F(1,2),F(3,2))

    def test_matching_parity_not_just_denominators_at_most_two(self):
        with self.assertRaises(ValueError):integer_components(F(2),F(1,2),F(3))
        with self.assertRaises(ValueError):integer_components(F(2),F(1),F(3,2))

    def test_structural_denominator_theorem_by_exhaustive_small_fractions(self):
        values=sorted({F(p,q) for q in range(1,13) for p in range(-12,13)})
        for x in values:
            for y in (v for v in values if v>=0):
                actual=all(v.denominator==1 for v in (-x+y,-x-y,2*x+12))
                equivalent=x.denominator==y.denominator and x.denominator in (1,2)
                self.assertEqual(actual,equivalent,(x,y))

    def test_all_sixth_n_values_structurally_allowed_before_equation_check(self):
        for k in range(-12,13):
            n=F(k,6)
            self.assertEqual(integer_components(n,F(1,2),F(3,2)),(1,-2,1+k))
        self.assertEqual({F(k,6).denominator for k in range(1,7)},{1,2,3,6})

    def test_mod_18_proves_any_390_integer_triple_has_integral_n(self):
        count=0
        for A,B,C in itertools.product(range(18),repeat=3):
            if (A**3+B**3+C**3-390)%18==0:
                count+=1
                self.assertEqual((A+B+C)%6,0)
                self.assertEqual((A%3,B%3,C%3),(1,1,1))
        self.assertGreater(count,0)

    def test_exact_cube_identity_without_using_search_polynomial(self):
        rng=random.Random(390)
        for _ in range(300):
            n=F(rng.randrange(-100,101),6)
            x=F(rng.choice([v for v in range(-50,51) if v]),rng.randrange(1,20))
            y=F(rng.randrange(100),rng.randrange(1,20))
            A,B,C=-x+y,-x-y,2*x+6*n
            rad=(x+6*n)**2+(36*n**3-65)/x
            self.assertEqual(A**3+B**3+C**3-390,-6*x*(y*y-rad))

    def test_new_policy_rejects_b_above_two_before_work(self):
        for b in (3,6,8,84,10**55):
            with self.assertRaisesRegex(ValueError,'denominator to be 1 or 2'):
                validate_search(cube_search(b))
        for b in (1,2):validate_search(cube_search(b))

    def test_boolean_policy_is_strict_and_old_missing_means_broad(self):
        for value in ('true',1,None,[],{}):
            with self.assertRaisesRegex(ValueError,'boolean'):
                validate_search(search(6,require_integer_components=value))
        for value in (False,):validate_search(search(6,require_integer_components=value))
        validate_search(search(6))

    def test_true_old_fixtures_are_not_new_integer_cube_solutions(self):
        for f in FIXTURES:
            s=fixture_search(f);verify_record(record(f),s)
            s['require_integer_components']=True
            with self.assertRaises(ValueError):verify_record(record(f),s)

    def test_false_integer_cube_metadata_on_real_rational_fixture_is_rejected(self):
        f=FIXTURES[0];r=record(f);r['cube_sum']='390'
        with self.assertRaisesRegex(ValueError,'ALL'):verify_record(r,fixture_search(f))

    def test_structural_example_is_not_an_equation_certificate(self):
        f=(2,F(2),F(49,2),F(51,2),F(-62,49))
        integer_components(f[1],f[2],f[3])
        with self.assertRaises(ValueError):verify_record(record(f),cube_search(2))

    def test_task_hash_changes_and_existing_ranks_do_not(self):
        for b in (1,2):
            original=task(search(b));modified=deepcopy(original)
            modified['search']['require_integer_components']=True
            with self.assertRaisesRegex(ValueError,'identity'):validate_task(modified)
            modified['task_id']=task_identity(modified)
            new=validate_task(modified);old=validate_task(original)
            self.assertNotEqual(original['task_id'],modified['task_id'])
            self.assertEqual(new['count'],old['count'])
            self.assertEqual(list(new['parameter_space'].iter_candidates(0,new['stop'])),
                             list(old['parameter_space'].iter_candidates(0,old['stop'])))

    def test_all_n_denominators_retained_no_arbitrary_old_residue_cut(self):
        for b in (1,2):
            s=cube_search(b);validate_search(s)
            self.assertEqual(s['n_denominators'],[1,2,3,6])
            self.assertEqual(s['congruence_policy'],'none')


class ComponentNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.helper=Path(cls.tmp.name)/'check-components'
        compiler=shlex.split(os.environ.get('CXX','g++'))
        if not compiler or not shutil.which(compiler[0]):raise unittest.SkipTest('C++ compiler required')
        build=subprocess.run([*compiler,*shlex.split(os.environ.get('CPPFLAGS','')),
            *shlex.split(os.environ.get('CXXFLAGS','-O2')), '-std=c++17',
            str(ROOT/'tests/check_integer_components.cpp'),'-o',str(cls.helper),
            *shlex.split(os.environ.get('LDFLAGS','')),
            *shlex.split(os.environ.get('LDLIBS','-lgmpxx -lgmp'))],text=True,capture_output=True)
        if build.returncode:raise RuntimeError(build.stdout+build.stderr)
        build=subprocess.run(['make','bin/xy_cf_worker'],cwd=ROOT,text=True,capture_output=True)
        if build.returncode:raise RuntimeError(build.stdout+build.stderr)
        cls.worker=ROOT/'bin/xy_cf_worker'

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def invoke(self,b,pairs,require=True,*extra):
        args=[str(self.worker),'--xy-denominator',str(b),'--n-min','2','--n-max','3',
              '--x-min','24','--x-max','30',*extra]
        if require:args+=['--require-integer-components']
        run=subprocess.run(args,input=''.join(f'{a} {q}\n' for a,q in pairs),
                           text=True,capture_output=True,timeout=20)
        return run,[json.loads(line) for line in run.stdout.splitlines()]

    def test_cpp_python_structural_differential_and_large_integers(self):
        rng=random.Random(391)
        cases=[(F(k,6),F(X,b),F(Y,b)) for b in range(1,10) for k in range(-6,7)
               for X,Y in ((1,3),(2,4),(3,6),(-1,3))]
        cases += [(F(rng.randrange(-10**50,10**50),6),F(rng.randrange(-10**60,10**60),b),
                   F(rng.randrange(10**60),b)) for b in (1,2,3,7) for _ in range(50)]
        run=subprocess.run([str(self.helper)],input=''.join(f'{n} {x} {y}\n' for n,x,y in cases),
                           text=True,capture_output=True,timeout=20)
        self.assertEqual(run.returncode,0,run.stderr)
        expected=[]
        for c in cases:
            try:expected.append('yes '+' '.join(map(str,integer_components(*c))))
            except ValueError:expected.append('no')
        self.assertEqual(run.stdout.splitlines(),expected)

    def test_serialization_rejects_integral_triple_with_wrong_cube_sum(self):
        run=subprocess.run([str(self.helper),'--invalid-sum'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)

    def test_direct_worker_disallows_bigger_denominators_in_final_mode(self):
        for b in (3,6,84):
            run,_=self.invoke(b,[(1,7)])
            self.assertEqual(run.returncode,2)
            self.assertIn('denominator 1 or 2',run.stderr)

    def test_final_worker_matches_independent_small_original_radical_oracle(self):
        # This test checks all candidate points in this rectangle. It need not
        # have a hit; no synthetic triple is mislabeled a 390 solution.
        for b in (1,2):
            sp=XYAQ(cube_search(b))
            pairs=[p for p in sp.iter_candidates(0,sp.count) if gcd(*p)==1]
            expected={p:set() for p in pairs}
            for k in list(range(-18,-11))+list(range(12,19)):
                n=F(k,6)
                for X in list(range(-30*b,-24*b+1))+list(range(24*b,30*b+1)):
                    x=F(X,b)
                    if x.denominator!=b:continue
                    r=(x+6*n)**2+(36*n**3-65)/x
                    if r<0:continue
                    u,v=isqrt(r.numerator),isqrt(r.denominator)
                    if u*u!=r.numerator or v*v!=r.denominator:continue
                    y=F(u,v)
                    if y.denominator!=b:continue
                    A,B,C=-x+y,-x-y,2*x+6*n
                    if any(z.denominator!=1 for z in (A,B,C)):continue
                    self.assertEqual(A**3+B**3+C**3,390)
                    slope=abs(y/abs(x)-1+6*n/x);p=(slope.numerator,slope.denominator)
                    self.assertIn(p,expected)
                    expected[p].add((n,x,y))
            run,rows=self.invoke(b,pairs)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(len(rows),len(pairs))
            for p,row in zip(pairs,rows):
                self.assertEqual(row['status'],'complete',row)
                self.assertTrue(row['integer_components_required'])
                actual={tuple(rational(h,k) for k in ('n','x','y')) for h in row['hits']}
                self.assertEqual(actual,expected[p],(b,p))
                for h in row['hits']:verify_record(h,cube_search(b))

    def test_invalid_fibers_still_rejected_before_prime_sieve(self):
        _,rows=self.invoke(2,[(0,7),(7,7),(14,7),(1,7)])
        self.assertEqual([r['status'] for r in rows],['error','error','error','complete'])
        self.assertTrue(rows[-1]['excluded_by_q_sieve'])

    def test_both_denominator_cases_and_all_sign_selectors_acknowledge_policy(self):
        for b in (1,2):
            for signs in ('all','pp','pn','np','nn'):
                _,rows=self.invoke(b,[(1,7)],True,'--signs',signs)
                self.assertEqual(rows[0]['status'],'complete')
                self.assertTrue(rows[0]['integer_components_required'])
                self.assertEqual(rows[0]['signs'],signs)

    def test_legacy_native_mode_still_finds_real_b6_solution(self):
        f=FIXTURES[0];_,n,x,y,_=f;slope=abs(y/abs(x)-1+6*n/x)
        run,rows=self.invoke(6,[(slope.numerator,slope.denominator)],False,
                             '--n-min','65','--n-max','65','--x-min','964','--x-max','965')
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertFalse(rows[0]['integer_components_required'])
        self.assertEqual(len(rows[0]['hits']),1)
        self.assertNotIn('cube_plus',rows[0]['hits'][0])


MOCK='''#!/usr/bin/env python3
import json,os,sys,time
args=sys.argv[1:]
def arg(k):return args[args.index(k)+1]
for line in sys.stdin:
 a,q=line.split()
 if os.environ.get('CUBE_TEST_SLOW')=='1':time.sleep(3)
 out=dict(a=a,q=q,status='complete',parameterization='n-sixths-equal-xy-denominators-v1',
  xy_denominator=arg('--xy-denominator'),n_denominators=[int(d) for d in arg('--n-denominators').split(',')],
  signs=arg('--signs'),congruence_policy=arg('--congruence-policy'),noninteger_d_required='--noninteger-d' in args,
  integer_components_required='--require-integer-components' in args,
  excluded_by_denominator=False,excluded_by_congruence=False,excluded_by_q_sieve=False,
  excluded_by_bounds=False,precision_bits=0,convergents=0,hits=[])
 policy=os.environ.get('CUBE_TEST_WRONG')
 if policy=='missing':out.pop('integer_components_required')
 if policy=='false':out['integer_components_required']=False
 if policy=='one':out['integer_components_required']=1
 print(json.dumps(out),flush=True)
'''


class ComponentLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.worker=ROOT/'bin/xy_cf_worker'
        r=subprocess.run(['make','bin/xy_cf_worker'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

    def tearDown(self):self.tmp.cleanup()

    def generate(self,*extra):
        parser=argument_parser(integer_components=True)
        args=parser.parse_args(['--campaign-id','cube-test','--n-min','2','--n-max','3',
           '--x-min','24','--x-max','30','--candidates-per-task','100',
           '--output-dir',str(self.root/'tasks'),*extra])
        plan=generate_components(args)
        return plan,[(self.root/'tasks'/p['page'],self.root/'tasks'/p['task_files'][0]) for p in plan['pages']]

    def run_task(self,p,out,env=None):
        return subprocess.run([sys.executable,str(ROOT/'run_xy_task.py'),'--task',str(p),
            '--output-dir',str(out),'--worker',str(self.worker)],capture_output=True,text=True,env=env,timeout=20)

    def mock(self):
        self.worker=self.root/'mock';self.worker.write_text(MOCK);self.worker.chmod(0o755)

    def test_wrapper_writes_two_distinct_explicit_policies_without_submitting(self):
        plan,pages=self.generate()
        self.assertTrue(plan['both_xy_denominators_selected'])
        self.assertEqual(plan['total_tasks_written'],2)
        tasks=[load_json(p) for _,p in pages]
        self.assertEqual({t['search']['xy_denominator'] for t in tasks},{'1','2'})
        self.assertEqual(len({t['task_id'] for t in tasks}),2)
        for t in tasks:
            self.assertTrue(t['search']['require_integer_components'])
            self.assertEqual(t['search']['n_denominators'],[1,2,3,6])
            self.assertEqual(t['search']['congruence_policy'],'none')
            self.assertEqual(t['search']['n_max'],'3')
            validate_task(t)

    def test_single_denominator_is_explicitly_marked_restricted(self):
        plan,pages=self.generate('--xy-denominator','2')
        self.assertFalse(plan['both_xy_denominators_selected'])
        self.assertEqual(len(pages),1)

    def test_real_two_case_pilots_collect_and_verify(self):
        _,pages=self.generate()
        for i,(page,p) in enumerate(pages):
            out=self.root/'returns'/str(i)
            r=self.run_task(p,out);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            s=load_json(out/'status.json');self.assertEqual(s['state'],'complete')
            self.assertEqual(s['output_coverage'],{'start':'0','stop':'100'})
            r=subprocess.run([sys.executable,str(ROOT/'verify_xy.py'),str(out/'hits.jsonl'),
                              '--task',str(p)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertTrue(json.loads(r.stdout)['integer_components_required'])
        result=collect([p for p,_ in pages],self.root/'returns',self.root/'collected')
        self.assertTrue(result['complete_selected_page'])
        self.assertEqual(len(result['tasks']),2)

    def test_worker_policy_is_required_even_for_empty_hit_lists(self):
        _,pages=self.generate('--xy-denominator','1');self.mock()
        for flag in ('missing','false','one'):
            out=self.root/flag;r=self.run_task(pages[0][1],out,dict(os.environ,CUBE_TEST_WRONG=flag))
            self.assertEqual(r.returncode,2,r.stdout+r.stderr)
            s=load_json(out/'status.json');self.assertEqual(s['state'],'error')
            self.assertLess(int(s['next_index']),100)
            self.assertIn('integer-component policy',(out/'error.json').read_text())

    def test_deadline_keeps_policy_and_pins_through_continuation(self):
        _,pages=self.generate('--xy-denominator','2','--seconds','1');page,p=pages[0];self.mock()
        out=self.root/'returns'/'first'
        r=self.run_task(p,out,dict(os.environ,CUBE_TEST_SLOW='1'))
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(load_json(out/'status.json')['state'],'partial')
        continuation=out/'continuation.task.json';t=load_json(continuation)
        self.assertTrue(t['search']['require_integer_components'])
        self.assertIn('expected_worker_sha256',t);self.assertIn('expected_implementation_sha256',t)
        r=self.run_task(continuation,self.root/'returns'/'second')
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertTrue(collect([page],self.root/'returns',self.root/'collected')['complete_selected_page'])

    def test_collector_rejects_changed_component_policy_and_identity(self):
        _,pages=self.generate('--xy-denominator','1');page,p=pages[0];out=self.root/'out'
        self.assertEqual(self.run_task(p,out).returncode,0)
        original=load_json(p);changed=deepcopy(original)
        changed['search']['require_integer_components']=False;changed['task_id']=task_identity(changed)
        with self.assertRaises(ValueError):checked_status(load_json(out/'status.json'),original,changed)

    def test_programmatic_wrapper_cannot_disable_integer_conditions(self):
        args=argument_parser(integer_components=True).parse_args(['--campaign-id','bad'])
        args.require_integer_components=False
        with self.assertRaises(ValueError):generate_components(args)

    def test_cube_wrapper_cli_defaults_production_bounds_and_both_denominators(self):
        r=subprocess.run([sys.executable,str(ROOT/'cube_campaign.py'),'--campaign-id','defaults',
                          '--output-dir',str(self.root/'defaults'),'--candidates-per-task','3'],
                         text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        for p in (self.root/'defaults').glob('b*/task-*.json'):
            t=load_json(p)
            self.assertEqual(t['search']['n_min'],str(10**43))
            self.assertEqual(t['search']['x_max'],str(10**55))
            self.assertTrue(t['search']['require_integer_components'])

    def test_runtime_packaging_contains_wrapper_and_validator(self):
        docker=(ROOT/'Dockerfile').read_text()
        self.assertIn('COPY cube_campaign.py /app/',docker)
        self.assertIn('xy_common.py',docker)


if __name__=='__main__':unittest.main()
