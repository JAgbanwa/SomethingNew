#!/usr/bin/env python3
"""Plan a gap-search campaign: calibrate, choose ratio_max, size it to a budget, write tasks.

Region (README.md): d = |x+y| in [d_start, d_stop) with d_start just above
Booker-Sutherland's d_max = 10^19/54 (their 2020 run covered k = 114 with that cut), and
floor(3.847 d) <= |z| <= ratio_max * d.

  # 1. measure this host (about a minute), print the cost model and the best ratio_max
  python3 gap_campaign.py --calibrate
  # 2. preview a 1800 core-hour plan with the measured cost
  python3 gap_campaign.py --campaign-id ce114-gap --core-hours 1800 --us-per-d 0.293 --ratio-max 64 \
      --output-dir gap-tasks --plan-only
  # 3. write it (drop --plan-only)

Nothing here submits jobs. Expected-yield figures use the Booker-Sutherland heuristic
(rho_sol from their Table 1) and are estimates, not promises.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import time

from gap_common import (D_LIMIT, DEFAULT_D_START, METHOD, PAGE_SCHEMA, RHO, TASK_SCHEMA, atomic_json, check_k,
                        coverage_fraction, expected_solutions)

ROOT = Path(__file__).resolve().parent
WORKER = ROOT / "bin" / "gap_worker"


def measure(k: int, d_start: int, count: int, ratio: int) -> float:
    """Seconds per d for one worker run, excluding sieve set-up."""
    t0 = time.monotonic()
    out = subprocess.run([str(WORKER), "--k", str(k), "--d-start", str(d_start), "--d-stop", str(d_start + count),
                          "--ratio-max", str(ratio), "--chunk", str(count)], check=True, capture_output=True, text=True).stdout
    wall = time.monotonic() - t0
    recs = [json.loads(line) for line in out.splitlines()]
    secs = sum(r["seconds"] for r in recs if r["type"] == "chunk")
    setup = next(r["setup_seconds"] for r in recs if r["type"] == "start")
    return secs / count, setup, wall


def calibrate(k: int, d_start: int, count: int) -> int:
    ratios = (16, 24, 32, 40, 48, 64, 80)
    rows = []
    for r in ratios:
        if (r + 18) * (d_start + count) >= 2 ** 64:
            continue
        per_d, setup, _ = measure(k, d_start, count, r)
        rows.append((r, per_d, setup))
        print(f"ratio_max={r:3d}  {per_d * 1e6:7.3f} us per d   coverage={coverage_fraction(r):.3f}   "
              f"yield per core-second ~ {coverage_fraction(r) / per_d:.3e} (relative)")
    best = max(rows, key=lambda row: coverage_fraction(row[0]) / row[1])
    print(f"\nsieve set-up per task: {rows[0][2]:.1f} s")
    print(f"best ratio_max on this host: {best[0]}  ({best[1] * 1e6:.3f} us per d)")
    print(f"use:  --ratio-max {best[0]} --us-per-d {best[1] * 1e6:.3f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=114)
    ap.add_argument("--calibrate", action="store_true", help="measure cost per d at several ratio_max and exit")
    ap.add_argument("--calibration-count", type=int, default=4_000_000)
    ap.add_argument("--campaign-id")
    ap.add_argument("--output-dir", type=Path)
    ap.add_argument("--d-start", type=int, default=DEFAULT_D_START)
    ap.add_argument("--d-stop", type=int, help="exclusive end of d (else derived from --core-hours)")
    ap.add_argument("--core-hours", type=float, help="search core-hours to plan (default 1800 unless --d-stop is given)")
    ap.add_argument("--us-per-d", type=float, default=0.30, help="measured microseconds per d (use --calibrate)")
    ap.add_argument("--ratio-max", type=int, default=64, help="|z| <= ratio_max * d (calibrate on the target CPU; 64 on the development host)")
    ap.add_argument("--task-hours", type=float, default=1.0, help="estimated core-hours per task")
    ap.add_argument("--task-d-count", type=int, help="d values per task (overrides --task-hours)")
    ap.add_argument("--deadline-seconds", type=int, default=0, help="per-attempt deadline written into tasks")
    ap.add_argument("--rho", type=float, help="Heath-Brown density for k (default: Booker-Sutherland Table 1)")
    ap.add_argument("--plan-only", action="store_true")
    a = ap.parse_args()
    check_k(a.k)
    if a.calibrate:
        if not WORKER.exists():
            ap.error("build first: make")
        return calibrate(a.k, a.d_start, a.calibration_count)
    if not a.campaign_id or not a.output_dir:
        ap.error("--campaign-id and --output-dir are required")
    if a.d_stop is not None and a.core_hours is not None:
        ap.error("give at most one of --d-stop or --core-hours")
    if a.d_stop is None and a.core_hours is None:
        a.core_hours = 1800.0
    d_stop = a.d_stop if a.d_stop is not None else a.d_start + int(a.core_hours * 3600e6 / a.us_per_d)
    if not 1 <= a.d_start < d_stop <= D_LIMIT:
        ap.error("need 1 <= d_start < d_stop <= 2^63/27")
    if a.ratio_max < 4 or a.ratio_max * d_stop + 18 * d_stop >= 2 ** 64:
        ap.error("ratio_max * d must stay below 2^64")
    per_task = a.task_d_count or max(1, int(a.task_hours * 3600e6 / a.us_per_d))
    n = d_stop - a.d_start
    if not a.task_d_count:                 # spread evenly: no near-empty final task
        per_task = -(-n // max(1, round(n / per_task)))
    est_hours = n * a.us_per_d / 3600e6
    rho = a.rho if a.rho is not None else RHO.get(a.k)
    e = expected_solutions(rho, a.d_start, d_stop, a.ratio_max) if rho else None
    ntasks = -(-n // per_task)
    print(f"k={a.k}  d in [{a.d_start}, {d_stop})  ({n:.3e} values)  |z| in [3.847 d, {a.ratio_max} d]")
    print(f"tasks={ntasks}  estimated core-hours={est_hours:.1f} at {a.us_per_d} us/d")
    if e is not None:
        print(f"heuristic expected solutions in region: {e:.2e}  (rho={rho}; about 1 in {1 / e:,.0f})")
    if a.plan_only:
        return 0
    tdir = a.output_dir / "tasks"
    tdir.mkdir(parents=True, exist_ok=True)
    width = len(str(ntasks))
    tasks = []
    for i in range(ntasks):
        lo = a.d_start + i * per_task
        hi = min(d_stop, lo + per_task)
        tid = f"{a.campaign_id}-{i:0{width}d}"
        task = {"schema": TASK_SCHEMA, "method": METHOD, "campaign_id": a.campaign_id, "task_id": tid, "k": a.k,
                "d_start": str(lo), "d_stop": str(hi), "ratio_max": a.ratio_max, "deadline_seconds": a.deadline_seconds}
        atomic_json(tdir / f"{tid}.json", task)
        tasks.append({"task_id": tid, "file": f"tasks/{tid}.json", "d_start": str(lo), "d_stop": str(hi),
                      "estimated_core_hours": round((hi - lo) * a.us_per_d / 3600e6, 4)})
    atomic_json(a.output_dir / "page.json", {
        "schema": PAGE_SCHEMA, "method": METHOD, "campaign_id": a.campaign_id, "k": a.k,
        "d_start": str(a.d_start), "d_stop": str(d_stop), "ratio_max": a.ratio_max, "us_per_d": a.us_per_d,
        "estimated_core_hours": round(est_hours, 2), "rho": rho,
        "heuristic_expected_solutions": e, "created": dt.datetime.now(dt.timezone.utc).isoformat(), "tasks": tasks})
    print(f"wrote {ntasks} tasks under {tdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
