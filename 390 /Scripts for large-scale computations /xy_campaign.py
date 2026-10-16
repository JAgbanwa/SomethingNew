#!/usr/bin/env python3
"""Generate corrected n-sixths, equal-x/y-denominator search jobs at a selected b."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from run_task import (DEFAULT_N_MIN, DEFAULT_N_MAX, DEFAULT_X_MIN, DEFAULT_X_MAX,
                      SIGN_POLICIES, atomic_json, integer, task_identity)
from xy_common import (SCHEMA, PARAMETERIZATION, PAGE_SCHEMA, CONGRUENCE_POLICIES,
                             XYAQ, parameter_space, validate_task)
from aq_traversal import InterleavedAQ



def generate(args: argparse.Namespace) -> dict:
    search = {k: getattr(args, k) for k in ("n_min", "n_max", "x_min", "x_max")}
    search["signs"] = args.signs
    search["xy_denominator"] = args.xy_denominator
    search["n_denominators"] = [int(d) for d in args.n_denominators.split(",")]
    search["congruence_policy"] = args.congruence_policy
    search["require_noninteger_d"] = args.noninteger_d
    if getattr(args, "require_integer_components", False):
        search["require_integer_components"] = True
    full = XYAQ(search)
    q_min = integer(args.q_min or "1", "q-min", positive=True)
    q_max = integer(args.q_max or str(full.full_q_max), "q-max", positive=True)
    if (q_min != 1 or q_max != full.full_q_max) and not args.allow_q_window:
        raise ValueError("restricted slope-denominator windows require --allow-q-window")
    order = getattr(args, "parameter_order", "q-major")
    if order not in ("q-major", "interleaved"):
        raise ValueError("parameter order must be q-major or interleaved")
    mode = XYAQ.MODE if order == "q-major" else InterleavedAQ.MODE
    space = parameter_space(search, q_min, q_max, mode)
    count = space.count
    fibers = {"mode": space.MODE, "q_min": str(q_min), "q_max": str(q_max)}
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
    manifest = {"schema": PAGE_SCHEMA, "campaign_id": args.campaign_id, "total_candidate_indices": str(count),
                "total_tasks": str(task_count), "page_start": str(page_start), "page_task_count": len(entries),
                "next_page_start": str(page_start + len(entries)) if page_start + len(entries) < task_count else None,
                "candidates_per_task": str(size), "tasks": entries,
                "coverage_note": "Only these slope indices at this exact common reduced x/y denominator are assigned. No other denominators or unprocessed indices are covered."}

    atomic_json(args.output_dir / f"page-{page_start:012d}.json", manifest)
    return manifest


def argument_parser(*, integer_components: bool = False) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=(
        "Generate the final integer-component target for b=1 and b=2; no jobs are submitted."
        if integer_components else __doc__))
    p.add_argument("--campaign-id", required=True)
    if integer_components:
        p.add_argument("--xy-denominator", choices=("all", "1", "2"), default="all",
                       help="all (default) generates BOTH exact reduced denominator cases; 1 or 2 restricts the search")
    else:
        p.add_argument("--xy-denominator", required=True, help="exact common REDUCED denominator of x and y, b >= 1")
    p.add_argument("--require-integer-components", action="store_true", default=integer_components,
                   help="require BOTH -x+y and -x-y, and 2*x+6*n, integral; implies b=1 or 2")
    p.add_argument("--n-denominators", default="1,2,3,6", help="sorted comma-separated subset of 1,2,3,6; default all four")
    p.add_argument("--congruence-policy", default="none", choices=CONGRUENCE_POLICIES, help="no extra congruences by default; opt in explicitly")
    p.add_argument("--noninteger-d", action="store_true", help="optionally exclude integer d; by default every rational d is allowed")
    p.add_argument("--q-min", help="inclusive denominator lower bound; requires --allow-q-window when it restricts the full enclosure")
    p.add_argument("--q-max", help="inclusive denominator upper bound; requires --allow-q-window when it restricts the full enclosure")
    p.add_argument("--allow-q-window", action="store_true",
                   help="explicitly allow a restricted q interval in general a/q mode (diagnostic only; not the default full enclosure)")
    p.add_argument("--parameter-order", choices=("interleaved", "q-major"),
                   default="interleaved" if integer_components else "q-major",
                   help="interleave both a and q across the full enclosure; q-major preserves historical ordering")
    p.add_argument("--candidates-per-task", default="10000", help="candidate indices, including noncoprime pairs")
    p.add_argument("--page-start", default="0", help="zero-based task ordinal, not candidate index")
    p.add_argument("--task-count", type=int, default=1, help="emit only this page, at most 10000 tasks")
    p.add_argument("--seconds", type=int, default=3600,
                   help="soft wall-time budget (default 3600): use CE --hours 2; use 3000 for CE --hours 1")
    p.add_argument("--signs", choices=SIGN_POLICIES, default="all", help="all four sign combinations by default; p/n refer to signs of n then x")
    p.add_argument("--precision-bits", type=int, default=512)
    p.add_argument("--max-precision-bits", type=int, default=16384)
    p.add_argument("--checkpoint-seconds", type=int, default=5)
    for name, default in (("n-min", DEFAULT_N_MIN), ("n-max", DEFAULT_N_MAX), ("x-min", DEFAULT_X_MIN), ("x-max", DEFAULT_X_MAX)):
        p.add_argument("--" + name, default=str(default), help="inclusive positive magnitude bound")
    p.add_argument("--output-dir", type=Path, default=Path("xy-tasks"))
    return p


def main(argv: list[str] | None = None) -> int:
    p = argument_parser()
    args = p.parse_args(argv)
    try:
        manifest = generate(args)
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    print(json.dumps({k: v for k, v in manifest.items() if k != "tasks"}, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
