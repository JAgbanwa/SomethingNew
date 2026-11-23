#!/usr/bin/env python3
"""Merge returned gap-search outputs: d coverage, gaps against page.json, verified hits.

  python3 collect_gap.py --page gap-tasks/page.json --results gap-results --output-dir gap-collected

Every directory under --results (any depth) with a task.json of this campaign
is read; its covered d values are the checkpoint's own [covered_start, d_next).
Writes hits.jsonl (verified, de-duplicated) and summary.json (coverage, gaps,
counters, worker core-seconds, heuristic expected solutions of the covered part).
Exit status 1 if any directory reports an error or a hit fails verification;
2 with --require-complete if the page has gaps.
All returned artifacts must identify one worker SHA-256. Mixed binaries are
rejected; --expected-worker-sha256 additionally pins the intended release.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from gap_common import (CHECKPOINT_SCHEMA, COUNTERS, METHOD, PAGE_SCHEMA, STATUS_SCHEMA,
                        atomic_json, expected_solutions, load_json, validate_task, verify_hit)


def merge(iv: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def checked_sha256(value: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise ValueError("worker SHA-256 must be 64 hexadecimal characters")
    return value.lower()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", type=Path, required=True)
    ap.add_argument("--results", type=Path, nargs="+", required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--require-complete", action="store_true", help="exit 2 if any part of the page is uncovered")
    ap.add_argument("--expected-worker-sha256", help="accept results only from this exact worker binary SHA-256")
    a = ap.parse_args()
    try:
        expected_sha = checked_sha256(a.expected_worker_sha256) if a.expected_worker_sha256 is not None else None
    except ValueError as exc:
        ap.error(str(exc))
    page = load_json(a.page)
    if page.get("schema") != PAGE_SCHEMA or page.get("method") != METHOD:
        ap.error("page has an unsupported schema or method")
    k, ratio = int(page["k"]), int(page["ratio_max"])
    primitive, frontier = bool(page.get("primitive", True)), float(page.get("frontier", 0) or 0)
    covered, errors, hits = [], [], {}
    counters = {c: 0 for c in COUNTERS}
    seconds = 0.0
    shas: set[str] = set()
    staged = []
    lo, hi = int(page["d_start"]), int(page["d_stop"])
    task_paths = {tj.resolve() for root in a.results for tj in root.rglob("task.json")}
    for tj in sorted(task_paths):
        d = tj.parent
        try:
            task = load_json(tj)
            if task.get("campaign_id") != page["campaign_id"]:
                continue
            t = validate_task(task)
            if (t["ratio_max"] != ratio or t["k"] != k or task.get("method") != METHOD
                    or t["primitive"] != primitive):
                raise ValueError("task parameters differ from page")
            cp = d / "checkpoint.json"
            cpd = load_json(cp) if cp.exists() else None
            st = load_json(d / "status.json") if (d / "status.json").exists() else {}
            local_shas = set()

            def check_hash(record, label, *, required=True):
                if "worker_sha256" not in record:
                    if required:
                        raise ValueError(f"{label} has no worker SHA-256")
                    return
                digest = checked_sha256(record["worker_sha256"])
                local_shas.add(digest)
                shas.add(digest)
                if expected_sha and digest != expected_sha:
                    raise ValueError(f"{label} worker SHA-256 {digest} differs from expected {expected_sha}")

            if cpd:
                check_hash(cpd, "checkpoint")
            if st:
                check_hash(st, "status", required=st.get("state") != "error")
                if st.get("state") == "error":
                    raise ValueError(f"task reported an error: {st.get('error')}")
            for label, record, schema in (("checkpoint", cpd, CHECKPOINT_SCHEMA), ("status", st, STATUS_SCHEMA)):
                if not record:
                    continue
                if (record.get("schema") != schema or record.get("task_id") != task["task_id"]
                        or record.get("campaign_id") != page["campaign_id"]):
                    raise ValueError(f"{label} belongs to another task or schema")
                if (int(record["k"]) != k or int(record["ratio_max"]) != ratio
                        or record.get("primitive", True) is not primitive
                        or record.get("method", METHOD) != METHOD):
                    raise ValueError(f"{label} parameters differ from page")
            task_interval = None
            task_counters = {c: 0 for c in COUNTERS}
            if cpd:   # the checkpoint is the durable record of finished d values
                start, nxt, stop = int(cpd["covered_start"]), int(cpd["d_next"]), int(cpd["d_stop"])
                if not (lo <= start <= t["d_start"] <= nxt <= stop <= hi) or stop != t["d_stop"]:
                    raise ValueError(f"checkpoint interval [{start}, {nxt}) outside the page or its task")
                if nxt == stop and cpd.get("terminal_state") != "complete" and st.get("state") != "complete":
                    raise ValueError("endpoint checkpoint has no confirmed complete terminal state")
                if nxt > start:
                    task_interval = (start, nxt)
                for c in COUNTERS:
                    task_counters[c] = int(cpd["counters"][c])
                    if task_counters[c] < 0:
                        raise ValueError("checkpoint has a negative counter")
            if st.get("state") == "complete" and (not cpd or int(st["d_next"]) != t["d_stop"]
                                                   or int(cpd["d_next"]) != t["d_stop"]):
                raise ValueError("complete status has no matching completed checkpoint")
            task_hits = {}
            if (d / "hits.jsonl").exists():
                for line in (d / "hits.jsonl").read_text().splitlines():
                    if line.strip():
                        rec = json.loads(line)
                        verify_hit(rec, k)
                        check_hash(rec, "hit", required=not local_shas)
                        task_hits[(rec["x"], rec["y"], rec["z"])] = rec
            if len(local_shas) > 1:
                raise ValueError("directory contains mixed worker SHA-256 values")
            # Nothing from this directory is accepted until every certificate and
            # provenance check passes. A corrupt hit cannot leave behind coverage.
            staged.append((task_interval, task_counters, task_hits, float(st.get("worker_seconds", 0.0))))
        except Exception as exc:  # noqa: BLE001
            errors.append({"dir": str(d), "error": f"unreadable or invalid: {exc}"})

    if len(shas) > 1:
        errors.append({"dir": "all results", "error": "mixed worker SHA-256 values; collect one release at a time"})
        staged = []
    if expected_sha and shas - {expected_sha}:
        errors.append({"dir": "all results", "error": "unexpected worker SHA-256; no returned coverage accepted"})
        staged = []
    for interval, task_counters, task_hits, task_seconds in staged:
        if interval:
            covered.append(interval)
        for c in COUNTERS:
            counters[c] += task_counters[c]
        hits.update(task_hits)
        seconds += task_seconds
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
    exp_over_rho = sum(expected_solutions(1.0, s, e, ratio, frontier) for s, e in cov) if cov else 0.0
    exp = rho * exp_over_rho if rho else None
    prim_hits = [r for r in hits.values() if r.get("primitive")]
    summary = {"campaign_id": page["campaign_id"], "k": k, "ratio_max": ratio, "primitive": primitive,
               "frontier": frontier, "primitive_hits": len(prim_hits),
               "heuristic_expected_over_rho_covered": exp_over_rho,
               "covered_d": [[str(s), str(e)] for s, e in cov], "gaps": gaps,
               "d_values_covered": sum(e - s for s, e in cov), "counters": counters,
               "worker_core_hours": round(seconds / 3600, 3), "hits": len(hits),
               "heuristic_expected_solutions_covered": exp, "worker_sha256": sorted(shas),
               "expected_worker_sha256": expected_sha, "errors": errors}
    atomic_json(a.output_dir / "summary.json", summary)
    print(json.dumps({key: summary[key] for key in ("hits", "primitive_hits", "gaps", "d_values_covered",
                                                     "worker_core_hours", "errors")}, indent=1))
    for rec in hits.values():
        tag = "PRIMITIVE" if rec.get("primitive") else "non-primitive"
        print(f"SOLUTION ({tag}): {rec['x']}^3 + {rec['y']}^3 + {rec['z']}^3 = {k}")
    if errors:
        return 1
    return 2 if (a.require_complete and gaps) else 0


if __name__ == "__main__":
    sys.exit(main())
