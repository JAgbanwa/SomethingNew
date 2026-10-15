"""Exact independent oracles, native comparisons, and rational job lifecycle tests."""
from __future__ import annotations
import argparse
import contextlib
from copy import deepcopy
from fractions import Fraction
import io
import json
from math import gcd, isqrt
import os
from pathlib import Path
import random
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import rational_common as rc
import rational_campaign as campaign
import run_rational_task as runner
import collect_rational as collector
import run_task as legacy
from q_sieve import reject_q


def search(b=51, integral=False, congruences="none", signs="all", bounds=(2,3,40,50)):
    return dict(zip(rc.BOUND_KEYS,map(str,bounds)), coordinate_denominator=str(b),
                require_integer_sqrt=integral, congruence_policy=congruences,
                require_noninteger_d=False, signs=signs)


def fixture():
    vals=dict(n=Fraction(110,51),x=Fraction(-2341,51),y=Fraction(1676,51),d=Fraction(-5,4682))
    vals["gap"]=vals["y"]-vals["x"]-6*vals["n"]
    out={k+s:str(getattr(v,attr)) for k,v in vals.items()
         for s,attr in (("_num","numerator"),("_den","denominator"))}
    return dict(out,sqrt_integer=False)


def make_job(folder: Path, size=1, ordinal=201):
    args=argparse.Namespace(campaign_id="test-rational-b51", denominator="51", sqrt_policy="rational",
         congruence_policy="none",noninteger_d=False,n_min="2",n_max="3",x_min="40",x_max="50",signs="all",
         q_min="2341",q_max="2341",allow_q_window=True,candidates_per_task=str(size),page_start=str(ordinal),
         task_count=1,seconds=20,precision_bits=512,max_precision_bits=16384,checkpoint_seconds=1,output_dir=folder)
    page=campaign.generate(args)
    return folder/page["tasks"][0]["file"],folder/f"page-{ordinal:012d}.json"


class RationalMathTests(unittest.TestCase):
    def test_known_fractional_pair_verifies_original_equation(self):
        hit=rc.verify_record(fixture(),search())
        self.assertEqual(hit,fixture())
        self.assertEqual(rc.validate_hit(hit,1325,2341,search()),hit)

    def test_radical_integer_policy_is_not_scaled_radical_policy(self):
        # 51*y=1676 is integer, but y itself is NOT. q|X alone is insufficient.
        with self.assertRaisesRegex(ValueError,"not an integer"):
            rc.verify_record(fixture(),search(integral=True))

    def test_equal_reduced_denominators_not_arbitrary_common_representations(self):
        for field in ("n","x"):
            bad=fixture()
            bad[field+"_num"]=str(2*int(bad[field+"_num"]))
            bad[field+"_den"]="102"
            with self.assertRaisesRegex(ValueError,"lowest terms"):
                rc.verify_record(bad,search())
        bad=fixture(); bad["x_den"]="53"
        with self.assertRaisesRegex(ValueError,"exact reduced denominator"):
            rc.verify_record(bad,search())
        with self.assertRaisesRegex(ValueError,"exact reduced denominator"):
            rc.verify_record(fixture(),search(b=102))

    def test_original_unsquared_equation_and_principal_root(self):
        for field in ("d_num","y_num","gap_num","n_num"):
            bad=fixture(); bad[field]=str(-int(bad[field]))
            with self.subTest(field=field),self.assertRaises(ValueError):
                rc.verify_record(bad,search(signs="pn"))
        bad=fixture();bad["sqrt_integer"]=1
        with self.assertRaises(ValueError):rc.verify_record(bad,search())
        with self.assertRaises(ValueError):rc.validate_hit(fixture(),1327,2341,search())

    def test_numerators_are_compared_to_scaled_bounds(self):
        self.assertEqual(rc.rational(rc.verify_record(fixture(),search()),"n"),Fraction(110,51))
        with self.assertRaises(ValueError):rc.verify_record(fixture(),search(bounds=(3,3,40,50)))

    def test_coordinate_denominator_must_be_positive_integer(self):
        for value in ("0","-1","1.5",True,51):
            bad=search();bad["coordinate_denominator"]=value
            with self.subTest(value=value),self.assertRaises(ValueError):rc.validate_search(bad)
        self.assertEqual(rc.validate_search(search(b=1))["denominator"],1)

    def test_policies_are_explicit_and_invalid_domains_rejected(self):
        for key in ("congruence_policy","require_integer_sqrt","require_noninteger_d"):
            bad=search();del bad[key]
            with self.assertRaises(ValueError):rc.validate_search(bad)
        for b in (2,3,7,51):
            with self.assertRaises(ValueError):rc.validate_search(search(b=b,congruences="rational-mod"))
        with self.assertRaises(ValueError):rc.RationalAQ(search(bounds=(2,3,18,50)))
        with self.assertRaises(ValueError):rc.RationalAQ(search(bounds=(2,3,20,50)))

    def test_modular_policies_have_distinct_explicit_meanings(self):
        self.assertTrue(rc.coordinate_congruences(11,193,5,"rational-mod"))
        self.assertFalse(rc.coordinate_congruences(11,193,5,"numerators"))
        self.assertTrue(rc.coordinate_congruences(16,29,5,"numerators"))
        self.assertFalse(rc.coordinate_congruences(16,29,5,"rational-mod"))
        for b in (1,5,13,17):
            for N in range(-20,21):
                for X in range(-20,21):
                    expected=(N*pow(b,-1,3)%3==1 and X*pow(b,-1,12)%12==5 and X*pow(b,-1,7)%7!=0)
                    self.assertEqual(rc.coordinate_congruences(N,X,b,"rational-mod"),expected)

    def test_prefix_ranking_and_stream_match_exhaustive_enumeration(self):
        for b in (1,2,5,51):
            for integral in (False,True):
                for lo,hi in ((1,80),(20,57),(51,51)):
                    hi=min(hi,rc.RationalAQ(search(b,integral)).full_q_max)
                    if lo>hi:continue
                    space=rc.RationalAQ(search(b,integral),lo,hi)
                    pairs=[(a,q) for q in range(lo,hi+1) for a in range(1,q)
                           if space.lower<=Fraction(a,q)<=space.upper]
                    self.assertEqual(space.count,len(pairs))
                    self.assertEqual(list(space.iter_candidates(0,space.count)),pairs)
                    for index,pair in enumerate(pairs):
                        self.assertEqual(space.candidate(index),pair)
                        self.assertEqual(space.index(*pair),index)

    def test_large_integer_rank_roundtrips_and_row_boundaries(self):
        rng=random.Random(390)
        for b in (1,2,51,10**30+1):
            for integral in (False,True):
                space=rc.RationalAQ(search(b,integral,bounds=(10**43,10**45,10**54,10**55)))
                for _ in range(20):
                    index=rng.randrange(space.count)
                    pair=space.candidate(index)
                    self.assertEqual(space.index(*pair),index)
                    end=min(space.count,index+6)
                    self.assertEqual(list(space.iter_candidates(index,end)),[space.candidate(i) for i in range(index,end)])

    def test_full_q_bound_differs_by_radical_policy(self):
        self.assertEqual(rc.RationalAQ(search()).full_q_max,2550*isqrt(2550))
        self.assertEqual(rc.RationalAQ(search(integral=True)).full_q_max,2550)
        rational_space=rc.RationalAQ(search(b=1, bounds=(5,5,81,81)))
        # Historical rational radical has q=729 > |X|=81 and is retained.
        self.assertTrue(0<=rational_space.index(545,729)<rational_space.count)
        with self.assertRaises(ValueError):rc.RationalAQ(search(integral=True),1,2551)

    def test_empty_integer_gap_region(self):
        space=rc.RationalAQ(search(b=1,integral=True,bounds=(2,2,1000,2000)))
        self.assertEqual(space.count,0)
        self.assertEqual(list(space.iter_candidates(0,0)),[])
        with self.assertRaises(ValueError):space.candidate(0)

    def test_no_old_parity_or_mod3_filter_is_assumed(self):
        space=rc.RationalAQ(search(),1,60)
        pairs=list(space.iter_candidates(0,space.count))
        self.assertTrue(any(a%2==0 or q%2==0 for a,q in pairs))
        self.assertTrue(any(a%3==0 or q%3==0 for a,q in pairs))

    def test_integer_root_sieve_remains_safe_for_coprime_scaled_coordinates(self):
        for b in range(1,31):
            for N in range(-60,61):
                if gcd(N,b)!=1:continue
                A=36*N**3-65*b**3
                for X in range(1,81):
                    if gcd(X,b)==1 and A%X==0:
                        self.assertFalse(reject_q(X,require_integer_sqrt=True),(b,N,X))

    def test_task_identity_binds_denominator_and_policies(self):
        with tempfile.TemporaryDirectory() as tmp:
            taskpath,_=make_job(Path(tmp))
            task=legacy.load_json(taskpath)
            rc.validate_task(task)
            for key,value in (("coordinate_denominator","52"),("require_integer_sqrt",True),("congruence_policy","numerators")):
                changed=deepcopy(task);changed["search"][key]=value
                with self.assertRaises(ValueError):rc.validate_task(changed)
            with self.assertRaises(ValueError):legacy.validate_task(task)
            changed=deepcopy(task);changed["schema"]="ce390-task-v2"
            with self.assertRaises(ValueError):rc.validate_task(changed)


class RationalNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build=subprocess.run(["make","-j2"],cwd=ROOT,text=True,capture_output=True)
        if build.returncode:raise RuntimeError(build.stdout+build.stderr)
        cls.binary=ROOT/"bin/rational_cf_worker"

    def invoke(self,pairs,config=None,*extra):
        s=config or search()
        cmd=[str(self.binary),"--coordinate-denominator",s["coordinate_denominator"],
             "--congruence-policy",s["congruence_policy"],"--signs",s["signs"],
             "--integer-sqrt" if s["require_integer_sqrt"] else "--allow-rational-sqrt"]
        for key in rc.BOUND_KEYS:cmd.extend(["--"+key.replace("_","-"),s[key]])
        if s["require_noninteger_d"]:cmd.append("--noninteger-d")
        p=subprocess.run(cmd+list(extra),input="".join(f"{a} {q}\n" for a,q in pairs),text=True,capture_output=True,timeout=20)
        self.assertEqual(p.returncode,0,p.stderr)
        rows=[json.loads(v) for v in p.stdout.splitlines()]
        self.assertEqual(len(rows),len(pairs))
        return rows

    def test_actual_cpp_generalized_fallback_is_essential(self):
        with tempfile.TemporaryDirectory() as tmp:
            compiler=shlex.split(os.environ.get("CXX","g++"))
            exe=Path(tmp)/"checks"
            cmd=[*compiler,*shlex.split(os.environ.get("CPPFLAGS","")),
                 *shlex.split(os.environ.get("CXXFLAGS","-O2")),"-std=c++17","-UNDEBUG",
                 str(ROOT/"tests/rational_cpp_checks.cpp"),"-o",str(exe),
                 *shlex.split(os.environ.get("LDFLAGS","")),
                 *shlex.split(os.environ.get("LDLIBS","-lgmpxx -lgmp"))]
            build=subprocess.run(cmd,text=True,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout+build.stderr)
            check=subprocess.run([str(exe)],text=True,capture_output=True,timeout=20)
            self.assertEqual(check.returncode,0,check.stdout+check.stderr)
            self.assertIn("nonconvergent fallback witness",check.stdout)

    def test_fractional_witness_and_all_sign_policies(self):
        for sign in legacy.SIGN_POLICIES:
            s=search(signs=sign)
            row=self.invoke([(1325,2341)],s)[0]
            self.assertEqual(row["status"],"complete",row)
            self.assertEqual(row["hits"],[fixture()] if sign in ("all","pn") else [])
            for hit in row["hits"]:rc.verify_record(hit,s)

    def test_integer_radical_rejects_scaled_integer_false_positive(self):
        row=self.invoke([(1325,2341)],search(integral=True))[0]
        self.assertEqual(row["status"],"complete",row)
        self.assertEqual(row["hits"],[])

    def test_numerator_residue_filter_is_optional_not_assumed(self):
        row=self.invoke([(1325,2341)],search(congruences="numerators"))[0]
        self.assertEqual(row["hits"],[])
        self.assertEqual(self.invoke([(1325,2341)])[0]["hits"],[fixture()])

    def test_integral_pairs_do_not_masquerade_as_denominator_two(self):
        row=self.invoke([(545,729)],search(b=2,bounds=(5,5,81,81)))[0]
        self.assertEqual(row["status"],"complete",row)
        self.assertEqual(row["hits"],[])
        row=self.invoke([(545,729)],search(b=1,bounds=(5,5,81,81)))[0]
        self.assertEqual([(h["n_num"],h["x_num"],h["n_den"],h["x_den"]) for h in row["hits"]],[("-5","81","1","1")])

    def test_denominator_one_matches_legacy_worker_with_even_q(self):
        fixtures=[(166,-2500,(100703,125000)),(2047,-45972,(147983,275832)),(-5,81,(545,729))]
        for n,x,pair in fixtures:
            s=search(b=1,bounds=(abs(n),abs(n),abs(x),abs(x)))
            row=self.invoke([pair],s)[0]
            self.assertEqual(row["status"],"complete",row)
            self.assertEqual(len(row["hits"]),1)
            hit=row["hits"][0]
            self.assertEqual((int(hit["n_num"]),int(hit["x_num"])),(n,x))
            rc.verify_record(hit,s)
            cmd=[str(ROOT/"bin/cf_worker"),"--allow-rational-sqrt","--relax-congruences"]
            for k in rc.BOUND_KEYS:cmd.extend(["--"+k.replace("_","-"),s[k]])
            old=subprocess.run(cmd,input=f"{pair[0]} {pair[1]}\n",capture_output=True,text=True,check=True)
            expected=json.loads(old.stdout)["hits"][0]
            for k in ("d_num","d_den","y_num","y_den"):self.assertEqual(hit[k],expected[k])

    def test_obstructing_prime_sieve_does_not_reject_rational_radicals(self):
        s=search(b=1,bounds=(5877899,5877899,11122866225,11122866225))
        pair=(7438954542449,1173073086419625)
        self.assertTrue(reject_q(pair[1],require_integer_sqrt=True))
        row=self.invoke([pair],s)[0]
        self.assertEqual(len(row["hits"]),1,row)
        self.assertFalse(row["excluded_by_q_sieve"])
        rc.verify_record(row["hits"][0],s)
        s["require_integer_sqrt"]=True
        row=self.invoke([pair],s)[0]
        self.assertTrue(row["excluded_by_q_sieve"])
        self.assertEqual(row["hits"],[])

    def test_new_denominator_target_matches_bruteforce_original_equation(self):
        # No cubic or continued fraction in this oracle. Includes a genuine hit.
        for b in (1,2,5,51):
            s=search(b=b)
            pairs={(1,2),(2,3),(3,5),(4,7),(5,9),(1325,2341)}
            expected={}
            for N in range(2*b,3*b+1):
                if gcd(N,b)!=1:continue
                for X in range(40*b,50*b+1):
                    if gcd(X,b)!=1:continue
                    for sn in (1,-1):
                        for sx in (1,-1):
                            u,v=sn*N,sx*X
                            M=v*v*(v+6*u)**2+(36*u**3-65*b**3)*v
                            if M<0:continue
                            m=isqrt(M)
                            if m*m!=M:continue
                            n,x,y=Fraction(u,b),Fraction(v,b),Fraction(m,b*X)
                            slope=abs(y/abs(x)-1+6*n/x)
                            if not 0<slope<1:continue
                            pair=(slope.numerator,slope.denominator)
                            pairs.add(pair)
                            expected.setdefault(pair,set()).add((u,v,y))
            for integral in (False,True):
                s["require_integer_sqrt"]=integral
                ordered=sorted(pairs)
                for pair,row in zip(ordered,self.invoke(ordered,s)):
                    self.assertEqual(row["status"],"complete",row)
                    want={p for p in expected.get(pair,set()) if not integral or p[2].denominator==1}
                    got={(int(h["n_num"]),int(h["x_num"]),rc.rational(h,"y")) for h in row["hits"]}
                    self.assertEqual(got,want,(b,integral,pair))
                    for h in row["hits"]:rc.verify_record(h,s)

    def test_bad_pair_does_not_skip_input_validation_or_poison_next_query(self):
        rows=self.invoke([(0,7),(7,7),(2,4),(1325,2341)])
        self.assertEqual([r["status"] for r in rows],["error","error","error","complete"])

    def test_large_bound_precision_cap_still_reports_error(self):
        s=search(b=51,bounds=(10**43,10**45,10**54,10**55))
        row=self.invoke([(1,10000000001)],s,"--precision-bits","64","--max-precision-bits","64")[0]
        self.assertEqual(row["status"],"error",row)
        row=self.invoke([(1,10000000001)],s,"--precision-bits","64")[0]
        self.assertEqual(row["status"],"complete",row)
        self.assertGreater(row["precision_bits"],64)


class RationalLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=subprocess.run(["make","-j2"],cwd=ROOT,capture_output=True,text=True)
        if p.returncode:raise RuntimeError(p.stdout+p.stderr)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.taskpath,self.page=make_job(self.root/"tasks")
        self.task=legacy.load_json(self.taskpath)
        self.output=self.root/"results"/"run1"

    def tearDown(self):self.temp.cleanup()

    def run_job(self,task=None,output=None,worker=None):
        args=argparse.Namespace(task=task or self.taskpath,output_dir=output or self.output,
             worker=worker or ROOT/"bin/rational_cf_worker",checkpoint=None)
        with contextlib.redirect_stdout(io.StringIO()):return runner.run(args)

    def test_real_run_collect_and_verify_fractional_certificate(self):
        self.assertEqual(self.run_job(),0)
        status=legacy.load_json(self.output/"status.json")
        self.assertTrue(status["complete"])
        self.assertEqual(status["next_index"],self.task["slice"]["stop"])
        self.assertEqual(status["unique_hits_in_this_output"],"1")
        summary=collector.collect([self.page],self.root/"results",self.root/"collected")
        self.assertTrue(summary["complete_selected_page"])
        self.assertEqual(summary["unique_verified_solutions"],1)
        p=subprocess.run([sys.executable,str(ROOT/"verify_rational.py"),str(self.root/"collected/hits.jsonl"),"--task",str(self.taskpath)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_resume_on_new_host_preserves_prior_hit_and_coverage(self):
        self.taskpath,self.page=make_job(self.root/"resume-tasks",size=3,ordinal=67)
        Native=runner.Worker
        class Pause(Native):
            def query(self,a,q):
                if a==1326:raise legacy.Halt("time_limit")
                return super().query(a,q)
        with patch.object(runner,"Worker",Pause):self.assertEqual(self.run_job(),0)
        status=legacy.load_json(self.output/"status.json")
        self.assertEqual((status["state"],status["next_index"]),("partial","202"))
        continuation=self.output/"continuation.task.json"
        c=legacy.load_json(continuation)
        self.assertIn("expected_implementation_sha256",c)
        other=self.root/"results/run2"
        self.assertEqual(self.run_job(task=continuation,output=other),0)
        self.assertEqual(legacy.load_json(other/"status.json")["output_coverage"]["start"],"202")
        only=collector.collect([self.page],other,self.root/"only-second")
        self.assertFalse(only["complete_selected_page"])
        combined=collector.collect([self.page],self.root/"results",self.root/"collected")
        self.assertTrue(combined["complete_selected_page"])
        self.assertEqual(combined["unique_verified_solutions"],1)

    def test_retained_output_recovery_and_whole_hit_loss_detection(self):
        self.assertEqual(self.run_job(),0)
        self.assertEqual(self.run_job(),0)
        self.assertEqual(len((self.output/"hits.jsonl").read_text().splitlines()),1)
        (self.output/"hits.jsonl").write_text("")
        with self.assertRaisesRegex(ValueError,"lost"):self.run_job()

    def test_worker_and_implementation_pins_reject_changed_execution(self):
        for key in ("expected_worker_sha256","expected_implementation_sha256"):
            t=deepcopy(self.task);t[key]="0"*64
            path=self.root/(key+".json");legacy.atomic_json(path,t)
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.run_job(task=path,output=self.root/key)

    def test_collector_rejects_tampered_denominators_and_counters(self):
        self.assertEqual(self.run_job(),0)
        hits=self.output/"hits.jsonl"
        row=json.loads(hits.read_text());original=hits.read_bytes()
        row["x_den"]="52";hits.write_text(json.dumps(row)+"\n")
        with self.assertRaises(ValueError):collector.collect([self.page],self.root/"results",self.root/"collected")
        hits.write_bytes(original)
        sp=self.output/"status.json";s=legacy.load_json(sp)
        s["counters_this_invocation"]["q_sieve_excluded"]="1"
        legacy.atomic_json(sp,s)
        with self.assertRaises(ValueError):collector.collect([self.page],self.root/"results",self.root/"collected")

    def test_mismatched_worker_policy_cannot_certify_completion(self):
        Native=runner.Worker
        class WrongPolicy(Native):
            def query(self,a,q):
                out=super().query(a,q);out["coordinate_denominator"]="1";return out
        with patch.object(runner,"Worker",WrongPolicy):self.assertEqual(self.run_job(),2)
        status=legacy.load_json(self.output/"status.json")
        self.assertEqual(status["state"],"error")
        self.assertEqual(status["next_index"],self.task["slice"]["start"])

    def test_actual_deadline_interrupts_unresponsive_worker_without_advancing(self):
        fake=self.root/"sleeping-worker"
        fake.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(10)\n")
        fake.chmod(0o755)
        task=deepcopy(self.task);task["execution"]["time_limit_seconds"]=1
        path=self.root/"short.task.json";legacy.atomic_json(path,task)
        self.assertEqual(self.run_job(task=path,worker=fake),0)
        status=legacy.load_json(self.output/"status.json")
        self.assertEqual((status["state"],status["reason"]),("partial","time_limit"))
        self.assertEqual(status["next_index"],self.task["slice"]["start"])
        self.assertTrue((self.output/"continuation.task.json").exists())

    def test_generator_requires_explicit_new_policy_options(self):
        p=subprocess.run([sys.executable,str(ROOT/"rational_campaign.py"),"--campaign-id","bad"],capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("--denominator",p.stderr)
        self.assertIn("--sqrt-policy",p.stderr)
        self.assertIn("--congruence-policy",p.stderr)

    def test_packaging_keeps_legacy_entrypoint_and_adds_explicit_rational_command(self):
        docker=(ROOT/"Dockerfile").read_text()
        self.assertIn("rational_common.py rational_campaign.py run_rational_task.py collect_rational.py verify_rational.py",docker)
        self.assertIn("COPY --from=build /build/bin/ /app/bin/",docker)
        self.assertIn("ENTRYPOINT [\"/app/container_entrypoint.sh\"]",docker)
        self.assertIn("bin/rational_cf_worker: src/rational_cf_worker.cpp src/q_sieve.hpp",(ROOT/"Makefile").read_text())


if __name__=="__main__":unittest.main()
