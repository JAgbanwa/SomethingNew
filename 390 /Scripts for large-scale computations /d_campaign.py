#!/usr/bin/env python3
"""Write d-first task files (height-shell ranges) for a Charity Engine campaign.

Tasks are contiguous, disjoint shell ranges [start, stop) that together cover
[--h-start, --h-stop). Each is sized so that its predicted run time is about
--target-seconds, using the per-pair cost measured by bench (D_FIRST.md):
the number of (p, q) pairs in shell H is 4H - 1, and the worker's cost is very
nearly proportional to the number of pairs. No job is submitted.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from math import isqrt
from pathlib import Path

from run_task import atomic_json, digest
from d_budget import (BUDGET_SCHEMA, DEFAULT_PLANNED_CORE_HOURS,
                      limit_nanoseconds, positive_decimal)
from dfirst_common import PAGE_SCHEMA, PARAMETERIZATION, TASK_SCHEMA, MAX_H, pairs_in_shells, task_identity, validate_task


def split_shells(start: int, stop: int, pairs_per_task: int) -> list[tuple[int, int]]:
    """Greedy split into ranges holding about pairs_per_task pairs each (at least one shell)."""
    out, lo = [], start
    while lo < stop:
        # Smallest hi with pairs_in_shells(lo, hi) >= pairs_per_task, by solving 2h^2 ~ cumulative.
        target = pairs_in_shells(1, lo) + pairs_per_task
        hi = max(lo + 1, isqrt(max(0, target // 2)))
        while hi < stop and pairs_in_shells(lo, hi) < pairs_per_task:
            hi += max(1, (hi - lo) // 64)
        hi = min(hi, stop)
        out.append((lo, hi))
        lo = hi
    return out


def make_task(campaign: str, ordinal: int, m: int, digits: int, start: int, stop: int, seconds: int) -> dict:
    task = {"schema": TASK_SCHEMA, "campaign_id": campaign, "ordinal": str(ordinal),
            "search": {"parameterization": PARAMETERIZATION, "m": str(m), "chart": "half", "g_max_digits": digits},
            "shells": {"start": str(start), "stop": str(stop)}, "seconds": seconds}
    task["task_id"] = task_identity(task)
    validate_task(task)
    return task


def stop_for_pairs(start: int, pair_budget: int) -> int:
    """Largest exclusive shell endpoint fitting an exact integer pair budget."""
    before = pairs_in_shells(1, start)
    last = min(MAX_H, (isqrt(1 + 8 * (before + pair_budget)) - 1) // 4)
    return last + 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign-id", required=True)
    ap.add_argument("--h-start", type=int, default=1, help="first height shell (inclusive)")
    ap.add_argument("--h-stop", type=int, help="last height shell (exclusive); otherwise derived from the planned hours")
    ap.add_argument("--m", type=int, default=65, help="65 for k = 390; other m only for validation")
    ap.add_argument("--g-max-digits", type=int, default=100, help="every point with |g| <= 10^digits is found")
    ap.add_argument("--seconds", type=int, default=3600, help="task wall-time budget (CE: --hours 2 for 3600)")
    ap.add_argument("--target-seconds", default="3000", help="predicted run time per task")
    ap.add_argument("--us-per-pair", default="4.5",
                    help="measured worker cost per (p,q) pair in microseconds (see D_FIRST.md, section 6)")
    ap.add_argument("--budget-core-hours", default="1800", help="hard controller cap, at most 1800 core-hours")
    ap.add_argument("--planned-core-hours", help="estimated search workload; default 1600 (or 8/9 of a smaller budget)")
    ap.add_argument("--max-tasks", type=int, default=10000)
    ap.add_argument("--plan-only", action="store_true", help="print the planned scope and budget without writing tasks")
    ap.add_argument("--output-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        budget_ns = limit_nanoseconds(a.budget_core_hours)
        budget = positive_decimal(a.budget_core_hours, "budget-core-hours")
        planned = (min(DEFAULT_PLANNED_CORE_HOURS, budget * Decimal(8) / Decimal(9))
                   if a.planned_core_hours is None else positive_decimal(a.planned_core_hours, "planned-core-hours"))
        if planned > budget:
            raise ValueError("planned-core-hours must not exceed budget-core-hours")
        us = positive_decimal(a.us_per_pair, "us-per-pair")
        target = positive_decimal(a.target_seconds, "target-seconds")
        if not 1 <= a.h_start <= MAX_H:
            raise ValueError("h-start must be between 1 and 200000000")
        pair_budget = int(planned * Decimal(3_600_000_000) / us)
        if a.h_stop is None:
            a.h_stop = stop_for_pairs(a.h_start, pair_budget)
        if not 1 <= a.h_start < a.h_stop <= MAX_H + 1:
            raise ValueError("need 1 <= h-start < h-stop <= 200000001; budget must cover at least one shell")
        total_pairs = pairs_in_shells(a.h_start, a.h_stop)
        if total_pairs > pair_budget:
            raise ValueError("requested height range exceeds the estimated-work budget; lower h-stop or recalibrate the rate")
        if not 1 <= a.seconds <= 86400 or target > a.seconds:
            raise ValueError("need 0 < target-seconds <= seconds <= 86400")
        if a.max_tasks < 1:
            raise ValueError("max-tasks must be positive")
    except ValueError as exc:
        ap.error(str(exc))
    pairs_per_task = max(1, int(target * Decimal(1_000_000) / us))
    ranges = split_shells(a.h_start, a.h_stop, pairs_per_task)
    if len(ranges) > a.max_tasks:
        ap.error(f"{len(ranges)} tasks exceed --max-tasks {a.max_tasks}; raise it or narrow the shells")
    if not a.plan_only and a.output_dir.exists() and any(a.output_dir.iterdir()):
        ap.error("output-dir must be empty; do not overwrite a campaign or its budget scope")
    if not a.plan_only:
        a.output_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for i, (lo, hi) in enumerate(ranges):
        task = make_task(a.campaign_id, i, a.m, a.g_max_digits, lo, hi, a.seconds)
        name = f"task-{i:06d}-{task['task_id'][:16]}.json"
        if not a.plan_only:
            atomic_json(a.output_dir / name, task)
        entries.append({"file": name, "task_id": task["task_id"], "shells": task["shells"],
                        "pairs": str(pairs_in_shells(lo, hi)), "task_sha256": digest(task),
                        "predicted_seconds": float(round(Decimal(pairs_in_shells(lo, hi)) * us / 1_000_000, 1))})
    page = {"schema": PAGE_SCHEMA, "campaign_id": a.campaign_id, "m": str(a.m), "g_max_digits": a.g_max_digits,
            "shells": {"start": str(a.h_start), "stop": str(a.h_stop)}, "tasks": entries,
            "total_pairs": str(total_pairs),
            "predicted_core_hours": float(round(Decimal(total_pairs) * us / 3_600_000_000, 6)),
            "budget": {"schema": BUDGET_SCHEMA, "core_hours": str(budget),
                       "limit_ns": budget_ns, "planned_core_hours": str(planned),
                       "us_per_pair": str(us), "accounting": "one reserved CPU core times invocation wall seconds",
                       "enforcement": "run_d_campaign.py persistent ledger; direct/CE jobs require external accounting"},
            "note": "Writes task files only; nothing is submitted. Use run_d_campaign.py for the project cap. "
                    "No n/x rectangle is imposed; |g| <= 10^g_max_digits still bounds each d."}
    if not a.plan_only:
        atomic_json(a.output_dir / "page.json", page)
    print(json.dumps({k: v for k, v in page.items() if k != "tasks"} | {"task_count": len(entries)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
