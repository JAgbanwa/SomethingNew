#!/usr/bin/env python3
"""Run one restartable gap-search task (see README.md).

The worker prints one record per chunk of d values; after each one this
runner rewrites checkpoint.json, so an interrupted host loses at most one chunk.
Every hit is re-verified exactly (gap_common.verify_hit) before it is stored.

Outputs in --output-dir: task.json, status.json, checkpoint.json, hits.jsonl,
chunks.jsonl, run.log, worker.stderr.log, continuation.task.json (only when d
values remain). Re-running with the same task and output directory resumes.
Exit status: 0 complete or deliberately partial, 1 error.

Charity Engine:
  python3 /app/run_gap_task.py --task /local/input/task.json --output-dir /local/output
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from gap_common import (CHECKPOINT_SCHEMA, COUNTERS, METHOD, STATUS_SCHEMA, atomic_json, load_json, sha256_file,
                        validate_task, verify_hit)

ROOT = Path(__file__).resolve().parent
DEFAULT_WORKER = ROOT / "bin" / "gap_worker"


class TaskMismatch(ValueError):
    """The output directory holds another task's or another interval's work: refuse, change nothing."""


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run(args: argparse.Namespace) -> int:
    task = load_json(args.task)
    t = validate_task(task)
    worker = Path(args.worker).resolve()
    if not worker.is_file() or not os.access(worker, os.X_OK):
        raise ValueError(f"worker is not executable: {worker}")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cp_path, hits_path = out / "checkpoint.json", out / "hits.jsonl"

    # This directory covers exactly [covered_start, d_next). A resume may only continue that
    # interval: a task starting before covered_start (e.g. the original task re-run where its
    # continuation ran) would otherwise be credited with d values this directory never searched.
    cursor = covered_start = t["d_start"]
    counters = {key: 0 for key in COUNTERS}
    elapsed_total = 0.0
    cp = None
    if cp_path.exists():
        try:
            cp = load_json(cp_path)
        except (OSError, ValueError):
            cp = None   # torn write: restart this task from its own d_start (coverage stays honest)
    if cp is not None:
        if cp.get("schema") != CHECKPOINT_SCHEMA or cp.get("task_id") != task["task_id"] \
                or cp.get("campaign_id") != task["campaign_id"]:
            raise TaskMismatch("output directory holds a checkpoint of a different task")
        cp_start, cp_next, cp_stop = int(cp["covered_start"]), int(cp["d_next"]), int(cp["d_stop"])
        if cp_stop != t["d_stop"] or int(cp["ratio_max"]) != t["ratio_max"] or int(cp["k"]) != t["k"]:
            raise TaskMismatch("checkpoint parameters differ from the task")
        if not cp_start <= t["d_start"] <= cp_next:
            raise TaskMismatch(f"task starts at {t['d_start']} but this directory covers [{cp_start}, {cp_next}); "
                             "use a fresh output directory")
        cursor, covered_start = cp_next, cp_start
        counters.update({key: int(cp["counters"].get(key, 0)) for key in COUNTERS})
        elapsed_total = float(cp.get("worker_seconds", 0.0))
    atomic_json(out / "task.json", task)
    seen = set()
    if hits_path.exists():
        for line in hits_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                h = json.loads(line)
                seen.add((h["x"], h["y"], h["z"]))

    log = (out / "run.log").open("a", encoding="utf-8")

    def say(msg: str) -> None:
        log.write(f"{now()} {msg}\n")
        log.flush()

    worker_sha = sha256_file(worker)

    def status(state: str, error: str | None = None) -> None:
        atomic_json(out / "status.json", {
            "schema": STATUS_SCHEMA, "state": state, "error": error, "method": METHOD,
            "campaign_id": task["campaign_id"], "task_id": task["task_id"], "k": t["k"],
            "d_start": str(t["d_start"]), "d_stop": str(t["d_stop"]), "covered_start": str(covered_start),
            "d_next": str(cursor),
            "ratio_max": t["ratio_max"], "worker_sha256": worker_sha, "counters": counters,
            "worker_seconds": round(elapsed_total, 3), "hits": len(seen), "updated": now()})

    if cursor >= t["d_stop"]:
        status("complete")
        return 0
    if cursor != t["d_start"] and not cp_path.exists():
        raise ValueError("internal: resume without checkpoint")
    deadline = t["deadline_seconds"] if args.deadline_seconds is None else args.deadline_seconds
    cmd = [str(worker), "--k", str(t["k"]), "--d-start", str(cursor), "--d-stop", str(t["d_stop"]),
           "--ratio-max", str(t["ratio_max"]), "--deadline-seconds", str(deadline), "--chunk", str(args.chunk)]
    say("start " + " ".join(cmd))
    status("running")
    stderr = (out / "worker.stderr.log").open("a", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
    stopped = {"signal": None}

    def on_signal(signum, _frame):
        stopped["signal"] = signum
        if proc.poll() is None:
            proc.terminate()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, on_signal)

    end_state = None
    t0 = time.monotonic()
    try:
        with hits_path.open("a", encoding="utf-8") as hits, (out / "chunks.jsonl").open("a", encoding="utf-8") as chunks:
            assert proc.stdout is not None
            for line in proc.stdout:
                rec = json.loads(line)
                kind = rec.get("type")
                if kind == "hit":
                    verify_hit(rec, t["k"])
                    key = (rec["x"], rec["y"], rec["z"])
                    if key not in seen:
                        seen.add(key)
                        hits.write(json.dumps(rec, sort_keys=True) + "\n")
                        hits.flush()
                        os.fsync(hits.fileno())
                        say(f"HIT x={rec['x']} y={rec['y']} z={rec['z']}")
                elif kind == "chunk":
                    if int(rec["d_start"]) != cursor:
                        raise RuntimeError(f"worker chunk starts at {rec['d_start']}, expected {cursor}")
                    for key in COUNTERS:
                        counters[key] += int(rec["counters"].get(key, 0))
                    cursor = int(rec["d_stop"])
                    chunks.write(json.dumps(rec, sort_keys=True) + "\n")
                    chunks.flush()
                    atomic_json(cp_path, {"schema": CHECKPOINT_SCHEMA, "campaign_id": task["campaign_id"],
                                          "task_id": task["task_id"], "k": t["k"], "ratio_max": t["ratio_max"],
                                          "covered_start": str(covered_start), "d_stop": str(t["d_stop"]),
                                          "worker_sha256": worker_sha, "d_next": str(cursor), "counters": counters,
                                          "worker_seconds": round(elapsed_total + time.monotonic() - t0, 3),
                                          "updated": now()})
                elif kind == "end":
                    end_state = rec["state"]
                    if int(rec["d_next"]) != cursor:
                        raise RuntimeError("worker end record disagrees with chunk records")
    finally:
        if proc.poll() is None:
            proc.kill()
        rc = proc.wait()
    elapsed_total += time.monotonic() - t0
    say(f"worker exit {rc}, d_next={cursor}")
    if cursor >= t["d_stop"]:
        status("complete")
        (out / "continuation.task.json").unlink(missing_ok=True)
        return 0
    if rc != 0 and stopped["signal"] is None:
        status("error", f"worker exited with status {rc}; see worker.stderr.log")
        return 1
    cont = dict(task)
    cont["d_start"] = str(cursor)
    cont["continues"] = {"original_d_start": str(t["d_start"]), "written": now()}
    atomic_json(out / "continuation.task.json", cont)
    status("partial")
    return args.partial_exit_code


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--worker", type=Path, default=DEFAULT_WORKER)
    ap.add_argument("--deadline-seconds", type=int, default=None, help="override the task deadline (0 = none)")
    ap.add_argument("--chunk", type=int, default=1 << 24, help="d values per checkpoint (default 2^24)")
    ap.add_argument("--partial-exit-code", type=int, default=0,
                    help="exit status when stopped before d_stop (default 0; a nonzero value lets a grid retry)")
    args = ap.parse_args()
    try:
        return run(args)
    except TaskMismatch as exc:
        print(f"run_gap_task: refused: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"run_gap_task: {exc}", file=sys.stderr)
        try:
            atomic_json(Path(args.output_dir) / "status.json",
                        {"schema": STATUS_SCHEMA, "state": "error", "error": str(exc), "updated": now()})
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
