#!/usr/bin/env python3
"""Run one immutable d-first page under its persistent 1,800-core-hour ceiling.

Run this controller on a POSIX/Linux host, reusing the same --output-dir on
every invocation. Each runner and its native worker share one process group
and one CPU affinity. All attempts, including failures and continuations,
consume one-core wall time in budget.json. Completed attempts return their
unused reservation. Crashed/unsettled attempts never receive an automatic
refund. The controller does not submit CE jobs or account for provider billing.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from d_budget import BUDGET_SCHEMA, NANOSECONDS, limit_nanoseconds, locked_ledger
from dfirst_common import PAGE_SCHEMA, STATUS_SCHEMA, validate_task
from run_d_task import GRACE_SECONDS
from run_task import digest, load_json, sha256_file

ROOT = Path(__file__).resolve().parent
# The runner may wait 30 s for an end-record process, then spend 5 s cleaning
# up; add startup allowance. The controller separately reserves its cleanup.
RUNNER_OVERHEAD_SECONDS = GRACE_SECONDS + 40
CLEANUP_SECONDS = 10


def load_page(path: Path) -> tuple[dict, list[tuple[Path, dict]], int]:
    page = load_json(path)
    if page.get("schema") != PAGE_SCHEMA or page.get("budget", {}).get("schema") != BUDGET_SCHEMA:
        raise ValueError("page needs a budget from the current d_campaign.py")
    budget_ns = limit_nanoseconds(page["budget"]["core_hours"])
    if page["budget"].get("limit_ns") != budget_ns:
        raise ValueError("page budget fields disagree")
    tasks = []
    cursor = int(page["shells"]["start"])
    seen = set()
    for entry in page["tasks"]:
        name = entry["file"]
        if Path(name).name != name:
            raise ValueError("task filename must be relative to the page directory")
        task_path = path.parent / name
        task = load_json(task_path)
        parsed = validate_task(task)
        if (task["task_id"] != entry["task_id"] or digest(task) != entry.get("task_sha256")
                or task["campaign_id"] != page["campaign_id"]
                or str(parsed["m"]) != page["m"] or parsed["g_max_digits"] != page["g_max_digits"]
                or task["shells"] != entry["shells"] or parsed["start"] != cursor
                or task["task_id"] in seen or "resume" in task):
            raise ValueError("page/task scope, hashes, or consecutive shell ranges disagree")
        seen.add(task["task_id"])
        cursor = parsed["stop"]
        tasks.append((task_path.resolve(), task))
    if not tasks or cursor != int(page["shells"]["stop"]):
        raise ValueError("page does not contain its complete task range")
    return page, tasks, budget_ns


def pin_one_cpu() -> None:
    available = os.sched_getaffinity(0)
    os.sched_setaffinity(0, {min(available)})


def execute_attempt(argv: list[str], output: Path, timeout: float,
                    stop_requested=lambda: False, cleanup_seconds: float = CLEANUP_SECONDS) -> dict:
    """Bound the entire process group, including a hung worker grandchild."""
    started = time.monotonic_ns()
    proc = None
    result = {"returncode": None, "timed_out": False, "interrupted": False, "error": None}
    try:
        output.mkdir(parents=True, exist_ok=False)
        with (output / "controller.log").open("wb") as console:
            proc = subprocess.Popen(argv, stdout=console, stderr=subprocess.STDOUT,
                                    start_new_session=True, preexec_fn=pin_one_cpu)
            deadline = started / NANOSECONDS + timeout
            while proc.poll() is None:
                if stop_requested():
                    result["interrupted"] = True
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    result["timed_out"] = True
                    break
                try:
                    proc.wait(timeout=min(0.25, remaining))
                except subprocess.TimeoutExpired:
                    pass
    except (OSError, ValueError) as exc:
        result["error"] = str(exc)
    finally:
        if proc is not None:
            # Even an exited runner may have left a worker in its process
            # group. TERM then KILL always addresses the entire group.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=cleanup_seconds / 2)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                result["returncode"] = proc.wait(timeout=cleanup_seconds / 2)
            except subprocess.TimeoutExpired:
                # Keep the reservation unresolved: process exit is unknown.
                raise RuntimeError("process group could not be reaped; its budget reservation remains held")
    result["elapsed_ns"] = time.monotonic_ns() - started
    return result


def run(args: argparse.Namespace) -> dict:
    if not hasattr(os, "sched_setaffinity"):
        raise ValueError("budgeted execution requires Linux CPU affinity support")
    page_path, output = args.page.resolve(), args.output_dir.resolve()
    page, tasks, budget_ns = load_page(page_path)
    worker = args.worker.resolve()
    if not worker.is_file() or not os.access(worker, os.X_OK):
        raise ValueError(f"worker is not executable: {worker}")
    identity = digest({"page": page, "output_dir": str(output),
                       "worker_sha256": sha256_file(worker)})
    stop = {"requested": False}
    old_handlers = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        old_handlers[sig] = signal.signal(sig, lambda _sig, _frame: stop.update(requested=True))
    reason, attempted, completed = "complete", 0, 0
    try:
        with locked_ledger(output, identity, budget_ns) as ledger:
            for original_path, original in tasks:
                history = [a for a in ledger.data["attempts"] if a["task_id"] == original["task_id"]]
                previous = history[-1] if history else None
                if previous and previous.get("task_state") == "complete":
                    completed += 1
                    continue
                current_path = original_path
                if previous and previous.get("continuation_file"):
                    current_path = Path(previous["continuation_file"])
                    if digest(load_json(current_path)) != previous["continuation_sha256"]:
                        raise ValueError("continuation was changed after its budget settlement")
                while True:
                    if stop["requested"] or (args.max_attempts is not None and attempted >= args.max_attempts):
                        reason = "signal" if stop["requested"] else "attempt_limit"
                        break
                    task = load_json(current_path)
                    parsed = validate_task(task)
                    if task["task_id"] != original["task_id"]:
                        raise ValueError("continuation belongs to another task")
                    timeout = parsed["seconds"] + RUNNER_OVERHEAD_SECONDS
                    attempt_dir = output / f"attempt-{len(ledger.data['attempts']):06d}"
                    entry = ledger.reserve(timeout + CLEANUP_SECONDS, task["task_id"],
                                           str(current_path), str(attempt_dir))
                    if entry is None:
                        reason = "budget_exhausted"
                        break
                    argv = [sys.executable, str(ROOT / "run_d_task.py"), "--task", str(current_path),
                            "--output-dir", str(attempt_dir), "--worker", str(worker),
                            "--managed-process-group"]
                    result = execute_attempt(argv, attempt_dir, timeout, lambda: stop["requested"])
                    attempted += 1
                    task_state, continuation, continuation_hash, next_h = "error", None, None, parsed["resume"]
                    try:
                        status = load_json(attempt_dir / "status.json")
                        if status.get("schema") != STATUS_SCHEMA or status.get("task_id") != task["task_id"]:
                            raise ValueError("runner returned a status for another task")
                        next_h = int(status["next_h"])
                        if not parsed["resume"] <= next_h <= parsed["stop"]:
                            raise ValueError("runner returned invalid coverage")
                        task_state = status["state"]
                        if task_state == "complete" and next_h != parsed["stop"]:
                            raise ValueError("runner claimed complete before the last shell")
                        candidate = attempt_dir / "continuation.task.json"
                        if candidate.exists():
                            cont = load_json(candidate)
                            checked = validate_task(cont)
                            if cont["task_id"] != task["task_id"] or checked["resume"] != next_h:
                                raise ValueError("runner continuation disagrees with its status")
                            continuation, continuation_hash = str(candidate), digest(cont)
                    except (OSError, ValueError, KeyError) as exc:
                        result["error"] = str(exc)
                        task_state = "error"
                    if result["returncode"] != 0 or result["timed_out"] or result["error"]:
                        task_state = "error"
                    elapsed = result.pop("elapsed_ns")
                    ledger.settle(entry, elapsed, **result, task_state=task_state,
                                  continuation_file=continuation, continuation_sha256=continuation_hash,
                                  next_h=str(next_h))
                    if task_state == "complete":
                        completed += 1
                        break
                    if task_state == "error" or result["interrupted"]:
                        reason = "signal" if result["interrupted"] else "task_error"
                        break
                    if next_h <= parsed["resume"] or continuation is None:
                        reason = "no_progress"
                        break
                    current_path = Path(continuation)
                if reason != "complete":
                    break
            summary = {"campaign_id": page["campaign_id"], "reason": reason,
                       "complete": completed == len(tasks), "completed_tasks": completed,
                       "total_tasks": len(tasks), "attempts_this_invocation": attempted,
                       "total_attempts": len(ledger.data["attempts"]),
                       "charged_core_hours": ledger.data["charged_ns"] / NANOSECONDS / 3600,
                       "remaining_core_hours": ledger.remaining_ns / NANOSECONDS / 3600,
                       "budget_core_hours": budget_ns / NANOSECONDS / 3600,
                       "budget_ledger": str(output / "budget.json")}
            return summary
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--page", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="reuse this directory to preserve the project ledger")
    parser.add_argument("--worker", type=Path, default=ROOT / "bin/dthue_worker")
    parser.add_argument("--max-attempts", type=int, help="stop after this many additional attempts, e.g. 1 for a pilot")
    args = parser.parse_args(argv)
    if args.max_attempts is not None and args.max_attempts < 1:
        parser.error("max-attempts must be positive")
    try:
        summary = run(args)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"run_d_campaign: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    return 1 if summary["reason"] == "task_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
