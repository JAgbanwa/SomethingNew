#!/usr/bin/env python3
"""Compare `bin/dthue_worker --raw` with PARI's thue() on the same equations.

    gp -q tools/pari_crosscheck.gp < /dev/null > pari.txt
    python3 tools/pari_compare.py pari.txt [--worker bin/dthue_worker]
"""
import argparse
import collections
import json
from pathlib import Path
import subprocess
import sys

ap = argparse.ArgumentParser()
ap.add_argument("pari_output", type=Path)
ap.add_argument("--worker", default=str(Path(__file__).resolve().parents[1] / "bin" / "dthue_worker"))
a = ap.parse_args()
pari, order = collections.defaultdict(set), []
for line in a.pari_output.read_text().splitlines():
    t = line.split()
    if len(t) < 4 or not t[0].lstrip("-").isdigit():
        continue
    T, p, q = map(int, t[:3])
    if t[3] == "END":
        order.append((T, p, q))
    elif int(t[4]) != 0:
        pari[(T, p, q)].add((int(t[3]), int(t[4])))
mismatches = solutions = beyond = 0
by_target = collections.defaultdict(list)
for T, p, q in order:
    by_target[T].append((p, q))
for T, pairs in by_target.items():
    out = subprocess.run([a.worker, "--raw", "--target", str(T), "--g-max", str(10**100)], check=True,
                         input="".join(f"{p} {q}\n" for p, q in pairs), text=True, capture_output=True).stdout
    for (p, q), line in zip(pairs, out.splitlines()):
        row = json.loads(line)
        got = {(int(n), int(g)) for n, g, _ in row["solutions"]}
        solutions += len(got)
        beyond += sum(abs(g) > int(row["g0"]) for _, g in got)
        if got != pari[(T, p, q)]:
            mismatches += 1
            print("MISMATCH", T, p, q, sorted(got), sorted(pari[(T, p, q)]))
print(f"{len(order)} equations compared; {mismatches} mismatches; {solutions} solutions, {beyond} beyond g0")
sys.exit(1 if mismatches else 0)
