"""Independent exact checks for the CORRECTED target; no external packages."""
from copy import deepcopy
from fractions import Fraction as F
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
sys.path.insert(0,str(ROOT))
from xy_common import (XYAQ, SCHEMA, PARAMETERIZATION, validate_search, validate_task,
                       verify_record, validate_hit, rational, reject_xy_q, coordinate_congruences)
from run_task import task_identity
from q_sieve import forbidden_primes

FIXTURES = [
    (6, F(-65), F(5785,6), F(3391,6), F(-3418,5785)),
    (8, F(5,2), F(199,8), F(321,8), F(-320,199)),
    (195, F(16,3), F(-16189,195), F(9824,195), F(-125,32378)),
    (84, F(17,6), F(-4523,84), F(3079,84), F(-8,4523)),
]

def search(b=8, **kw):
    out=dict(n_min="2", n_max="3", x_min="24", x_max="30", signs="all",
             xy_denominator=str(b), n_denominators=[1,2,3,6],
             congruence_policy="none", require_noninteger_d=False)
    out.update(kw)
    return out

def fixture_search(f):
    b,n,x,_,_=f
    return search(b,n_min=str(abs(n.numerator)//n.denominator),
                  n_max=str(-(-abs(n.numerator)//n.denominator)),
                  x_min=str(abs(x.numerator)//x.denominator),
                  x_max=str(-(-abs(x.numerator)//x.denominator)))

def record(f):
    b,n,x,y,d=f
    values=dict(n=n,x=x,y=y,d=d,gap=y-x-6*n)
    out={k+s:str(getattr(v,attr)) for k,v in values.items()
         for s,attr in (("_num","numerator"),("_den","denominator"))}
    out["sqrt_integer"]=y.denominator==1
    return out

def task(s=None, *, q_min=None, q_max=None, stop=100):
    s=s or search()
    full=XYAQ(s)
    q_min=1 if q_min is None else q_min
    q_max=full.full_q_max if q_max is None else q_max
    space=XYAQ(s,q_min,q_max)
    out=dict(schema=SCHEMA,parameterization=PARAMETERIZATION,campaign_id="xy-test",
             search=s,fibers=dict(mode=XYAQ.MODE,q_min=str(q_min),q_max=str(q_max)),
             slice=dict(start="0",stop=str(min(stop,space.count))),
             execution=dict(time_limit_seconds=10,precision_bits=512,
                            max_precision_bits=16384,checkpoint_seconds=1))
    out['task_id']=task_identity(out)
    return out

class XYCertificateTests(unittest.TestCase):
    def test_all_four_n_denominators_with_unequal_n_and_x_denominators(self):
        self.assertEqual({f[1].denominator for f in FIXTURES},{1,2,3,6})
        for f in FIXTURES:
            self.assertNotEqual(f[1].denominator, f[0])
            checked=verify_record(record(f),fixture_search(f))
            self.assertEqual(rational(checked,'y').denominator,f[0])

    def test_denominators_mean_lowest_terms_not_displayed_values(self):
        h=record(FIXTURES[1]);h['y_num']=str(int(h['y_num'])*2);h['y_den']='16'
        with self.assertRaisesRegex(ValueError,'lowest terms'):
            verify_record(h,fixture_search(FIXTURES[1]))

    def test_wrong_y_denominator_is_rejected(self):
        h=record(FIXTURES[1]);h['y_den']='7'
        with self.assertRaisesRegex(ValueError,'x and y'):
            verify_record(h,fixture_search(FIXTURES[1]))

    def test_wrong_x_denominator_is_rejected(self):
        h=record(FIXTURES[1]);h['x_den']='7'
        with self.assertRaisesRegex(ValueError,'x and y'):
            verify_record(h,fixture_search(FIXTURES[1]))

    def test_n_denominator_outside_set_rejected(self):
        h=record(FIXTURES[1]);h['n_den']='7'
        with self.assertRaisesRegex(ValueError,'n must'):
            verify_record(h,fixture_search(FIXTURES[1]))

    def test_n_subset_is_enforced_independently(self):
        s=fixture_search(FIXTURES[1]);s['n_denominators']=[1,3,6]
        with self.assertRaisesRegex(ValueError,'n must'):
            verify_record(record(FIXTURES[1]),s)

    def test_original_equation_and_not_just_squared_identity(self):
        h=record(FIXTURES[1]);h['d_num']='-319'
        with self.assertRaisesRegex(ValueError,'unsquared'):
            verify_record(h,fixture_search(FIXTURES[1]))

    def test_negative_root_is_not_principal(self):
        h=record(FIXTURES[1]);h['y_num']='-321'
        with self.assertRaisesRegex(ValueError,'principal'):
            verify_record(h,fixture_search(FIXTURES[1]))

    def test_boolean_numbers_and_wrong_integer_flag_rejected(self):
        for key,value in [('n_num',True),('sqrt_integer',True)]:
            h=record(FIXTURES[1]);h[key]=value
            with self.assertRaises(ValueError):verify_record(h,fixture_search(FIXTURES[1]))

    def test_scope_and_canonical_n_denominator_list(self):
        for ds in ([],[0],[4],[True],[1,1],[2,1],[1,2,3,6,12],"1,2,3,6"):
            with self.assertRaises(ValueError):validate_search(search(n_denominators=ds))
        for ds in ([1],[2],[3],[6],[1,2,3,6]):validate_search(search(n_denominators=ds))

    def test_old_congruences_not_silently_inherited(self):
        s=fixture_search(FIXTURES[1])
        verify_record(record(FIXTURES[1]),s)
        s['congruence_policy']='numerators'
        with self.assertRaisesRegex(ValueError,'congruence'):
            verify_record(record(FIXTURES[1]),s)

    def test_rational_congruences_require_inverses(self):
        with self.assertRaises(ValueError):validate_search(search(8,congruence_policy='rational-mod'))
        with self.assertRaises(ValueError):validate_search(search(5,congruence_policy='rational-mod'))
        validate_search(search(5,n_denominators=[1,2],congruence_policy='rational-mod'))
        self.assertTrue(coordinate_congruences(F(5,2),F(67,11),'rational-mod'))
        self.assertFalse(coordinate_congruences(F(5,2),F(67,11),'numerators'))

    def test_sieve_proof_for_every_prime_below_20000(self):
        bad=set(forbidden_primes())
        flags=bytearray(b'\1')*20000;flags[:2]=b'\0\0'
        for p in range(2,20000):
            if not flags[p]:continue
            flags[p*p::p]=b'\0'*len(flags[p*p::p])
            if p<=3:continue
            soluble=any(pow(k,3,p)==390%p for k in range(p))
            self.assertEqual(p in bad,not soluble,p)

    def test_prime_sieve_accepts_all_actual_fixtures(self):
        for _,n,x,y,_ in FIXTURES:
            q=abs(y/abs(x)-1+6*n/x).denominator
            self.assertFalse(reject_xy_q(q))
            self.assertEqual(x.numerator % q,0)
            self.assertEqual((int(6*n)**3-390)%abs(x.numerator),0)
        self.assertTrue(reject_xy_q(7*10**55))
        for value in (0,-1,True,F(7)):
            with self.assertRaises(ValueError):reject_xy_q(value)

class XYSpaceTests(unittest.TestCase):
    def test_full_enclosure_matches_simple_enumeration(self):
        for b in (1,2,3,8):
            sp=XYAQ(search(b))
            expected=[]
            for q in range(1,sp.full_q_max+1):
                lo,hi=sp.numerator_bounds(q)
                expected.extend((a,q) for a in range(lo,hi+1))
            self.assertEqual(sp.count,len(expected))
            self.assertEqual(list(sp.iter_candidates(0,sp.count)),expected)
            for i in range(0,sp.count,max(1,sp.count//31)):
                self.assertEqual(sp.candidate(i),expected[i]);self.assertEqual(sp.index(*expected[i]),i)

    def test_n_numerators_scale_by_six_not_by_b(self):
        sp=XYAQ(search(195))
        self.assertEqual(sp.Mmin,2*195*12+1)
        self.assertEqual(sp.full_q_max,195*30)

    def test_all_real_fixtures_are_in_enclosure(self):
        for f in FIXTURES:
            _,n,x,y,_=f;sp=XYAQ(fixture_search(f));a=abs(y/abs(x)-1+6*n/x)
            i=sp.index(a.numerator,a.denominator)
            self.assertEqual(sp.candidate(i),(a.numerator,a.denominator))

    def test_slope_above_one_is_not_incorrectly_lost(self):
        f=FIXTURES[1];p=abs(f[3]/abs(f[2])-1+6*f[1]/f[2]);self.assertGreater(p,1)
        validate_hit(record(f),p.numerator,p.denominator,fixture_search(f))

    def test_large_rank_roundtrips_all_b_without_float(self):
        rng=random.Random(83)
        for b in (1,84,10**30+1,10**55+13):
            s=search(b,n_min=str(10**43),n_max=str(10**45),x_min=str(10**54),x_max=str(10**55))
            sp=XYAQ(s)
            for i in [0,sp.count-1]+[rng.randrange(sp.count) for _ in range(8)]:
                self.assertEqual(sp.index(*sp.candidate(i)),i)
                pairs=list(sp.iter_candidates(i,min(i+3,sp.count)))
                self.assertEqual([sp.index(*p) for p in pairs],list(range(i,min(i+3,sp.count))))

    def test_windows_partition_without_reindexing_holes(self):
        s=search(8);sp=XYAQ(s)
        parts=[XYAQ(s,1,100),XYAQ(s,101,sp.full_q_max)]
        self.assertEqual(sum(z.count for z in parts),sp.count)
        self.assertEqual([p for z in parts for p in z.iter_candidates(0,z.count)],list(sp.iter_candidates(0,sp.count)))

    def test_empty_region_and_necessary_b_ceiling(self):
        sp=XYAQ(search(1,n_min='2',n_max='2',x_min='1000',x_max='1001'))
        self.assertEqual(sp.count,0)
        sp=XYAQ(search(1000,n_min='2',n_max='3',x_min='24',x_max='30'))
        self.assertEqual(sp.count,0);self.assertEqual(sp.max_possible_b,(18**3+390)//24)

    def test_invalid_enclosures_and_indices(self):
        for kw in ({'n_min':'1'}, {'x_min':'18'}, {'x_min':'19'}, {'xy_denominator':'0'}):
            with self.assertRaises(ValueError):XYAQ(search(**kw))
        sp=XYAQ(search())
        for i in (-1,sp.count,True):
            with self.assertRaises(ValueError):sp.candidate(i)
        with self.assertRaises(ValueError):sp.index(0,1)

    def test_task_identity_binds_corrected_denominators(self):
        t=task();validate_task(t)
        for key,val in [('xy_denominator','9'),('n_denominators',[1])]:
            u=deepcopy(t);u['search'][key]=val
            with self.assertRaises(ValueError):validate_task(u)
        u=deepcopy(t);u['search']['require_integer_sqrt']=True
        with self.assertRaises(ValueError):validate_task(u)
        u=deepcopy(t);u['schema']='ce390-rational-task-v1'
        with self.assertRaises(ValueError):validate_task(u)

class XYWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.worker=Path(cls.tmp.name)/'xy_worker'
        compiler=shlex.split(os.environ.get('CXX','g++'))
        if not compiler or not shutil.which(compiler[0]):raise unittest.SkipTest('C++17/GMP compiler required')
        command=[*compiler,*shlex.split(os.environ.get('CPPFLAGS','')),
                 *shlex.split(os.environ.get('CXXFLAGS','-O2 -Wall -Wextra')),'-std=c++17',
                 str(ROOT/'src/xy_cf_worker.cpp'),'-o',str(cls.worker),
                 *shlex.split(os.environ.get('LDFLAGS','')),*shlex.split(os.environ.get('LDLIBS','-lgmpxx -lgmp'))]
        result=subprocess.run(command,text=True,capture_output=True)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def invoke(self,pairs,s,extra=()):
        argv=[str(self.worker),'--xy-denominator',s['xy_denominator'],
              '--congruence-policy',s['congruence_policy'],'--signs',s['signs'],
              '--n-denominators',','.join(map(str,s['n_denominators']))]
        for k in ('n_min','n_max','x_min','x_max'):argv+=['--'+k.replace('_','-'),s[k]]
        if s['require_noninteger_d']:argv+=['--noninteger-d']
        r=subprocess.run([*argv,*extra],input=''.join(f'{a} {q}\n' for a,q in pairs),text=True,capture_output=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stderr)
        rows=[json.loads(z) for z in r.stdout.splitlines()];self.assertEqual(len(rows),len(pairs));return rows

    def test_nonempty_fixtures_all_four_denominators_and_all_sign_selectors(self):
        for f in FIXTURES:
            b,n,x,y,_=f;a=abs(y/abs(x)-1+6*n/x);signs=('p' if n>0 else 'n')+('p' if x>0 else 'n')
            for policy in ('all','pp','pn','np','nn'):
                s=fixture_search(f);s['signs']=policy
                row=self.invoke([(a.numerator,a.denominator)],s)[0]
                self.assertEqual(row['status'],'complete',row)
                hits={(rational(h,'n'),rational(h,'x')) for h in row['hits']}
                self.assertEqual(hits,{(n,x)} if policy in ('all',signs) else set())
                for h in row['hits']:verify_record(h,s)

    def test_n_denominator_subset_not_forced_equal_to_b(self):
        for f in FIXTURES:
            _,n,x,y,_=f;a=abs(y/abs(x)-1+6*n/x)
            for ds in ([n.denominator],[z for z in (1,2,3,6) if z!=n.denominator]):
                s=fixture_search(f);s['n_denominators']=ds
                row=self.invoke([(a.numerator,a.denominator)],s)[0]
                self.assertEqual(bool(row['hits']),n.denominator in ds)

    def test_nonempty_cf_and_nonempty_exact_fallback_are_both_exercised(self):
        for f,cf in ((FIXTURES[0],True),(FIXTURES[1],False)):
            a=abs(f[3]/abs(f[2])-1+6*f[1]/f[2]);r=self.invoke([(a.numerator,a.denominator)],fixture_search(f))[0]
            self.assertTrue(r['hits']);self.assertEqual(r['convergents']>0,cf)

    def test_complete_small_oracle_including_fractional_y(self):
        # Oracle enumerates k and X, not slopes or worker polynomials.
        for b in (1,2,3,8):
            s=search(b);sp=XYAQ(s);expected={}
            for k in list(range(-18,-11))+list(range(12,19)):
                for X in list(range(-30*b,-24*b+1))+list(range(24*b,30*b+1)):
                    if gcd(X,b)!=1:continue
                    n,x=F(k,6),F(X,b);r=(x+6*n)**2+(36*n**3-65)/x
                    if r<0:continue
                    u,v=isqrt(r.numerator),isqrt(r.denominator)
                    if u*u!=r.numerator or v*v!=r.denominator:continue
                    y=F(u,v)
                    if y.denominator!=b:continue
                    a=abs(y/abs(x)-1+6*n/x)
                    expected.setdefault((a.numerator,a.denominator),set()).add((n,x))
            pairs=[p for p in sp.iter_candidates(0,sp.count) if gcd(*p)==1]
            rows=self.invoke(pairs,s)
            found=set()
            for pair,row in zip(pairs,rows):
                self.assertEqual(row['status'],'complete',row)
                actual={(rational(h,'n'),rational(h,'x')) for h in row['hits']}
                self.assertEqual(actual,expected.get(pair,set()),(b,pair))
                found.update(actual)
            if b==8:self.assertIn((F(5,2),F(199,8)),found)

    def test_sieve_applies_to_corrected_fractional_y_mode(self):
        pairs=[(1,p) for p in forbidden_primes() if gcd(p,84)==1]
        rows=self.invoke(pairs,search(84))
        self.assertTrue(all(r['status']=='complete' and r['excluded_by_q_sieve'] and not r['hits'] for r in rows))

    def test_common_q_b_factor_is_certified_empty(self):
        r=self.invoke([(1,2),(1,3),(1,6)],search(84))
        self.assertTrue(all(z['excluded_by_denominator'] and not z['hits'] for z in r))

    def test_invalid_fibers_rejected_before_sieve(self):
        rows=self.invoke([(0,7),(14,7),(7,7),(1,7),(2,5),(1,1)],search(8))
        self.assertEqual([r['status'] for r in rows],['error','error','error','complete','complete','complete'])

    def test_no_old_a_q_parity_filters(self):
        rows=self.invoke([(2,5),(1,6),(3,5)],search(1))
        self.assertTrue(all(r['status']=='complete' for r in rows))

    def test_old_sqrt_policy_is_not_accepted(self):
        r=subprocess.run([str(self.worker),'--xy-denominator','8','--integer-sqrt'],text=True,capture_output=True)
        self.assertEqual(r.returncode,2)

    def test_precision_failure_does_not_become_empty_completion(self):
        s=search(84,n_min=str(10**43),n_max=str(10**45),x_min=str(10**54),x_max=str(10**55))
        sp=XYAQ(s)
        pairs=[]
        for a,q in sp.iter_candidates(0,100):
            if gcd(a,q)==gcd(q,84)==1 and not reject_xy_q(q):pairs.append((a,q))
        low=self.invoke(pairs,s,('--precision-bits','64','--max-precision-bits','64'))
        high=self.invoke(pairs,s,('--precision-bits','1024'))
        self.assertTrue(any(r['status']=='error' for r in low))
        self.assertTrue(all(r['status']=='complete' for r in high))

if __name__=='__main__':unittest.main()
