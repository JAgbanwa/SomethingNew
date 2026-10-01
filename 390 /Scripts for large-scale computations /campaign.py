#!/usr/bin/env python3
"""Generate only a requested page of deterministic, nonoverlapping CE390 tasks."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from run_task import (SCHEMA, PARAMETERIZATION, DEFAULT_N_MIN, DEFAULT_N_MAX, DEFAULT_X_MIN,
                      DEFAULT_X_MAX, SIGN_POLICIES, atomic_json, integer, task_identity, validate_task)
from parameter_space import GeneralAQ


def generate(args: argparse.Namespace) -> dict:
    search = {k: getattr(args, k) for k in ("n_min", "n_max", "x_min", "x_max")}
    search["signs"] = args.signs
    search["require_integer_sqrt"] = args.require_integer_sqrt
    raw_a = getattr(args, "a_values", None)
    if raw_a is None:
        if not args.require_integer_sqrt:
            raise ValueError("general a/q enumeration requires integer roots; explicit --a-values is needed for exploratory rational roots")
        bounds = {k: integer(search[k], k, positive=True) for k in ("n_min", "n_max", "x_min", "x_max")}
        q_min = integer("1" if args.q_min is None else args.q_min, "q-min", positive=True)
        q_max = integer(search["x_max"] if args.q_max is None else args.q_max, "q-max", positive=True)
        space = GeneralAQ(bounds, q_min, q_max)
        count = space.count
        fibers = {"mode": "general-aq-v1", "q_min": str(q_min), "q_max": str(q_max)}
    else:
        if not args.q_min or not args.q_max:
            raise ValueError("explicit --a-values requires both --q-min and --q-max")
        a_values = raw_a.split(",")
        q_min = integer(args.q_min, "q-min", positive=True)
        q_max = integer(args.q_max, "q-max", positive=True)
        if q_min % 2 == 0 or q_max % 2 == 0 or q_min > q_max:
            raise ValueError("q-min and q-max must be ordered positive odd integers for --a-values")
        count = len(a_values) * ((q_max - q_min) // 2 + 1)
        fibers = {"a_values": a_values, "q_min": str(q_min), "q_max": str(q_max)}
    size = integer(args.candidates_per_task, "candidates-per-task", positive=True)
    page_start = integer(args.page_start, "page-start")
    if not 1 <= args.task_count <= 10000:
        raise ValueError("task-count must be between 1 and 10000")
    if count == 0:
        raise ValueError("the selected denominator interval contains no parameters in the derived enclosure")
    task_count = (count + size - 1) // size
    if page_start >= task_count:
        raise ValueError(f"page-start {page_start} is beyond the {task_count} campaign tasks")
    execution = {"time_limit_seconds": args.seconds, "precision_bits": args.precision_bits,
                 "max_precision_bits": args.max_precision_bits, "checkpoint_seconds": args.checkpoint_seconds}
    tasks = []
    for ordinal in range(page_start, min(page_start + args.task_count, task_count)):
        start, stop = ordinal * size, min((ordinal + 1) * size, count)
        task = {"schema": SCHEMA, "parameterization": PARAMETERIZATION, "campaign_id": args.campaign_id,
                "search": search, "fibers": fibers, "slice": {"start": str(start), "stop": str(stop)},
                "execution": execution}
        task["task_id"] = task_identity(task)
        validate_task(task)
        tasks.append((ordinal, task))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for ordinal, task in tasks:
        filename = f"task-{ordinal:012d}-{task['task_id'][:16]}.json"
        path = args.output_dir / filename
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != task:
                raise ValueError(f"refusing to overwrite a different task: {path}")
        else:
            atomic_json(path, task)
        entries.append({"ordinal": str(ordinal), "file": filename, "task_id": task["task_id"], "slice": task["slice"]})
    manifest = {"schema": "ce390-page-v2", "campaign_id": args.campaign_id, "total_candidate_indices": str(count),
                "total_tasks": str(task_count), "page_start": str(page_start), "page_task_count": len(entries),
                "next_page_start": str(page_start + len(entries)) if page_start + len(entries) < task_count else None,
                "candidates_per_task": str(size), "tasks": entries,
                "coverage_note": ("General a/q enclosure with all derived numerators; only the assigned index slices are covered, not the whole signed n,x region."
                                  if "mode" in fibers else
                                  "Explicitly restricted numerator list; only selected absolute-slope fibers and requested signs are covered, not the whole signed n,x region.")}
    atomic_json(args.output_dir / f"page-{page_start:012d}.json", manifest)
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--a-values", help="explicit restricted legacy mode: comma-separated positive odd numerators; omitted by default to search general a/q")
    p.add_argument("--q-min", help="inclusive denominator lower bound (general default: 1)")
    p.add_argument("--q-max", help="inclusive denominator upper bound (general default: x-max, proved by integer-root requirement)")
    p.add_argument("--candidates-per-task", default="10000", help="candidate indices, including noncoprime pairs")
    p.add_argument("--page-start", default="0", help="zero-based task ordinal, not candidate index")
    p.add_argument("--task-count", type=int, default=10, help="emit only this page, at most 10000 tasks")
    p.add_argument("--seconds", type=int, default=3600,
                   help="soft wall-time budget (default 3600): use CE --hours 2; use 3000 for CE --hours 1")
    p.add_argument("--signs", choices=SIGN_POLICIES, default="all", help="all four sign combinations by default; p/n refer to signs of n then x")
    sqrt_policy = p.add_mutually_exclusive_group()
    sqrt_policy.add_argument("--require-integer-sqrt", dest="require_integer_sqrt", action="store_true",
                             help="require an integer principal square root (default)")
    sqrt_policy.add_argument("--allow-rational-sqrt", dest="require_integer_sqrt", action="store_false",
                             help="explicitly allow noninteger rational square roots")
    p.set_defaults(require_integer_sqrt=True)
    p.add_argument("--precision-bits", type=int, default=512)
    p.add_argument("--max-precision-bits", type=int, default=16384)
    p.add_argument("--checkpoint-seconds", type=int, default=5)
    for name, default in (("n-min", DEFAULT_N_MIN), ("n-max", DEFAULT_N_MAX), ("x-min", DEFAULT_X_MIN), ("x-max", DEFAULT_X_MAX)):
        p.add_argument("--" + name, default=str(default), help="inclusive positive magnitude bound")
    p.add_argument("--output-dir", type=Path, default=Path("tasks"))
    args = p.parse_args()
    try:
        manifest = generate(args)
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    print(json.dumps({k: v for k, v in manifest.items() if k != "tasks"}, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
