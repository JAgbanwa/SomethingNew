#!/bin/bash
# usage: launch_sv.sh <tag> <lo> <hi> <sign> [nworkers]
cd "$(dirname "$0")"
tag=$1; lo=$2; hi=$3; sgn=$4; nw=${5:-1}
step=$(( (hi-lo)/nw ))
for ((i=0;i<nw;i++)); do
  a=$((lo+i*step)); b=$((lo+(i+1)*step-1)); [ $i -eq $((nw-1)) ] && b=$hi
  setsid nohup ./search_sv4 $a $b $sgn > sv_${tag}_$i.txt 2> sverr_${tag}_$i.txt &
done
