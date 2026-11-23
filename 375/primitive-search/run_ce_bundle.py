#!/usr/bin/env python3
"""Run the task group selected by CE_JOB_COPY from a Charity Engine bundle.

Each group contains at most two independent, restartable run_gap_task.py tasks.
The runner forwards termination to both process groups and gives them time to
write checkpoints. A deliberately partial task is a successful job whose
continuation.task.json can be planned again; its coverage is never called complete.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime as dt
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Any

from gap_common import atomic_json, load_json, sha256_file, validate_task

ROOT = Path(__file__).resolve().parent
BUNDLE_SCHEMA = "ce375-bundle-v1"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
TIME_HEADROOM_SECONDS = 120


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def decimal_number(value: Any, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{name} must be a JSON number")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class BundleInfo:
    campaign_id: str
    groups: list[list[dict]]
    hours: Decimal
    cores: int
    reserved_core_hours: Decimal


def validate_bundle(bundle: dict) -> BundleInfo:
    """Validate the actual allocation, rather than trusting the declared total."""
    if not isinstance(bundle, dict) or bundle.get("schema") != BUNDLE_SCHEMA:
        raise ValueError(f"bundle schema must be {BUNDLE_SCHEMA}")
    campaign = bundle.get("campaign_id")
    if not isinstance(campaign, str) or not SAFE_ID.fullmatch(campaign):
        raise ValueError("campaign_id must be a safe, nonempty identifier of at most 160 characters")
    task_campaigns = bundle.get("task_campaign_ids", [campaign])
    if not isinstance(task_campaigns, list) or not task_campaigns \
            or any(not isinstance(item, str) or not SAFE_ID.fullmatch(item) for item in task_campaigns) \
            or len(set(task_campaigns)) != len(task_campaigns):
        raise ValueError("task_campaign_ids must be an explicit list of unique safe campaign identifiers")
    allowed_campaigns = set(task_campaigns)
    cores = bundle.get("cores_per_instance")
    if type(cores) is not int or cores != 2:
        raise ValueError("this runtime requires cores_per_instance = 2")
    hours = decimal_number(bundle.get("max_instance_hours"), "max_instance_hours")
    if hours <= 0 or hours * 3600 <= TIME_HEADROOM_SECONDS:
        raise ValueError("max_instance_hours must allow at least 120 seconds of runtime headroom")
    groups = bundle.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("groups must be a nonempty list")
    seen: set[str] = set()
    for i, group in enumerate(groups):
        if not isinstance(group, list) or not 1 <= len(group) <= cores:
            raise ValueError(f"group {i} must contain one or two tasks")
        for task in group:
            if not isinstance(task, dict):
                raise ValueError(f"group {i} contains a non-object task")
            validated = validate_task(task)
            task_id = task["task_id"]
            if not SAFE_ID.fullmatch(task_id) or task_id in {"bundle.status.json", "bundle.manifest.json"}:
                raise ValueError(f"unsafe task_id in group {i}")
            if task_id in seen:
                raise ValueError(f"duplicate task_id: {task_id}")
            seen.add(task_id)
            if task["campaign_id"] not in allowed_campaigns:
                raise ValueError(f"task {task_id} belongs to an unlisted campaign")
            if validated["k"] != 375 or not validated["primitive_only"]:
                raise ValueError(f"task {task_id} must search primitive k=375 solutions")
            deadline = task.get("deadline_seconds")
            if type(deadline) is not int or deadline <= 0:
                raise ValueError(f"task {task_id} needs an explicit positive integer deadline_seconds")
            if Decimal(deadline + TIME_HEADROOM_SECONDS) > hours * 3600:
                raise ValueError(f"task {task_id} deadline leaves less than 120 seconds before the CE limit")
    total = Decimal(len(groups) * cores) * hours
    declared = decimal_number(bundle.get("total_reserved_core_hours"), "total_reserved_core_hours")
    if abs(total - declared) > Decimal("0.000000001"):
        raise ValueError(f"declared core-hour total disagrees with {len(groups)} copies x {hours} hours x {cores} cores")
    for field in ("worker_source_sha256", "worker_sha256"):
        if field in bundle and (not isinstance(bundle[field], str) or not SHA256.fullmatch(bundle[field])):
            raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return BundleInfo(campaign, groups, hours, cores, total)


def verify_worker_binding(bundle: dict, worker: Path) -> None:
    """Support source-bound Docker builds and optional exact local binary binding."""
    expected_source = bundle.get("worker_source_sha256")
    if expected_source:
        source = ROOT / "src" / "gap_worker.cpp"
        digest_file = ROOT / "source.sha256"
        if source.is_file():
            actual = sha256_file(source)
        elif digest_file.is_file():
            parts = digest_file.read_text(encoding="ascii").strip().split()
            actual = parts[0] if parts else ""
        else:
            raise ValueError("worker_source_sha256 is bound, but src/gap_worker.cpp and source.sha256 are absent")
        if actual != expected_source:
            raise ValueError("worker source SHA-256 differs from the bundle")
    if bundle.get("worker_sha256") and sha256_file(worker) != bundle["worker_sha256"]:
        raise ValueError("worker binary SHA-256 differs from the bundle")


def run(args: argparse.Namespace) -> int:
    bundle = load_json(args.manifest)
    info = validate_bundle(bundle)
    copy_text = args.copy_index if args.copy_index is not None else os.environ.get("CE_JOB_COPY")
    if copy_text is None:
        raise ValueError("CE_JOB_COPY is missing; use --copy-index explicitly for a local run")
    try:
        copy_index = int(copy_text)
    except (TypeError, ValueError) as exc:
        raise ValueError("CE_JOB_COPY must be an integer") from exc
    if not 0 <= copy_index < len(info.groups):
        raise ValueError("CE_JOB_COPY is outside this batch's group list")
    if not 1 <= args.grace_seconds <= 90:
        raise ValueError("grace-seconds must be between 1 and 90")
    runner = Path(args.runner).resolve()
    worker = Path(args.worker).resolve()
    if not runner.is_file():
        raise ValueError(f"task runner is missing: {runner}")
    verify_worker_binding(bundle, worker)
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    group = info.groups[copy_index]
    status_path = out / "bundle.status.json"
    atomic_json(out / "bundle.manifest.json", bundle)
    processes: list[tuple[dict, subprocess.Popen, Any, Any]] = []
    stop = {"signal": None, "time": None, "reason": None}

    def stop_processes(signum: int, reason: str) -> None:
        if stop["time"] is None:
            stop.update(signal=signum, time=time.monotonic(), reason=reason)
        for _task, proc, _stdout, _stderr in processes:
            # Each runner and its native child have their own process group.
            # Send to the group even if the runner has just exited, so a native
            # child cannot be left behind by an interrupted Python startup.
            try:
                os.killpg(proc.pid, signum)
            except ProcessLookupError:
                pass

    def on_signal(signum, _frame):
        stop_processes(signum, f"signal {signum}")

    previous = {sig: signal.signal(sig, on_signal) for sig in (signal.SIGINT, signal.SIGTERM)}
    started = now()
    # This wall-clock guard includes Python startup and worker setup. It is a
    # fallback for a child which fails to respect its own explicit deadline.
    watchdog = time.monotonic() + max(task["deadline_seconds"] for task in group) + 30
    failure: str | None = None
    killed = False
    environment = dict(os.environ)
    environment.pop("CE_AUTH_TOKEN", None)  # Credentials never belong in a compute worker.
    atomic_json(status_path, {"schema": "ce375-bundle-status-v1", "state": "running",
                             "campaign_id": info.campaign_id, "copy_index": copy_index,
                             "group_offset": bundle.get("group_offset", 0), "started": started,
                             "task_ids": [task["task_id"] for task in group]})
    try:
        for task in group:
            if stop["time"] is not None:
                break
            task_out = out / task["task_id"]
            task_out.mkdir(exist_ok=True)
            task_file = task_out / "task.input.json"
            atomic_json(task_file, task)
            stdout = (task_out / "runner.stdout.log").open("a", encoding="utf-8")
            stderr = (task_out / "runner.stderr.log").open("a", encoding="utf-8")
            try:
                proc = subprocess.Popen(
                    [sys.executable, str(runner), "--task", str(task_file), "--output-dir", str(task_out),
                     "--worker", str(worker), "--deadline-seconds", str(task["deadline_seconds"])],
                    cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, start_new_session=True)
            except BaseException:
                stdout.close()
                stderr.close()
                raise
            processes.append((task, proc, stdout, stderr))
            if stop["time"] is not None:  # A signal arrived between Popen and registration.
                stop_processes(stop["signal"], stop["reason"])
        while any(proc.poll() is None for _task, proc, _stdout, _stderr in processes):
            current = time.monotonic()
            if stop["time"] is None and current >= watchdog:
                stop_processes(signal.SIGTERM, "bundle wall-clock deadline")
            if stop["time"] is not None and current - stop["time"] >= args.grace_seconds:
                killed = True
                for _task, proc, _stdout, _stderr in processes:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                break
            time.sleep(0.1)
    except Exception as exc:  # Preserve completed task outputs if a sibling failed to start.
        failure = str(exc)
        stop_processes(signal.SIGTERM, "bundle runtime error")
        until = time.monotonic() + args.grace_seconds
        while any(proc.poll() is None for _task, proc, _stdout, _stderr in processes) and time.monotonic() < until:
            time.sleep(0.1)
    finally:
        for _task, proc, stdout, stderr in processes:
            if proc.poll() is None:
                killed = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            proc.wait()
            stdout.close()
            stderr.close()
        for sig, previous_handler in previous.items():
            signal.signal(sig, previous_handler)
    results = []
    for task, proc, _stdout, _stderr in processes:
        try:
            task_status = load_json(out / task["task_id"] / "status.json")
            if task_status.get("task_id") != task["task_id"] or task_status.get("campaign_id") != task["campaign_id"]:
                raise ValueError("task status identity disagrees with the bundle")
            state = task_status["state"]
        except (OSError, ValueError, KeyError, TypeError):
            state = "error"
        if proc.returncode != 0 or state not in {"complete", "partial"}:
            state = "error"
        results.append({"task_id": task["task_id"], "returncode": proc.returncode, "state": state})
    error = failure is not None or killed or any(result["state"] == "error" for result in results)
    complete = len(results) == len(group) and all(result["state"] == "complete" for result in results)
    state = "error" if error else "complete" if complete else "partial"
    atomic_json(status_path, {"schema": "ce375-bundle-status-v1", "state": state,
                             "campaign_id": info.campaign_id, "copy_index": copy_index,
                             "group_offset": bundle.get("group_offset", 0), "started": started,
                             "finished": now(), "stop_reason": stop["reason"], "error": failure,
                             "tasks": results,
                             "not_started": [task["task_id"] for task in group[len(results):]]})
    print(json.dumps({"state": state, "copy_index": copy_index, "tasks": results}, sort_keys=True))
    return 1 if error else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("/local/input/bundle.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("/local/output"))
    parser.add_argument("--copy-index", type=int, help="local-test override for CE_JOB_COPY")
    parser.add_argument("--runner", type=Path, default=ROOT / "run_gap_task.py")
    parser.add_argument("--worker", type=Path, default=ROOT / "bin" / "gap_worker")
    parser.add_argument("--grace-seconds", type=int, default=60)
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"run_ce_bundle: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
