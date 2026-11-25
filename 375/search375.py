#!/usr/bin/env python3
"""Continue exact EJ jobs until a qualifying cube triple is found or execution is paused.

This is a local coordinator, not a Charity Engine submission client. Every job
is finite. The default diagonal schedule revisits unfinished shells while
introducing successively larger shells, with no final height. A completed job
is credited only after independent collection; planning is never coverage.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
from fractions import Fraction
import importlib.util
import json
from math import gcd, isfinite
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "Scripts for large-scale computations" / "elkies-jahnel" / "ej375.py"
spec = importlib.util.spec_from_file_location("ce375_ej_backend", BACKEND)
ej = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ej)
SCHEMA = "ce375-continuing-search-v1"


def small_375_check():
    """Discharge the finite exception below the native H>=25 construction."""
    cubes = {i**3: i for i in range(-24, 25)}
    triples = set()
    for a in range(-24, 25):
        for b in range(-24, 25):
            c = cubes.get(375-a**3-b**3)
            if c is not None:
                triples.add(tuple(sorted((a, b, c))))
    primitive = [t for t in triples if gcd(gcd(t[0], t[1]), t[2]) == 1]
    if primitive:
        raise ValueError("small-case expectation changed: handle the primitive result explicitly")
    return {"k": 375, "region": "max(abs(cube coordinates)) <25",
            "method": "exhaustive exact pair enumeration",
            "triples": [list(t) for t in sorted(triples)], "primitive_triples": 0}


def runner_active(result):
    """An orphaned runner may outlive a killed coordinator; never overlap it."""
    lock_path = result / "runner.lock"
    if not lock_path.exists():
        return False
    with lock_path.open("r+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle, fcntl.LOCK_UN)
    return False


def initial_progress():
    return {"round": 0, "next_level": 0, "sweep_level": 0,
            "levels": {}, "completed_tasks": 0, "chain_head": None,
            "tiles": 0, "lattice_points": "0"}


def choose_level(progress, config):
    """Diagonal visits: 0; 1,0; 2,1,0; ... ; completed shells are skipped."""
    while True:
        if config["schedule"] == "interleave":
            if progress["next_level"] < 0:
                progress["round"] += 1
                progress["next_level"] = progress["round"]
            level = progress["next_level"]
        else:
            level = progress["sweep_level"]
        key = str(level)
        if key not in progress["levels"]:
            h = int(config["height"]) << level
            progress["levels"][key] = {"height": str(h),
                "lower": str(ej.lower_index(h, config["k"])),
                "upper": str(ej.upper_index(h, config["k"])),
                "next_index": str(ej.upper_index(h, config["k"]))}
        shell = progress["levels"][key]
        if int(shell["next_index"]) > int(shell["lower"]):
            return level
        advance_schedule(progress, config)


def advance_schedule(progress, config):
    if config["schedule"] == "interleave":
        progress["next_level"] -= 1
    else:
        level = progress["levels"][str(progress["sweep_level"])]
        if level["next_index"] == level["lower"]:
            progress["sweep_level"] += 1


def band(progress, config, level):
    shell = progress["levels"][str(level)]
    right = int(shell["next_index"])
    return int(shell["height"]), max(int(shell["lower"]), right-config["grid_span"]), right


def selected_solution(hit, config):
    """Count distinct unordered primitive triples, never the two signs of y."""
    xyz = tuple(ej.integer(hit[v]) for v in ("x", "y", "z"))
    if ej.integer(hit["k"]) != config["k"] or sum(v**3 for v in xyz) != config["k"]:
        raise ValueError("solution fails its exact cube identity")
    if gcd(gcd(*xyz[:2]), xyz[2]) != 1:
        raise ValueError("solution is not a primitive cube triple")
    points = [p for p in ej.original_points(xyz, config["k"])
              if (config["chart"] == "any" or p["chart"] == config["chart"])
              and (not config["primitive_point"] or p["primitive_point"])]
    if not points:
        return None
    return {"k": config["k"], "cubes": [str(v) for v in xyz],
            "key": [str(v) for v in sorted(xyz)], "original_points": points,
            "primitive_cubes": True}


def add_solutions(state, hits):
    unique = {tuple(r["key"]): r for r in state["solutions"]}
    discoveries = {tuple(r["key"]): r for r in state["cube_solutions"]}
    new = []
    for hit in hits:
        discovery = selected_solution(hit, {**state["config"], "chart": "any", "primitive_point": False})
        if tuple(discovery["key"]) not in discoveries:
            discoveries[tuple(discovery["key"])] = discovery
            new.append(discovery)
        row = selected_solution(hit, state["config"])
        if row:
            unique[tuple(row["key"])] = row
    state["solutions"] = [unique[k] for k in sorted(unique)]
    state["cube_solutions"] = [discoveries[k] for k in sorted(discoveries)]
    return new


def save(out, state):
    ej.atomic_json(out / "state.json", state)
    ej.atomic_json(out / "solutions.json", {"k": state["config"]["k"],
        "acceptance": {k: state["config"][k] for k in ("chart", "primitive_point")},
        "distinct_triples": len(state["solutions"]), "solutions": state["solutions"]})
    ej.atomic_json(out / "cube_solutions.json", {"k": state["config"]["k"],
        "distinct_primitive_triples": len(state["cube_solutions"]), "solutions": state["cube_solutions"]})


def task_matches(task, state, progress, level):
    cfg = state["config"]
    h, lo, hi = band(progress, cfg, level)
    ej.validate_task(task)
    expected = {"k": cfg["k"], "campaign_id": cfg["campaign_id"],
                "height": str(h), "index_start": str(lo), "index_stop": str(hi),
                "primitive": True, "tile_scale": cfg["tile_scale"],
                "max_tiles": cfg["task_max_tiles"],
                "deadline_seconds": cfg["task_deadline_seconds"],
                "checkpoint_every": cfg["checkpoint_every"],
                "worker_sha256": state["worker_sha256"]}
    if any(task.get(k) != v for k, v in expected.items()):
        raise ValueError("job parameters differ from the continuing search")


def credit(progress, receipt, state):
    cfg = state["config"]
    level = choose_level(progress, cfg)
    if receipt["level"] != level or receipt["job"] != progress["completed_tasks"] \
            or receipt["previous_receipt"] != progress["chain_head"]:
        raise ValueError("completed-job journal is out of order")
    task = receipt["task"]
    task_matches(task, state, progress, level)
    cp = receipt["checkpoint"]
    if receipt["worker_sha256"] != state["worker_sha256"] \
            or cp.get("worker_sha256") != state["worker_sha256"] \
            or cp.get("task_sha256") != ej.digest(task) \
            or cp.get("complete") is not True \
            or ej.integer(cp["next_index"]) != ej.integer(task["index_start"]):
        raise ValueError("completed-job receipt has invalid identity or coverage")
    for hit in receipt["hits"]:
        ej.verify_hit(hit, task)
        if hit.get("worker_sha256") != state["worker_sha256"]:
            raise ValueError("receipt contains a hit from another binary")
    if receipt["hit_count"] != len({tuple(h[k] for k in ("x", "y", "z")) for h in receipt["hits"]}):
        raise ValueError("receipt hit count disagrees")
    progress["levels"][str(level)]["next_index"] = task["index_start"]
    advance_schedule(progress, cfg)
    progress["completed_tasks"] += 1
    progress["tiles"] += ej.integer(cp["tiles"])
    progress["lattice_points"] = str(int(progress["lattice_points"])+ej.integer(cp["lattice_points"]))
    progress["chain_head"] = ej.digest(receipt)


def validate_history(out, state):
    """Rebuild scheduling progress from validated, self-contained job receipts."""
    expected_small = small_375_check() if state["config"]["k"] == 375 else None
    if state.get("small_case_check") != expected_small:
        raise ValueError("small-case record disagrees with exact enumeration")
    rebuilt = initial_progress()
    derived = []
    for job in range(state["progress"]["completed_tasks"]):
        receipt = ej.load(out / "jobs" / f"{job:012d}" / "receipt.json")
        credit(rebuilt, receipt, state)
        derived.extend(receipt["hits"])
    if state["pending"] is not None:
        level = choose_level(rebuilt, state["config"])
        if state["pending"] != {"job": rebuilt["completed_tasks"], "level": level}:
            raise ValueError("pending job disagrees with verified history")
    if rebuilt != state["progress"]:
        raise ValueError("search cursor disagrees with verified completed-job receipts")
    saved = state["solutions"]
    state["solutions"] = []
    for row in state["cube_solutions"]:
        hit = dict(zip(("x", "y", "z"), row["cubes"]), k=row["k"])
        clean = selected_solution(hit, {**state["config"], "chart": "any", "primitive_point": False})
        if clean is None or clean != row:
            raise ValueError("saved cube solution fails exact validation")
    for row in saved:
        hit = dict(zip(("x", "y", "z"), row["cubes"]), k=row["k"])
        clean = selected_solution(hit, state["config"])
        if clean is None or clean != row:
            raise ValueError("saved solution fails the acceptance criteria")
        state["solutions"].append(clean)
    add_solutions(state, derived)


def ensure_job(out, state, log):
    cfg, pending = state["config"], state["pending"]
    directory = out / "jobs" / f"{pending['job']:012d}"
    page_dir = directory / "page"
    if not (page_dir / "page.json").exists():
        h, _, hi = band(state["progress"], cfg, pending["level"])
        args = argparse.Namespace(cursor=None, height=h, right_index=hi, k=cfg["k"],
            campaign_id=cfg["campaign_id"], include_nonprimitive=False,
            tile_scale=cfg["tile_scale"], grid_span=cfg["grid_span"], page_size=1,
            max_tiles=cfg["task_max_tiles"], deadline_seconds=cfg["task_deadline_seconds"],
            checkpoint_every=cfg["checkpoint_every"], worker_sha256=state["worker_sha256"],
            output_dir=page_dir)
        with contextlib.redirect_stdout(log):
            ej.plan(args)
    page = ej.load(page_dir / "page.json")
    if len(page["tasks"]) != 1:
        raise ValueError("coordinator job must contain exactly one task")
    entry = page["tasks"][0]
    rel = Path(entry["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("invalid task path")
    task_path = page_dir / rel
    task = ej.load(task_path)
    if ej.digest(task) != entry["sha256"] or task["task_id"] != entry["task_id"]:
        raise ValueError("job page/task mismatch")
    task_matches(task, state, state["progress"], pending["level"])
    return directory, task_path, task


def collect_job(directory, task, worker_sha, log):
    result = directory / "result"
    status = ej.load(result / "status.json")
    if status.get("state") not in ("complete", "partial"):
        raise ValueError("worker attempt did not produce a successful complete/partial result")
    raw = [json.loads(s) for s in (result / "hits.jsonl").read_text().splitlines() if s.strip()]
    unique = {ej.verify_hit(h, task) for h in raw}
    if ej.integer(status["hits"]) != len(unique):
        raise ValueError("returned hit file is incomplete")
    args = argparse.Namespace(page=directory / "page" / "page.json", results=result,
        output_dir=directory / "collected", expected_worker_sha256=worker_sha,
        require_complete=False)
    with contextlib.redirect_stdout(log):
        rc = ej.collect(args)
    if rc:
        raise ValueError("result collection rejected this job; see its summary")
    summary = ej.load(args.output_dir / "summary.json")
    if summary["complete"] != (status["state"] == "complete"):
        raise ValueError("execution and validated coverage disagree")
    hits = [json.loads(s) for s in (args.output_dir / "hits.jsonl").read_text().splitlines() if s.strip()]
    return status, summary, hits


def start_state(args, worker):
    k, h = args.k, args.height
    ej.lower_index(h, k)
    if k % 6 != 3:
        raise ValueError("the original integer-variable chart needs k=3 modulo6 (default375)")
    if args.grid_span < 1 or args.task_max_tiles < 0 or args.task_deadline_seconds < 0 \
            or args.checkpoint_every < 1 or args.solutions < 0 or Fraction(args.tile_scale) <= 0:
        raise ValueError("invalid positive job size, tile scale, or execution budget")
    cfg = {"k": k, "height": str(h), "schedule": args.schedule,
           "grid_span": args.grid_span, "tile_scale": str(Fraction(args.tile_scale)),
           "chart": args.chart, "primitive_point": args.primitive_point,
           "task_max_tiles": args.task_max_tiles,
           "task_deadline_seconds": args.task_deadline_seconds,
           "checkpoint_every": args.checkpoint_every,
           "campaign_id": "search-"+uuid.uuid4().hex[:20]}
    return {"schema": SCHEMA, "config": cfg, "worker": str(worker),
            "worker_sha256": ej.file_hash(worker), "progress": initial_progress(),
            "pending": None, "solutions": [], "cube_solutions": [], "solution_target": args.solutions,
            "state": "running", "attempts": 0, "last_error": None,
            "small_case_check": small_375_check() if k == 375 else None,
            "final_height_bound": None}


def run(args):
    out = args.output_dir.resolve()
    if args.max_tasks < 0 or args.max_attempts < 0 or not isfinite(args.max_seconds) or args.max_seconds < 0:
        raise ValueError("execution budgets must be nonnegative; zero means no execution limit")
    if args.command == "resume":
        state = ej.load(out / "state.json")
        if state.get("schema") != SCHEMA:
            raise ValueError("not a continuing-search directory")
        worker = (args.worker or Path(state["worker"])).resolve()
        if ej.file_hash(worker) != state["worker_sha256"]:
            raise ValueError("changed worker binary; resume requires the original pinned build")
    else:
        worker = (args.worker or ej.DEFAULT_WORKER).resolve()
        if out.exists() and any(out.iterdir()):
            raise ValueError("start needs a new or empty output directory; use resume")
        state = start_state(args, worker)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "controller.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("another controller already owns this search") from None
        if args.command == "resume":
            # Re-read after acquiring the lock, before changing any search files.
            state = ej.load(out / "state.json")
            if ej.file_hash(worker) != state["worker_sha256"]:
                raise ValueError("worker pin changed while acquiring the search lock")
            validate_history(out, state)
            if args.solutions is not None:
                if args.solutions < 0:
                    raise ValueError("solution target must be nonnegative")
                state["solution_target"] = args.solutions
        return drive(args, out, worker, state)


def drive(args, out, worker, state):
    began, initial_tasks = time.monotonic(), state["progress"]["completed_tasks"]
    attempts = 0
    stop = {"reason": None, "proc": None, "signals": 0}

    def interrupt(signum, _frame):
        stop["reason"] = f"signal {signum}"
        stop["signals"] += 1
        proc = stop["proc"]
        if proc is not None and proc.poll() is None:
            if stop["signals"] > 1:
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.terminate()

    def budget_reason():
        if stop["reason"]:
            return stop["reason"]
        if args.max_seconds and time.monotonic()-began >= args.max_seconds:
            return "execution time budget"
        if args.max_tasks and state["progress"]["completed_tasks"]-initial_tasks >= args.max_tasks:
            return "completed-task budget"
        if args.max_attempts and attempts >= args.max_attempts:
            return "worker-attempt budget"
        return None

    previous = {s: signal.signal(s, interrupt) for s in (signal.SIGINT, signal.SIGTERM)}
    state["last_error"] = None
    try:
        with (out / "controller.log").open("a", buffering=1) as log:
            while True:
                target = state["solution_target"]
                if target and len(state["solutions"]) >= target:
                    state["state"], state["stop_reason"] = "found", "qualifying solution target reached"
                    save(out, state)
                    break
                reason = budget_reason()
                if reason:
                    state["state"], state["stop_reason"] = "paused", reason
                    save(out, state)
                    break
                state["state"] = "running"
                if state["pending"] is None:
                    level = choose_level(state["progress"], state["config"])
                    state["pending"] = {"job": state["progress"]["completed_tasks"], "level": level}
                    save(out, state)  # journal assignment before writing its page
                directory, task_path, task = ensure_job(out, state, log)
                print(json.dumps({"job": state["pending"]["job"], "height": task["height"],
                    "index_start": task["index_start"], "index_stop": task["index_stop"],
                    "action": "execute or resume"}), flush=True)
                status_path = directory / "result" / "status.json"
                if runner_active(directory / "result"):
                    print(json.dumps({"job": state["pending"]["job"],
                                      "action": "waiting for an already-running task"}), flush=True)
                while runner_active(directory / "result") and not budget_reason():
                    time.sleep(0.2)
                if budget_reason():
                    continue
                existing = ej.load(status_path) if status_path.exists() else {}
                if existing.get("state") != "complete":
                    proc = subprocess.Popen([sys.executable, str(BACKEND), "run", "--task", str(task_path),
                        "--output-dir", str(directory / "result"), "--worker", str(worker)],
                        stdout=log, stderr=log, start_new_session=True)
                    stop["proc"] = proc
                    termination_sent = False
                    while proc.poll() is None:
                        if (stop["reason"] or args.max_seconds and time.monotonic()-began >= args.max_seconds) \
                                and not termination_sent:
                            stop["reason"] = stop["reason"] or "execution time budget"
                            proc.terminate()
                            termination_sent = True
                        try:
                            proc.wait(timeout=0.2)
                        except subprocess.TimeoutExpired:
                            pass
                    stop["proc"] = None
                    attempts += 1
                    state["attempts"] += 1
                    if proc.returncode:
                        raise ValueError(f"worker runner exited {proc.returncode}; task remains uncredited")
                status, summary, hits = collect_job(directory, task, state["worker_sha256"], log)
                for discovery in add_solutions(state, hits):
                    print(json.dumps({"event": "primitive_cube_solution", "k": discovery["k"],
                        "cubes": discovery["cubes"], "original_points": discovery["original_points"]}), flush=True)
                if summary["complete"]:
                    receipt = {"job": state["pending"]["job"], "level": state["pending"]["level"],
                        "previous_receipt": state["progress"]["chain_head"], "task": task,
                        "worker_sha256": state["worker_sha256"], "checkpoint": status["checkpoint"],
                        "hit_count": len(hits), "hits": hits}
                    receipt_path = directory / "receipt.json"
                    if receipt_path.exists() and ej.load(receipt_path) != receipt:
                        raise ValueError("prepared completion receipt differs from the validated result")
                    ej.atomic_json(receipt_path, receipt)
                    credit(state["progress"], receipt, state)
                    state["pending"] = None
                save(out, state)
                print(json.dumps({"state": status["state"], "completed_tasks": state["progress"]["completed_tasks"],
                    "primitive_triples": len(state["cube_solutions"]), "qualifying_triples": len(state["solutions"]),
                    "tiles_this_task": status["checkpoint"]["tiles"]}), flush=True)
    except BaseException as exc:
        state["state"], state["last_error"] = "error", str(exc)
        save(out, state)
        raise
    finally:
        proc = stop["proc"]
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print(json.dumps({"state": state["state"], "reason": state["stop_reason"],
        "completed_tasks": state["progress"]["completed_tasks"],
        "primitive_triples": len(state["cube_solutions"]), "qualifying_triples": len(state["solutions"]), "final_height_bound": None,
        "solutions_file": str(out / "solutions.json")}), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="start an open-ended local search")
    resume = sub.add_parser("resume", help="validate saved receipts and continue")
    for p in (start, resume):
        p.add_argument("--output-dir", type=Path, required=True)
        p.add_argument("--worker", type=Path)
        p.add_argument("--solutions", type=int, default=1 if p is start else None,
                       help="stop after this many distinct qualifying triples;0 keeps going")
        p.add_argument("--max-tasks", type=int, default=0, help="pause after N completed tasks this invocation;0 unlimited")
        p.add_argument("--max-attempts", type=int, default=0, help="pause after N worker attempts;0 unlimited")
        p.add_argument("--max-seconds", type=float, default=0, help="cooperative execution budget;0 unlimited")
    start.add_argument("--height", type=int, default=25, help="initial cube-height shell; no final height")
    start.add_argument("--k", type=int, default=375, help="375; other compatible targets provide positive controls")
    start.add_argument("--schedule", choices=("interleave", "sweep"), default="interleave")
    start.add_argument("--grid-span", type=int, default=1000)
    start.add_argument("--tile-scale", default="11/2")
    start.add_argument("--task-max-tiles", type=int, default=1000, help="checkpoint/acceptance opportunities per attempt;0 full task")
    start.add_argument("--task-deadline-seconds", type=int, default=0)
    start.add_argument("--checkpoint-every", type=int, default=100)
    start.add_argument("--chart", choices=("half", "integer", "any"), default="half")
    start.add_argument("--primitive-point", action="store_true", help="optional extra point-gcd condition")
    args = parser.parse_args()
    try:
        return run(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"search375: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
