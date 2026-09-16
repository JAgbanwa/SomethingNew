#!/bin/bash
cd "$(dirname "$0")"
EFF=${EFF:-3}
for i in 0 1 2 3; do
  lo=$((i*5000+1)); hi=$(((i+1)*5000))
  setsid nohup python3 ec_scan.py $lo $hi 1 $EFF > ecp_$i.txt 2> ecerr_p$i.txt &
  setsid nohup python3 ec_scan.py $lo $hi -1 $EFF > ecm_$i.txt 2> ecerr_m$i.txt &
done
