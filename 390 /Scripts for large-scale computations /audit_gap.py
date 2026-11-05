#!/usr/bin/env python3
"""Re-run a random sample of returned chunks on trusted hardware and compare counters.

Every chunk record a worker returns (chunks.jsonl) lists exact, deterministic
counters for its d range: d values killed, roots, candidates, filter passes,
exact checks. A volunteer host with faulty RAM or CPU that silently skipped
work would produce different counters. Booker and Sutherland report detected
hardware errors in their own grid runs, so audit a few percent before
claiming coverage.

  python3 audit_gap.py --page gap-tasks/page.json --results gap-results --fraction 0.02

Exit status 1 if any sampled chunk disagrees (re-issue that task).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import subprocess
import sys

from gap_common import COUNTERS, load_json

ROOT = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", type=Path, required=True)
    ap.add_argument("--results", type=Path, nargs="+", required=True)
    ap.add_argument("--fraction", type=float, default=0.02, help="share of chunks to re-run (default 2%%)")
    ap.add_argument("--min-chunks", type=int, default=5)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--worker", type=Path, default=ROOT / "bin" / "gap_worker")
    a = ap.parse_args()
    page = load_json(a.page)
    k, ratio = int(page["k"]), int(page["ratio_max"])
    chunks = []
    for root in a.results:
        for tj in root.rglob("task.json"):
            task = load_json(tj)
            if task.get("campaign_id") != page["campaign_id"] or not (tj.parent / "chunks.jsonl").exists():
                continue
            for line in (tj.parent / "chunks.jsonl").read_text().splitlines():
                if line.strip():
                    chunks.append((str(tj.parent), json.loads(line)))
    if not chunks:
        print("no chunk records found")
        return 1
    rng = random.Random(a.seed)
    n = min(len(chunks), max(a.min_chunks, round(a.fraction * len(chunks))))
    bad = 0
    for where, rec in rng.sample(chunks, n):
        lo, hi = int(rec["d_start"]), int(rec["d_stop"])
        out = subprocess.run([str(a.worker), "--k", str(k), "--d-start", str(lo), "--d-stop", str(hi),
                              "--ratio-max", str(ratio), "--chunk", str(hi - lo)],
                             check=True, capture_output=True, text=True).stdout
        mine = [json.loads(line) for line in out.splitlines() if '"chunk"' in line]
        got = {c: sum(int(m["counters"][c]) for m in mine) for c in COUNTERS}
        want = {c: int(rec["counters"][c]) for c in COUNTERS}
        ok = got == want
        bad += not ok
        print(f"{'OK  ' if ok else 'BAD '} [{lo}, {hi})  {where}" + ("" if ok else f"\n     returned {want}\n     audited  {got}"))
    print(f"{n - bad}/{n} sampled chunks agree")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
