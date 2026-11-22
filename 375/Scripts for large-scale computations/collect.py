#!/usr/bin/env python3
"""Merge returned CE375 task outputs: coverage, gaps, verified hits.

Point --results at one or more directories. Every subdirectory (any depth)
holding a status.json or checkpoint.json is read as one task output. Covered
n per directory is [first block start, next_n). Every hit is re-verified.

Writes to --output-dir:
  hits.jsonl          verified, de-duplicated points (both forms, all primitivity)
  desired_points.txt  THE RESULT: primitive points, one per line (n, x, y)
  points.txt          every point, tagged DESIRED or non-primitive
  incomplete.txt      n whose N(n) could not be factored (not covered; rerun them)
  summary.json        coverage, gaps against page.json, counters
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from common375 import COUNTERS, atomic_json, hit_key, load_json, verify_hit


def merge(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def line(v: dict) -> str:
    return (f"form={v['form']:<7}  n={v['n']}  x={v['x']}  y=+-{v['y']}  "
            f"cubes={','.join(v['cubes'])}  point_gcd={v['point_gcd']}  cube_gcd={v['cube_gcd']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, nargs="+", required=True)
    ap.add_argument("--page", type=Path, help="page.json to compute gaps against")
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()

    page = load_json(args.page) if args.page else None
    k = page["k"] if page else None
    covered: list[tuple[int, int]] = []
    counters = {c: 0 for c in COUNTERS}
    hits: dict[str, dict] = {}
    incomplete: dict[str, dict] = {}
    errors = []
    dirs = set()
    for root in args.results:
        for marker in list(root.rglob("status.json")) + list(root.rglob("checkpoint.json")):
            dirs.add(marker.parent)
    for d in sorted(dirs):
        try:
            task = load_json(d / "task.json")
            if page and task["campaign_id"] != page["campaign_id"]:
                continue
            k = k if k is not None else int(task["k"])
            if int(task["k"]) != k:
                raise ValueError("mixed k values")
            cp = d / "checkpoint.json"
            if cp.exists():
                cpd = load_json(cp)
                nxt = int(cpd["next_n"])
                for c, v in cpd["counters"].items():
                    if c in counters:
                        counters[c] += int(v)
            else:
                nxt = int(task["n_start"])
            first = int(task["n_start"])
            blocks = d / "blocks.jsonl"
            if blocks.exists():
                starts = [int(json.loads(l)["n_start"]) for l in blocks.read_text().splitlines() if l.strip()]
                if starts:
                    first = min(starts)
            if nxt > first:
                covered.append((first, nxt))
            for name, store in (("hits.jsonl", hits), ("incomplete.jsonl", incomplete)):
                path = d / name
                if path.exists():
                    for l in path.read_text(encoding="utf-8").splitlines():
                        if l.strip():
                            rec = json.loads(l)
                            if name == "hits.jsonl":
                                verify_hit(rec, k)
                                store[hit_key(rec)] = rec
                            else:
                                store[rec["n"]] = rec
            status = load_json(d / "status.json") if (d / "status.json").exists() else {}
            if status.get("state") == "error":
                errors.append({"dir": str(d), "error": status.get("error")})
        except Exception as exc:  # noqa: BLE001
            errors.append({"dir": str(d), "error": f"unreadable: {exc}"})

    cov = merge(covered)
    gaps = []
    if page:
        cursor = page["n_start"]
        for a, b in cov:
            if a > cursor:
                gaps.append([cursor, min(a, page["n_stop"])])
            cursor = max(cursor, b)
        if cursor < page["n_stop"]:
            gaps.append([cursor, page["n_stop"]])
        gaps = [g for g in gaps if g[0] < g[1]]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ordered = sorted(hits.values(), key=lambda r: (abs(int(r["n"])), int(r["n"]), int(r["X"])))
    verified = [verify_hit(r, k) for r in ordered]
    with (args.output_dir / "hits.jsonl").open("w", encoding="utf-8") as f:
        for rec in ordered:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    with (args.output_dir / "points.txt").open("w", encoding="utf-8") as f:
        for v in verified:
            f.write(("DESIRED        " if v["desired"] else "non-primitive  ") + line(v) + "\n")
    desired = [v for v in verified if v["desired"]]
    with (args.output_dir / "desired_points.txt").open("w", encoding="utf-8") as f:
        for v in desired:
            f.write(line(v) + "\n")
    with (args.output_dir / "incomplete.txt").open("w", encoding="utf-8") as f:
        for n in sorted(incomplete, key=int):
            f.write(f"n={n}  N={incomplete[n]['N']}\n")
    summary = {"k": k, "covered_n": [list(c) for c in cov], "gaps": gaps, "counters": counters,
               "points": len(verified), "desired_points": len(desired),
               "integer_form_points": sum(v["form"] == "integer" for v in verified),
               "half_form_points": sum(v["form"] == "half" for v in verified),
               "incomplete_n": sorted((int(n) for n in incomplete)), "task_dirs": len(dirs), "errors": errors}
    atomic_json(args.output_dir / "summary.json", summary)
    print(json.dumps({key: summary[key] for key in ("k", "covered_n", "gaps", "points", "desired_points",
                                                    "incomplete_n", "errors")}))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
