#!/bin/sh
# Cross-validation: every engine must (re)discover the same small solutions.
# Usage: sh selftest.sh
set -e
CC=${CC:-clang}
cd "$(dirname "$0")"
$CC -O3 -o scan_box scan_box.c -lm
$CC -O3 -o scan_curve scan_curve.c -lm
$CC -O3 -o engine_m engine_m.c -lm
$CC -O3 -o engine_sqfree engine_sqfree.c -lm

echo "== B (box scan, |n|<=3000, |x|<=200000)"
./scan_box -3000 3000 200000 | sort -u

echo "== A (curve scan, x=81 and x=-2500, |n|<=5000)"
./scan_curve 81 81 -5000 5000
./scan_curve -2500 -2500 -5000 5000

echo "== C (divisor/m engine, |m|<=100000)"
./engine_m 100000 | sort -u

echo "== E (squarefree sieve, |x|<=50000, |n|<=3000)"
./engine_sqfree 50000 3000 | sort -u

echo "== F (complete engine, |n|<=3000 -- all x)"
python3 engine_full.py -3000 3000 4

echo "== all engines agree on: (n,x) = (-5,81), (166,-2500), (2047,-45972)"
