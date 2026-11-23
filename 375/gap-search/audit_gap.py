#!/usr/bin/env python3
"""Re-run sampled committed chunks and compare counters AND exact solution identities.

All returned artifacts are first validated by the collector's checks, including
saved-hit counts and worker provenance. Audits must use the same worker binary
SHA-256 as the returned work. Replayed, uncommitted chunk records are not sampled.

  python3 audit_gap.py --page gap-tasks/page.json --results gap-results --fraction 0.02

Exit status 1 if an artifact is invalid or any sampled chunk disagrees.
A passing sample does not certify chunks that were not re-run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import subprocess
import sys

from collect_gap import (checked_counters, checked_hit, checked_int, checked_sha256,
                         load_result_directory)
from gap_common import COUNTERS, METHOD, PAGE_SCHEMA, load_json, sha256_file

ROOT = Path(__file__).resolve().parent


def rerun_chunk(worker: Path, page: dict, lo: int, hi: int) -> tuple[dict, set[tuple[int, int, int]]]:
    """Require a complete native protocol, not merely exit status zero."""
    k, ratio, primitive = int(page["k"]), int(page["ratio_max"]), page.get("primitive", True)
    proc = subprocess.run([str(worker), "--k", str(k), "--d-start", str(lo), "--d-stop", str(hi),
                           "--ratio-max", str(ratio), "--chunk", str(hi - lo), "--deadline-seconds", "0"]
                          + (["--primitive"] if primitive else []), capture_output=True, text=True)
    if proc.returncode:
        raise ValueError(f"audit worker exited {proc.returncode}: {proc.stderr.strip()}")
    if proc.stdout and not proc.stdout.endswith("\n"):
        raise ValueError("audit worker returned a truncated final record")
    started = ended = False
    cursor, counters, hits = lo, dict.fromkeys(COUNTERS, 0), {}
    for line in proc.stdout.splitlines():
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError("audit worker record must be an object")
        if ended:
            raise ValueError("audit worker emitted output after its terminal record")
        kind = record.get("type")
        if kind == "start":
            if (started or record.get("method") != METHOD or int(record["k"]) != k
                    or int(record["d_start"]) != lo or int(record["d_stop"]) != hi
                    or int(record["ratio_max"]) != ratio or record.get("primitive") is not primitive):
                raise ValueError("audit worker start record does not match the audited chunk")
            started = True
        elif not started:
            raise ValueError("audit worker output has no matching start record")
        elif kind == "hit":
            identity, normalized = checked_hit(record, k, lo, hi, ratio)
            hits[identity] = normalized
        elif kind == "chunk":
            a, b = (checked_int(record[key], f"audit chunk.{key}") for key in ("d_start", "d_stop"))
            if a != cursor or not cursor < b <= hi:
                raise ValueError("audit worker chunk does not continue the audited interval")
            counts = checked_counters(record, "audit chunk")
            if counts["d_total"] != b - a:
                raise ValueError("audit worker d_total disagrees with its chunk interval")
            for key in COUNTERS:
                counters[key] += counts[key]
            cursor = b
        elif kind == "end":
            if record.get("state") != "complete" or int(record["d_next"]) != cursor or cursor != hi:
                raise ValueError("audit worker did not complete the audited interval")
            ended = True
        else:
            raise ValueError(f"unknown audit worker record type: {kind!r}")
    if not started or not ended:
        raise ValueError("audit worker exited without a valid complete terminal record")
    if counters["hits"] != len(hits) or counters["hits_primitive"] != sum(r["primitive"] for r in hits.values()):
        raise ValueError("audit worker hit identities disagree with its own counters")
    return counters, set(hits)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", type=Path, required=True)
    ap.add_argument("--results", type=Path, nargs="+", required=True)
    ap.add_argument("--fraction", type=float, default=0.02, help="share of chunks to re-run (default 2%%)")
    ap.add_argument("--min-chunks", type=int, default=5)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--worker", type=Path, default=ROOT / "bin" / "gap_worker")
    ap.add_argument("--expected-worker-sha256", help="pin the worker release for both returned work and reruns")
    a = ap.parse_args()
    if not 0 < a.fraction <= 1 or a.min_chunks < 1:
        ap.error("need 0 < fraction <= 1 and min-chunks >= 1")
    try:
        page = load_json(a.page)
        if not isinstance(page, dict) or page.get("schema") != PAGE_SCHEMA or page.get("method") != METHOD:
            raise ValueError("page has an unsupported schema or method")
        worker = a.worker.resolve()
        actual_sha = sha256_file(worker)
        expected_sha = checked_sha256(a.expected_worker_sha256) if a.expected_worker_sha256 is not None else actual_sha
        if actual_sha != expected_sha:
            raise ValueError(f"audit worker SHA-256 {actual_sha} differs from expected {expected_sha}")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f"audit_gap: {exc}", file=sys.stderr)
        return 1
    chunks, errors = [], []
    task_paths = {tj.resolve() for root in a.results for tj in root.rglob("task.json")}
    for tj in sorted(task_paths):
        try:
            result = load_result_directory(tj.parent, page, expected_sha)
            if result is not None:
                chunks.extend((result, record) for record in result["chunks"])
        except (OSError, KeyError, TypeError, ValueError) as exc:
            errors.append(f"{tj.parent}: {exc}")
    if errors:
        for error in errors:
            print(f"audit_gap: invalid returned artifacts: {error}", file=sys.stderr)
        return 1
    if not chunks:
        print("no committed chunk records found")
        return 1
    rng = random.Random(a.seed)
    n = min(len(chunks), max(a.min_chunks, round(a.fraction * len(chunks))))
    bad = 0
    for result, record in rng.sample(chunks, n):
        lo, hi = int(record["d_start"]), int(record["d_stop"])
        where = result["directory"]
        try:
            got, got_hits = rerun_chunk(worker, page, lo, hi)
            want = checked_counters(record, "returned chunk")
            want_hits = {identity for identity, hit in result["hits"].items() if lo <= int(hit["d"]) < hi}
            if got != want or got_hits != want_hits:
                details = []
                if got != want:
                    details.append(f"returned counters {want}\n     audited counters  {got}")
                if got_hits != want_hits:
                    details.append(f"missing returned identities {sorted(got_hits - want_hits)}\n"
                                   f"     unexpected returned identities {sorted(want_hits - got_hits)}")
                raise ValueError("\n     ".join(details))
            print(f"OK   [{lo}, {hi})  {where}")
        except (OSError, KeyError, TypeError, ValueError) as exc:
            bad += 1
            print(f"BAD  [{lo}, {hi})  {where}\n     {exc}")
    print(f"{n - bad}/{n} sampled chunks agree in counters and exact solution identities")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
