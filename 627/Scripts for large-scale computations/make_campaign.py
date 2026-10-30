#!/usr/bin/env python3
"""Write CE627 d-first task files and a page.json manifest.

Heights h_start <= H < h_stop are cut into consecutive, disjoint tasks of
roughly equal estimated work. Shell H holds 4H - 1 raw pairs (p, q), so shells
1..H hold 2H^2 + H pairs. Work is estimated as pairs * us_per_pair; calibrate
us_per_pair on the target hardware with a short pilot (see README.md).

Either give --h-stop explicitly, or give --core-hours and let the generator
derive the largest h_stop whose estimated work fits.

Nothing here starts computation or submits jobs.
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import sys

from common627 import (PAGE_SCHEMA, PARAMETERIZATION, PRODUCTION_K, TASK_SCHEMA, atomic_json, check_k,
                       pairs_in, pairs_through)


def derive_h_stop(h_start: int, core_hours: float, us_per_pair: float) -> int:
    budget_pairs = int(core_hours * 3600e6 / us_per_pair) + pairs_through(h_start - 1)
    lo, hi = h_start, h_start + 1
    while pairs_through(hi) <= budget_pairs:
        hi *= 2
    while hi - lo > 1:  # largest H with pairs_through(H) <= budget
        mid = (lo + hi) // 2
        if pairs_through(mid) <= budget_pairs:
            lo = mid
        else:
            hi = mid
    return lo + 1


def split(h_start: int, h_stop: int, task_pairs: int) -> list[tuple[int, int]]:
    out, a = [], h_start
    while a < h_stop:
        b = a + 1
        # grow b while the task stays within its pair allowance
        step = 1
        while b + step <= h_stop and pairs_in(a, b + step) <= task_pairs:
            b += step
            step *= 2
        while step > 1:
            step //= 2
            if b + step <= h_stop and pairs_in(a, b + step) <= task_pairs:
                b += step
        out.append((a, b))
        a = b
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign-id", required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--k", type=int, default=PRODUCTION_K)
    ap.add_argument("--h-start", type=int, default=1)
    ap.add_argument("--h-stop", type=int, help="exclusive upper height (else derived from --core-hours)")
    ap.add_argument("--core-hours", type=float, help="estimated search core-hours to plan")
    ap.add_argument("--us-per-pair", type=float, default=9.0,
                    help="measured microseconds per raw (p,q) pair (default 9.0, measure your own)")
    ap.add_argument("--task-hours", type=float, default=1.0, help="estimated core-hours per task")
    ap.add_argument("--deadline-seconds", type=int, default=0,
                    help="per-attempt worker deadline written into each task (0 = none)")
    ap.add_argument("--g-max-digits", type=int, default=100)
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args()

    check_k(args.k)
    if (args.h_stop is None) == (args.core_hours is None):
        ap.error("give exactly one of --h-stop or --core-hours")
    if args.us_per_pair <= 0 or args.task_hours <= 0:
        ap.error("--us-per-pair and --task-hours must be positive")
    h_stop = args.h_stop if args.h_stop is not None else derive_h_stop(args.h_start, args.core_hours, args.us_per_pair)
    if not 1 <= args.h_start < h_stop:
        ap.error("need 1 <= h_start < h_stop")

    task_pairs = max(1, int(args.task_hours * 3600e6 / args.us_per_pair))
    ranges = split(args.h_start, h_stop, task_pairs)
    est = lambda a, b: pairs_in(a, b) * args.us_per_pair / 3600e6  # noqa: E731
    total = sum(est(a, b) for a, b in ranges)
    print(f"k={args.k}  heights [{args.h_start}, {h_stop})  tasks={len(ranges)}  "
          f"pairs={pairs_in(args.h_start, h_stop)}  estimated core-hours={total:.3f}  "
          f"|g| <= 10^{args.g_max_digits}")
    if args.plan_only:
        return 0

    tasks_dir = args.output_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    width = len(str(len(ranges)))
    entries = []
    for i, (a, b) in enumerate(ranges):
        task_id = f"{args.campaign_id}-{i:0{width}d}"
        task = {"schema": TASK_SCHEMA, "campaign_id": args.campaign_id, "task_id": task_id,
                "k": args.k, "h_start": a, "h_stop": b, "g_max_digits": args.g_max_digits,
                "deadline_seconds": args.deadline_seconds, "parameterization": PARAMETERIZATION}
        path = tasks_dir / f"{task_id}.json"
        atomic_json(path, task)
        entries.append({"task_id": task_id, "file": f"tasks/{path.name}", "h_start": a, "h_stop": b,
                        "pairs": pairs_in(a, b), "estimated_core_hours": round(est(a, b), 6)})
    atomic_json(args.output_dir / "page.json", {
        "schema": PAGE_SCHEMA, "campaign_id": args.campaign_id, "k": args.k,
        "h_start": args.h_start, "h_stop": h_stop, "g_max_digits": args.g_max_digits,
        "us_per_pair": args.us_per_pair, "estimated_core_hours": round(total, 3),
        "parameterization": PARAMETERIZATION,
        "created": dt.datetime.now(dt.timezone.utc).isoformat(), "tasks": entries})
    print(f"wrote {len(entries)} tasks to {tasks_dir} and {args.output_dir / 'page.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
