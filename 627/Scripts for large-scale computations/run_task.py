#!/usr/bin/env python3
"""Run one restartable CE627 d-first task.

A task is a range of height shells h_start <= H < h_stop. The native worker
prints one record per completed shell; after each one this runner rewrites
checkpoint.json, so an interrupted host loses at most one shell of work.
Every hit is re-verified here in exact rational arithmetic (common627) before
it is appended to hits.jsonl.

Output files (under --output-dir):
  task.json, status.json, checkpoint.json, hits.jsonl, shells.jsonl,
  run.log, worker.stderr.log, continuation.task.json (only when shells remain)

Running again with the same task and output directory resumes after the last
checkpointed shell. Exit status 0: complete or deliberately partial; 1: error.

Charity Engine:  python3 /app/run_task.py --task /local/input/task.json --output-dir /local/output
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

from common627 import (CHECKPOINT_SCHEMA, COUNTERS, PARAMETERIZATION, STATUS_SCHEMA, atomic_json,
                       hit_key, load_json, sha256_file, validate_task, verify_hit)

ROOT = Path(__file__).resolve().parent
DEFAULT_WORKER = ROOT / "bin" / "thue627_worker"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def consume(proc, t, task, out, cp_path, hits_path, seen, counters, say, cursor):
    """Stream worker records; returns (end_state, next cursor)."""
    end_state = None
    with hits_path.open("a", encoding="utf-8") as hits, (out / "shells.jsonl").open("a", encoding="utf-8") as shells:
        assert proc.stdout is not None
        for line in proc.stdout:
            record = json.loads(line)
            kind = record.get("type")
            if kind == "hit":
                verify_hit(record, t["k"])  # raises on any discrepancy
                key = hit_key(record)
                if key not in seen:
                    seen.add(key)
                    hits.write(json.dumps(record, sort_keys=True) + "\n")
                    hits.flush()
                    os.fsync(hits.fileno())
                    say(f"HIT chart={record['chart']} d={record['d_num']}/{record['d_den']}")
            elif kind == "shell":
                h = int(record["h"])
                if h != cursor:
                    raise RuntimeError(f"worker reported shell {h}, expected {cursor}")
                for key in COUNTERS:
                    counters[key] += int(record.get(key, 0))
                cursor = h + 1
                shells.write(json.dumps(record, sort_keys=True) + "\n")
                shells.flush()
                atomic_json(cp_path, {"schema": CHECKPOINT_SCHEMA, "campaign_id": task["campaign_id"],
                                      "task_id": task["task_id"], "next_h": cursor,
                                      "counters": counters, "updated": now()})
            elif kind == "end":
                end_state = record["state"]
                if int(record["next_h"]) != cursor:
                    raise RuntimeError("worker end record disagrees with shell records")
    return end_state, cursor


def run(args: argparse.Namespace) -> int:
    task = load_json(args.task)
    t = validate_task(task)
    worker = Path(args.worker).resolve()
    if not worker.is_file() or not os.access(worker, os.X_OK):
        raise ValueError(f"worker is not executable: {worker}")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    cursor = t["h_start"]
    counters = {key: 0 for key in COUNTERS}
    cp_path = out / "checkpoint.json"
    if cp_path.exists():
        cp = load_json(cp_path)
        if cp.get("schema") != CHECKPOINT_SCHEMA or cp.get("task_id") != task["task_id"] \
                or cp.get("campaign_id") != task["campaign_id"]:
            raise ValueError("output directory holds a checkpoint of a different task")
        cursor = int(cp["next_h"])
        counters.update({key: int(cp["counters"].get(key, 0)) for key in COUNTERS})
    atomic_json(out / "task.json", task)

    seen = set()
    hits_path = out / "hits.jsonl"
    if hits_path.exists():
        for line in hits_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seen.add(hit_key(json.loads(line)))

    log = (out / "run.log").open("a", encoding="utf-8")

    def say(message: str) -> None:
        log.write(f"{now()} {message}\n")
        log.flush()

    def status(state: str, error: str | None = None) -> None:
        atomic_json(out / "status.json", {
            "schema": STATUS_SCHEMA, "state": state, "error": error,
            "campaign_id": task["campaign_id"], "task_id": task["task_id"],
            "k": t["k"], "h_start": t["h_start"], "h_stop": t["h_stop"],
            "covered_h_start": t["h_start"], "next_h": cursor,
            "g_max_digits": t["g_max_digits"], "parameterization": PARAMETERIZATION,
            "worker_sha256": sha256_file(worker), "counters": counters,
            "hits": len(seen), "updated": now()})

    if cursor >= t["h_stop"]:
        status("complete")
        say("nothing to do: task already complete")
        return 0

    deadline = t["deadline_seconds"]
    if args.deadline_seconds is not None:
        deadline = args.deadline_seconds
    cmd = [str(worker), "--k", str(t["k"]), "--h-start", str(cursor), "--h-stop", str(t["h_stop"]),
           "--g-max-digits", str(t["g_max_digits"]), "--deadline-seconds", str(deadline)]
    say("start " + " ".join(cmd))
    status("running")
    stderr = (out / "worker.stderr.log").open("a", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)

    stop = {"signal": None}

    def on_signal(signum, _frame):
        stop["signal"] = signum
        if proc.poll() is None:
            proc.terminate()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, on_signal)

    end_state = None
    started = time.monotonic()
    try:
        end_state = consume(proc, t, task, out, cp_path, hits_path, seen, counters, say, cursor)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    end_state, cursor = end_state
    rc = proc.wait()
    elapsed = time.monotonic() - started
    say(f"worker exit {rc} after {elapsed:.1f}s, next_h={cursor}")

    if cursor >= t["h_stop"]:
        status("complete")
        (out / "continuation.task.json").unlink(missing_ok=True)
        return 0
    if rc != 0 and stop["signal"] is None:
        status("error", f"worker exited with status {rc}; see worker.stderr.log")
        return 1
    cont = dict(task)
    cont["h_start"] = cursor
    cont["task_id"] = f"{task['task_id']}"
    cont["continues"] = {"original_h_start": t["h_start"], "resumed_at": now()}
    atomic_json(out / "continuation.task.json", cont)
    status("partial" if end_state == "partial" or stop["signal"] else "error",
           None if end_state == "partial" or stop["signal"] else "worker stopped early")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--worker", type=Path, default=DEFAULT_WORKER)
    ap.add_argument("--deadline-seconds", type=int, default=None,
                    help="override the task's deadline (0 = none)")
    args = ap.parse_args()
    try:
        return run(args)
    except Exception as exc:  # noqa: BLE001 - recorded, then non-zero exit
        print(f"run_task: {exc}", file=sys.stderr)
        try:
            atomic_json(Path(args.output_dir) / "status.json",
                        {"schema": STATUS_SCHEMA, "state": "error", "error": str(exc), "updated": now()})
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
