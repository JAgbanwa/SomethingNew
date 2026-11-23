#!/usr/bin/env python3
"""Merge returned CE375 task outputs: coverage, gaps, and verified hits.

Point --results at one or more directories. Every subdirectory (any depth)
holding a status.json or checkpoint.json is read as one task output. Covered
heights per task are [h_start, next_h). Every hit is re-verified exactly.

Writes to --output-dir:
  hits.jsonl             verified, de-duplicated hits (both charts, all primitivity)
  desired_hits.jsonl     only the desired (primitive) hits
  desired_d_values.txt   THE RESULT: d with a primitive point, with chart and (n, x, s)
  d_values.txt           every d found, each line tagged DESIRED or non-primitive
  summary.json           coverage, gaps against page.json, counters
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from common375 import (CHECKPOINT_SCHEMA, COUNTERS, G_VALUES, MAX_H, MODES, PAGE_SCHEMA,
                       PARAMETERIZATION, STATUS_SCHEMA, atomic_json, check_k, hit_key,
                       load_json, validate_scope, validate_task, verify_hit)


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
    k = int(page["k"]) if page else None
    mode = page.get("mode", "xy") if page else None
    campaign_id = page["campaign_id"] if page else None
    if page:
        try:
            validate_scope(page, PAGE_SCHEMA)
            check_k(k)
            if mode not in MODES or not 1 <= int(page["h_start"]) < int(page["h_stop"]) <= MAX_H + 1:
                raise ValueError("invalid page mode or height range")
        except (KeyError, ValueError) as exc:
            print(f"collect: {exc}", file=sys.stderr)
            return 1
    covered: list[tuple[int, int]] = []
    counters = {c: 0 for c in COUNTERS}
    hits: dict[str, dict] = {}
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
            t = validate_task(task)
            if k is not None and t["k"] != k:
                raise ValueError("mixed k values")
            if mode is not None and t["mode"] != mode:
                raise ValueError("mixed search modes")
            if campaign_id is not None and task["campaign_id"] != campaign_id:
                raise ValueError("mixed campaigns")
            start = t["h_start"]
            cp = d / "checkpoint.json"
            status_path = d / "status.json"
            status = load_json(status_path) if status_path.exists() else {}
            checkpoint = load_json(cp) if cp.exists() else {}
            for record, schema in ((status, STATUS_SCHEMA), (checkpoint, CHECKPOINT_SCHEMA)):
                if not record:
                    continue
                validate_scope(record, schema)
                if record.get("campaign_id") != task["campaign_id"] or record.get("task_id") != task["task_id"] \
                        or int(record["k"]) != t["k"] or record.get("mode") != t["mode"]:
                    raise ValueError("result metadata does not match its task")
            nxt = int(checkpoint["next_h"]) if checkpoint else int(status.get("next_h", start))
            if not start <= nxt <= t["h_stop"]:
                raise ValueError("result cursor lies outside the task range")
            task_counters = {c: 0 for c in COUNTERS}
            if cp.exists():
                for c, v in checkpoint["counters"].items():
                    if c in task_counters:
                        task_counters[c] += int(v)
            # coverage of this directory: from the first shell it ran to next_h
            first = start
            shells = d / "shells.jsonl"
            if shells.exists():
                hs = [json.loads(line)["h"] for line in shells.read_text().splitlines() if line.strip()]
                if hs:
                    first = min(hs)
            task_hits = {}
            hp = d / "hits.jsonl"
            if hp.exists():
                for line in hp.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        rec = json.loads(line)
                        verify_hit(rec, t["k"])
                        if rec.get("mode", "both") != t["mode"]:
                            raise ValueError("hit mode does not match its task")
                        task_hits[hit_key(rec)] = rec
            # Commit this directory only after all scope and certificate checks pass.
            k, mode, campaign_id = t["k"], t["mode"], task["campaign_id"]
            if nxt > first:
                covered.append((first, nxt))
            for c, v in task_counters.items():
                counters[c] += v
            hits.update(task_hits)
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
    desired = [rec for rec in ordered if verify_hit(rec, k)["desired"]]
    with (args.output_dir / "desired_hits.jsonl").open("w", encoding="utf-8") as f:
        for rec in desired:
            f.write(json.dumps(rec, sort_keys=True) + "\n")

    def line(v: dict) -> str:
        if v.get("mode") in ("xy", "xy-half"):
            if v["chart"] == "integer":
                return (f"d = {v['d']}  chart=integer  n={v['n']}  x={int(v['X']) // 2}  y=+-{int(v['Y']) // 2}  "
                        f"cubes={','.join(v['cubes'])}  gcd(n,x,y)={v['point_gcd']}  gcd_cubes={v['cube_gcd']}")
            return (f"d = {v['d']}  chart=half  n={v['n']}  x={v['X']}/2  y=+-{v['Y']}/2  "
                    f"cubes={','.join(v['cubes'])}  gcd(X,Y)={v['point_gcd']}  gcd_cubes={v['cube_gcd']}")
        return (f"d = {v['d']}  chart={v['chart']}  n={v['n']}  x={v['x']}  s={v['s']}  "
                f"cubes={','.join(v['cubes'])}  gcd_point={v['point_gcd']}  gcd_cubes={v['cube_gcd']}")
    with (args.output_dir / "d_values.txt").open("w", encoding="utf-8") as f:
        for rec in ordered:
            v = verify_hit(rec, k)
            f.write(("DESIRED        " if v["desired"] else "non-primitive  ") + line(v) + "\n")
    with (args.output_dir / "desired_d_values.txt").open("w", encoding="utf-8") as f:
        for rec in desired:
            f.write(line(verify_hit(rec, k)) + "\n")
    summary = {"k": k, "mode": mode, "campaign_id": campaign_id,
               "covered_heights": [list(c) for c in cov], "gaps": gaps,
               "g_values": list(G_VALUES), "parameterization": PARAMETERIZATION, "counters": counters,
               "hits": len(ordered), "desired_hits": len(desired),
               "desired_d_values": sorted({f"{r['d_num']}/{r['d_den']}" for r in desired}),
               "integer_chart_hits": sum(r["chart"] == "integer" for r in ordered),
               "half_chart_hits": sum(r["chart"] == "half" for r in ordered),
               "task_dirs": len(dirs), "errors": errors}
    atomic_json(args.output_dir / "summary.json", summary)
    print(json.dumps({k2: summary[k2] for k2 in ("k", "covered_heights", "gaps", "hits", "desired_hits", "errors")}, indent=1))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
