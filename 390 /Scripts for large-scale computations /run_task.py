#!/usr/bin/env python3
"""Bounded, restartable CE390 worker supervisor (Python 3 standard library only)."""
from __future__ import annotations

import argparse
import datetime as dt
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time
from typing import Any

SCHEMA = "ce390-task-v1"
PARAMETERIZATION = "d=-1-a/(2q);positive-odd-coprime-a-q"
DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\Z")
SIGNED = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_LINE_BYTES = 16 * 1024 * 1024
DEFAULT_N_MIN = 10**43
DEFAULT_N_MAX = 10**45
DEFAULT_X_MIN = 10**54
DEFAULT_X_MAX = 10**55


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def keys(value: Any, required: set[str], optional: set[str], context: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object")
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing or unknown:
        raise ValueError(f"{context}: missing keys {sorted(missing)}, unknown keys {sorted(unknown)}")


def integer(value: Any, context: str, *, positive: bool = False, signed: bool = False) -> int:
    pattern = SIGNED if signed else DECIMAL
    if not isinstance(value, str) or len(value) > 5000 or not pattern.fullmatch(value):
        raise ValueError(f"{context} must be a canonical decimal integer string")
    result = int(value)
    if positive and result <= 0:
        raise ValueError(f"{context} must be positive")
    return result


def small_int(value: Any, low: int, high: int, context: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{context} must be an integer in [{low}, {high}]")
    return value


def task_identity(task: dict[str, Any]) -> str:
    return digest({key: task[key] for key in ("schema", "parameterization", "campaign_id", "search", "fibers", "slice")})


def validate_task(task: Any) -> dict[str, Any]:
    keys(task, {"schema", "parameterization", "campaign_id", "task_id", "search", "fibers", "slice", "execution"},
         {"resume_index", "expected_worker_sha256"}, "task")
    if task["schema"] != SCHEMA or task["parameterization"] != PARAMETERIZATION:
        raise ValueError("unsupported task schema or parameterization")
    if not isinstance(task["campaign_id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", task["campaign_id"]):
        raise ValueError("campaign_id must be 1-96 safe ASCII filename characters")
    keys(task["search"], {"n_min", "n_max", "x_min", "x_max"}, {"require_integer_sqrt"}, "search")
    if type(task["search"].get("require_integer_sqrt", False)) is not bool:
        raise ValueError("search.require_integer_sqrt must be a boolean")
    bounds = {k: integer(task["search"][k], f"search.{k}", positive=True) for k in ("n_min", "n_max", "x_min", "x_max")}
    if bounds["n_min"] > bounds["n_max"] or bounds["x_min"] > bounds["x_max"]:
        raise ValueError("search bounds must be ordered and inclusive")
    keys(task["fibers"], {"a_values", "q_min", "q_max"}, set(), "fibers")
    raw_a = task["fibers"]["a_values"]
    if not isinstance(raw_a, list) or not raw_a or len(raw_a) > 100000:
        raise ValueError("a_values must contain between 1 and 100000 positive odd integers")
    values_a = [integer(v, "fibers.a_values[]", positive=True) for v in raw_a]
    if len(set(values_a)) != len(values_a) or any(a % 2 == 0 for a in values_a):
        raise ValueError("a_values must be unique and odd")
    q_min = integer(task["fibers"]["q_min"], "fibers.q_min", positive=True)
    q_max = integer(task["fibers"]["q_max"], "fibers.q_max", positive=True)
    if q_min % 2 == 0 or q_max % 2 == 0 or q_min > q_max:
        raise ValueError("q_min and q_max must be ordered, positive and odd")
    q_count = (q_max - q_min) // 2 + 1
    count = q_count * len(values_a)
    keys(task["slice"], {"start", "stop"}, set(), "slice")
    start = integer(task["slice"]["start"], "slice.start")
    stop = integer(task["slice"]["stop"], "slice.stop", positive=True)
    if not 0 <= start < stop <= count:
        raise ValueError("slice must be a nonempty half-open interval inside the candidate list")
    resume = integer(task.get("resume_index", str(start)), "resume_index")
    if not start <= resume <= stop:
        raise ValueError("resume_index is outside the slice")
    keys(task["execution"], {"time_limit_seconds", "precision_bits"}, {"max_precision_bits", "checkpoint_seconds"}, "execution")
    seconds = small_int(task["execution"]["time_limit_seconds"], 1, 6600, "execution.time_limit_seconds")
    precision = small_int(task["execution"]["precision_bits"], 64, 16384, "execution.precision_bits")
    max_precision = small_int(task["execution"].get("max_precision_bits", 16384), precision, 65536, "execution.max_precision_bits")
    checkpoint_seconds = small_int(task["execution"].get("checkpoint_seconds", 5), 1, 60, "execution.checkpoint_seconds")
    if task["task_id"] != task_identity(task):
        raise ValueError("task_id does not match the immutable search definition")
    if "expected_worker_sha256" in task and not HEX64.fullmatch(str(task["expected_worker_sha256"])):
        raise ValueError("expected_worker_sha256 must be a lowercase SHA256 digest")
    return dict(bounds=bounds, a_values=values_a, q_min=q_min, q_count=q_count, count=count,
                start=start, stop=stop, resume=resume, seconds=seconds, precision=precision,
                max_precision=max_precision, checkpoint_seconds=checkpoint_seconds)


def load_json(path: Path) -> Any:
    # Reject duplicate keys: silently choosing the last value can change a task.
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for k, v in pairs:
            if k in obj:
                raise ValueError(f"duplicate JSON key: {k}")
            obj[k] = v
        return obj
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def atomic_json(path: Path, value: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as out:
        json.dump(value, out, sort_keys=True, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)
    directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def candidate(parsed: dict[str, Any], index: int) -> tuple[int, int]:
    ai, qi = divmod(index, parsed["q_count"])
    return parsed["a_values"][ai], parsed["q_min"] + 2 * qi


def validate_hit(hit: Any, a: int, q: int, bounds: dict[str, int]) -> dict[str, Any]:
    if not isinstance(hit, dict):
        raise ValueError("worker hit must be an object")
    required = {"n", "x", "y_num", "y_den", "d_num", "d_den", "gap_num", "gap_den", "sqrt_integer"}
    if not required <= hit.keys():
        raise ValueError(f"worker hit missing {sorted(required - hit.keys())}")
    values = {k: integer(hit[k], f"hit.{k}", signed=True) for k in required - {"sqrt_integer"}}
    n, x = values["n"], values["x"]
    if not bounds["n_min"] <= n <= bounds["n_max"] or not bounds["x_min"] <= x <= bounds["x_max"]:
        raise ValueError("worker hit violates search bounds")
    if n % 3 != 1 or x % 12 != 5 or x % 7 == 0:
        raise ValueError("worker hit violates congruences")
    if any(values[k] <= 0 for k in ("y_den", "d_den", "gap_den")):
        raise ValueError("certificate denominators must be positive")
    y = Fraction(values["y_num"], values["y_den"])
    d = Fraction(values["d_num"], values["d_den"])
    gap = Fraction(values["gap_num"], values["gap_den"])
    if any(math.gcd(abs(values[k + "_num"]), values[k + "_den"]) != 1 for k in ("y", "d", "gap")):
        raise ValueError("certificate rational values must be reduced")
    c = 36 * n**3 - 65
    if y < 0 or y*y != (x + 6*n)**2 + Fraction(c, x):
        raise ValueError("worker hit fails exact nonnegative radical check")
    if d != -1 - Fraction(a, 2*q) or gap != y - (x + 6*n):
        raise ValueError("worker hit has wrong rational fiber or square-root gap")
    if c != -2 * d * x*x * gap:
        raise ValueError("worker hit fails original equation")
    if type(hit["sqrt_integer"]) is not bool or hit["sqrt_integer"] != (y.denominator == 1):
        raise ValueError("incorrect sqrt_integer marker")
    result = {k: str(values[k]) for k in sorted(values)}
    result["sqrt_integer"] = hit["sqrt_integer"]
    return result


def certificate_key(hit: dict[str, Any]) -> str:
    return digest({key: hit[key] for key in ("n", "x", "d_num", "d_den", "y_num", "y_den")})


def recover_hits(path: Path, bounds: dict[str, int], task_id: str, require_integer_sqrt: bool = False) -> set[str]:
    seen: set[str] = set()
    if not path.exists():
        path.touch()
        return seen
    with path.open("rb+") as source:
        while True:
            offset = source.tell()
            line = source.readline()
            if not line:
                break
            if not line.endswith(b"\n"):
                # Only an interrupted trailing append is discarded. Complete malformed
                # records are fatal and can never silently remove certified results.
                source.truncate(offset)
                source.flush()
                os.fsync(source.fileno())
                break
            row = json.loads(line)
            a = integer(row["a"], "stored hit.a", positive=True)
            q = integer(row["q"], "stored hit.q", positive=True)
            if a % 2 != 1 or q % 2 != 1 or math.gcd(a, q) != 1:
                raise ValueError("stored certificate has an invalid rational fiber")
            checked = validate_hit(row, a, q, bounds)
            if require_integer_sqrt and not checked["sqrt_integer"]:
                raise ValueError("stored certificate violates the integer-square-root subset")
            key = certificate_key(checked)
            if row.get("task_id") != task_id or row.get("certificate_sha256") != key:
                raise ValueError("stored certificate identity or checksum mismatch")
            seen.add(key)
    return seen


class Halt(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class Worker:
    def __init__(self, argv: list[str], stderr: Any, deadline: float, stopped: Any):
        self.deadline = deadline
        self.stopped = stopped
        self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=stderr, start_new_session=True, bufsize=0)
        assert self.process.stdout is not None
        os.set_blocking(self.process.stdout.fileno(), False)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer = bytearray()

    def query(self, a: int, q: int) -> Any:
        if self.stopped():
            raise Halt("signal")
        if time.monotonic() >= self.deadline:
            raise Halt("time_limit")
        assert self.process.stdin is not None and self.process.stdout is not None
        try:
            self.process.stdin.write(f"{a} {q}\n".encode("ascii"))
            self.process.stdin.flush()
        except BrokenPipeError as exc:
            raise RuntimeError("worker exited before accepting a fiber") from exc
        while True:
            if self.stopped():
                raise Halt("signal")
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise Halt("time_limit")
            if b"\n" in self.buffer:
                line, _, rest = self.buffer.partition(b"\n")
                self.buffer = bytearray(rest)
                try:
                    return json.loads(line)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise RuntimeError("worker produced invalid JSON") from exc
            ready = self.selector.select(min(0.2, remaining))
            if ready:
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise RuntimeError(f"worker exited or closed stdout (exit {self.process.poll()})")
                self.buffer.extend(chunk)
                if len(self.buffer) > MAX_LINE_BYTES:
                    raise RuntimeError("worker record exceeded the 16 MiB limit")

    def close(self) -> None:
        self.selector.close()
        if self.process.stdin is not None:
            try:
                self.process.stdin.close()
            except BrokenPipeError:
                pass
        if self.process.poll() is None:
            # All child processes are in the worker's own process group.
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.process.wait(timeout=2)
        if self.process.stdout is not None:
            self.process.stdout.close()


def run(args: argparse.Namespace) -> int:
    task = load_json(args.task)
    parsed = validate_task(task)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Prevent two supervisors from corrupting a shared output directory.
    import fcntl
    lock = (output / ".run.lock").open("a")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise ValueError("another supervisor owns this output directory") from exc
    worker_path = args.worker.resolve()
    if not worker_path.is_file() or not os.access(worker_path, os.X_OK):
        raise ValueError(f"worker is not an executable file: {worker_path}")
    worker_sha = sha256_file(worker_path)
    if task.get("expected_worker_sha256", worker_sha) != worker_sha:
        raise ValueError("worker differs from the binary pinned by this continuation")
    checkpoint_path = args.checkpoint if args.checkpoint else output / "checkpoint.json"
    cursor = parsed["resume"]
    if checkpoint_path.exists():
        cp = load_json(checkpoint_path)
        if cp.get("schema") != "ce390-checkpoint-v1" or cp.get("task_id") != task["task_id"]:
            raise ValueError("checkpoint belongs to another task")
        if cp.get("worker_sha256") != worker_sha:
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
        if prior_status.get("task_id") != task["task_id"] or prior_status.get("worker_sha256") != worker_sha:
            raise ValueError("retained status identity differs from this task or worker")
        required_retained_hits = integer(prior_status.get("unique_hits_in_this_output"), "retained status unique hit count")
    local_checkpoint = output / "checkpoint.json"
    if local_checkpoint.exists():
        local_cp = load_json(local_checkpoint)
        if local_cp.get("task_id") != task["task_id"] or local_cp.get("worker_sha256") != worker_sha:
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
    seen = recover_hits(output / "hits.jsonl", parsed["bounds"], task["task_id"], task["search"].get("require_integer_sqrt", False))
    if len(seen) < required_retained_hits:
        raise ValueError("retained hit records were lost: recovered unique count is below durable status/checkpoint count")
    atomic_json(output / "task.json", task)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    started_monotonic = time.monotonic()
    deadline = started_monotonic + parsed["seconds"]
    initial_cursor = cursor
    counters = {"fibers_completed": 0, "cf_fibers_completed": 0, "non_coprime_skipped": 0,
                "congruence_excluded": 0, "bounds_excluded": 0, "new_hits": 0, "convergents": 0}
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
            "schema": "ce390-status-v1", "task_id": task["task_id"], "campaign_id": task["campaign_id"],
            "worker_sha256": worker_sha, "state": state, "reason": reason,
            "complete": cursor == parsed["stop"] and state == "complete",
            "started_utc": started, "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - started_monotonic, 6),
            "time_limit_seconds": parsed["seconds"], "slice": task["slice"],
            "invocation_coverage": {"start": str(initial_cursor), "stop": str(cursor)},
            "output_coverage": {"start": str(output_start), "stop": str(cursor)},
            "next_index": str(cursor), "remaining_indices": str(parsed["stop"] - cursor),
            "counters_this_invocation": {key: str(value) for key, value in counters.items()},
            "unique_hits_in_this_output": str(len(seen)),
            "coverage_note": "Only the selected rational-d fibers are covered; this is not an exhaustive search of the n,x rectangle.",
        }

    def checkpoint(state: str, reason: str) -> None:
        atomic_json(output / "checkpoint.json", {"schema": "ce390-checkpoint-v1", "task_id": task["task_id"],
                    "worker_sha256": worker_sha, "next_index": str(cursor), "output_coverage_start": str(output_start),
                    "unique_hits_in_this_output": str(len(seen)), "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat()})
        atomic_json(output / "status.json", snapshot(state, reason))
        if cursor < parsed["stop"]:
            continuation = dict(task)
            continuation["resume_index"] = str(cursor)
            continuation["expected_worker_sha256"] = worker_sha
            atomic_json(output / "continuation.task.json", continuation)
        else:
            (output / "continuation.task.json").unlink(missing_ok=True)

    argv = [str(worker_path), "--n-min", task["search"]["n_min"], "--n-max", task["search"]["n_max"],
            "--x-min", task["search"]["x_min"], "--x-max", task["search"]["x_max"],
            "--precision-bits", str(parsed["precision"]), "--max-precision-bits", str(parsed["max_precision"])]
    if task["search"].get("require_integer_sqrt", False):
        argv.append("--integer-sqrt")
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
            while cursor < parsed["stop"]:
                if stop_signal:
                    raise Halt("signal")
                if time.monotonic() >= deadline:
                    raise Halt("time_limit")
                a, q = candidate(parsed, cursor)
                if math.gcd(a, q) != 1:
                    counters["non_coprime_skipped"] += 1
                    cursor += 1
                elif q % 3 == 0 or (a + q) % 3 != 0:
                    counters["congruence_excluded"] += 1
                    cursor += 1
                else:
                    assert worker is not None
                    result = worker.query(a, q)
                    if not isinstance(result, dict) or result.get("a") != str(a) or result.get("q") != str(q):
                        raise RuntimeError("worker result did not match the submitted fiber")
                    if result.get("status") != "complete":
                        atomic_json(output / "worker_error.json", {"candidate_index": str(cursor), "worker_result": result})
                        raise RuntimeError("worker could not certify completion of this fiber; see worker_error.json")
                    if result.get("congruences_enforced") is not True:
                        raise RuntimeError("worker reply did not enforce the requested congruences")
                    expected_integer_sqrt = task["search"].get("require_integer_sqrt", False)
                    if result.get("integer_sqrt_required") is not expected_integer_sqrt:
                        raise RuntimeError("worker reply used the wrong integer-square-root search policy")
                    for flag in ("excluded_by_congruence", "excluded_by_bounds"):
                        if type(result.get(flag)) is not bool:
                            raise RuntimeError(f"worker reply has a missing or nonboolean {flag} flag")
                    rows = result.get("hits")
                    if not isinstance(rows, list):
                        raise RuntimeError("worker result has no hit list")
                    # Check every hit before accepting any part of this completed fiber.
                    checked_hits = [validate_hit(row, a, q, parsed["bounds"]) for row in rows]
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
                            log(f"Certified hit {key}: n={hit['n']} x={hit['x']}")
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
        lock.close()
    # A soft deadline is a successful artifact-producing invocation, not completion.
    # Operators must inspect status.json and submit continuation.task.json if present.
    return 2 if error else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, default=Path("/local/input/task.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("/local/output"))
    parser.add_argument("--worker", type=Path, default=Path(__file__).resolve().parent / "bin" / "cf_worker")
    parser.add_argument("--checkpoint", type=Path, help="checkpoint retrieved from an earlier host")
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as exc:
        error = f"CE390 supervisor error: {type(exc).__name__}: {exc}"
        print(error, file=sys.stderr, flush=True)
        try:
            # A unique name preserves existing task artifacts even when the failure
            # is an identity/lock conflict. Never overwrite another task's status.
            args.output_dir.mkdir(parents=True, exist_ok=True)
            failure = args.output_dir / f"startup-error-{time.time_ns()}-{os.getpid()}.json"
            atomic_json(failure, {"schema": "ce390-startup-error-v1", "state": "error", "complete": False,
                        "reason": "startup_error", "error": error, "input_task": str(args.task),
                        "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat()})
        except OSError as output_exc:
            print(f"Could not retain startup error artifact: {output_exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
