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
from math import isqrt
from pathlib import Path

from run_task import atomic_json
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign-id", required=True)
    ap.add_argument("--h-start", type=int, default=1, help="first height shell (inclusive)")
    ap.add_argument("--h-stop", type=int, required=True, help="last height shell (exclusive)")
    ap.add_argument("--m", type=int, default=65, help="65 for k = 390; other m only for validation")
    ap.add_argument("--g-max-digits", type=int, default=100, help="every point with |g| <= 10^digits is found")
    ap.add_argument("--seconds", type=int, default=3600, help="task wall-time budget (CE: --hours 2 for 3600)")
    ap.add_argument("--target-seconds", type=float, default=3000.0, help="predicted run time per task")
    ap.add_argument("--us-per-pair", type=float, default=4.5,
                    help="measured worker cost per (p,q) pair in microseconds (see D_FIRST.md, section 6)")
    ap.add_argument("--max-tasks", type=int, default=10000)
    ap.add_argument("--output-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    if not 1 <= a.h_start < a.h_stop <= MAX_H + 1:
        ap.error("need 1 <= --h-start < --h-stop <= 200000001")
    if a.us_per_pair <= 0 or a.target_seconds <= 0:
        ap.error("--us-per-pair and --target-seconds must be positive")
    pairs_per_task = max(1, int(a.target_seconds / (a.us_per_pair * 1e-6)))
    ranges = split_shells(a.h_start, a.h_stop, pairs_per_task)
    if len(ranges) > a.max_tasks:
        ap.error(f"{len(ranges)} tasks exceed --max-tasks {a.max_tasks}; raise it or narrow the shells")
    a.output_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for i, (lo, hi) in enumerate(ranges):
        task = make_task(a.campaign_id, i, a.m, a.g_max_digits, lo, hi, a.seconds)
        name = f"task-{i:06d}-{task['task_id'][:16]}.json"
        atomic_json(a.output_dir / name, task)
        entries.append({"file": name, "task_id": task["task_id"], "shells": task["shells"],
                        "pairs": str(pairs_in_shells(lo, hi)),
                        "predicted_seconds": round(pairs_in_shells(lo, hi) * a.us_per_pair * 1e-6, 1)})
    page = {"schema": PAGE_SCHEMA, "campaign_id": a.campaign_id, "m": str(a.m), "g_max_digits": a.g_max_digits,
            "shells": {"start": str(a.h_start), "stop": str(a.h_stop)}, "tasks": entries,
            "total_pairs": str(pairs_in_shells(a.h_start, a.h_stop)),
            "predicted_core_hours": round(pairs_in_shells(a.h_start, a.h_stop) * a.us_per_pair * 1e-6 / 3600, 2),
            "note": "Writes task files only; nothing is submitted. Run each with run_d_task.py."}
    atomic_json(a.output_dir / "page.json", page)
    print(json.dumps({k: v for k, v in page.items() if k != "tasks"} | {"task_count": len(entries)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
