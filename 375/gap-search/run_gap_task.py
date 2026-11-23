#!/usr/bin/env python3
"""Run one restartable gap-search task (see README.md).

The worker prints one record per chunk of d values; after each one this
runner rewrites checkpoint.json, so an interrupted host loses at most one chunk.
Every hit is re-verified exactly (gap_common.verify_hit) before it is stored.

Outputs in --output-dir: task.json, status.json, checkpoint.json, hits.jsonl,
chunks.jsonl, run.log, worker.stderr.log, continuation.task.json (only when d
values remain). Re-running with the same task and output directory resumes.
Exit status: 0 complete or deliberately partial, 1 error.
Resumes must use the same worker SHA-256 as all saved results. Pin a release
explicitly with --expected-worker-sha256.

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


def checked_sha256(value: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise ValueError("worker SHA-256 must be 64 hexadecimal characters")
    return value.lower()


def run(args: argparse.Namespace) -> int:
    task = load_json(args.task)
    t = validate_task(task)
    worker = Path(args.worker).resolve()
    if not worker.is_file() or not os.access(worker, os.X_OK):
        raise ValueError(f"worker is not executable: {worker}")
    worker_sha = sha256_file(worker)
    expected_sha = checked_sha256(args.expected_worker_sha256) if args.expected_worker_sha256 is not None else None
    if expected_sha and worker_sha != expected_sha:
        raise TaskMismatch(f"worker SHA-256 {worker_sha} differs from expected {expected_sha}")
    deadline = t["deadline_seconds"] if args.deadline_seconds is None else args.deadline_seconds
    if deadline < 0 or args.chunk <= 0 or not 0 <= args.partial_exit_code <= 255:
        raise ValueError("need deadline >= 0, chunk > 0 and partial-exit-code in [0, 255]")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cp_path, hits_path = out / "checkpoint.json", out / "hits.jsonl"
    saved_status = load_json(out / "status.json") if (out / "status.json").exists() else {}
    saved_task = load_json(out / "task.json") if (out / "task.json").exists() else None
    if saved_task is not None:
        saved = validate_task(saved_task)
        if (any(saved_task[key] != task[key] for key in ("campaign_id", "task_id"))
                or any(saved[key] != t[key] for key in ("k", "d_stop", "ratio_max", "primitive"))):
            raise TaskMismatch("output directory holds a different task or search scope")

    # This directory covers exactly [covered_start, d_next). A resume may only continue that
    # interval: a task starting before covered_start (e.g. the original task re-run where its
    # continuation ran) would otherwise be credited with d values this directory never searched.
    cursor = covered_start = t["d_start"]
    counters = {key: 0 for key in COUNTERS}
    elapsed_total = 0.0
    cp = None
    recovery_notice = None
    if cp_path.exists():
        try:
            cp = load_json(cp_path)
        except (OSError, ValueError) as exc:
            recovery_notice = f"unreadable checkpoint; restarting at the task's d_start: {exc}"
    provenance = set()
    for label, record in (("checkpoint", cp), ("status", saved_status)):
        if record and "worker_sha256" in record:
            try:
                provenance.add(checked_sha256(record["worker_sha256"]))
            except ValueError as exc:
                raise TaskMismatch(f"saved {label} has invalid worker provenance: {exc}") from exc
        elif record and label == "checkpoint":
            raise TaskMismatch("saved checkpoint has no worker SHA-256; use a fresh output directory")
    if provenance and provenance != {worker_sha}:
        raise TaskMismatch("saved results were produced by a different worker SHA-256; use a fresh output directory")
    if cp is not None:
        if cp.get("schema") != CHECKPOINT_SCHEMA or cp.get("task_id") != task["task_id"] \
                or cp.get("campaign_id") != task["campaign_id"]:
            raise TaskMismatch("output directory holds a checkpoint of a different task")
        cp_start, cp_next, cp_stop = int(cp["covered_start"]), int(cp["d_next"]), int(cp["d_stop"])
        if (cp_stop != t["d_stop"] or int(cp["ratio_max"]) != t["ratio_max"] or int(cp["k"]) != t["k"]
                or bool(cp.get("primitive", True)) != t["primitive"]):
            raise TaskMismatch("checkpoint parameters differ from the task")
        if not 1 <= cp_start <= t["d_start"] <= cp_next <= cp_stop:
            raise TaskMismatch(f"task starts at {t['d_start']} but this directory covers [{cp_start}, {cp_next}); "
                             "use a fresh output directory")
        cursor, covered_start = cp_next, cp_start
        counters.update({key: int(cp["counters"].get(key, 0)) for key in COUNTERS})
        elapsed_total = float(cp.get("worker_seconds", 0.0))
    elif saved_task is not None and saved["d_start"] != t["d_start"]:
        raise TaskMismatch("changed starting point has no matching checkpoint; use a fresh output directory")
    seen = set()
    if hits_path.exists():
        for line in hits_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    h = json.loads(line)
                    verify_hit(h, t["k"])
                    if "worker_sha256" in h:
                        hit_sha = checked_sha256(h["worker_sha256"])
                        if hit_sha != worker_sha:
                            raise ValueError("hit was produced by a different worker SHA-256")
                        provenance.add(hit_sha)
                    elif not provenance:
                        raise ValueError("hit has no saved worker provenance")
                except (KeyError, TypeError, ValueError) as exc:
                    raise TaskMismatch(f"saved hit cannot be reused: {exc}") from exc
                seen.add((h["x"], h["y"], h["z"]))
    if (out / "chunks.jsonl").exists() and (out / "chunks.jsonl").stat().st_size and not provenance:
        raise TaskMismatch("saved chunks have no worker provenance; use a fresh output directory")
    if cursor == t["d_stop"] and cp.get("terminal_state") != "complete" and saved_status.get("state") != "complete":
        raise TaskMismatch("checkpoint reaches the endpoint without a confirmed completion; use a fresh output directory")
    atomic_json(out / "task.json", task)

    log = (out / "run.log").open("a", encoding="utf-8")

    def say(msg: str) -> None:
        log.write(f"{now()} {msg}\n")
        log.flush()

    if recovery_notice:
        print(f"run_gap_task: {recovery_notice}", file=sys.stderr)
        say(recovery_notice)

    def status(state: str, error: str | None = None) -> None:
        atomic_json(out / "status.json", {
            "schema": STATUS_SCHEMA, "state": state, "error": error, "method": METHOD,
            "campaign_id": task["campaign_id"], "task_id": task["task_id"], "k": t["k"],
            "d_start": str(t["d_start"]), "d_stop": str(t["d_stop"]), "covered_start": str(covered_start),
            "d_next": str(cursor),
            "ratio_max": t["ratio_max"], "primitive": t["primitive"], "worker_sha256": worker_sha, "counters": counters,
            "worker_seconds": round(elapsed_total, 3), "hits": len(seen), "updated": now()})

    if cursor >= t["d_stop"]:
        status("complete")
        (out / "continuation.task.json").unlink(missing_ok=True)
        return 0
    if cursor != t["d_start"] and not cp_path.exists():
        raise ValueError("internal: resume without checkpoint")
    cmd = [str(worker), "--k", str(t["k"]), "--d-start", str(cursor), "--d-stop", str(t["d_stop"]),
           "--ratio-max", str(t["ratio_max"]), "--deadline-seconds", str(deadline), "--chunk", str(args.chunk)]
    if t["primitive"]:
        cmd.append("--primitive")
    say("start " + " ".join(cmd))
    status("running")
    stderr = (out / "worker.stderr.log").open("a", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
    stopped = {"signal": None}

    def on_signal(signum, _frame):
        stopped["signal"] = signum
        if proc.poll() is None:
            proc.terminate()
    old_handlers = {sig: signal.signal(sig, on_signal) for sig in (signal.SIGTERM, signal.SIGINT)}

    end_state = None
    started = False
    attempt_start = cursor
    durable_cursor, durable_counters = cursor, dict(counters)
    protocol_error = None
    t0 = time.monotonic()

    def checkpoint(terminal_state=None):
        nonlocal durable_cursor, durable_counters
        atomic_json(cp_path, {"schema": CHECKPOINT_SCHEMA, "campaign_id": task["campaign_id"],
                              "task_id": task["task_id"], "k": t["k"], "ratio_max": t["ratio_max"],
                              "primitive": t["primitive"], "method": METHOD,
                              "covered_start": str(covered_start), "d_stop": str(t["d_stop"]),
                              "worker_sha256": worker_sha, "d_next": str(cursor), "counters": counters,
                              "worker_seconds": round(elapsed_total + time.monotonic() - t0, 3),
                              "terminal_state": terminal_state, "updated": now()})
        durable_cursor, durable_counters = cursor, dict(counters)

    try:
        with hits_path.open("a", encoding="utf-8") as hits, (out / "chunks.jsonl").open("a", encoding="utf-8") as chunks:
            assert proc.stdout is not None
            for line in proc.stdout:
                rec = json.loads(line)
                kind = rec.get("type")
                if end_state is not None:
                    raise RuntimeError("worker emitted output after its terminal record")
                if kind == "start":
                    if started:
                        raise RuntimeError("worker emitted more than one start record")
                    if (rec.get("method") != METHOD or int(rec["k"]) != t["k"]
                            or int(rec["d_start"]) != attempt_start or int(rec["d_stop"]) != t["d_stop"]
                            or int(rec["ratio_max"]) != t["ratio_max"] or rec.get("primitive") is not t["primitive"]):
                        raise RuntimeError("worker start record does not match the task")
                    started = True
                    continue
                if not started:
                    raise RuntimeError("worker output is missing a matching start record")
                if kind == "hit":
                    verify_hit(rec, t["k"])
                    if "worker_sha256" in rec and checked_sha256(rec["worker_sha256"]) != worker_sha:
                        raise RuntimeError("worker hit has conflicting provenance")
                    rec["worker_sha256"] = worker_sha
                    key = (rec["x"], rec["y"], rec["z"])
                    if key not in seen:
                        seen.add(key)
                        hits.write(json.dumps(rec, sort_keys=True) + "\n")
                        hits.flush()
                        os.fsync(hits.fileno())
                        say(f"HIT x={rec['x']} y={rec['y']} z={rec['z']} primitive={rec.get('primitive')}")
                elif kind == "chunk":
                    if int(rec["d_start"]) != cursor:
                        raise RuntimeError(f"worker chunk starts at {rec['d_start']}, expected {cursor}")
                    next_cursor = int(rec["d_stop"])
                    if not cursor < next_cursor <= t["d_stop"]:
                        raise RuntimeError("worker chunk endpoint is outside the remaining task interval")
                    for key in COUNTERS:
                        if int(rec["counters"][key]) < 0:
                            raise RuntimeError("worker chunk has a negative counter")
                    for key in COUNTERS:
                        counters[key] += int(rec["counters"][key])
                    cursor = next_cursor
                    rec["worker_sha256"] = worker_sha
                    chunks.write(json.dumps(rec, sort_keys=True) + "\n")
                    chunks.flush()
                    # Commit the final chunk only after a valid terminal record and exit.
                    # A crash in that small window therefore replays at most one chunk.
                    if cursor < t["d_stop"]:
                        checkpoint()
                elif kind == "end":
                    end_state = rec["state"]
                    if int(rec["d_next"]) != cursor:
                        raise RuntimeError("worker end record disagrees with chunk records")
                    if end_state not in ("complete", "partial"):
                        raise RuntimeError("worker terminal state must be complete or partial")
                    if (end_state == "complete") != (cursor == t["d_stop"]):
                        raise RuntimeError("worker terminal state does not match the completed interval")
                else:
                    raise RuntimeError(f"unknown worker record type: {kind!r}")
    except Exception as exc:  # retain the last durable checkpoint and report the protocol failure
        protocol_error = str(exc)
    finally:
        if protocol_error is not None and proc.poll() is None:
            proc.kill()
        try:
            rc = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = proc.wait()
            protocol_error = protocol_error or "worker did not exit after closing its output"
        for sig, previous in old_handlers.items():
            signal.signal(sig, previous)
        stderr.close()
    if not protocol_error and rc == 0 and end_state == "complete":
        checkpoint("complete")
    elif cursor == t["d_stop"]:
        cursor, counters = durable_cursor, durable_counters
    elapsed_total += time.monotonic() - t0
    say(f"worker exit {rc}, d_next={cursor}")
    if protocol_error:
        status("error", protocol_error)
        return 1
    if rc != 0 and stopped["signal"] is None:
        status("error", f"worker exited with status {rc}; see worker.stderr.log")
        return 1
    if not started and stopped["signal"] is None:
        status("error", "worker stopped without a matching start record")
        return 1
    if end_state is None and stopped["signal"] is None:
        status("error", "worker stopped without a valid terminal record")
        return 1
    if end_state == "complete" and rc == 0:
        status("complete")
        (out / "continuation.task.json").unlink(missing_ok=True)
        return 0
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
    ap.add_argument("--expected-worker-sha256", help="require this exact worker binary SHA-256")
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
