#!/usr/bin/env python3
"""Merge returned gap-search outputs: d coverage, gaps against page.json, verified hits.

  python3 collect_gap.py --page gap-tasks/page.json --results gap-results --output-dir gap-collected

Every directory under --results (any depth) with a task.json of this campaign
is read; its covered d values are the checkpoint's own [covered_start, d_next).
Writes hits.jsonl (verified, de-duplicated) and summary.json (coverage, gaps,
counters, worker core-seconds, heuristic expected solutions of the covered part).
Exit status 1 if any directory reports an error or a hit fails verification;
2 with --require-complete if the page has gaps.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from gap_common import COUNTERS, METHOD, atomic_json, expected_solutions, load_json, verify_hit


def merge(iv: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", type=Path, required=True)
    ap.add_argument("--results", type=Path, nargs="+", required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--require-complete", action="store_true", help="exit 2 if any part of the page is uncovered")
    a = ap.parse_args()
    page = load_json(a.page)
    k, ratio = int(page["k"]), int(page["ratio_max"])
    covered, errors, hits = [], [], {}
    counters = {c: 0 for c in COUNTERS}
    seconds = 0.0
    shas: set[str] = set()
    lo, hi = int(page["d_start"]), int(page["d_stop"])
    for root in a.results:
        for tj in sorted(root.rglob("task.json")):
            d = tj.parent
            try:
                task = load_json(tj)
                if task.get("campaign_id") != page["campaign_id"]:
                    continue
                if int(task["ratio_max"]) != ratio or int(task["k"]) != k or task.get("method") != METHOD:
                    raise ValueError("task parameters differ from page")
                cp = d / "checkpoint.json"
                if cp.exists():   # the checkpoint is the durable record of finished d values
                    cpd = load_json(cp)
                    if cpd.get("task_id") != task["task_id"] or cpd.get("campaign_id") != page["campaign_id"]:
                        raise ValueError("checkpoint belongs to another task")
                    if int(cpd["k"]) != k or int(cpd["ratio_max"]) != ratio:
                        raise ValueError("checkpoint parameters differ from page")
                    start, nxt, stop = int(cpd["covered_start"]), int(cpd["d_next"]), int(cpd["d_stop"])
                    if not (lo <= start <= nxt <= stop <= hi):
                        raise ValueError(f"checkpoint interval [{start}, {nxt}) outside the page or its task")
                    if nxt > start:
                        covered.append((start, nxt))
                    shas.add(cpd.get("worker_sha256", "unknown"))
                    for c in COUNTERS:
                        counters[c] += int(cpd["counters"].get(c, 0))
                if (d / "hits.jsonl").exists():
                    for line in (d / "hits.jsonl").read_text().splitlines():
                        if line.strip():
                            rec = json.loads(line)
                            verify_hit(rec, k)
                            hits[(rec["x"], rec["y"], rec["z"])] = rec
                st = load_json(d / "status.json") if (d / "status.json").exists() else {}
                seconds += float(st.get("worker_seconds", 0.0))
                if st.get("state") == "error":
                    errors.append({"dir": str(d), "error": st.get("error")})
            except Exception as exc:  # noqa: BLE001
                errors.append({"dir": str(d), "error": f"unreadable or invalid: {exc}"})
    cov = merge(covered)
    gaps, cur = [], lo
    for s, e in cov:
        if s > cur:
            gaps.append([str(cur), str(min(s, hi))])
        cur = max(cur, e)
    if cur < hi:
        gaps.append([str(cur), str(hi)])
    a.output_dir.mkdir(parents=True, exist_ok=True)
    with (a.output_dir / "hits.jsonl").open("w", encoding="utf-8") as f:
        for rec in hits.values():
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    rho = page.get("rho")
    exp = sum(expected_solutions(rho, s, e, ratio) for s, e in cov) if rho else None
    summary = {"campaign_id": page["campaign_id"], "k": k, "ratio_max": ratio,
               "covered_d": [[str(s), str(e)] for s, e in cov], "gaps": gaps,
               "d_values_covered": sum(e - s for s, e in cov), "counters": counters,
               "worker_core_hours": round(seconds / 3600, 3), "hits": len(hits),
               "heuristic_expected_solutions_covered": exp, "worker_sha256": sorted(shas), "errors": errors}
    atomic_json(a.output_dir / "summary.json", summary)
    print(json.dumps({key: summary[key] for key in ("hits", "gaps", "d_values_covered", "worker_core_hours", "errors")},
                     indent=1))
    for rec in hits.values():
        print(f"SOLUTION: {rec['x']}^3 + {rec['y']}^3 + {rec['z']}^3 = {k}")
    if errors:
        return 1
    return 2 if (a.require_complete and gaps) else 0


if __name__ == "__main__":
    sys.exit(main())
