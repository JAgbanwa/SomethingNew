#!/usr/bin/env python3
"""Run one restartable CE375 task with g restricted to {-1, 1}.

The worker must send a matching start, ordered completed shells, and exactly
one valid terminal record. Completion also requires a successful worker exit.
The last shell remains pending until another shell or a successful terminal
record confirms it; an interrupted attempt replays its uncommitted tail.
Every hit is checked in exact rational arithmetic before it is stored.

Outputs: task.json, status.json, checkpoint.json, hits.jsonl, shells.jsonl,
run.log, worker.stderr.log, and continuation.task.json when shells remain.
Resumes must use the same worker SHA-256 as the saved results. An explicit
--expected-worker-sha256 pins a release before the output directory is touched.
Exit status 0: complete or deliberately partial; 1: error.

Charity Engine: python3 /app/run_task.py --task /local/input/task.json --output-dir /local/output
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

from common375 import (CHECKPOINT_SCHEMA, COUNTERS, G_VALUES, PARAMETERIZATION, STATUS_SCHEMA,
                       atomic_json, checked_sha256, hit_key, load_json, read_result_progress,
                       record_integer, sha256_file, shell_counters, validate_scope, validate_task,
                       verify_task_hit)

ROOT = Path(__file__).resolve().parent
DEFAULT_WORKER = ROOT / "bin" / "thue375_worker"


class TaskMismatch(ValueError):
    """Refuse an incompatible task or binary without changing saved output."""


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run(args: argparse.Namespace) -> int:
    task = load_json(args.task)
    t = validate_task(task)
    worker = Path(args.worker).resolve()
    if not worker.is_file() or not os.access(worker, os.X_OK):
        raise TaskMismatch(f"worker is not executable: {worker}")
    worker_sha = sha256_file(worker)
    pins = [checked_sha256(v) for v in (getattr(args, "expected_worker_sha256", None),
                                      task.get("expected_worker_sha256")) if v is not None]
    if any(pin != worker_sha for pin in pins):
        raise TaskMismatch("worker SHA-256 differs from the command-line or task pin")
    deadline = t["deadline_seconds"] if args.deadline_seconds is None else args.deadline_seconds
    if deadline < 0:
        raise ValueError("deadline_seconds must be >= 0")
    out = Path(args.output_dir)
    cp_path, hits_path = out / "checkpoint.json", out / "hits.jsonl"
    saved_task_path = out / "task.json"
    try:
        if saved_task_path.exists():
            saved_task = load_json(saved_task_path)
            saved = validate_task(saved_task)
            if (any(saved_task[key] != task[key] for key in ("campaign_id", "task_id"))
                    or any(saved[key] != t[key] for key in ("k", "mode", "h_stop", "g_values"))):
                raise ValueError("output directory holds a different task or search scope")
            if (saved_task.get("expected_worker_sha256") is not None
                    and checked_sha256(saved_task["expected_worker_sha256"]) != worker_sha):
                raise ValueError("saved task was pinned to a different worker SHA-256")
        elif any((out / name).exists() for name in ("checkpoint.json", "status.json", "hits.jsonl", "shells.jsonl")):
            raise ValueError("saved results have no task manifest")
        progress = read_result_progress(out, task, t)
        if progress["worker_sha256"] is not None and progress["worker_sha256"] != worker_sha:
            raise ValueError("saved results were produced by a different worker SHA-256")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise TaskMismatch(f"cannot resume: {exc}; use a fresh output directory") from exc

    cursor, covered_start = progress["next_h"], progress["covered_h_start"]
    counters, seen = progress["counters"], set(progress["hits"])
    # Pin continuations even when they move to a fresh output directory.
    task = dict(task, expected_worker_sha256=worker_sha)
    out.mkdir(parents=True, exist_ok=True)
    atomic_json(saved_task_path, task)
    shell_path = out / "shells.jsonl"
    if shell_path.exists():
        with shell_path.open("r+b") as handle:
            handle.truncate(progress["shell_offset"])
    log = (out / "run.log").open("a", encoding="utf-8")

    def say(message: str) -> None:
        log.write(f"{now()} {message}\n")
        log.flush()

    def status(state: str, error: str | None = None) -> None:
        atomic_json(out / "status.json", {
            "schema": STATUS_SCHEMA, "state": state, "error": error,
            "campaign_id": task["campaign_id"], "task_id": task["task_id"],
            "k": t["k"], "mode": t["mode"], "h_start": t["h_start"], "h_stop": t["h_stop"],
            "covered_h_start": covered_start, "next_h": cursor,
            "g_values": list(G_VALUES), "parameterization": PARAMETERIZATION,
            "worker_sha256": worker_sha, "counters": counters,
            "hits": len(seen), "updated": now()})

    if cursor == t["h_stop"]:
        status("complete")
        (out / "continuation.task.json").unlink(missing_ok=True)
        say("nothing to do: task already has confirmed completion")
        log.close()
        return 0

    cmd = [str(worker), "--k", str(t["k"]), "--mode", t["mode"], "--h-start", str(cursor),
           "--h-stop", str(t["h_stop"]), "--deadline-seconds", str(deadline)]
    say("start " + " ".join(cmd))
    status("running")
    stderr = (out / "worker.stderr.log").open("a", encoding="utf-8")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
    except OSError as exc:
        stderr.close()
        status("error", str(exc))
        log.close()
        return 1
    stopped = {"signal": None}

    def on_signal(signum, _frame):
        stopped["signal"] = signum
        if proc.poll() is None:
            proc.terminate()

    old_handlers = {sig: signal.signal(sig, on_signal) for sig in (signal.SIGTERM, signal.SIGINT)}
    attempt_start = observed_cursor = cursor
    end_state = pending = None
    started = False
    protocol_error = None
    t0 = time.monotonic()

    def checkpoint(terminal_state=None):
        atomic_json(cp_path, {
            "schema": CHECKPOINT_SCHEMA, "campaign_id": task["campaign_id"], "task_id": task["task_id"],
            "k": t["k"], "mode": t["mode"], "h_stop": t["h_stop"],
            "covered_h_start": covered_start, "next_h": cursor,
            "parameterization": PARAMETERIZATION, "g_values": list(G_VALUES),
            "worker_sha256": worker_sha, "counters": counters, "terminal_state": terminal_state,
            "hits": len(seen),
            "worker_exit_code": 0 if terminal_state is not None else None, "updated": now()})

    try:
        with hits_path.open("a", encoding="utf-8") as hits, shell_path.open("a", encoding="utf-8") as shells:
            def commit_pending(terminal_state=None):
                nonlocal pending, cursor, counters
                if pending is not None:
                    record, counts = pending
                    shells.write(json.dumps(record, sort_keys=True) + "\n")
                    shells.flush()
                    os.fsync(shells.fileno())
                    next_counts = {key: counters[key] + counts[key] for key in COUNTERS}
                    old_cursor, old_counts = cursor, counters
                    cursor, counters = int(record["h"]) + 1, next_counts
                    try:
                        checkpoint(terminal_state)
                    except Exception:
                        cursor, counters = old_cursor, old_counts
                        raise
                    pending = None
                elif terminal_state is not None:
                    checkpoint(terminal_state)

            assert proc.stdout is not None
            for line in proc.stdout:
                record = json.loads(line)
                kind = record.get("type")
                if end_state is not None:
                    raise RuntimeError("worker emitted output after its terminal record")
                if kind == "start":
                    if started:
                        raise RuntimeError("worker emitted more than one start record")
                    validate_scope(record)
                    if (record_integer(record.get("k"), "worker k"), record.get("mode"),
                        record_integer(record.get("h_start"), "worker h_start"),
                        record_integer(record.get("h_stop"), "worker h_stop")) \
                            != (t["k"], t["mode"], attempt_start, t["h_stop"]):
                        raise RuntimeError("worker start record does not match the task")
                    started = True
                    continue
                if not started:
                    raise RuntimeError("worker output is missing a matching unit-g start record")
                if kind in ("hit", "shell"):
                    if ("worker_sha256" in record
                            and checked_sha256(record["worker_sha256"]) != worker_sha):
                        raise RuntimeError("worker record has conflicting binary provenance")
                    record["worker_sha256"] = worker_sha
                if kind == "hit":
                    verify_task_hit(record, t, observed_cursor, min(observed_cursor + 1, t["h_stop"]))
                    key = hit_key(record)
                    if key not in seen:
                        seen.add(key)
                        hits.write(json.dumps(record, sort_keys=True) + "\n")
                        hits.flush()
                        os.fsync(hits.fileno())
                        say(f"HIT chart={record['chart']} d={record['d_num']}/{record['d_den']}")
                elif kind == "shell":
                    if observed_cursor >= t["h_stop"]:
                        raise RuntimeError("worker shell extends beyond the task")
                    counts = shell_counters(record, observed_cursor)
                    commit_pending()
                    pending = record, counts
                    observed_cursor += 1
                elif kind == "end":
                    state = record.get("state")
                    if record_integer(record.get("next_h"), "worker next_h") != observed_cursor:
                        raise RuntimeError("worker end record disagrees with shell records")
                    if state not in ("complete", "partial"):
                        raise RuntimeError("worker terminal state must be complete or partial")
                    if (state == "complete") != (observed_cursor == t["h_stop"]):
                        raise RuntimeError("worker terminal state does not match the completed interval")
                    end_state = state
                else:
                    raise RuntimeError(f"unknown worker record type: {kind!r}")
            if not started and stopped["signal"] is None:
                raise RuntimeError("worker stopped without a matching start record")
            if end_state is None and stopped["signal"] is None:
                raise RuntimeError("worker stopped without a valid terminal record")
            try:
                rc = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                raise RuntimeError("worker did not exit after closing its output") from None
            if rc == 0 and end_state is not None:
                commit_pending(end_state)
    except Exception as exc:
        protocol_error = str(exc)
    finally:
        if proc.poll() is None:
            proc.kill()
        rc = proc.wait()
        if proc.stdout is not None:
            proc.stdout.close()
        for sig, previous in old_handlers.items():
            signal.signal(sig, previous)
        stderr.close()

    say(f"worker exit {rc} after {time.monotonic() - t0:.1f}s, durable next_h={cursor}")
    if protocol_error or (rc != 0 and stopped["signal"] is None):
        status("error", protocol_error or f"worker exited with status {rc}; see worker.stderr.log")
        log.close()
        return 1
    if end_state == "complete" and rc == 0:
        status("complete")
        (out / "continuation.task.json").unlink(missing_ok=True)
        log.close()
        return 0
    cont = dict(task)
    cont["h_start"] = cursor
    cont["continues"] = {"original_h_start": covered_start, "resumed_at": now()}
    atomic_json(out / "continuation.task.json", cont)
    status("partial")
    log.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--worker", type=Path, default=DEFAULT_WORKER)
    ap.add_argument("--expected-worker-sha256", help="require this exact worker binary SHA-256")
    ap.add_argument("--deadline-seconds", type=int, default=None, help="override the task deadline (0 = none)")
    args = ap.parse_args()
    try:
        return run(args)
    except Exception as exc:  # Preflight refusal must not overwrite existing result files.
        print(f"run_task: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
