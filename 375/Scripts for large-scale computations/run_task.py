#!/usr/bin/env python3
"""Run one restartable CE375 task (a range n_start <= n < n_stop).

The native worker prints one "block" record per finished block of n; after
each one this runner rewrites checkpoint.json, so an interrupted host loses at
most one block. Every hit is re-verified here in exact rational arithmetic
(common375) before it is appended to hits.jsonl. Any n whose N(n) could not be
factored is written to incomplete.jsonl (never silently skipped).

Output files (under --output-dir):
  task.json, status.json, checkpoint.json, hits.jsonl, incomplete.jsonl,
  blocks.jsonl, run.log, worker.stderr.log, continuation.task.json (if n remain)

Running again with the same task and output directory resumes after the last
checkpointed block. Exit status 0: complete or deliberately partial; 1: error.

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

from common375 import (CHECKPOINT_SCHEMA, COUNTERS, METHOD, STATUS_SCHEMA, atomic_json, hit_key, load_json,
                       sha256_file, validate_task, verify_hit)

ROOT = Path(__file__).resolve().parent
DEFAULT_WORKER = ROOT / "bin" / "xy375_worker"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def append(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def consume(proc, t, task, out, seen, counters, say, cursor):
    """Stream worker records; returns (end_state, next cursor)."""
    end_state = None
    assert proc.stdout is not None
    for line in proc.stdout:
        record = json.loads(line)
        kind = record.get("type")
        if kind == "hit":
            v = verify_hit(record, t["k"])  # raises on any discrepancy
            key = hit_key(record)
            if key not in seen:
                seen.add(key)
                append(out / "hits.jsonl", record)
                say(f"HIT {'DESIRED' if v['desired'] else 'non-primitive'} form={v['form']} "
                    f"n={v['n']} x={v['x']} y=+-{v['y']}")
        elif kind == "incomplete":
            append(out / "incomplete.jsonl", record)
            say(f"INCOMPLETE n={record['n']}: N(n) not factored")
        elif kind == "block":
            a, b = int(record["n_start"]), int(record["n_stop"])
            if a != cursor or b <= a:
                raise RuntimeError(f"worker reported block [{a}, {b}), expected start {cursor}")
            for key in COUNTERS:
                counters[key] += int(record.get(key, 0))
            cursor = b
            append(out / "blocks.jsonl", record)
            atomic_json(out / "checkpoint.json", {"schema": CHECKPOINT_SCHEMA, "campaign_id": task["campaign_id"],
                                                  "task_id": task["task_id"], "next_n": cursor,
                                                  "counters": counters, "updated": now()})
        elif kind == "end":
            end_state = record["state"]
            if int(record["next_n"]) != cursor:
                raise RuntimeError("worker end record disagrees with block records")
    return end_state, cursor


def run(args: argparse.Namespace) -> int:
    task = load_json(args.task)
    t = validate_task(task)
    worker = Path(args.worker).resolve()
    if not worker.is_file() or not os.access(worker, os.X_OK):
        raise ValueError(f"worker is not executable: {worker}")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    cursor = t["n_start"]
    counters = {key: 0 for key in COUNTERS}
    cp_path = out / "checkpoint.json"
    if cp_path.exists():
        cp = load_json(cp_path)
        if cp.get("schema") != CHECKPOINT_SCHEMA or cp.get("task_id") != task["task_id"] \
                or cp.get("campaign_id") != task["campaign_id"]:
            raise ValueError("output directory holds a checkpoint of a different task")
        cursor = int(cp["next_n"])
        counters.update({key: int(cp["counters"].get(key, 0)) for key in COUNTERS})
    if not (out / "task.json").exists():
        atomic_json(out / "task.json", task)

    seen = set()
    if (out / "hits.jsonl").exists():
        for line in (out / "hits.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                seen.add(hit_key(json.loads(line)))

    log = (out / "run.log").open("a", encoding="utf-8")

    def say(message: str) -> None:
        log.write(f"{now()} {message}\n")
        log.flush()

    def status(state: str, error: str | None = None) -> None:
        atomic_json(out / "status.json", {
            "schema": STATUS_SCHEMA, "state": state, "error": error,
            "campaign_id": task["campaign_id"], "task_id": task["task_id"], "k": t["k"],
            "n_start": t["n_start"], "n_stop": t["n_stop"], "next_n": cursor, "method": METHOD,
            "worker_sha256": sha256_file(worker), "counters": counters, "hits": len(seen), "updated": now()})

    if cursor >= t["n_stop"]:
        status("complete")
        say("nothing to do: task already complete")
        return 0

    deadline = t["deadline_seconds"] if args.deadline_seconds is None else args.deadline_seconds
    cmd = [str(worker), "--k", str(t["k"]), "--n-start", str(cursor), "--n-stop", str(t["n_stop"]),
           "--deadline-seconds", str(deadline)]
    if args.block:
        cmd += ["--block", str(args.block)]
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

    started = time.monotonic()
    end_state = None
    try:
        end_state, cursor = consume(proc, t, task, out, seen, counters, say, cursor)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    rc = proc.wait()
    say(f"worker exit {rc} after {time.monotonic() - started:.1f}s, next_n={cursor}")

    if cursor >= t["n_stop"]:
        status("complete")
        (out / "continuation.task.json").unlink(missing_ok=True)
        return 0
    if rc != 0 and stop["signal"] is None:
        status("error", f"worker exited with status {rc}; see worker.stderr.log")
        return 1
    cont = dict(task)
    cont["n_start"] = cursor
    cont["continues"] = {"original_n_start": t["n_start"], "resumed_at": now()}
    atomic_json(out / "continuation.task.json", cont)
    clean = end_state == "partial" or stop["signal"] is not None
    status("partial" if clean else "error", None if clean else "worker stopped early")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--worker", type=Path, default=DEFAULT_WORKER)
    ap.add_argument("--deadline-seconds", type=int, default=None, help="override the task's deadline (0 = none)")
    ap.add_argument("--block", type=int, default=None, help="n per checkpoint (worker default 32768)")
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
