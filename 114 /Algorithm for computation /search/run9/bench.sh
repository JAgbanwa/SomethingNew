#!/bin/sh
# bench.sh --- the throughput measurements quoted in grid/README.md and HALF_INTEGER.md.
# Run from this directory after `make` in grid/.  One core, a few minutes in total.
G="../../grid "
t() {  # t <label> <command...>: print the DONE line and the wall time
  label="$1"; shift
  s=$(date +%s.%N); r=$("$@" | tail -1); e=$(date +%s.%N)
  printf '%-44s %6.1f s   %s\n' "$label" "$(echo "$e - $s" | bc)" "$r"
}
t "dsweep int family |U| in [1e9,1e9+2e6)"      "$G/dsweep" --ulo 1000000000 --uhi 1002000000
t "dsweep int integral"                          "$G/dsweep" --ulo 1000000000 --uhi 1002000000 --integral
t "dsweep half integral"                         "$G/dsweep" --ulo 1000000000 --uhi 1002000000 --half
t "dsweep half rational |V| in [1e8,1e8+2e5)"   "$G/dsweep" --ulo 100000000 --uhi 100200000 --half --rational-sqrt
t "dsmooth int B=60 [1e20,1e21) shard 0/20000"  "$G/dsmooth" --lo 1e20 --hi 1e21 --B 60 --shard 0 --shards 20000
t "xscan int x=7, 1e9 values of m"              "$G/xscan" --u0 0 --u1 1 --m0 1000000000 --m1 2000000000
t "xscan half X=5, 1e9 values of m"             "$G/xscan" --half --u0 0 --u1 1 --m0 1000000000 --m1 2000000000
N0=2000000000000000000
for ch in half int; do
  f=""; [ $ch = half ] && f="--half"
  t "xroots $ch |X|<1e3 n in [2e18,+1e10)"       "$G/xroots" $f --X0 1 --X1 1000 --n0 $N0 --n1 2000000010000000000
  t "xroots $ch |X| in [1e3,1e5) n window 1e10"  "$G/xroots" $f --X0 1000 --X1 100000 --n0 $N0 --n1 2000000010000000000
  t "xroots $ch |X| in [1e5,1e6) n window 1e10"  "$G/xroots" $f --X0 100000 --X1 1000000 --n0 $N0 --n1 2000000010000000000
done
