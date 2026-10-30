#!/usr/bin/env python3
"""Merge returned CE627 task outputs: coverage, gaps, and verified hits.

Point --results at one or more directories. Every subdirectory (any depth)
holding a status.json or checkpoint.json is read as one task output. Covered
heights per task are [h_start, next_h). Every hit is re-verified exactly.

Writes to --output-dir:
  hits.jsonl     verified, de-duplicated hits (both charts)
  d_values.txt   distinct rational d found, with chart and (n, x, s)
  summary.json   coverage, gaps against page.json, counters
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from common627 import COUNTERS, hit_key, load_json, verify_hit, atomic_json


def merge(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


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
    errors, digits = [], set()
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
            digits.add(int(task["g_max_digits"]))
            start = int(task["h_start"])
            nxt = int(load_json(d / "checkpoint.json")["next_h"]) if (d / "checkpoint.json").exists() \
                else int(load_json(d / "status.json").get("next_h", start))
            cp = d / "checkpoint.json"
            if cp.exists():
                for c, v in load_json(cp)["counters"].items():
                    if c in counters:
                        counters[c] += int(v)
            # coverage of this directory: from the first shell it ran to next_h
            first = start
            shells = d / "shells.jsonl"
            if shells.exists():
                hs = [json.loads(line)["h"] for line in shells.read_text().splitlines() if line.strip()]
                if hs:
                    first = min(hs)
            if nxt > first:
                covered.append((first, nxt))
            hp = d / "hits.jsonl"
            if hp.exists():
                for line in hp.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        rec = json.loads(line)
                        verify_hit(rec, k)
                        hits[hit_key(rec)] = rec
            status = load_json(d / "status.json") if (d / "status.json").exists() else {}
            if status.get("state") == "error":
                errors.append({"dir": str(d), "error": status.get("error")})
        except Exception as exc:  # noqa: BLE001
            errors.append({"dir": str(d), "error": f"unreadable: {exc}"})

    cov = merge(covered)
    gaps = []
    if page:
        cursor = page["h_start"]
        for a, b in cov:
            if a > cursor:
                gaps.append([cursor, min(a, page["h_stop"])])
            cursor = max(cursor, b)
        if cursor < page["h_stop"]:
            gaps.append([cursor, page["h_stop"]])
        gaps = [g for g in gaps if g[0] < g[1]]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ordered = sorted(hits.values(), key=lambda r: (max(abs(int(r["d_num"])), int(r["d_den"])), r["d_den"], r["d_num"]))
    with (args.output_dir / "hits.jsonl").open("w", encoding="utf-8") as f:
        for rec in ordered:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    with (args.output_dir / "d_values.txt").open("w", encoding="utf-8") as f:
        for rec in ordered:
            v = verify_hit(rec, k)
            f.write(f"d = {v['d']}  chart={v['chart']}  n={v['n']}  x={v['x']}  s={v['s']}  "
                    f"cubes={','.join(v['cubes'])}\n")
    summary = {"k": k, "covered_heights": [list(c) for c in cov], "gaps": gaps,
               "g_max_digits": sorted(digits), "counters": counters,
               "hits": len(ordered), "integer_chart_hits": sum(r["chart"] == "integer" for r in ordered),
               "half_chart_hits": sum(r["chart"] == "half" for r in ordered),
               "task_dirs": len(dirs), "errors": errors}
    atomic_json(args.output_dir / "summary.json", summary)
    print(json.dumps({k2: summary[k2] for k2 in ("k", "covered_heights", "gaps", "hits", "errors")}, indent=1))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
