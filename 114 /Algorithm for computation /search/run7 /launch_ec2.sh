#!/bin/bash
# Continue the elliptic-curve (Mordell) scan over x, in the ranges the earlier run left open.
cd "$(dirname "$0")"
EFF=${EFF:-3}
run() { setsid nohup python3 ../ec_scan.py $1 $2 $3 $EFF > ec_$4.txt 2> ecerr_$4.txt & }
run 12001 15000  1 a_p
run 12001 15000 -1 a_m
run 16551 20000  1 b_p
run 16551 20000 -1 b_m
# continuation beyond |x| = 20000
# run 20001 24000  1 c_p ; run 20001 24000 -1 c_m
