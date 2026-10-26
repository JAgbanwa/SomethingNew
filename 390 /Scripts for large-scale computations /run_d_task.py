#!/usr/bin/env python3
"""Run one restartable d-first task (see D_FIRST.md).

A task is a range of height shells start <= H < stop. The native worker
streams one record per completed shell; after every shell this runner writes
checkpoint.json, so an interrupted host loses at most one shell of work.
Every hit is re-verified here with exact rational arithmetic (dfirst_common)
before it is appended to hits.jsonl.

Output files (all under --output-dir):
  task.json, status.json, checkpoint.json, hits.jsonl, run.log,
  worker.stderr.log, continuation.task.json (only when shells remain).
Exit status: 0 for complete or intentionally partial, 1 for an error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
from typing import Any

from run_task import atomic_json, digest, load_json, sha256_file
from dfirst_common import (CHECKPOINT_SCHEMA, COUNTERS, STATUS_SCHEMA, hit_key, validate_task,
                           verify_hit)

ROOT = Path(__file__).resolve().parent
IMPLEMENTATION_FILES = ("run_d_task.py", "dfirst_common.py", "run_task.py")
GRACE_SECONDS = 120          # worker deadline is checked between shells
MAX_LINE_BYTES = 16 * 1024 * 1024


def implementation_sha256() -> str:
    return digest({name: sha256_file(ROOT / name) for name in IMPLEMENTATION_FILES})


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class Log:
    def __init__(self, path: Path):
        self.handle = path.open("a", encoding="utf-8")

    def __call__(self, message: str) -> None:
        self.handle.write(f"{now()} {message}\n")
        self.handle.flush()

    def close(self) -> None:
        self.handle.close()


def run(args: argparse.Namespace) -> int:
    task = load_json(args.task)
    parsed = validate_task(task)
    worker_path = args.worker.resolve()
    if not worker_path.is_file() or not os.access(worker_path, os.X_OK):
        raise ValueError(f"worker is not an executable file: {worker_path}")
    worker_sha, code_sha = sha256_file(worker_path), implementation_sha256()
    resume = task.get("resume")
    if resume:
        if resume["expected_worker_sha256"] != worker_sha:
            raise ValueError("worker differs from the binary pinned by this continuation")
        if resume["expected_implementation_sha256"] != code_sha:
            raise ValueError("Python implementation differs from the pinned continuation")

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    cursor, coverage_start = parsed["resume"], parsed["resume"]
    counters = {k: 0 for k in COUNTERS}
    seen: set[str] = set()
    checkpoint_path = output / "checkpoint.json"
    if checkpoint_path.exists():  # resume inside the same output directory
        cp = load_json(checkpoint_path)
        if (cp.get("schema") != CHECKPOINT_SCHEMA or cp.get("task_id") != task["task_id"]
                or cp.get("worker_sha256") != worker_sha or cp.get("implementation_sha256") != code_sha):
            raise ValueError("checkpoint.json belongs to another task, worker or implementation")
        next_h, start_h = int(cp["next_h"]), int(cp["output_coverage_start"])
        if not parsed["start"] <= start_h <= next_h <= parsed["stop"]:
            raise ValueError("checkpoint coverage is invalid")
        if next_h >= cursor:
            cursor, coverage_start = next_h, start_h
            counters = {k: int(cp["counters"][k]) for k in COUNTERS}
    hits_path = output / "hits.jsonl"
    if hits_path.exists():
        for line in hits_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                verify_hit(record, parsed["m"], (parsed["start"], parsed["stop"]))
                seen.add(hit_key(record))
    atomic_json(output / "task.json", task)
    log = Log(output / "run.log")
    log(f"task {task['task_id']} shells [{parsed['start']}, {parsed['stop']}) m={parsed['m']} "
        f"resume at {cursor}; worker {worker_sha[:16]} implementation {code_sha[:16]}")

    started, t0 = now(), time.monotonic()
    state, reason, error = "partial", "", None

    def write_checkpoint() -> None:
        atomic_json(checkpoint_path, {
            "schema": CHECKPOINT_SCHEMA, "task_id": task["task_id"], "next_h": str(cursor),
            "output_coverage_start": str(coverage_start), "counters": {k: str(v) for k, v in counters.items()},
            "unique_hits_in_this_output": str(len(seen)), "worker_sha256": worker_sha,
            "implementation_sha256": code_sha, "updated_utc": now()})

    def write_status() -> None:
        status = {
            "schema": STATUS_SCHEMA, "task_id": task["task_id"], "campaign_id": task["campaign_id"],
            "ordinal": task["ordinal"], "state": state, "reason": reason,
            "search": task["search"], "shells": task["shells"],
            "output_coverage": {"start": str(coverage_start), "stop": str(cursor)},
            "next_h": str(cursor), "remaining_shells": str(parsed["stop"] - cursor),
            "counters": {k: str(v) for k, v in counters.items()},
            "unique_hits_in_this_output": str(len(seen)),
            "elapsed_seconds": round(time.monotonic() - t0, 3), "started_utc": started, "updated_utc": now(),
            "worker_sha256": worker_sha, "implementation_sha256": code_sha,
            "coverage_note": (f"Every admissible d = p/q with {coverage_start} <= max(|p|,q) < {cursor} was "
                              f"solved for ALL half-chart points with 1 <= |g| <= 10^{parsed['g_max_digits']} "
                              "(x = -q*g/2). Inadmissible d provably have none."),
        }
        if error:
            status["error"] = error
        atomic_json(output / "status.json", status)

    if cursor >= parsed["stop"]:
        state, reason = "complete", "already_complete"
        write_status()
        log("nothing to do: task already complete in this output directory")
        log.close()
        return 0

    stop_requested = {"flag": False}

    def on_signal(signum: int, _frame: Any) -> None:
        stop_requested["flag"] = True
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, on_signal)

    budget = max(1, parsed["seconds"] - int(args.reserve_seconds))
    argv = [str(worker_path), "--m", str(parsed["m"]), "--h-start", str(cursor), "--h-stop", str(parsed["stop"]),
            "--g-max-digits", str(parsed["g_max_digits"]), "--deadline-seconds", str(budget),
            "--precision-bits", str(parsed["precision_bits"]),
            "--max-precision-bits", str(parsed["max_precision_bits"])]
    with (output / "worker.stderr.log").open("ab") as stderr, (hits_path).open("a", encoding="utf-8") as hits_out:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=stderr, start_new_session=True)
        assert proc.stdout is not None
        os.set_blocking(proc.stdout.fileno(), False)
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        buffer = bytearray()
        hard_deadline = t0 + parsed["seconds"] + GRACE_SECONDS
        ended = False
        try:
            while not ended:
                if stop_requested["flag"]:
                    reason = "signal"
                    break
                if time.monotonic() > hard_deadline:
                    reason = "hard_time_limit"
                    break
                for _ in selector.select(0.5):
                    chunk = os.read(proc.stdout.fileno(), 1 << 16)
                    if not chunk:
                        ended = True
                        break
                    buffer.extend(chunk)
                    if len(buffer) > MAX_LINE_BYTES:
                        raise RuntimeError("worker record exceeded 16 MiB")
                while b"\n" in buffer:
                    line, _, rest = buffer.partition(b"\n")
                    buffer = bytearray(rest)
                    record = json.loads(line)
                    kind = record.get("type")
                    if kind == "hit":
                        verify_hit(record, parsed["m"], (parsed["start"], parsed["stop"]))
                        key = hit_key(record)
                        if key not in seen:
                            seen.add(key)
                            hits_out.write(json.dumps(record, sort_keys=True) + "\n")
                            hits_out.flush()
                            os.fsync(hits_out.fileno())
                            log(f"HIT d={record['d_num']}/{record['d_den']} n={record['n_num']} "
                                f"x={record['x_num']}/2 y={record['y_num']}/2")
                    elif kind == "shell":
                        h = int(record["h"])
                        if h != cursor:
                            raise RuntimeError(f"worker reported shell {h}, expected {cursor}")
                        for k in COUNTERS:
                            counters[k] += int(record[k])
                        cursor = h + 1
                        write_checkpoint()
                        if h % args.status_every == 0:
                            write_status()
                    elif kind == "end":
                        if int(record["next_h"]) != cursor:
                            raise RuntimeError("worker end record disagrees with the shells received")
                        reason = "worker_deadline" if record["state"] == "partial" else "shells_exhausted"
                        ended = True
                    elif kind != "start":
                        raise RuntimeError(f"unknown worker record {kind!r}")
            rc = proc.wait(timeout=30) if ended else None
            if ended and rc != 0:
                raise RuntimeError(f"worker exited with status {rc}; see worker.stderr.log")
            if ended and not reason:
                raise RuntimeError("worker closed its output without an end record")
        except Exception as exc:  # keep every completed shell; report the failure
            error, state = str(exc), "error"
            log(f"ERROR {exc}")
        finally:
            selector.close()
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                    proc.wait(timeout=5)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            proc.stdout.close()
    if state != "error":
        state = "complete" if cursor >= parsed["stop"] else "partial"
    write_checkpoint()
    write_status()
    continuation = output / "continuation.task.json"
    if cursor < parsed["stop"]:
        cont = {k: v for k, v in task.items() if k != "resume"}
        cont["resume"] = {"next_h": str(cursor), "expected_worker_sha256": worker_sha,
                          "expected_implementation_sha256": code_sha}
        atomic_json(continuation, cont)
    elif continuation.exists():
        continuation.unlink()
    log(f"{state}: {reason or error}; covered shells [{coverage_start}, {cursor}); "
        f"admissible d {counters['admissible']}; hits {len(seen)}")
    log.close()
    return 1 if state == "error" else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--worker", type=Path, default=ROOT / "bin" / "dthue_worker")
    parser.add_argument("--reserve-seconds", type=int, default=60,
                        help="stop starting new shells this many seconds before the task budget")
    parser.add_argument("--status-every", type=int, default=1, help="write status.json every N shells")
    args = parser.parse_args()
    if args.status_every < 1 or args.reserve_seconds < 0:
        parser.error("--status-every must be >= 1 and --reserve-seconds >= 0")
    try:
        return run(args)
    except (OSError, ValueError, KeyError) as exc:
        print(f"run_d_task: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
