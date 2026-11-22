#!/usr/bin/env python3
"""Plan a k = 375 primitive gap-search campaign: calibrate, optimise (d_start, ratio_max) against the
frontier, size it to a budget, write tasks.

The campaign searches d = |x+y| in [d_start, d_stop) and floor(3.847 d) <= |z| <= ratio_max * d with
--primitive. Unlike k = 114, the unsearched region for primitive 375 is bounded by a *frontier* in
max(|x|, |y|, |z|) (README.md, section 3), so the best plan starts at small d with a large ratio_max.

  # 1. measure this host at the d where the campaign will run (a few minutes)
  python3 gap_campaign.py --calibrate --calibration-d 1e10 --save-calibration calib.json
  # 2. choose d_start and ratio_max for the budget and frontier
  python3 gap_campaign.py --optimize calib.json --core-hours 1800 --frontier 1e14
  # 3. write the tasks
  python3 gap_campaign.py --campaign-id ce375-gap --core-hours 1800 --d-start <D0> --ratio-max <R> \\
      --us-per-d <measured> --frontier 1e14 --output-dir ce375-gap-tasks
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from math import exp, log
from pathlib import Path
import subprocess
import sys

from gap_common import (D_LIMIT, DEFAULT_D_START, DEFAULT_FRONTIER, METHOD, PAGE_SCHEMA, RHO, TASK_SCHEMA,
                        atomic_json, check_k, cube_primes, expected_solutions, ratio_ok)

ROOT = Path(__file__).resolve().parent
WORKER = ROOT / "bin" / "gap_worker"
CAL_RATIOS = (1024, 2048, 4096, 8192, 16384, 32768, 65536)


def measure(k: int, d_start: int, count: int, ratio: int, primitive: bool) -> tuple[float, float]:
    """Seconds per d for one worker run (sieve set-up excluded), and the set-up seconds."""
    cmd = [str(WORKER), "--k", str(k), "--d-start", str(d_start), "--d-stop", str(d_start + count),
           "--ratio-max", str(ratio), "--chunk", str(count)] + (["--primitive"] if primitive else [])
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    recs = [json.loads(line) for line in out.splitlines()]
    secs = sum(r["seconds"] for r in recs if r["type"] == "chunk")
    setup = next(r["setup_seconds"] for r in recs if r["type"] == "start")
    return secs / count, setup


def calibrate(a) -> int:
    d0 = int(float(a.calibration_d))
    rows = []
    for r in CAL_RATIOS:
        if not ratio_ok(r, d0 + a.calibration_count):
            continue
        per_d, setup = measure(a.k, d0, a.calibration_count, r, a.primitive)
        rows.append({"ratio_max": r, "us_per_d": per_d * 1e6})
        print(f"ratio_max={r:6d}  {per_d * 1e6:8.4f} us per d   (set-up {setup:.1f} s)")
    if a.save_calibration:
        atomic_json(a.save_calibration, {"k": a.k, "primitive": a.primitive, "calibration_d": d0,
                                         "count": a.calibration_count, "rows": rows})
        print(f"saved {a.save_calibration}")
    return 0


def plan_value(d_start: int, ratio: int, us_per_d: float, hours: float, frontier: float) -> tuple[float, int]:
    d_stop = d_start + int(hours * 3600e6 / us_per_d)
    return expected_solutions(1.0, d_start, d_stop, ratio, frontier), d_stop


def optimize(a) -> int:
    cal = json.loads(Path(a.optimize).read_text())
    best = None
    starts = sorted({int(round(exp(log(10) * e / 4))) for e in range(0, 4 * 17 + 1)})
    for row in cal["rows"]:
        r, us = int(row["ratio_max"]), float(row["us_per_d"])
        for d0 in starts:
            v, d1 = plan_value(d0, r, us, a.core_hours, a.frontier)
            if d1 > D_LIMIT or not ratio_ok(r, d1):
                continue
            if best is None or v > best[0]:
                best = (v, r, us, d0, d1)
    if best is None:
        print("no admissible plan")
        return 1
    v, r, us, d0, d1 = best
    print(f"frontier {a.frontier:.3g}, {a.core_hours:g} core-hours, calibrated at d = {cal['calibration_d']:.3g}")
    print(f"best: --d-start {d0} --ratio-max {r} --us-per-d {us:.4f}   (d up to {d1:.4e})")
    rho = a.rho if a.rho is not None else RHO.get(a.k)
    print(f"heuristic E/rho = {v:.4g}" + (f",  E = {rho * v:.3g} (rho = {rho}),  P(>= 1 solution) = {1 - exp(-rho * v):.1%}"
                                         if rho else "  (rho not set)"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=375)
    ap.add_argument("--no-primitive", dest="primitive", action="store_false", help="search all solutions (default: primitive only)")
    ap.add_argument("--calibrate", action="store_true", help="measure cost per d at several ratio_max and exit")
    ap.add_argument("--calibration-d", default="1e10", help="d at which to calibrate (default 1e10)")
    ap.add_argument("--calibration-count", type=int, default=2_000_000)
    ap.add_argument("--save-calibration", type=Path)
    ap.add_argument("--optimize", type=Path, metavar="CALIBRATION_JSON",
                    help="choose d_start and ratio_max maximising the heuristic yield, then exit")
    ap.add_argument("--frontier", type=float, default=float(DEFAULT_FRONTIER),
                    help="max coordinate below which primitive solutions are already excluded (default 1e14)")
    ap.add_argument("--campaign-id")
    ap.add_argument("--output-dir", type=Path)
    ap.add_argument("--d-start", type=int, default=DEFAULT_D_START)
    ap.add_argument("--d-stop", type=int, help="exclusive end of d (else derived from --core-hours)")
    ap.add_argument("--core-hours", type=float, help="search core-hours (default 1800 unless --d-stop is given)")
    ap.add_argument("--us-per-d", type=float, default=0.3, help="measured microseconds per d (use --calibrate; default 0.3)")
    ap.add_argument("--ratio-max", type=int, default=4096, help="|z| <= ratio_max * d")
    ap.add_argument("--task-hours", type=float, default=1.0, help="estimated core-hours per task")
    ap.add_argument("--task-d-count", type=int, help="d values per task (overrides --task-hours)")
    ap.add_argument("--deadline-seconds", type=int, default=0, help="per-attempt deadline written into tasks")
    ap.add_argument("--rho", type=float, help="Heath-Brown density for primitive solutions of k, if known")
    ap.add_argument("--plan-only", action="store_true")
    a = ap.parse_args()
    check_k(a.k)
    if a.primitive and any(p % 3 != 2 for p in cube_primes(a.k)):
        ap.error("primitive mode needs every p with p^3 | k to be == 2 (mod 3)")
    if a.calibrate:
        if not WORKER.exists():
            ap.error("build first: make")
        return calibrate(a)
    if a.core_hours is None and a.d_stop is None:
        a.core_hours = 1800.0
    if a.optimize:
        return optimize(a)
    if not a.campaign_id or not a.output_dir:
        ap.error("--campaign-id and --output-dir are required")
    if a.d_stop is not None and a.core_hours is not None:
        ap.error("give at most one of --d-stop or --core-hours")
    d_stop = a.d_stop if a.d_stop is not None else a.d_start + int(a.core_hours * 3600e6 / a.us_per_d)
    if not 1 <= a.d_start < d_stop <= D_LIMIT:
        ap.error("need 1 <= d_start < d_stop <= 2^63/27")
    if not ratio_ok(a.ratio_max, d_stop):
        ap.error("ratio_max out of range: need 4 <= ratio_max <= 2^40 and (ratio_max + 18) * d < 2^126")
    per_task = a.task_d_count or max(1, int(a.task_hours * 3600e6 / a.us_per_d))
    n = d_stop - a.d_start
    if not a.task_d_count:                 # spread evenly: no near-empty final task
        per_task = -(-n // max(1, round(n / per_task)))
    est_hours = n * a.us_per_d / 3600e6
    rho = a.rho if a.rho is not None else RHO.get(a.k)
    e_over_rho = expected_solutions(1.0, a.d_start, d_stop, a.ratio_max, a.frontier)
    ntasks = -(-n // per_task)
    print(f"k={a.k} primitive={a.primitive}  d in [{a.d_start}, {d_stop})  ({n:.3e} values)  "
          f"|z| in [3.847 d, {a.ratio_max} d]  frontier {a.frontier:.3g}")
    print(f"tasks={ntasks}  estimated core-hours={est_hours:.1f} at {a.us_per_d} us/d")
    print(f"heuristic E/rho in region: {e_over_rho:.4g}"
          + (f"  ->  E = {rho * e_over_rho:.3g} (rho={rho}), P(>= 1) = {1 - exp(-rho * e_over_rho):.2%}" if rho else "  (rho not set)"))
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
                "d_start": str(lo), "d_stop": str(hi), "ratio_max": a.ratio_max, "primitive": a.primitive,
                "deadline_seconds": a.deadline_seconds}
        atomic_json(tdir / f"{tid}.json", task)
        tasks.append({"task_id": tid, "file": f"tasks/{tid}.json", "d_start": str(lo), "d_stop": str(hi),
                      "estimated_core_hours": round((hi - lo) * a.us_per_d / 3600e6, 4)})
    atomic_json(a.output_dir / "page.json", {
        "schema": PAGE_SCHEMA, "method": METHOD, "campaign_id": a.campaign_id, "k": a.k, "primitive": a.primitive,
        "d_start": str(a.d_start), "d_stop": str(d_stop), "ratio_max": a.ratio_max, "us_per_d": a.us_per_d,
        "frontier": a.frontier, "estimated_core_hours": round(est_hours, 2), "rho": rho,
        "heuristic_expected_over_rho": e_over_rho,
        "heuristic_expected_solutions": rho * e_over_rho if rho else None,
        "created": dt.datetime.now(dt.timezone.utc).isoformat(), "tasks": tasks})
    print(f"wrote {ntasks} tasks under {tdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
