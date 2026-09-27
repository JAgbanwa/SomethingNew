#!/usr/bin/env python3
"""Validate and collect returned CE390 jobs; certify only selected-page coverage."""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

from run_task import (HEX64, MAX_LINE_BYTES, atomic_json, candidate, canonical, certificate_key,
                      integer, keys, load_json, task_identity, validate_task)
from verify import Bounds, verify_record


def interval(value: Any, context: str) -> tuple[int, int]:
    keys(value, {"start", "stop"}, set(), context)
    start = integer(value["start"], context + ".start")
    stop = integer(value["stop"], context + ".stop")
    if start > stop:
        raise ValueError(f"{context}: reversed interval")
    return start, stop


def intervals_json(values: list[tuple[int, int]]) -> list[dict[str, str]]:
    return [{"start": str(a), "stop": str(b)} for a, b in values]


def merge_coverage(values: list[tuple[int, int]], start: int, stop: int) -> dict[str, Any]:
    merged: list[tuple[int, int]] = []
    total = sum(b - a for a, b in values)
    for a, b in sorted(values):
        if a == b:
            continue
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    gaps = []
    cursor = start
    for a, b in merged:
        if cursor < a:
            gaps.append((cursor, a))
        cursor = b
    if cursor < stop:
        gaps.append((cursor, stop))
    covered = sum(b - a for a, b in merged)
    return {"coverage": intervals_json(merged), "gaps": intervals_json(gaps),
            "covered_indices": str(covered), "overlapping_returned_indices": str(total - covered),
            "complete": not gaps}


def selected_tasks(pages: list[Path]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    campaign_definitions: dict[str, tuple[Any, ...]] = {}
    for page_path in pages:
        page = load_json(page_path)
        keys(page, {"schema", "campaign_id", "total_candidate_indices", "total_tasks",
                    "page_start", "page_task_count", "next_page_start", "candidates_per_task",
                    "tasks", "coverage_note"}, set(), f"page {page_path}")
        if page["schema"] != "ce390-page-v2" or not isinstance(page["tasks"], list):
            raise ValueError(f"invalid task page: {page_path}")
        count = integer(page["total_candidate_indices"], "page.total_candidate_indices", positive=True)
        size = integer(page["candidates_per_task"], "page.candidates_per_task", positive=True)
        total_tasks = integer(page["total_tasks"], "page.total_tasks", positive=True)
        start = integer(page["page_start"], "page.page_start")
        entries = page["tasks"]
        if (type(page["page_task_count"]) is not int or page["page_task_count"] != len(entries)
                or not entries or len(entries) > 10000 or total_tasks != (count + size - 1) // size
                or start + len(entries) > total_tasks):
            raise ValueError(f"inconsistent task-page counts: {page_path}")
        next_start = str(start + len(entries)) if start + len(entries) < total_tasks else None
        if page["next_page_start"] != next_start:
            raise ValueError(f"inconsistent next_page_start: {page_path}")
        for offset, entry in enumerate(entries):
            keys(entry, {"ordinal", "file", "task_id", "slice"}, set(), "page task entry")
            ordinal = integer(entry["ordinal"], "entry.ordinal")
            name = entry["file"]
            if (ordinal != start + offset or not isinstance(name, str)
                    or not name or Path(name).name != name or name in {".", ".."}):
                raise ValueError("invalid task ordinal or task filename")
            path = page_path.parent / name
            if path.is_symlink():
                raise ValueError(f"task file must not be a symlink: {path}")
            task = load_json(path)
            parsed = validate_task(task)
            if (task["task_id"] != entry["task_id"] or task["slice"] != entry["slice"]
                    or task["campaign_id"] != page["campaign_id"] or parsed["count"] != count
                    or (parsed["start"], parsed["stop"]) != (ordinal * size, min((ordinal + 1) * size, count))):
                raise ValueError(f"page does not bind its original task: {path}")
            definition = (canonical(task["search"]), canonical(task["fibers"]), count, size)
            prior = campaign_definitions.setdefault(task["campaign_id"], definition)
            if prior != definition:
                raise ValueError("one campaign_id refers to conflicting campaign definitions")
            tid = task["task_id"]
            if tid in selected:
                raise ValueError(f"selected pages overlap at task {tid}")
            selected[tid] = {"task": task, "parsed": parsed, "ordinal": str(ordinal),
                             "intervals": [], "returns": [], "worker_sha256": None,
                             "a_index": {a: i for i, a in enumerate(parsed["a_values"])}}
    if not selected:
        raise ValueError("at least one nonempty task page is required")
    return selected


def checked_status(status: Any, original: dict[str, Any], returned: dict[str, Any]) -> tuple[tuple[int, int], tuple[int, int]]:
    required = {"schema", "task_id", "campaign_id", "worker_sha256", "state", "reason", "complete",
                "started_utc", "updated_utc", "elapsed_seconds", "time_limit_seconds", "slice",
                "invocation_coverage", "next_index", "remaining_indices", "counters_this_invocation",
                "unique_hits_in_this_output", "coverage_note"}
    keys(status, required, {"output_coverage"}, "returned status")
    parsed = validate_task(returned)
    if (status["schema"] != "ce390-status-v2" or status["task_id"] != original["task_id"]
            or status["campaign_id"] != original["campaign_id"] or status["slice"] != original["slice"]
            or returned["task_id"] != original["task_id"] or task_identity(returned) != task_identity(original)):
        raise ValueError("returned status/task identity does not match the selected original task")
    sha = status["worker_sha256"]
    if not isinstance(sha, str) or not HEX64.fullmatch(sha):
        raise ValueError("invalid returned worker SHA256")
    for task in (original, returned):
        if task.get("expected_worker_sha256", sha) != sha:
            raise ValueError("returned worker differs from the task's pinned worker")
    state = status["state"]
    if state not in {"complete", "partial", "running", "error"} or type(status["complete"]) is not bool:
        raise ValueError("invalid returned state/complete marker")
    if (any(not isinstance(status[k], str) for k in ("reason", "started_utc", "updated_utc", "coverage_note"))
            or type(status["elapsed_seconds"]) not in (int, float)
            or not math.isfinite(status["elapsed_seconds"]) or status["elapsed_seconds"] < 0
            or type(status["time_limit_seconds"]) is not int
            or status["time_limit_seconds"] != returned["execution"]["time_limit_seconds"]):
        raise ValueError("malformed returned status metadata")
    cursor = integer(status["next_index"], "status.next_index")
    invocation = interval(status["invocation_coverage"], "status.invocation_coverage")
    coverage = interval(status.get("output_coverage", status["invocation_coverage"]), "status.output_coverage")
    start, stop = parsed["start"], parsed["stop"]
    if not (start <= coverage[0] <= invocation[0] <= invocation[1] == coverage[1] == cursor <= stop):
        raise ValueError("returned coverage/cursor is outside or inconsistent with its task slice")
    if invocation[0] < parsed["resume"]:
        raise ValueError("invocation starts before its supplied resume_index")
    if integer(status["remaining_indices"], "status.remaining_indices") != stop - cursor:
        raise ValueError("returned remaining-index count is inconsistent")
    if status["complete"] != (state == "complete" and cursor == stop) or (state == "complete" and cursor != stop):
        raise ValueError("complete state does not match the final cursor")
    counters = status["counters_this_invocation"]
    keys(counters, {"fibers_completed", "non_coprime_skipped", "new_hits", "convergents"},
         {"cf_fibers_completed", "congruence_excluded", "bounds_excluded"}, "status counters")
    counters = {k: integer(v, "status counter " + k) for k, v in counters.items()}
    if "cf_fibers_completed" in counters:
        if not {"congruence_excluded", "bounds_excluded"} <= counters.keys():
            raise ValueError("incomplete categorized fiber counters")
        completed = sum(counters[k] for k in ("cf_fibers_completed", "non_coprime_skipped",
                                               "congruence_excluded", "bounds_excluded"))
    else:
        completed = counters["fibers_completed"] + counters["non_coprime_skipped"] + counters.get("congruence_excluded", 0)
    if completed != invocation[1] - invocation[0]:
        raise ValueError("completed-fiber counters disagree with invocation coverage")
    integer(status["unique_hits_in_this_output"], "status.unique_hits_in_this_output")
    return invocation, coverage


def collect(pages: list[Path], results_dir: Path, output_dir: Path, *, skip_unrelated: bool = False) -> dict[str, Any]:
    selected = selected_tasks(pages)
    if not results_dir.is_dir():
        raise ValueError("results-dir must be an existing directory")
    certificates: dict[str, dict[str, Any]] = {}
    unrelated: list[str] = []
    error_returns: list[str] = []
    running_returns: list[str] = []
    certificate_rows = 0
    output_root = output_dir.resolve()
    for orphan in sorted(results_dir.rglob("hits.jsonl")):
        if orphan.parent.resolve() == output_root or (orphan.parent / "status.json").is_file():
            continue
        relative = str(orphan.parent.relative_to(results_dir))
        if not skip_unrelated:
            raise ValueError(f"returned hits have no adjacent status.json: {orphan}")
        unrelated.append(relative)
    for path in sorted(results_dir.rglob("status.json")):
        status = load_json(path)
        if not isinstance(status, dict) or not isinstance(status.get("task_id"), str):
            raise ValueError(f"missing task identity in {path}")
        tid = status["task_id"]
        relative = str(path.parent.relative_to(results_dir))
        if tid not in selected:
            if skip_unrelated:
                unrelated.append(relative)
                continue
            raise ValueError(f"unselected returned task in {path}; use --skip-unrelated to skip explicitly")
        slot = selected[tid]
        returned = load_json(path.parent / "task.json")
        invocation, coverage = checked_status(status, slot["task"], returned)
        sha = status["worker_sha256"]
        if slot["worker_sha256"] not in (None, sha):
            raise ValueError(f"different worker hashes returned for task {tid}")
        slot["worker_sha256"] = sha
        slot["intervals"].append(coverage)
        slot["returns"].append({"directory": relative, "state": status["state"],
                                "reason": status["reason"], "invocation_coverage": intervals_json([invocation])[0],
                                "retained_output_coverage": intervals_json([coverage])[0]})
        if status["state"] == "error":
            error_returns.append(relative)
        elif status["state"] == "running":
            running_returns.append(relative)
        parsed = slot["parsed"]
        bounds = Bounds(**parsed["bounds"], magnitudes=True, signs=parsed["signs"])
        hits_path = path.parent / "hits.jsonl"
        output_certificates: set[str] = set()
        with hits_path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if len(line.encode("utf-8")) > MAX_LINE_BYTES or not line.endswith("\n") or not line.strip():
                    raise ValueError(f"truncated or blank certificate at {hits_path}:{line_number}")
                # Reuse the duplicate-key rejecting task loader for each JSON object.
                def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                    out: dict[str, Any] = {}
                    for key, value in pairs:
                        if key in out:
                            raise ValueError(f"duplicate certificate key: {key}")
                        out[key] = value
                    return out
                row = json.loads(line, object_pairs_hook=unique)
                checked = verify_record(row, bounds, require_congruences=True,
                                        require_integer_sqrt=slot["task"]["search"].get("require_integer_sqrt", False))
                n, x = int(checked["n"]), int(checked["x"])
                y = Fraction(int(checked["y_num"]), int(checked["y_den"]))
                ratio = abs(y / abs(x) - 1 + Fraction(6*n, x))
                a, q = ratio.numerator, ratio.denominator
                if a not in slot["a_index"] or q < parsed["q_min"] or (q - parsed["q_min"]) % 2:
                    raise ValueError("verified certificate does not belong to the selected absolute-slope fiber list")
                qi = (q - parsed["q_min"]) // 2
                index = slot["a_index"][a] * parsed["q_count"] + qi
                if qi >= parsed["q_count"] or not parsed["start"] <= index < parsed["stop"]:
                    raise ValueError("verified certificate does not belong to its task slice")
                if row.get("task_id", tid) != tid:
                    raise ValueError("certificate task_id differs from its returned task")
                if "candidate_index" in row and integer(row["candidate_index"], "hit.candidate_index") != index:
                    raise ValueError("certificate candidate_index differs from its absolute-slope fiber")
                if "a" in row and (integer(row["a"], "hit.a", positive=True), integer(row["q"], "hit.q", positive=True)) != candidate(parsed, index):
                    raise ValueError("certificate a,q is not the canonical selected candidate")
                key = certificate_key(checked)
                if row.get("certificate_sha256", key) != key:
                    raise ValueError("certificate checksum mismatch")
                output_certificates.add(key)
                source = {"task_id": tid, "candidate_index": str(index), "directory": relative}
                if key not in certificates:
                    certificates[key] = dict(checked, a=str(a), q=str(q), certificate_sha256=key, sources=[])
                if source not in certificates[key]["sources"]:
                    certificates[key]["sources"].append(source)
                certificate_rows += 1
        expected_hits = integer(status["unique_hits_in_this_output"], "status.unique_hits_in_this_output")
        if (len(output_certificates) < expected_hits
                or (status["state"] != "running" and len(output_certificates) != expected_hits)):
            raise ValueError(f"returned hit file/count mismatch: {hits_path}")

    tasks = []
    missing = []
    for tid, slot in selected.items():
        parsed = slot["parsed"]
        coverage = merge_coverage(slot["intervals"], parsed["start"], parsed["stop"])
        if not slot["returns"]:
            missing.append(tid)
        tasks.append({"task_id": tid, "campaign_id": slot["task"]["campaign_id"], "ordinal": slot["ordinal"],
                      "slice": slot["task"]["slice"], "signs": parsed["signs"], "worker_sha256": slot["worker_sha256"],
                      "returned_invocations": slot["returns"], **coverage})
    complete = all(task["complete"] for task in tasks)
    campaign_workers: dict[str, list[str]] = {}
    for task in tasks:
        hashes = campaign_workers.setdefault(task["campaign_id"], [])
        sha = task["worker_sha256"]
        if sha is not None and sha not in hashes:
            hashes.append(sha)
    for hashes in campaign_workers.values():
        hashes.sort()
    summary = {"schema": "ce390-collection-v2", "complete_selected_page": complete,
               "selected_tasks": len(tasks), "missing_tasks": missing, "tasks": tasks,
               "campaign_worker_sha256": campaign_workers,
               "campaigns_with_multiple_worker_hashes": sorted(k for k, v in campaign_workers.items() if len(v) > 1),
               "error_returns": error_returns, "running_returns": running_returns,
               "skipped_unrelated_returns": unrelated, "certificate_rows": certificate_rows,
               "unique_verified_solutions": len(certificates), "duplicate_certificate_rows": certificate_rows - len(certificates),
               "coverage_note": "Completeness covers only the selected task-page fiber indices. It does not exhaust or prove anything about unsearched absolute-slope fibers in the signed n,x magnitude regions."}
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "hits.jsonl"
    temporary = output_dir / "hits.jsonl.tmp"
    with temporary.open("wb") as out:
        for key in sorted(certificates):
            out.write(canonical(certificates[key]) + b"\n")
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, target)
    atomic_json(output_dir / "summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", action="append", type=Path, required=True, help="task page; may be repeated")
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("collected"))
    parser.add_argument("--skip-unrelated", action="store_true", help="explicitly skip result directories for unselected tasks")
    args = parser.parse_args(argv)
    try:
        summary = collect(args.page, args.results_dir, args.output_dir, skip_unrelated=args.skip_unrelated)
        print(json.dumps({k: v for k, v in summary.items() if k != "tasks"}, sort_keys=True, indent=2))
        return 0 if summary["complete_selected_page"] else 2
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
