#!/usr/bin/env python3
"""Generate the final CE390 integer-component target, for BOTH b=1 and b=2.

Each denominator has its own immutable campaign ID/page/coverage. This writes
finite task pages only; it never submits jobs or claims to exhaust the region.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from run_task import atomic_json
from xy_campaign import argument_parser, generate


def generate_components(args: argparse.Namespace) -> dict:
    denominators = (1, 2) if args.xy_denominator == "all" else (int(args.xy_denominator),)
    if any(b not in (1, 2) for b in denominators):
        raise ValueError("integer components require x/y denominator 1 or 2")
    if not args.require_integer_components:
        raise ValueError("cube campaigns must require integer components")
    entries = []
    for b in denominators:
        options = argparse.Namespace(**vars(args))
        options.xy_denominator = str(b)
        options.campaign_id = f"{args.campaign_id}-b{b}"
        options.output_dir = args.output_dir / f"b{b}"
        page = generate(options)
        name = f"page-{int(args.page_start):012d}.json"
        entries.append({"xy_denominator": str(b), "campaign_id": options.campaign_id,
                        "page": str(Path(f"b{b}") / name),
                        "task_files": [str(Path(f"b{b}") / t["file"]) for t in page["tasks"]],
                        "page_task_count": page["page_task_count"],
                        "assigned_indices": str(sum(int(t["slice"]["stop"])-int(t["slice"]["start"])
                                                     for t in page["tasks"]))})
    plan = {"schema": "ce390-integer-components-plan-v1", "require_integer_components": True,
            "both_xy_denominators_selected": denominators == (1, 2),
            "total_tasks_written": sum(e["page_task_count"] for e in entries), "pages": entries,
            "coverage_note": "Only these pages are assigned. Both denominator cases do not imply completion of all slopes or of the n,x region. No jobs are submitted."}
    atomic_json(args.output_dir / f"components-page-{int(args.page_start):012d}.json", plan)
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argument_parser(integer_components=True)
    parser.set_defaults(output_dir=Path("cube-tasks"))
    args = parser.parse_args(argv)
    try:
        plan = generate_components(args)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(plan, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
