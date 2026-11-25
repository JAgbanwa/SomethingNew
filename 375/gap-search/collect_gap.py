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
from math import gcd, isfinite
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


def checked_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{label} must be an integer")
    return int(value)


def checked_counters(record: dict, label: str) -> dict[str, int]:
    if not isinstance(record.get("counters"), dict):
        raise ValueError(f"{label} counters must be an object")
    counters = {key: checked_int(record["counters"][key], f"{label}.{key}") for key in COUNTERS}
    if any(value < 0 for value in counters.values()):
        raise ValueError(f"{label} has a negative counter")
    if counters["hits_primitive"] > counters["hits"]:
        raise ValueError(f"{label} has more primitive hits than hits")
    return counters


def read_jsonl(path: Path) -> list[dict]:
    """A missing or partially written artifact cannot certify an empty result."""
    records = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.endswith("\n"):
                raise ValueError(f"{path.name}:{number}: truncated JSONL record (missing newline)")
            if line.strip():
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError(f"{path.name}:{number}: record must be an object")
                records.append(record)
    return records


def checked_hit(record: dict, k: int, start: int, stop: int, ratio: int) -> tuple[tuple[int, int, int], dict]:
    if record.get("type") != "hit" or record.get("method", METHOD) != METHOD:
        raise ValueError("hit has an unsupported type or method")
    for key in ("k", "x", "y", "z", "d"):
        checked_int(record[key], f"hit.{key}")
    if "primitive" in record and type(record["primitive"]) is not bool:
        raise ValueError("hit primitive flag must be Boolean")
    identity = verify_hit(record, k)
    d, z = int(record["d"]), identity[2]
    if not start <= d < stop or not 3847 * d // 1000 <= abs(z) <= ratio * d:
        raise ValueError("hit lies outside its task's d or |z| search interval")
    normalized = dict(record)
    normalized.update({key: str(int(record[key])) for key in ("k", "x", "y", "z", "d")})
    normalized["primitive"] = gcd(*identity) == 1
    return identity, normalized


def load_result_directory(directory: Path, page: dict, expected_sha: str | None = None,
                          observed_hashes: set[str] | None = None) -> dict | None:
    """Validate one returned directory without crediting any of its data yet.

    Checkpoint counters refer to the durable prefix. The hit log may additionally
    contain hits from an interrupted next chunk, which are preserved on resume.
    Chunk logs may likewise contain replayed records; only the latest contiguous
    partition of the durable prefix contributes counters or audit work.
    """
    task = load_json(directory / "task.json")
    if not isinstance(task, dict):
        raise ValueError("task must be an object")
    if task.get("campaign_id") != page["campaign_id"]:
        return None
    t = validate_task(task)
    k, ratio = int(page["k"]), int(page["ratio_max"])
    primitive = page.get("primitive", True)
    lo, hi = int(page["d_start"]), int(page["d_stop"])
    if (t["ratio_max"] != ratio or t["k"] != k or task.get("method") != METHOD
            or t["primitive"] is not primitive or not lo <= t["d_start"] < t["d_stop"] <= hi):
        raise ValueError("task parameters differ from page")
    cp_path = directory / "checkpoint.json"
    cp = load_json(cp_path) if cp_path.exists() else None
    status = load_json(directory / "status.json")
    if not isinstance(status, dict) or (cp_path.exists() and not isinstance(cp, dict)):
        raise ValueError("status and checkpoint must be objects")
    local_shas: set[str] = set()

    def check_hash(record, label, *, required=True):
        if "worker_sha256" not in record:
            if required:
                raise ValueError(f"{label} has no worker SHA-256")
            return
        digest = checked_sha256(record["worker_sha256"])
        local_shas.add(digest)
        if observed_hashes is not None:
            observed_hashes.add(digest)
        if expected_sha and digest != expected_sha:
            raise ValueError(f"{label} worker SHA-256 {digest} differs from expected {expected_sha}")

    for label, record in (("checkpoint", cp), ("status", status)):
        if record is not None:
            check_hash(record, label, required=label != "status" or record.get("state") != "error")
    if status.get("state") == "error":
        raise ValueError(f"task reported an error: {status.get('error')}")
    if status.get("state") not in ("running", "partial", "complete"):
        raise ValueError("status has an unsupported state")
    for label, record, schema in (("checkpoint", cp, CHECKPOINT_SCHEMA), ("status", status, STATUS_SCHEMA)):
        if record is None:
            continue
        if (record.get("schema") != schema or record.get("task_id") != task["task_id"]
                or record.get("campaign_id") != page["campaign_id"]):
            raise ValueError(f"{label} belongs to another task or schema")
        if (int(record["k"]) != k or int(record["ratio_max"]) != ratio
                or record.get("primitive", True) is not primitive or record.get("method", METHOD) != METHOD):
            raise ValueError(f"{label} parameters differ from page")

    start = nxt = t["d_start"]
    counters = dict.fromkeys(COUNTERS, 0)
    if cp is not None:
        start, nxt, stop = (checked_int(cp[key], f"checkpoint.{key}")
                            for key in ("covered_start", "d_next", "d_stop"))
        if not lo <= start <= t["d_start"] <= nxt <= stop <= hi or stop != t["d_stop"]:
            raise ValueError(f"checkpoint interval [{start}, {nxt}) outside the page or its task")
        if nxt == stop and cp.get("terminal_state") != "complete" and status["state"] != "complete":
            raise ValueError("endpoint checkpoint has no confirmed complete terminal state")
        if cp.get("terminal_state") == "complete" and nxt != stop:
            raise ValueError("complete checkpoint stops before the task endpoint")
        counters = checked_counters(cp, "checkpoint")
    if counters["d_total"] != nxt - start:
        raise ValueError("checkpoint d_total disagrees with its covered interval")

    st_next = checked_int(status["d_next"], "status.d_next")
    st_counters = checked_counters(status, "status")
    if (int(status["covered_start"]) != start or int(status["d_start"]) != t["d_start"]
            or int(status["d_stop"]) != t["d_stop"] or not t["d_start"] <= st_next <= nxt
            or st_counters["d_total"] != st_next - start):
        raise ValueError("status interval disagrees with the task or checkpoint")
    if status["state"] == "running":
        if any(st_counters[key] > counters[key] for key in COUNTERS):
            raise ValueError("running status counters exceed the durable checkpoint")
    elif st_next != nxt or st_counters != counters:
        raise ValueError("terminal status counters or cursor disagree with the checkpoint")
    if status["state"] == "complete" and (cp is None or nxt != t["d_stop"]):
        raise ValueError("complete status has no matching completed checkpoint")
    if status["state"] == "partial" and nxt == t["d_stop"]:
        raise ValueError("partial status reaches the task endpoint")

    hits = {}
    for record in read_jsonl(directory / "hits.jsonl"):
        identity, normalized = checked_hit(record, k, start, t["d_stop"], ratio)
        check_hash(record, "hit")
        hits[identity] = normalized
    saved_count = checked_int(status["hits"], "status.hits")
    if saved_count < 0 or (len(hits) < saved_count if status["state"] == "running" else len(hits) != saved_count):
        raise ValueError("saved hit count disagrees with status.hits (missing, truncated or unexpected hits)")
    committed_hits = [record for record in hits.values() if int(record["d"]) < nxt]
    if len(committed_hits) != counters["hits"] or sum(r["primitive"] for r in committed_hits) != counters["hits_primitive"]:
        raise ValueError("saved hits in the durable interval disagree with checkpoint hit counters")

    chunks = read_jsonl(directory / "chunks.jsonl")
    for record in chunks:
        if record.get("type") != "chunk":
            raise ValueError("chunk log contains a non-chunk record")
        a, b = (checked_int(record[key], f"chunk.{key}") for key in ("d_start", "d_stop"))
        if not start <= a < b <= t["d_stop"]:
            raise ValueError("chunk lies outside its task interval")
        check_hash(record, "chunk")
        if checked_counters(record, "chunk")["d_total"] != b - a:
            raise ValueError("chunk d_total disagrees with its interval")
    selected, cursor = [], nxt
    if cursor > start:
        for record in reversed(chunks):
            if int(record["d_stop"]) == cursor:
                selected.append(record)
                cursor = int(record["d_start"])
                if cursor == start:
                    break
    if cursor != start:
        raise ValueError("chunk log does not cover the durable checkpoint interval")
    selected.reverse()
    if {key: sum(int(record["counters"][key]) for record in selected) for key in COUNTERS} != counters:
        raise ValueError("committed chunk counters disagree with the checkpoint")
    if len(local_shas) != 1:
        raise ValueError("directory contains mixed worker SHA-256 values")
    seconds = max(float(status.get("worker_seconds", 0)), float((cp or {}).get("worker_seconds", 0)))
    if not isfinite(seconds) or seconds < 0:
        raise ValueError("invalid worker_seconds")
    return {"directory": directory, "task": task, "checkpoint": cp, "status": status,
            "interval": (start, nxt) if nxt > start else None, "counters": counters,
            "hits": hits, "chunks": selected, "worker_sha256": next(iter(local_shas)), "seconds": seconds}


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
            result = load_result_directory(d, page, expected_sha, shas)
            # Nothing from this directory is accepted until every certificate and
            # provenance check passes. A corrupt hit cannot leave behind coverage.
            if result is not None:
                staged.append(result)
        except Exception as exc:  # noqa: BLE001
            errors.append({"dir": str(d), "error": f"unreadable or invalid: {exc}"})

    if len(shas) > 1:
        errors.append({"dir": "all results", "error": "mixed worker SHA-256 values; collect one release at a time"})
        staged = []
    if expected_sha and shas - {expected_sha}:
        errors.append({"dir": "all results", "error": "unexpected worker SHA-256; no returned coverage accepted"})
        staged = []
    for result in staged:
        interval = result["interval"]
        if interval:
            covered.append(interval)
        for c in COUNTERS:
            counters[c] += result["counters"][c]
        hits.update(result["hits"])
        seconds += result["seconds"]
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
