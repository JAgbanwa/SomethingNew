#!/usr/bin/env python3
"""Run a bounded local primitive-375 calibration; never submit grid jobs.

Use --quick for a build/integration smoke check only: those rows cannot be
used by band_campaign.py as a performance fit.  Normal runs sample several
d and ratio ranges, save all returned hits for exact verification, and fit
ns/d = base_ns + ratio_ns * (R - height_cutoff_ratio).

The default label is local.  --measurement-environment charity-engine is
appropriate only when this command actually runs on the target CE worker.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time

from band_campaign import lower_ratio, mean_scan_ratio
from gap_common import atomic_json, sha256_file, verify_hit

ROOT = Path(__file__).resolve().parent


def fit_rows(rows: list[dict]) -> dict | None:
    good = [r for r in rows if r.get("completed_d", 0) > 0 and r.get("search_seconds", 0) > 0]
    if len(good) < 6:
        return None
    # Medians of repeat samples reduce scheduling noise without claiming to
    # eliminate machine heterogeneity or variation with the size of d.
    groups: dict[tuple[int, int], list[dict]] = {}
    for r in good:
        groups.setdefault((int(r["d_start"]), int(r["ratio_max"])), []).append(r)
    points = [(statistics.median(r["mean_scan_ratio"] for r in group),
               statistics.median(r["ns_per_d"] for r in group))
              for group in groups.values()]
    if len(points) < 6:
        return None
    xbar = statistics.mean(x for x, _ in points)
    ybar = statistics.mean(y for _, y in points)
    variance = sum((x - xbar) ** 2 for x, _ in points)
    if variance <= 0:
        return None
    b = sum((x - xbar) * (y - ybar) for x, y in points) / variance
    a = ybar - b * xbar
    if not all(math.isfinite(v) and v > 0 for v in (a, b)):
        return None
    rss = sum((y - a - b * x) ** 2 for x, y in points)
    tss = sum((y - ybar) ** 2 for _, y in points)
    relative = [abs(y - a - b * x) / y for x, y in points]
    return {"base_ns": a, "ratio_ns": b, "r_squared": 1 - rss / tss if tss else None,
            "median_absolute_relative_error": statistics.median(relative),
            "max_absolute_relative_error": max(relative), "distinct_samples": len(points)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--worker", type=Path, default=ROOT / "bin" / "gap_worker")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--height-min", type=int, default=10 ** 16)
    ap.add_argument("--budget-seconds", type=float, default=180, help="wall-time cap for the whole sample series")
    ap.add_argument("--sample-seconds", type=float, default=2.0, help="modeled productive seconds per sample")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--quick", action="store_true", help="100,000 d per sample; smoke test, never a usable fit")
    ap.add_argument("--measurement-environment", choices=("local", "charity-engine"), default="local")
    args = ap.parse_args()
    if args.height_min <= 0 or args.budget_seconds <= 0 or args.sample_seconds <= 0 or args.repeats < 1:
        ap.error("height, timing limits, and repeats must be positive")
    if not args.worker.is_file():
        ap.error("worker is missing; build first")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        ap.error("output already exists; choose a new filename")
    rows, hits, warnings = [], [], []
    started = time.monotonic()
    worker_hash = sha256_file(args.worker)
    source_path = ROOT / "src" / "gap_worker.cpp"
    source_hash = sha256_file(source_path) if source_path.is_file() else None
    cases = []
    for d in (10 ** 10, 10 ** 11, 10 ** 12, 10 ** 13):
        r0 = lower_ratio(d, args.height_min)
        for multiplier in (8, 32, 64):
            ratio = 1 << max(2, math.ceil(math.log2(multiplier * r0)))
            cases.append((d, ratio))
    stop = False
    for repeat in range(args.repeats):
        for d, ratio in cases:
            if sha256_file(args.worker) != worker_hash:
                warnings.append("The worker binary changed during calibration; timings are not a usable fit.")
                stop = True
                break
            remaining = args.budget_seconds - (time.monotonic() - started)
            if remaining < 1:
                warnings.append("Wall-time budget reached before all requested samples completed.")
                stop = True
                break
            predicted_ns = 260 + 0.025 * max(0, ratio - lower_ratio(d, args.height_min))
            count = 100_000 if args.quick else max(100_000, min(20_000_000, int(args.sample_seconds * 1e9 / predicted_ns)))
            command = [str(args.worker.resolve()), "--k", "375", "--primitive-only",
                       "--height-min", str(args.height_min), "--d-start", str(d),
                       "--d-stop", str(d + count), "--ratio-max", str(ratio),
                       "--chunk", str(count)]
            wall_start = time.monotonic()
            timed_out = False
            try:
                proc = subprocess.run(command, capture_output=True, text=True, timeout=remaining)
                output, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
            except subprocess.TimeoutExpired as exc:
                output = exc.stdout or ""
                if isinstance(output, bytes):
                    output = output.decode("utf-8", errors="replace")
                stderr, returncode, timed_out = "benchmark wall-time limit", -1, True
            records = []
            for line in output.splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                records.append(rec)
                if rec.get("type") == "hit":
                    verify_hit(rec, 375, primitive_only=True, height_min=args.height_min)
                    hits.append(rec)
            chunks = [r for r in records if r.get("type") == "chunk"]
            completed = sum(int(r["d_stop"]) - int(r["d_start"]) for r in chunks)
            search_seconds = sum(float(r["seconds"]) for r in chunks)
            setup = next((r.get("setup_seconds") for r in records if r.get("type") == "start"), None)
            row = {"repeat": repeat, "d_start": str(d), "requested_d": count,
                   "completed_d": completed, "ratio_max": ratio,
                   "mean_scan_ratio": mean_scan_ratio(d, d + max(1, completed), ratio, args.height_min),
                   "search_seconds": search_seconds,
                   "ns_per_d": search_seconds * 1e9 / completed if completed else None,
                   "setup_seconds": setup, "wall_seconds": time.monotonic() - wall_start,
                   "returncode": returncode, "timed_out": timed_out,
                   "stderr": stderr.strip(), "worker_records": records}
            rows.append(row)
            if returncode and not timed_out:
                warnings.append(f"Worker failed at d={d}, R={ratio}: {stderr.strip()}")
                stop = True
            value = f"{row['ns_per_d']:.1f}" if row["ns_per_d"] is not None else "incomplete"
            print(f"d={d} R={ratio} repeat={repeat} completed={completed} ns/d={value}", flush=True)
            # Save after each sample so a failed or interrupted calibration
            # cannot silently discard an independently verified discovery.
            partial = {"schema": "ce375-benchmark-v1", "k": 375, "primitive_only": True,
                       "height_min": str(args.height_min), "quick": args.quick,
                       "measurement_environment": args.measurement_environment,
                       "worker_sha256": worker_hash, "worker_source_sha256": source_hash,
                       "rows": rows, "hits": hits,
                       "warnings": warnings, "fit_usable": False, "fitted_cost_model": None}
            atomic_json(args.output, partial)
            if timed_out or stop:
                stop = True
                break
        if stop:
            break
    fit = None if args.quick else fit_rows(rows)
    usable = (fit is not None and all(r["returncode"] == 0 for r in rows)
              and sha256_file(args.worker) == worker_hash)
    if fit and fit["median_absolute_relative_error"] > 0.25:
        warnings.append("The pooled cost fit has >25% median relative error; use per-band measurements before a full run.")
        usable = False
    if args.quick:
        warnings.append("Quick mode is an integration smoke test; its timing is not a usable calibration.")
    if args.measurement_environment != "charity-engine":
        warnings.append("Measured on a local host, not Charity Engine hardware.")
    result = {"schema": "ce375-benchmark-v1", "k": 375, "primitive_only": True,
              "height_min": str(args.height_min), "quick": args.quick,
              "measurement_environment": args.measurement_environment,
              "worker_sha256": worker_hash, "worker_source_sha256": source_hash,
              "host": {"platform": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count()},
              "created": dt.datetime.now(dt.timezone.utc).isoformat(),
              "elapsed_wall_seconds": time.monotonic() - started,
              "rows": rows, "hits": hits, "warnings": warnings,
              "fit_usable": usable, "fitted_cost_model": fit}
    atomic_json(args.output, result)
    if fit:
        print(f"fit base={fit['base_ns']:.3f} ns/d, incremental={fit['ratio_ns']:.6f} ns/ratio; usable={usable}")
    print(f"saved {args.output}; independently verified primitive hits={len(hits)}")
    return 0 if rows and all(r["returncode"] == 0 for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
