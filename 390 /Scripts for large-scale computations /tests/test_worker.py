"""Black-box worker differentials and arithmetic checks of the actual C++ code."""
import json
from fractions import Fraction
from math import gcd, isqrt
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verify import Bounds, verify_record


class WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shlex.split(os.environ.get("CXX", "g++"))
        if not compiler or not shutil.which(compiler[0]):
            raise unittest.SkipTest("a C++17 compiler is required for GMP worker tests")
        cls.temp = tempfile.TemporaryDirectory()
        cls.worker = Path(cls.temp.name)/"cf_worker"
        cls.checks = Path(cls.temp.name)/"cpp_checks"
        for source, target in [(ROOT/"src/cf_worker.cpp", cls.worker),
                               (ROOT/"tests/cpp_checks.cpp", cls.checks)]:
            build = subprocess.run([*compiler,
                                    *shlex.split(os.environ.get("CPPFLAGS", "")),
                                    *shlex.split(os.environ.get("CXXFLAGS", "-O2 -Wall -Wextra")),
                                    "-std=c++17", "-UNDEBUG", str(source), "-o", str(target),
                                    *shlex.split(os.environ.get("LDFLAGS", "")),
                                    *shlex.split(os.environ.get("LDLIBS", "-lgmpxx -lgmp"))],
                                   text=True, capture_output=True)
            if build.returncode:
                raise RuntimeError(build.stdout+build.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def invoke(self, pairs, *options):
        run = subprocess.run([str(self.worker), *options],
                             input="".join(f"{a} {q}\n" for a,q in pairs),
                             text=True, capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        rows = [json.loads(line) for line in run.stdout.splitlines()]
        self.assertEqual(len(rows),len(pairs))
        return rows

    def test_actual_gmp_helpers_against_independent_brackets_and_fixtures(self):
        run = subprocess.run([str(self.checks)], text=True, capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("54 root brackets", run.stdout)

    def test_fibers_against_exhaustive_original_radical_all_quadrants(self):
        pairs=[(a,q) for a in range(1,14,2) for q in range(3,24,2)
               if a<q and gcd(a,q)==1]
        pairs.append((545,729))  # Nonempty negative-n fiber: (-5,81).
        # This oracle uses only the ORIGINAL square-radical equation.  It has
        # no cubic polynomial, root isolation or continued-fraction machinery.
        expected_by_pair={p:set() for p in pairs}
        for n in range(-80,81):
            if n==0:
                continue
            for x in range(-120,121):
                if x==0:
                    continue
                m2=x*x*(x+6*n)**2+(36*n**3-65)*x
                if m2<0:
                    continue
                m=isqrt(m2)
                if m*m!=m2:
                    continue
                y=Fraction(m,abs(x))
                beta=y/abs(x)-1+Fraction(6*n,x)
                tau=1 if n*x>0 else -1
                if tau*beta<=0:
                    continue
                slope=tau*beta
                pair=(slope.numerator,slope.denominator)
                if pair in expected_by_pair:
                    expected_by_pair[pair].add((n,x))
        self.assertIn((-5,81),expected_by_pair[(545,729)])
        for congruences in [False,True]:
            with self.subTest(congruences=congruences):
                rows=self.invoke(pairs,"--n-min","1","--n-max","80",
                                 "--x-min","1","--x-max","120",
                                 *([] if congruences else ["--relax-congruences"]))
                for (a,q),row in zip(pairs,rows):
                    expected={p for p in expected_by_pair[(a,q)] if not congruences
                              or (p[0]%3==1 and p[1]%12==5 and p[1]%7!=0)}
                    self.assertEqual(row["status"],"complete",row)
                    actual={(int(h["n"]),int(h["x"])) for h in row["hits"]}
                    self.assertEqual(actual,expected,(a,q,congruences))
                    for hit in row["hits"]:
                        verify_record(hit,Bounds(1,80,1,120,magnitudes=True),
                                      require_congruences=congruences)

    def test_nonempty_signed_fibers_and_every_sign_selector(self):
        # Independently fixed historical solutions, not production campaign
        # hits. Even q is admitted only with --relax-congruences.
        fixtures=[(-5,81,Fraction(-913,1458),(545,729)),
                  (166,-2500,Fraction(-1103,250000),(100703,125000)),
                  (2047,-45972,Fraction(-599,551664),(147983,275832)),
                  (-5877899,11122866225,
                   Fraction(-2338707218296801,2346146172839250),
                   (7438954542449,1173073086419625))]
        for n,x,d,pair in fixtures:
            quadrant=("p" if n>0 else "n")+("p" if x>0 else "n")
            for signs in ("all","pp","pn","np","nn"):
                with self.subTest(n=n,x=x,signs=signs):
                    row=self.invoke([pair],"--n-min",str(abs(n)),"--n-max",str(abs(n)),
                                    "--x-min",str(abs(x)),"--x-max",str(abs(x)),
                                    "--signs",signs,"--relax-congruences")[0]
                    self.assertEqual(row["status"],"complete",row)
                    actual={(int(h["n"]),int(h["x"])) for h in row["hits"]}
                    expected={(n,x)} if signs in ("all",quadrant) else set()
                    self.assertEqual(actual,expected,row)
                    for hit in row["hits"]:
                        verify_record(hit,Bounds(abs(n),abs(n),abs(x),abs(x),
                                      magnitudes=True,signs=signs),require_congruences=False)
                        self.assertEqual(Fraction(int(hit["d_num"]),int(hit["d_den"])),d)

    def test_production_precision_refines_without_changing_results(self):
        pairs=[(1,10**10+1),(3,10**11+3),(7,10**11+1)]
        pairs=[p for p in pairs if gcd(*p)==1]
        low=self.invoke(pairs,"--precision-bits","64","--relax-congruences")
        high=self.invoke(pairs,"--precision-bits","1024","--relax-congruences")
        for l,h in zip(low,high):
            self.assertEqual(l["status"],"complete",l)
            self.assertEqual(h["status"],"complete",h)
            self.assertEqual(l["hits"],h["hits"])
            self.assertGreater(int(l["precision_bits"]),64)

    def test_precision_cap_is_reported_as_error_not_empty_complete(self):
        row=self.invoke([(1,10000000001)],"--precision-bits","64",
                        "--max-precision-bits","64","--relax-congruences")[0]
        self.assertEqual(row["status"],"error",row)

    def test_invalid_fibers_do_not_poison_following_valid_query(self):
        rows=self.invoke([(0,1),(2,3),(3,3),(1,5)])
        self.assertEqual([r["status"] for r in rows],["error","error","error","complete"])


if __name__=="__main__":
    unittest.main()
