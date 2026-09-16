#!/bin/bash
cd "$(dirname "$0")"
KNOWN='n=1 |n=-54 |n=798 |n=909 |n=14709 |n=-29317 |n=-1160307 |n=12512774 |n=-64722106 |n=101116178 '
for i in $(seq 1 ${2:-110}); do
  if grep -h SOL sv_p*.txt sv_m*.txt sv_h*.txt 2>/dev/null | grep -v -E "$KNOWN" | grep -q SOL; then
     echo HIT; grep -h SOL sv_p*.txt sv_m*.txt sv_h*.txt | grep -v -E "$KNOWN"; exit 0
  fi
  sleep ${1:-5}
done
echo "no new hit"; for f in sverr_p4_0.txt sverr_p3_1.txt sverr_p3_2.txt sverr_m4_0.txt sverr_p2_0.txt; do echo -n "$f "; tail -n1 $f; done
