"""Black-box worker differentials and arithmetic checks of the actual C++ code."""
import json
from math import gcd
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


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
        self.assertIn("48 root brackets", run.stdout)

    def test_fibers_against_exhaustive_integer_polynomial(self):
        pairs=[(a,q) for a in range(1,14,2) for q in range(1,24,2) if gcd(a,q)==1]
        # Enumerate independently, then require exact equality to the worker.
        # This small positive box contains no known fixture: nonempty-hit
        # acceptance is separately tested against signed historical fixtures.
        for congruences in [False,True]:
            with self.subTest(congruences=congruences):
                rows=self.invoke(pairs,"--n-min","1","--n-max","80",
                                 "--x-min","1","--x-max","120",
                                 *([] if congruences else ["--relax-congruences"]))
                for (a,q),row in zip(pairs,rows):
                    expected=set()
                    for n in range(1,81):
                        for x in range(1,121):
                            if congruences and not(n%3==1 and x%12==5 and x%7):
                                continue
                            lhs=36*q*q*n**3+12*q*(2*q+a)*n*x*x-a*(2*q+a)*x**3
                            if lhs==65*q*q and (q+a)*x>=6*n*q:
                                expected.add((n,x))
                    self.assertEqual(row["status"],"complete",row)
                    actual={(int(h["n"]),int(h["x"])) for h in row["hits"]}
                    self.assertEqual(actual,expected,(a,q,congruences))

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
