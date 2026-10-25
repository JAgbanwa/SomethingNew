#!/bin/sh
# selftest.sh --- run every self test of the grid programs (about two minutes on one core).
# Build first (make).  Exits nonzero on the first failure.
set -e
cd "$(dirname "$0")"
V="python3 verify.py"
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

expect() {   # expect <description> <pattern> <file>
  if grep -q "$2" "$3"; then echo "ok   $1"; else echo "FAIL $1"; cat "$3"; exit 1; fi
}

./dsweep --ulo 2 --uhi 20000 --general > "$tmp"; $V "$tmp" > "$tmp.v"
expect "dsweep, integer chart: the three smallest known d" "3 genuine solutions" "$tmp.v"
./dsmooth --lo 2 --hi 20000 --B 20000 --test > "$tmp"; $V "$tmp" > "$tmp.v"
expect "dsmooth, integer chart: same certificates, independent path" "3 genuine solutions" "$tmp.v"
./dsweep --ulo 2 --uhi 250000 --half --rational-sqrt > "$tmp"; $V "$tmp" > "$tmp.v"
expect "dsweep, half chart: d = -142/4913 and -9671/625" "2 genuine solutions" "$tmp.v"
./dsmooth --lo 2 --hi 250000 --B 250000 --half --rational-sqrt > "$tmp"; $V "$tmp" > "$tmp.v"
expect "dsmooth, half chart: same two" "2 genuine solutions" "$tmp.v"
./xscan --selftest > "$tmp"
expect "xscan residue arithmetic, both charts, both signs" "selftest ok" "$tmp"
./xscan --half --xneg --u0 48 --u1 49 --m0 0 --m1 100 > "$tmp"; $V "$tmp" > "$tmp.v"
expect "xscan --half finds (n, X) = (15, -289)" "1 genuine solutions" "$tmp.v"
./xroots --selftest > "$tmp"
expect "xroots cube roots modulo prime powers" "selftest ok" "$tmp"
python3 xcurve.py --selftest > "$tmp"
expect "xcurve Mordell correspondence, both charts" "selftest ok" "$tmp"
python3 validate.py --quick > "$tmp"
expect "integral radicals on equations with known solutions (incl. 42 and 906)" "validation ok" "$tmp"
rm -f "$tmp.v"
echo "all self tests passed"
