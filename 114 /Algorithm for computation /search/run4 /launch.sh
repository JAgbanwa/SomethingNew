#!/bin/bash
# Sweep n upward in chunks, 8 workers (4 positive n, 4 negative n).
# Usage: ./launch.sh <lo> <hi> <tag>      (n range in absolute value)
# Each worker gets an interleaved set of chunks so that the covered range
# grows uniformly and stopping early still leaves a nearly contiguous prefix.
set -u
LO=$1; HI=$2; TAG=$3
K=${K:-10000}
BUDGET=${BUDGET:-5000}
CHUNK=${CHUNK:-2000000}
DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="$DIR/../search_xl"
ROOTS="$DIR/../roots3e7.bin"

worker() {   # $1 = worker index 0..3, $2 = sign
  local w=$1 sgn=$2
  local name="${TAG}_$([ "$sgn" = 1 ] && echo p || echo m)$w"
  local out="$DIR/out_${name}.txt" err="$DIR/err_${name}.txt" prog="$DIR/prog_${name}.txt"
  : > "$out"; : > "$err"; : > "$prog"
  local c=$((LO + w*CHUNK))
  while [ "$c" -le "$HI" ]; do
    local hi=$((c + CHUNK - 1)); [ "$hi" -gt "$HI" ] && hi=$HI
    "$BIN" "$c" "$hi" "$sgn" "$K" "$ROOTS" "$BUDGET" >> "$out" 2>> "$err"
    echo "$c $hi $(date +%s)" >> "$prog"
    c=$((c + 4*CHUNK))
  done
  echo "WORKER $name DONE" >> "$prog"
}

for w in 0 1 2 3; do
  worker $w 1  &
  worker $w -1 &
done
wait
