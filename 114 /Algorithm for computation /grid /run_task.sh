#!/bin/sh
# run_task.sh --- execute one work unit of the manifest produced by make_jobs.py.
#
#   ./run_task.sh "000123 dsweep --ulo 3000000000 --uhi 4600000000" results/
#
# Writes results/<id>.out (the raw hits) and results/<id>.done (a one line stamp) and
# exits nonzero if the unit did not finish.  This is the single entry point a grid client
# (Charity Engine / BOINC wrapper) has to call; it needs no state beyond its arguments,
# so units may be run in any order, repeated for validation, or re-issued after a
# timeout.  Every hit is re-checked afterwards with verify.py, which is the only step
# that must be trusted.
set -e
line="$1"
outdir="${2:-results}"
mkdir -p "$outdir"

id=$(echo "$line" | awk '{print $1}')
algo=$(echo "$line" | awk '{print $2}')
rest=$(echo "$line" | cut -d' ' -f3-)
here=$(dirname "$0")
out="$outdir/$id.out"

case "$algo" in
  dsweep) "$here/dsweep" $rest --out "$out" ;;
  xscan)  "$here/xscan"  $rest --out "$out" ;;
  dsmooth) "$here/dsmooth" $rest --out "$out" ;;
  xcurve)
      u0=$(echo "$rest" | sed -n 's/.*--u0 \([0-9]*\).*/\1/p')
      u1=$(echo "$rest" | sed -n 's/.*--u1 \([0-9]*\).*/\1/p')
      if command -v gp >/dev/null 2>&1; then
        XCURVE_U0="$u0" XCURVE_U1="$u1" gp -q "$here/xcurve.gp" > "$out"
      else
        python3 "$here/xcurve.py" --u "$u0" "$u1" > "$out"
      fi ;;
  *) echo "unknown algorithm: $algo" >&2; exit 2 ;;
esac

if grep -q '^DONE' "$out"; then
  hits=$(grep -c '^HIT\|^CAND' "$out" || true)
  echo "$id $algo hits=$hits" > "$outdir/$id.done"
  exit 0
fi
echo "$id did not finish" >&2
exit 1
