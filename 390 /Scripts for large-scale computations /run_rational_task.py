#!/usr/bin/env python3
"""Run one restartable CE390 task with equal reduced rational coordinate denominators.

The durable output/continuation lifecycle follows run_task.py but uses distinct
schemas, certificates, policies, and pins both the worker and Python source.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import signal
import sys
import time
from typing import Any
from run_task import (Worker, Halt, DECIMAL, atomic_json, canonical, digest, integer,
                      keys, load_json, sha256_file)
from q_sieve import reject_q
from rational_common import (PARAMETERIZATION, validate_task, validate_hit,
                             certificate_key, candidate_index, iter_candidates)


def implementation_sha256() -> str:
    root=Path(__file__).resolve().parent
    names=("run_rational_task.py", "rational_common.py", "run_task.py", "parameter_space.py", "q_sieve.py")
    return digest({name:sha256_file(root/name) for name in names})


def recover_hits(path: Path, task: dict, parsed: dict) -> set[str]:
    seen=set()
    if not path.exists():
        path.touch()
        return seen
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:
                raise ValueError("duplicate stored certificate key")
            result[key]=value
        return result
    with path.open("rb+") as source:
        while True:
            offset=source.tell()
            line=source.readline()
            if not line:
                break
            if not line.endswith(b"\n"):
                source.truncate(offset)
                source.flush()
                os.fsync(source.fileno())
                break
            row=json.loads(line, object_pairs_hook=unique)
            a=integer(row["a"],"stored a",positive=True)
            q=integer(row["q"],"stored q",positive=True)
            checked=validate_hit(row,a,q,task["search"])
            key=certificate_key(checked)
            index=candidate_index(parsed,a,q)
            if (row.get("task_id")!=task["task_id"] or row.get("certificate_sha256")!=key
                    or row.get("candidate_index")!=str(index)
                    or not parsed["start"]<=index<parsed["stop"]):
                raise ValueError("stored rational certificate identity, hash or index mismatch")
            seen.add(key)
    return seen


def run(args: argparse.Namespace) -> int:
    task = load_json(args.task)
    parsed = validate_task(task)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (output / ".run.lock").open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("another supervisor owns this output directory") from exc
        return _run_locked(args, task, parsed, output)


def _run_locked(args: argparse.Namespace, task: dict, parsed: dict, output: Path) -> int:
    worker_path = args.worker.resolve()
    if not worker_path.is_file() or not os.access(worker_path, os.X_OK):
        raise ValueError(f"worker is not an executable file: {worker_path}")
    worker_sha = sha256_file(worker_path)
    code_sha = implementation_sha256()
    if task.get("expected_implementation_sha256", code_sha) != code_sha:
        raise ValueError("Python implementation differs from the pinned rational continuation")
    if task.get("expected_worker_sha256", worker_sha) != worker_sha:
        raise ValueError("worker differs from the binary pinned by this continuation")
    checkpoint_path = args.checkpoint if args.checkpoint else output / "checkpoint.json"
    cursor = parsed["resume"]
    if checkpoint_path.exists():
        cp = load_json(checkpoint_path)
        if cp.get("schema") != "ce390-rational-checkpoint-v1" or cp.get("task_id") != task["task_id"]:
            raise ValueError("checkpoint belongs to another task")
        if cp.get("worker_sha256") != worker_sha or cp.get("implementation_sha256") != code_sha:
            raise ValueError("checkpoint worker hash differs from this executable")
        cp_index = integer(cp.get("next_index"), "checkpoint.next_index")
        if not parsed["start"] <= cp_index <= parsed["stop"]:
            raise ValueError("checkpoint cursor lies outside the task slice")
        cursor = max(cursor, cp_index)
    elif args.checkpoint:
        raise ValueError("explicit checkpoint file does not exist")
    # A retained local checkpoint carries contiguous coverage of this output
    # directory. An imported checkpoint establishes only the new starting cursor.
    output_start = cursor
    required_retained_hits = 0
    prior_status = None
    if (output / "status.json").exists():
        prior_status = load_json(output / "status.json")
        if prior_status.get("task_id") != task["task_id"] or prior_status.get("worker_sha256") != worker_sha or prior_status.get("implementation_sha256") != code_sha:
            raise ValueError("retained status identity differs from this task or worker")
        required_retained_hits = integer(prior_status.get("unique_hits_in_this_output"), "retained status unique hit count")
    local_checkpoint = output / "checkpoint.json"
    if local_checkpoint.exists():
        local_cp = load_json(local_checkpoint)
        if local_cp.get("task_id") != task["task_id"] or local_cp.get("worker_sha256") != worker_sha or local_cp.get("implementation_sha256") != code_sha:
            raise ValueError("retained output checkpoint identity differs from this task or worker")
        checkpoint_hit_count = integer(local_cp.get("unique_hits_in_this_output", "0"), "retained checkpoint unique hit count")
        required_retained_hits = max(required_retained_hits, checkpoint_hit_count)
        local_stop = integer(local_cp.get("next_index"), "retained checkpoint.next_index")
        local_start = integer(local_cp.get("output_coverage_start", str(local_stop)), "retained checkpoint.output_coverage_start")
        if not parsed["start"] <= local_start <= local_stop <= parsed["stop"]:
            raise ValueError("retained output coverage is invalid")
        retained_files = all((output / name).exists() for name in ("task.json", "status.json", "hits.jsonl"))
        if local_stop == cursor and retained_files:
            assert prior_status is not None
            prior_coverage = prior_status.get("output_coverage", prior_status.get("invocation_coverage"))
            keys(prior_coverage, {"start", "stop"}, set(), "retained status coverage")
            prior_start = integer(prior_coverage["start"], "retained status coverage.start")
            prior_stop = integer(prior_coverage["stop"], "retained status coverage.stop")
            # The checkpoint is written before status. It may include more fully
            # verified fibers than the last status snapshot after a hard crash.
            if prior_start != local_start or not local_start <= prior_stop <= local_stop:
                raise ValueError("retained status coverage conflicts with its checkpoint")
            if prior_status.get("next_index") != str(prior_stop):
                raise ValueError("retained status cursor conflicts with its coverage")
            output_start = local_start
    if (output / "task.json").exists():
        prior_task = load_json(output / "task.json")
        validate_task(prior_task)
        if prior_task.get("task_id") != task["task_id"]:
            raise ValueError("output directory already belongs to a different task")
    if required_retained_hits and not (output / "hits.jsonl").exists():
        raise ValueError("retained hit file is missing despite a positive durable hit count")
    seen = recover_hits(output / "hits.jsonl", task, parsed)
    if len(seen) < required_retained_hits:
        raise ValueError("retained hit records were lost: recovered unique count is below durable status/checkpoint count")
    atomic_json(output / "task.json", task)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    started_monotonic = time.monotonic()
    deadline = started_monotonic + parsed["seconds"]
    initial_cursor = cursor
    counters = {"fibers_completed": 0, "cf_fibers_completed": 0, "non_coprime_skipped": 0,
                "congruence_excluded": 0, "q_sieve_excluded": 0, "bounds_excluded": 0, "new_hits": 0, "convergents": 0}
    stop_signal: list[int] = []

    def on_signal(signum: int, _frame: Any) -> None:
        stop_signal.append(signum)

    old_handlers = {sig: signal.signal(sig, on_signal) for sig in (signal.SIGINT, signal.SIGTERM)}
    log_file = (output / "run.log").open("a", encoding="utf-8", buffering=1)

    def log(message: str) -> None:
        line = f"{dt.datetime.now(dt.timezone.utc).isoformat()} {message}"
        print(line, flush=True)
        log_file.write(line + "\n")

    def snapshot(state: str, reason: str) -> dict[str, Any]:
        return {
            "schema": "ce390-rational-status-v1", "task_id": task["task_id"], "campaign_id": task["campaign_id"],
            "worker_sha256": worker_sha, "implementation_sha256": code_sha, "state": state, "reason": reason,
            "complete": cursor == parsed["stop"] and state == "complete",
            "started_utc": started, "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - started_monotonic, 6),
            "time_limit_seconds": parsed["seconds"], "slice": task["slice"],
            "invocation_coverage": {"start": str(initial_cursor), "stop": str(cursor)},
            "output_coverage": {"start": str(output_start), "stop": str(cursor)},
            "next_index": str(cursor), "remaining_indices": str(parsed["stop"] - cursor),
            "counters_this_invocation": {key: str(value) for key, value in counters.items()},
            "unique_hits_in_this_output": str(len(seen)),
            "coverage_note": "Only completed slope indices at this exact reduced coordinate denominator are covered; other b values and unfinished indices are not covered.",
        }

    def checkpoint(state: str, reason: str) -> None:
        atomic_json(output / "checkpoint.json", {"schema": "ce390-rational-checkpoint-v1", "task_id": task["task_id"],
                    "worker_sha256": worker_sha, "implementation_sha256": code_sha, "next_index": str(cursor), "output_coverage_start": str(output_start),
                    "unique_hits_in_this_output": str(len(seen)), "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat()})
        atomic_json(output / "status.json", snapshot(state, reason))
        if cursor < parsed["stop"]:
            continuation = dict(task)
            continuation["resume_index"] = str(cursor)
            continuation["expected_worker_sha256"] = worker_sha
            continuation["expected_implementation_sha256"] = code_sha
            atomic_json(output / "continuation.task.json", continuation)
        else:
            (output / "continuation.task.json").unlink(missing_ok=True)

    argv = [str(worker_path), "--n-min", task["search"]["n_min"], "--n-max", task["search"]["n_max"],
            "--x-min", task["search"]["x_min"], "--x-max", task["search"]["x_max"],
            "--precision-bits", str(parsed["precision"]), "--max-precision-bits", str(parsed["max_precision"]),
            "--signs", parsed["signs"]]
    argv += ["--coordinate-denominator", task["search"]["coordinate_denominator"],
             "--congruence-policy", task["search"]["congruence_policy"]]
    if task["search"]["require_noninteger_d"]:
        argv.append("--noninteger-d")
    # No missing-policy default is allowed in the new task schema.
    if task["search"].get("require_integer_sqrt", False):
        argv.append("--integer-sqrt")
    else:
        argv.append("--allow-rational-sqrt")
    log(f"Starting task {task['task_id']} at candidate {cursor}, stop {parsed['stop']}; worker SHA256 {worker_sha}")
    checkpoint("running", "started")
    worker: Worker | None = None
    state, reason = "partial", "unknown"
    last_checkpoint = time.monotonic()
    error: str | None = None
    try:
        with (output / "worker.stderr.log").open("ab", buffering=0) as worker_stderr, (output / "hits.jsonl").open("ab", buffering=0) as hits_out:
            if cursor < parsed["stop"]:
                worker = Worker(argv, worker_stderr, deadline, lambda: bool(stop_signal))
            candidates = iter_candidates(parsed, cursor, parsed["stop"])
            while cursor < parsed["stop"]:
                if stop_signal:
                    raise Halt("signal")
                if time.monotonic() >= deadline:
                    raise Halt("time_limit")
                a, q = next(candidates)
                if math.gcd(a, q) != 1:
                    counters["non_coprime_skipped"] += 1
                    cursor += 1
                elif reject_q(q, require_integer_sqrt=task["search"].get("require_integer_sqrt", False)):
                    # Integer y implies q | |X| and X | (36*N^3-65*b^3). An obstructing
                    # prime proves this indexed fibre empty. Keep its index
                    # and the common checkpoint/deadline path unchanged.
                    counters["congruence_excluded"] += 1
                    counters["q_sieve_excluded"] += 1
                    cursor += 1
                else:
                    assert worker is not None
                    result = worker.query(a, q)
                    if not isinstance(result, dict) or result.get("a") != str(a) or result.get("q") != str(q):
                        raise RuntimeError("worker result did not match the submitted fiber")
                    if result.get("status") != "complete":
                        atomic_json(output / "worker_error.json", {"candidate_index": str(cursor), "worker_result": result})
                        raise RuntimeError("worker could not certify completion of this fiber; see worker_error.json")
                    if result.get("parameterization") != PARAMETERIZATION:
                        raise RuntimeError("worker reply used the wrong mathematical parameterization")
                    if result.get("signs") != parsed["signs"]:
                        raise RuntimeError("worker reply used the wrong signed search policy")
                    if (result.get("coordinate_denominator") != task["search"]["coordinate_denominator"]
                            or result.get("congruence_policy") != task["search"]["congruence_policy"]
                            or result.get("noninteger_d_required") is not task["search"]["require_noninteger_d"]):
                        raise RuntimeError("worker reply used the wrong rational-coordinate policy")
                    expected_integer_sqrt = task["search"].get("require_integer_sqrt", False)
                    if result.get("integer_sqrt_required") is not expected_integer_sqrt:
                        raise RuntimeError("worker reply used the wrong integer-square-root search policy")
                    for flag in ("excluded_by_congruence", "excluded_by_bounds", "excluded_by_q_sieve"):
                        if type(result.get(flag)) is not bool:
                            raise RuntimeError(f"worker reply has a missing or nonboolean {flag} flag")
                    rows = result.get("hits")
                    if not isinstance(rows, list):
                        raise RuntimeError("worker result has no hit list")
                    # Check every hit before accepting any part of this completed fiber.
                    checked_hits = [validate_hit(row, a, q, task["search"]) for row in rows]
                    if task["search"].get("require_integer_sqrt", False) and any(not row["sqrt_integer"] for row in checked_hits):
                        raise RuntimeError("worker returned a noninteger square root in integer-only mode")
                    for hit in checked_hits:
                        key = certificate_key(hit)
                        if key not in seen:
                            hit.update(a=str(a), q=str(q), task_id=task["task_id"],
                                       candidate_index=str(cursor), certificate_sha256=key)
                            hits_out.write(canonical(hit) + b"\n")
                            os.fsync(hits_out.fileno())
                            seen.add(key)
                            counters["new_hits"] += 1
                            log(f"Certified hit {key}: n={hit['n_num']}/{hit['n_den']} x={hit['x_num']}/{hit['x_den']}")
                    counter = result.get("convergents", "0")
                    if isinstance(counter, str) and DECIMAL.fullmatch(counter):
                        counters["convergents"] += int(counter)
                    elif type(counter) is int and counter >= 0:
                        counters["convergents"] += counter
                    else:
                        raise RuntimeError("invalid worker convergents counter")
                    if result.get("excluded_by_congruence", False):
                        counters["congruence_excluded"] += 1
                    elif result.get("excluded_by_bounds", False):
                        counters["bounds_excluded"] += 1
                    else:
                        counters["cf_fibers_completed"] += 1
                    if result["excluded_by_q_sieve"]:
                        if not expected_integer_sqrt or not result["excluded_by_congruence"] or rows:
                            raise RuntimeError("invalid worker q-sieve exclusion")
                        counters["q_sieve_excluded"] += 1
                    counters["fibers_completed"] += 1
                    cursor += 1
                now = time.monotonic()
                if now - last_checkpoint >= parsed["checkpoint_seconds"]:
                    checkpoint("running", "in_progress")
                    log(f"Checkpoint next candidate {cursor}; fibers completed this invocation {counters['fibers_completed']}")
                    last_checkpoint = now
            state, reason = "complete", "selected_fibers_exhausted"
    except Halt as exc:
        state, reason = "partial", exc.reason
    except Exception as exc:
        state, reason, error = "error", "worker_or_io_error", f"{type(exc).__name__}: {exc}"
        log(error)
        atomic_json(output / "error.json", {"error": error, "task_id": task["task_id"], "next_index": str(cursor)})
    finally:
        if worker is not None:
            worker.close()
        checkpoint(state, reason)
        log(f"Task {state}: {reason}; next candidate {cursor}; remaining {parsed['stop'] - cursor}")
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        log_file.close()
    # A soft deadline is a successful artifact-producing invocation, not completion.
    # Operators must inspect status.json and submit continuation.task.json if present.
    return 2 if error else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, default=Path("/local/input/task.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("/local/output"))
    parser.add_argument("--worker", type=Path, default=Path(__file__).resolve().parent / "bin" / "rational_cf_worker")
    parser.add_argument("--checkpoint", type=Path, help="checkpoint retrieved from an earlier host")
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as exc:
        error = f"CE390 rational supervisor error: {type(exc).__name__}: {exc}"
        print(error, file=sys.stderr, flush=True)
        try:
            # A unique name preserves existing task artifacts even when the failure
            # is an identity/lock conflict. Never overwrite another task's status.
            args.output_dir.mkdir(parents=True, exist_ok=True)
            failure = args.output_dir / f"startup-error-{time.time_ns()}-{os.getpid()}.json"
            atomic_json(failure, {"schema": "ce390-rational-startup-error-v1", "state": "error", "complete": False,
                        "reason": "startup_error", "error": error, "input_task": str(args.task),
                        "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat()})
        except OSError as output_exc:
            print(f"Could not retain startup error artifact: {output_exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
