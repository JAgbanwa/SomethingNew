#!/bin/bash
cd /workspace/request-project/search
NMAX=100000000
CH=$((NMAX/8))
for i in 0 1 2 3 4 5 6 7; do
  lo=$((i*CH+1)); hi=$(((i+1)*CH))
  setsid ./search_div $lo $hi 1 > dv_p$i.txt 2> dverr_p$i.txt < /dev/null &
  setsid ./search_div $lo $hi -1 > dv_m$i.txt 2> dverr_m$i.txt < /dev/null &
done
