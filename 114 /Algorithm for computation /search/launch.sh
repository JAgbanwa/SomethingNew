#!/bin/bash
cd /workspace/request-project/search
bnds=(1 176777 250000 306186 353553 395285 433013 467707 500001)
for i in 0 1 2 3 4 5 6 7; do
  lo=${bnds[$i]}; hi=$((${bnds[$((i+1))]}-1))
  setsid ./search_ey $lo $hi 1 > ey_p$i.txt 2> eyerr_p$i.txt < /dev/null &
  setsid ./search_ey $lo $hi -1 > ey_m$i.txt 2> eyerr_m$i.txt < /dev/null &
done
