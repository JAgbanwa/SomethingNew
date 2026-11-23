#!/usr/bin/env python3
"""Plan a primitive-375 search page with explicit height and resource bounds.

Region (README.md): d = |x+y| in [d_start, d_stop), with
floor(3.847 d) <= |z| <= ratio_max*d and maximum coordinate height strictly
above height_min. The default target is primitive k=375 above height 10^16.

Use benchmark375.py and band_campaign.py for a calibrated multi-band campaign.
This script writes one constant-ratio page and its restartable tasks. Nothing
here submits jobs. Runtime and expected-yield figures are models.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import time
import math
import statistics

from gap_common import (D_LIMIT, DEFAULT_D_START, METHOD, PAGE_SCHEMA, PRIMITIVE_RHO, RHO, TASK_SCHEMA,
                        atomic_json, check_k, new_fraction, expected_solutions, ratio_ok, worker_options)

ROOT = Path(__file__).resolve().parent
WORKER = ROOT / "bin" / "gap_worker"


def measure(k: int, d_start: int, count: int, ratio: int, primitive_only: bool = False,
            height_min: int = 0) -> tuple[float, float, float]:
    """Seconds per d for one worker run, excluding sieve set-up."""
    t0 = time.monotonic()
    out = subprocess.run([str(WORKER), "--k", str(k), "--d-start", str(d_start), "--d-stop", str(d_start + count),
                          "--ratio-max", str(ratio), "--chunk", str(count),
                          *worker_options({"primitive_only": primitive_only, "height_min": height_min})],
                         check=True, capture_output=True, text=True).stdout
    wall = time.monotonic() - t0
    recs = [json.loads(line) for line in out.splitlines()]
    secs = sum(r["seconds"] for r in recs if r["type"] == "chunk")
    setup = next(r["setup_seconds"] for r in recs if r["type"] == "start")
    return secs / count, setup, wall


def calibrate(k: int, d_start: int, count: int, primitive_only: bool, height_min: int,
              repeats: int = 3, ratio_list: str | None = None) -> int:
    if ratio_list:
        ratios = sorted({int(x) for x in ratio_list.split(",")})
    else:
        h = height_min / d_start
        lower = max(4.0, (max(0.0, 3*h*h - 3*h + 1)) ** (1/3)) if h > 1 else 4.0
        ratios = sorted({max(4, math.ceil(lower * m)) for m in (2, 4, 8, 16, 32, 64)})
    rows = []
    for r in ratios:
        if not ratio_ok(r, d_start + count):
            continue
        measured = [measure(k, d_start, count, r, primitive_only, height_min) for _ in range(repeats)]
        per_d = statistics.median(v[0] for v in measured)
        setup = statistics.median(v[1] for v in measured)
        mass = new_fraction(d_start + count / 2, r, height_min)
        rows.append((r, per_d, setup, mass))
        print(f"ratio_max={r:9d}  {per_d * 1e6:8.3f} us per d   new angular mass={mass:.6f}   "
              f"relative yield per core-second={mass / per_d:.3e}")
    if not rows or max(row[3] for row in rows) == 0:
        raise ValueError("no calibrated ratio reaches above height_min")
    best = max(rows, key=lambda row: row[3] / row[1])
    print(f"\nsieve set-up per task: {rows[0][2]:.1f} s")
    print(f"best ratio_max on this host: {best[0]}  ({best[1] * 1e6:.3f} us per d)")
    print(f"use:  --ratio-max {best[0]} --us-per-d {best[1] * 1e6:.3f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=375)
    ap.add_argument("--primitive-only", action=argparse.BooleanOptionalAction, default=None,
                    help="require gcd(x,y,z)=1 (default on for k=375)")
    ap.add_argument("--height-min", type=int, default=None,
                    help="require max absolute coordinate strictly above this (default 10^16 for k=375)")
    ap.add_argument("--calibrate", action="store_true", help="measure cost per d at several ratio_max and exit")
    ap.add_argument("--calibration-count", type=int, default=1_000_000)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--ratios", help="comma-separated calibration ratios")
    ap.add_argument("--campaign-id")
    ap.add_argument("--output-dir", type=Path)
    ap.add_argument("--d-start", type=int, default=DEFAULT_D_START)
    ap.add_argument("--d-stop", type=int, help="exclusive end of d (else derived from --core-hours)")
    ap.add_argument("--core-hours", type=float, help="search core-hours to plan (default 1800 unless --d-stop is given)")
    ap.add_argument("--us-per-d", type=float, default=0.29, help="measured microseconds per d (use --calibrate)")
    ap.add_argument("--ratio-max", type=int, default=1024, help="|z| <= ratio_max * d; choose using the height floor and target-CPU calibration")
    ap.add_argument("--task-hours", type=float, default=1.0, help="estimated core-hours per task")
    ap.add_argument("--task-d-count", type=int, help="d values per task (overrides --task-hours)")
    ap.add_argument("--deadline-seconds", type=int, default=0, help="per-attempt deadline written into tasks")
    ap.add_argument("--rho", type=float, help="Heath-Brown density for k (default: Booker-Sutherland Table 1)")
    ap.add_argument("--plan-only", action="store_true")
    a = ap.parse_args()
    check_k(a.k)
    primitive_only = a.primitive_only if a.primitive_only is not None else abs(a.k) == 375
    height_min = a.height_min if a.height_min is not None else (10 ** 16 if abs(a.k) == 375 else 0)
    if not 0 <= height_min < 2 ** 126:
        ap.error("height-min must be in [0, 2^126)")
    if not math.isfinite(a.us_per_d) or a.us_per_d <= 0 or not math.isfinite(a.task_hours) or a.task_hours <= 0:
        ap.error("timing inputs must be finite and positive")
    if a.core_hours is not None and (not math.isfinite(a.core_hours) or a.core_hours <= 0):
        ap.error("core-hours must be finite and positive")
    if a.task_d_count is not None and a.task_d_count <= 0:
        ap.error("task-d-count must be positive")
    if a.deadline_seconds < 0 or a.calibration_count <= 0 or a.repeats <= 0:
        ap.error("invalid deadline or calibration size")
    if a.calibrate:
        if not WORKER.exists():
            ap.error("build first: make")
        return calibrate(a.k, a.d_start, a.calibration_count, primitive_only, height_min, a.repeats, a.ratios)
    if not a.campaign_id or not a.output_dir:
        ap.error("--campaign-id and --output-dir are required")
    if a.d_stop is not None and a.core_hours is not None:
        ap.error("give at most one of --d-stop or --core-hours")
    if a.d_stop is None and a.core_hours is None:
        a.core_hours = 1800.0
    d_stop = a.d_stop if a.d_stop is not None else a.d_start + int(a.core_hours * 3600e6 / a.us_per_d)
    if not 1 <= a.d_start < d_stop <= D_LIMIT:
        ap.error("need 1 <= d_start < d_stop <= 2^63/27")
    if not ratio_ok(a.ratio_max, d_stop):
        ap.error("ratio_max out of range: need 4 <= ratio_max <= 2^40 and (ratio_max + 18) * d < 2^126")
    per_task = a.task_d_count or max(1, int(a.task_hours * 3600e6 / a.us_per_d))
    n = d_stop - a.d_start
    if not a.task_d_count:                 # spread evenly without exceeding the modeled task allowance
        per_task = -(-n // max(1, -(-n // per_task)))
    est_hours = n * a.us_per_d / 3600e6
    rho = a.rho if a.rho is not None else (PRIMITIVE_RHO.get(abs(a.k)) if primitive_only else RHO.get(abs(a.k)))
    e = expected_solutions(rho, a.d_start, d_stop, a.ratio_max, height_min) if rho else None
    ntasks = -(-n // per_task)
    print(f"k={a.k}  d in [{a.d_start}, {d_stop})  ({n:.3e} values)  |z| in [3.847 d, {a.ratio_max} d]")
    print(f"tasks={ntasks}  estimated core-hours={est_hours:.1f} at {a.us_per_d} us/d")
    print(f"primitive_only={primitive_only}; max(|x|,|y|,|z|) > {height_min}")
    if e is not None:
        print(f"heuristic expected solutions in region: {e:.2e}  (rho={rho})")
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
                "d_start": str(lo), "d_stop": str(hi), "ratio_max": a.ratio_max, "deadline_seconds": a.deadline_seconds,
                "primitive_only": primitive_only, "height_min": str(height_min)}
        atomic_json(tdir / f"{tid}.json", task)
        tasks.append({"task_id": tid, "file": f"tasks/{tid}.json", "d_start": str(lo), "d_stop": str(hi),
                      "estimated_core_hours": round((hi - lo) * a.us_per_d / 3600e6, 4)})
    atomic_json(a.output_dir / "page.json", {
        "schema": PAGE_SCHEMA, "method": METHOD, "campaign_id": a.campaign_id, "k": a.k,
        "d_start": str(a.d_start), "d_stop": str(d_stop), "ratio_max": a.ratio_max, "us_per_d": a.us_per_d,
        "primitive_only": primitive_only, "height_min": str(height_min),
        "estimated_core_hours": round(est_hours, 2), "rho": rho,
        "heuristic_expected_solutions": e, "created": dt.datetime.now(dt.timezone.utc).isoformat(), "tasks": tasks})
    print(f"wrote {ntasks} tasks under {tdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
