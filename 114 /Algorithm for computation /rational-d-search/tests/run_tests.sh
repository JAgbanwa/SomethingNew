#!/bin/sh
# 1. rd_worker == independent brute force over every n with |n| <= 450, both charts.
# 2. rd_worker re-finds all eleven previously known integer-chart solutions.
# 3. Every hit passes the exact verifier.
set -eu
cd "$(dirname "$0")/.."
T=$(mktemp -d)
./bin/rd_worker --selftest --sieve 100000
./bin/brute -450 450 | sort > "$T/brute.txt"
./bin/rd_worker --n0 -450 --n1 450 --sieve 100000 2>/dev/null | grep '^HIT' | sort > "$T/worker.txt"
diff "$T/brute.txt" "$T/worker.txt"
echo "brute force |n| <= 450: identical ($(wc -l < "$T/worker.txt") hits)"
printf '%s\n' 909 14709 -29317 798 -1160307 12512774 -64722106 101116178 -516368250 > "$T/known.txt"
./bin/rd_worker --list "$T/known.txt" 2>/dev/null | grep '^HIT' > "$T/known_hits.txt"
test "$(wc -l < "$T/known_hits.txt")" -eq 9
python3 verify_rd.py "$T/worker.txt" "$T/known_hits.txt" > "$T/verified.jsonl"
test "$(wc -l < "$T/verified.jsonl")" -eq 14
echo "known solutions re-found and all 14 hits verified exactly"
rm -rf "$T"
