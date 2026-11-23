#!/usr/bin/env python3
"""Plan disjoint primitive-375 search bands above a chosen height floor.

The native worker searches pair sums d=|x+y|, with |z|<=R*d.  A lower
maximum-coordinate height H avoids overlap when that height has been searched
or reserved by another campaign; this script does not establish that fact. At d<<H,
the lower ratio is approximately 3^(1/3)*(H/d)^(2/3).  For a cost model
    nanoseconds per d = base_ns + ratio_ns * max(0, R-lower_ratio),
equal marginal heuristic yield suggests R proportional to d^(-2/3).

This script optimizes that family, approximates it by disjoint constant-R
bands, and budgets the ACTUAL bands.  Cost and discovery probability remain
models.  No jobs are submitted.  Each band gets its own ordinary page.json
and tasks, so existing runners and collectors can process it independently.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any

from gap_common import (ALPHA, D_LIMIT, METHOD, PRIMITIVE_RHO, RATIO_LIMIT,
                        atomic_json, expected_solutions, load_json)

ROOT = Path(__file__).resolve().parent
SCHEMA = "ce375-primitive-bands-v1"


def lower_ratio(d: float, height_min: int) -> float:
    """Asymptotic geometric cutoff; never used to reject a real candidate."""
    if height_min <= 0 or d >= height_min:
        return 1 / ALPHA
    h = height_min / d
    return max(1 / ALPHA, (3 * h * h - 3 * h + 1) ** (1 / 3))


def mean_scan_ratio(lo: int, hi: int, ratio: int, height_min: int) -> float:
    """Simpson average over d, on a short geometric band."""
    panels = 8
    step = (hi - lo) / panels
    total = 0.0
    for i in range(panels + 1):
        value = max(0.0, ratio - lower_ratio(lo + i * step, height_min))
        total += (1 if i in (0, panels) else 4 if i % 2 else 2) * value
    return total / (3 * panels)


def make_bands(d_start: int, d_stop: int, kappa: float, height_min: int,
               base_ns: float, ratio_ns: float, band_factor: float = 1.25,
               *, with_yield: bool = True) -> list[dict[str, Any]]:
    if not 1 <= d_start < d_stop <= D_LIMIT:
        raise ValueError("need 1 <= d_start < d_stop <= D_LIMIT")
    if not (math.isfinite(kappa) and kappa > 1):
        raise ValueError("kappa must be finite and greater than one")
    if not (1.01 <= band_factor <= 2):
        raise ValueError("band_factor must be between 1.01 and 2")
    if not all(math.isfinite(v) and v > 0 for v in (base_ns, ratio_ns)):
        raise ValueError("both cost coefficients must be finite and positive")
    bands = []
    lo = d_start
    while lo < d_stop:
        hi = min(d_stop, max(lo + 1, int(lo * band_factor)))
        mid = math.sqrt(lo * hi)
        ratio = min(RATIO_LIMIT, max(4, int(math.ceil(kappa * lower_ratio(mid, height_min)))))
        ns = base_ns + ratio_ns * mean_scan_ratio(lo, hi, ratio, height_min)
        row = {
            "d_start": str(lo), "d_stop": str(hi), "ratio_max": ratio,
            "model_ns_per_d": ns,
            "estimated_core_hours": (hi - lo) * ns / 3.6e12,
        }
        if with_yield:
            row["heuristic_expected_solutions"] = expected_solutions(
                PRIMITIVE_RHO[375], lo, hi, ratio, height_min)
        bands.append(row)
        lo = hi
    return bands


def continuous_guess(core_hours: float, height_min: int, base_ns: float,
                     ratio_ns: float) -> float:
    """Stationary kappa of the d<<H, d_start=0 approximation."""
    a, b = base_ns * 1e-9, ratio_ns * 1e-9
    target = core_hours * 3600
    big_b = 3 * b * 3 ** (1 / 3) * height_min ** (2 / 3)

    def cost(v: float) -> float:
        u = math.sqrt(big_b / (3 * a)) * (v - 1) * math.sqrt(2 * v + 1)
        return a * u ** 3 + big_b * (v * v - 1) * u

    lo, hi = 1.0, 2.0
    while cost(hi) < target:
        hi *= 2
    for _ in range(64):
        mid = (lo + hi) / 2
        if cost(mid) > target:
            hi = mid
        else:
            lo = mid
    return ((lo + hi) / 2) ** 2


def fit_budget(core_hours: float, d_start: int, kappa: float, height_min: int,
               base_ns: float, ratio_ns: float, band_factor: float,
               *, with_yield: bool = True) -> list[dict[str, Any]]:
    """Largest integer endpoint within the modeled productive-time budget."""
    target_ns = core_hours * 3.6e12
    high = min(D_LIMIT, d_start + max(2, int(target_ns / base_ns) + 2))
    low = d_start
    while low + 1 < high:
        mid = (low + high) // 2
        bands = make_bands(d_start, mid, kappa, height_min, base_ns,
                           ratio_ns, band_factor, with_yield=False)
        cost_ns = sum(r["estimated_core_hours"] for r in bands) * 3.6e12
        if cost_ns <= target_ns:
            low = mid
        else:
            high = mid
    if low <= d_start:
        raise ValueError("budget is too small for even one modeled d")
    return make_bands(d_start, low, kappa, height_min, base_ns,
                      ratio_ns, band_factor, with_yield=with_yield)


def optimize(core_hours: float, height_min: int, base_ns: float,
             ratio_ns: float, d_start: int = 10 ** 6,
             band_factor: float = 1.25) -> dict[str, Any]:
    if not math.isfinite(core_hours) or core_hours <= 0 or height_min <= 0:
        raise ValueError("positive productive core-hours and height_min are required")
    guess = continuous_guess(core_hours, height_min, base_ns, ratio_ns)
    # Search a broad neighborhood; the actual constant-R bands and finite
    # d_start, rather than the continuous approximation, determine the result.
    left = math.log(max(1.001, guess / 4))
    right = math.log(max(2.0, guess * 4))
    inv_phi = (math.sqrt(5) - 1) / 2
    cache: dict[float, tuple[float, list[dict[str, Any]]]] = {}

    def score(log_kappa: float) -> tuple[float, list[dict[str, Any]]]:
        if log_kappa not in cache:
            bands = fit_budget(core_hours, d_start, math.exp(log_kappa), height_min,
                               base_ns, ratio_ns, band_factor)
            cache[log_kappa] = (sum(r["heuristic_expected_solutions"] for r in bands), bands)
        return cache[log_kappa]

    x1 = right - inv_phi * (right - left)
    x2 = left + inv_phi * (right - left)
    for _ in range(24):
        if score(x1)[0] < score(x2)[0]:
            left, x1 = x1, x2
            x2 = left + inv_phi * (right - left)
        else:
            right, x2 = x2, x1
            x1 = right - inv_phi * (right - left)
    candidates = [x1, x2, math.log(guess)]
    best = max(candidates, key=lambda x: score(x)[0])
    expected, bands = score(best)
    return {
        "kappa": math.exp(best), "continuous_kappa_guess": guess,
        "d_start": str(d_start), "d_stop": bands[-1]["d_stop"],
        "band_factor": band_factor, "bands": bands,
        "estimated_core_hours": sum(b["estimated_core_hours"] for b in bands),
        "heuristic_expected_solutions": expected,
        "poisson_heuristic_hit_probability": -math.expm1(-expected),
    }


def planned_task_count(bands: list[dict[str, Any]], task_hours: float) -> int:
    """Match gap_campaign's conservative, evenly distributed task sizing."""
    count = 0
    for band in bands:
        n = int(band["d_stop"]) - int(band["d_start"])
        capacity = max(1, int(task_hours * 3.6e12 / band["model_ns_per_d"]))
        required = (n + capacity - 1) // capacity
        per_task = (n + required - 1) // required
        count += (n + per_task - 1) // per_task
    return count


def optimize_with_task_limit(core_hours: float, height_min: int, base_ns: float,
                             ratio_ns: float, d_start: int, band_factor: float,
                             task_hours: float, max_tasks: int | None) -> dict[str, Any]:
    """Reduce modeled productive hours when band rounding exceeds a task cap."""
    hours = core_hours
    plan = optimize(hours, height_min, base_ns, ratio_ns, d_start, band_factor)
    count = planned_task_count(plan["bands"], task_hours)
    if max_tasks is not None:
        if max_tasks < 1:
            raise ValueError("max_tasks must be positive")
        # The task total is dominated by hours/task_hours plus one rounding
        # term per band. Re-optimization after reducing hours keeps the search
        # shape appropriate to the actual resource cap.
        attempts = 0
        while count > max_tasks:
            attempts += 1
            if attempts > 12:
                raise ValueError("could not fit task cap; increase max_tasks or reduce the initial budget")
            hours -= (count - max_tasks + 1) * task_hours
            if hours <= 0:
                hours = plan["estimated_core_hours"] * max_tasks / (count + 1) * 0.8
            plan = optimize(hours, height_min, base_ns, ratio_ns, d_start, band_factor)
            count = planned_task_count(plan["bands"], task_hours)
    plan.update(planned_task_count=count, max_tasks=max_tasks,
                budget_reduced_for_task_limit=hours < core_hours,
                task_limited_productive_core_hours=hours)
    return plan


def cost_model(args: argparse.Namespace) -> tuple[float, float, dict[str, Any]]:
    if args.benchmark_json:
        record = load_json(args.benchmark_json)
        model = record.get("fitted_cost_model")
        if not record.get("fit_usable") or not model:
            raise ValueError("benchmark is quick, incomplete, or has no usable positive cost fit")
        if int(record.get("height_min", -1)) != args.height_min:
            raise ValueError("benchmark height_min differs from the planned height_min")
        a, b = float(model["base_ns"]), float(model["ratio_ns"])
        provenance = {
            "type": "measured_fit", "source": str(args.benchmark_json),
            "measurement_environment": record.get("measurement_environment", "local"),
            "worker_sha256": record.get("worker_sha256"),
            "fit_diagnostics": model,
            "charity_engine_calibrated": record.get("measurement_environment") == "charity-engine",
        }
    else:
        a, b = args.base_ns, args.ratio_ns
        provenance = {"type": "assumed_model", "charity_engine_calibrated": False}
    if not all(math.isfinite(v) and v > 0 for v in (a, b)):
        raise ValueError("cost coefficients must be finite and positive")
    provenance.update(base_ns=a, ratio_ns=b)
    return a, b, provenance


def write_bundle(plan: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError("output directory is not empty; choose a new directory")
    total_tasks = 0
    for i, band in enumerate(plan["bands"]):
        bid = f"{args.campaign_id}-b{i:03d}"
        relative = Path("bands") / f"b{i:03d}"
        destination = out / relative
        command = [sys.executable, str(ROOT / "gap_campaign.py"), "--k", "375",
                   "--primitive-only", "--height-min", str(args.height_min),
                   "--campaign-id", bid, "--output-dir", str(destination),
                   "--d-start", band["d_start"], "--d-stop", band["d_stop"],
                   "--ratio-max", str(band["ratio_max"]),
                   "--us-per-d", repr(band["model_ns_per_d"] / 1000),
                   "--task-hours", repr(args.task_hours),
                   "--deadline-seconds", str(args.deadline_seconds)]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode:
            raise RuntimeError(f"band {i} planning failed: {completed.stderr.strip() or completed.stdout.strip()}")
        page = load_json(destination / "page.json")
        band.update(campaign_id=bid, page=str(relative / "page.json"), task_count=len(page["tasks"]))
        total_tasks += band["task_count"]
    plan["task_count"] = total_tasks
    if plan.get("max_tasks") is not None and total_tasks > plan["max_tasks"]:
        raise ValueError("actual task count exceeded the planned cap; task-sizing interfaces may have changed")
    atomic_json(out / "campaign.json", plan)
    return plan


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign-id", default="ce375-primitive")
    ap.add_argument("--output-dir", type=Path)
    ap.add_argument("--core-hours", type=float, default=1350, help="productive search hours, excluding setup/retries/audit")
    ap.add_argument("--height-min", type=int, default=10 ** 16)
    ap.add_argument("--d-start", type=int, default=10 ** 6)
    ap.add_argument("--base-ns", type=float, default=260)
    ap.add_argument("--ratio-ns", type=float, default=0.025)
    ap.add_argument("--benchmark-json", type=Path, help="use a non-quick benchmark375.py fit instead of assumed coefficients")
    ap.add_argument("--band-factor", type=float, default=1.25)
    ap.add_argument("--task-hours", type=float, default=0.75)
    ap.add_argument("--max-tasks", type=int, help="reduce productive hours so all bands together fit this many tasks")
    ap.add_argument("--deadline-seconds", type=int, default=2700)
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args()
    try:
        if not args.plan_only and args.output_dir is None:
            ap.error("--output-dir is required unless --plan-only")
        if not math.isfinite(args.task_hours) or args.task_hours <= 0 or args.deadline_seconds < 0:
            ap.error("task-hours must be positive and deadline-seconds nonnegative")
        if not 1 <= args.d_start < D_LIMIT:
            ap.error("d-start is outside the worker range")
        a, b, provenance = cost_model(args)
        plan = optimize_with_task_limit(args.core_hours, args.height_min, a, b,
                                        args.d_start, args.band_factor, args.task_hours, args.max_tasks)
        plan.update(schema=SCHEMA, method=METHOD, campaign_id=args.campaign_id,
                    k=375, primitive_only=True, height_min=str(args.height_min),
                    rho=PRIMITIVE_RHO[375], requested_productive_core_hours=args.core_hours,
                    task_hours=args.task_hours, deadline_seconds=args.deadline_seconds,
                    cost_model=provenance, created=dt.datetime.now(dt.timezone.utc).isoformat(),
                    caveats=["Expected counts use the Heath-Brown and Booker-Sutherland heuristics.",
                             "The displayed hit probability additionally assumes a Poisson model.",
                             "Predicted runtime excludes setup, retries, and independent audits.",
                             "Height frontier and novelty must be checked against other searches.",
                             "This is an optimized family of regions, not a proof of globally optimal allocation."])
        if not args.plan_only:
            write_bundle(plan, args)
        label = "CE-measured model" if provenance["charity_engine_calibrated"] else "MODEL; not calibrated on Charity Engine"
        print(f"{label}: base={a:.3f} ns/d, incremental={b:.6f} ns per ratio unit")
        print(f"primitive k=375, max coordinate height > {args.height_min}, d in [{plan['d_start']}, {plan['d_stop']})")
        print(f"{len(plan['bands'])} disjoint bands, kappa={plan['kappa']:.3f}, productive hours={plan['estimated_core_hours']:.3f}")
        print(f"planned tasks={plan['planned_task_count']} at at most {args.task_hours:g} modeled hours each; task cap={args.max_tasks}")
        if plan["budget_reduced_for_task_limit"]:
            print(f"productive budget reduced from {args.core_hours:g} hours to respect the task cap")
        print(f"heuristic expected hits={plan['heuristic_expected_solutions']:.6g}; Poisson-style probability={100*plan['poisson_heuristic_hit_probability']:.4f}%")
        if not args.plan_only:
            print(f"wrote {plan['task_count']} tasks and {args.output_dir / 'campaign.json'}")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        ap.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
