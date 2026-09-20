#!/bin/sh
# Driver: build every engine and run the full search pipeline.
# Usage:  sh run_all.sh [NCORES]
set -e
CORES=${1:-8}
CC=${CC:-clang}
cd "$(dirname "$0")"

$CC -O3 -march=native -o scan_box      scan_box.c      -lm
$CC -O3 -march=native -o scan_curve    scan_curve.c    -lm
$CC -O3 -march=native -o engine_m      engine_m.c      -lm
$CC -O3 -march=native -o engine_sqfree engine_sqfree.c -lm
echo "built."

mkdir -p hits

# --- ENGINE F: complete in x (no bound), for every |n| <= 200000 -------------
python3 engine_full.py 1 200000 "$CORES"  > hits/F_pos.txt &
python3 engine_full.py -200000 -1 "$CORES" > hits/F_neg.txt &
wait

# --- ENGINE E: |x| <= 10^6, |n| <= 10^8 --------------------------------------
i=0
while [ "$i" -lt "$CORES" ]; do
  ./engine_sqfree 1000000 100000000 "$CORES" "$i" > "hits/E_$i.txt" &
  i=$((i+1))
done
wait

# --- ENGINE C: huge |x| via the divisor method -------------------------------
i=0
while [ "$i" -lt "$CORES" ]; do
  ./engine_m 3000000 "$CORES" "$i" > "hits/M_$i.txt" &
  i=$((i+1))
done
wait

# --- ENGINE B: exhaustive box sweep ------------------------------------------
i=0
while [ "$i" -lt "$CORES" ]; do
  ./scan_box -20000 20000 1000000 "$CORES" "$i" > "hits/B_$i.txt" &
  i=$((i+1))
done
wait

cat hits/*.txt | python3 verify.py | tee hits/REPORT.txt
echo "done -- see hits/REPORT.txt"
