#!/usr/bin/env python3
"""Write CE375 task files and a page.json manifest for a range of n.

The range n_start <= n < n_stop is cut into consecutive, disjoint tasks of
about --task-hours each. Only n = 2 (mod 3) are processed (METHOD.md section 2),
and the cost per processed n grows slowly with |n|; give --us-per-n measured
on the target CPU near the largest |n| of the campaign (see README.md).

Nothing here starts computation or submits jobs.
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import sys

from common375 import (METHOD, N_LIMIT, PAGE_SCHEMA, PRODUCTION_K, TASK_SCHEMA, atomic_json, check_k, ns_in)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign-id", required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--k", type=int, default=PRODUCTION_K)
    ap.add_argument("--n-start", type=int, required=True)
    ap.add_argument("--n-stop", type=int, required=True, help="exclusive")
    ap.add_argument("--us-per-n", type=float, default=1500.0,
                    help="measured microseconds per processed n (default 1500, measure your own)")
    ap.add_argument("--task-hours", type=float, default=1.0, help="estimated core-hours per task")
    ap.add_argument("--deadline-seconds", type=int, default=0,
                    help="per-attempt worker deadline written into each task (0 = none)")
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args()

    check_k(args.k)
    if not -N_LIMIT <= args.n_start < args.n_stop <= N_LIMIT + 1:
        ap.error("need -10^12 <= n_start < n_stop <= 10^12 + 1")
    if args.us_per_n <= 0 or args.task_hours <= 0:
        ap.error("--us-per-n and --task-hours must be positive")

    per_task = max(1, int(args.task_hours * 3600e6 / args.us_per_n)) * 3   # n per task (1/3 processed)
    ranges, a = [], args.n_start
    while a < args.n_stop:
        b = min(args.n_stop, a + per_task)
        ranges.append((a, b))
        a = b
    est = lambda a, b: ns_in(a, b, args.k) * args.us_per_n / 3600e6  # noqa: E731
    total = sum(est(a, b) for a, b in ranges)
    print(f"k={args.k}  n in [{args.n_start}, {args.n_stop})  processed n={ns_in(args.n_start, args.n_stop, args.k)}  "
          f"tasks={len(ranges)}  estimated core-hours={total:.3f}")
    if args.plan_only:
        return 0

    tasks_dir = args.output_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    width = len(str(len(ranges)))
    entries = []
    for i, (a, b) in enumerate(ranges):
        task_id = f"{args.campaign_id}-{i:0{width}d}"
        atomic_json(tasks_dir / f"{task_id}.json", {
            "schema": TASK_SCHEMA, "campaign_id": args.campaign_id, "task_id": task_id, "k": args.k,
            "n_start": a, "n_stop": b, "deadline_seconds": args.deadline_seconds, "method": METHOD})
        entries.append({"task_id": task_id, "file": f"tasks/{task_id}.json", "n_start": a, "n_stop": b,
                        "processed_n": ns_in(a, b, args.k), "estimated_core_hours": round(est(a, b), 6)})
    atomic_json(args.output_dir / "page.json", {
        "schema": PAGE_SCHEMA, "campaign_id": args.campaign_id, "k": args.k, "n_start": args.n_start,
        "n_stop": args.n_stop, "us_per_n": args.us_per_n, "estimated_core_hours": round(total, 3),
        "method": METHOD, "created": dt.datetime.now(dt.timezone.utc).isoformat(), "tasks": entries})
    print(f"wrote {len(entries)} tasks to {tasks_dir} and {args.output_dir / 'page.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
