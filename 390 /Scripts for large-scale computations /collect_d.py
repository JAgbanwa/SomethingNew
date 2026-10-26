#!/usr/bin/env python3
"""Collect returned d-first outputs: coverage, gaps, and verified hits.

Reads the campaign's page.json, then every status.json (and its hits.jsonl)
found below --results-dir. Coverage is the union of each output directory's
output_coverage for the matching task_id; overlapping returns are allowed and
reported. Every hit is re-verified exactly. Writes summary.json and hits.jsonl.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from run_task import atomic_json, load_json
from dfirst_common import COUNTERS, PAGE_SCHEMA, STATUS_SCHEMA, hit_key, verify_hit


def merge(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for lo, hi in sorted(intervals):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def collect(page_path: Path, results: Path, output: Path) -> dict:
    page = load_json(page_path)
    if page.get("schema") != PAGE_SCHEMA:
        raise ValueError("not a d-first page.json")
    m = int(page["m"])
    tasks = {e["task_id"]: e for e in page["tasks"]}
    cover: dict[str, list[tuple[int, int]]] = {t: [] for t in tasks}
    counters: dict[str, dict[str, int]] = {t: {k: 0 for k in COUNTERS} for t in tasks}
    hits: dict[str, dict] = {}
    workers: set[str] = set()
    errors, unrelated = [], []
    for status_path in sorted(results.rglob("status.json")):
        status = load_json(status_path)
        if status.get("schema") != STATUS_SCHEMA or status.get("task_id") not in tasks:
            unrelated.append(str(status_path))
            continue
        tid = status["task_id"]
        lo, hi = int(status["shells"]["start"]), int(status["shells"]["stop"])
        if status["state"] == "error":
            errors.append({"path": str(status_path), "error": status.get("error", "")})
        c0, c1 = int(status["output_coverage"]["start"]), int(status["output_coverage"]["stop"])
        if not lo <= c0 <= c1 <= hi:
            raise ValueError(f"{status_path}: coverage outside the task's shells")
        if c1 > c0:
            cover[tid].append((c0, c1))
        workers.add(status["worker_sha256"])
        for k in COUNTERS:
            counters[tid][k] += int(status["counters"][k])
        hits_file = status_path.parent / "hits.jsonl"
        if hits_file.exists():
            for line in hits_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    record = json.loads(line)
                    verify_hit(record, m, (lo, hi))
                    hits.setdefault(hit_key(record), record)
    per_task, complete = [], True
    for tid, entry in tasks.items():
        lo, hi = int(entry["shells"]["start"]), int(entry["shells"]["stop"])
        merged = merge(cover[tid])
        gaps, at = [], lo
        for a, b in merged:
            if a > at:
                gaps.append((at, a))
            at = max(at, b)
        if at < hi:
            gaps.append((at, hi))
        complete &= not gaps
        per_task.append({"task_id": tid, "shells": entry["shells"],
                         "covered": [{"start": str(a), "stop": str(b)} for a, b in merged],
                         "gaps": [{"start": str(a), "stop": str(b)} for a, b in gaps],
                         "counters": {k: str(v) for k, v in counters[tid].items()}})
    output.mkdir(parents=True, exist_ok=True)
    with (output / "hits.jsonl").open("w", encoding="utf-8") as out:
        for key in sorted(hits):
            out.write(json.dumps(hits[key], sort_keys=True) + "\n")
    all_cover = merge([iv for t in cover.values() for iv in t])
    summary = {
        "schema": "ce390-dfirst-collection-v1", "campaign_id": page["campaign_id"], "m": page["m"],
        "g_max_digits": page["g_max_digits"], "campaign_shells": page["shells"],
        "all_tasks_complete": complete, "covered_shells": [{"start": str(a), "stop": str(b)} for a, b in all_cover],
        "admissible_d_solved": str(sum(c["admissible"] for c in counters.values())),
        "verified_hits": len(hits), "worker_sha256": sorted(workers), "error_returns": errors,
        "unrelated_status_files": unrelated, "tasks": per_task,
        "statement": ("For every covered shell range [a, b): every d = p/q with a <= max(|p|, q) < b has NO "
                      "half-chart point with 1 <= |g| <= 10^g_max_digits other than the verified hits listed."),
    }
    atomic_json(output / "summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", type=Path, required=True)
    ap.add_argument("--results-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        s = collect(a.page, a.results_dir, a.output_dir)
    except (OSError, ValueError, KeyError) as exc:
        print(f"collect_d: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({k: v for k, v in s.items() if k != "tasks"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
