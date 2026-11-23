#!/usr/bin/env python3
"""Plan, partition, run, resume and audit large finite target-375 searches.

Plans contain arithmetic partitions, not a materialized list of billions of
tasks. Merely writing a plan completes no search. Each used task has immutable
attempt output and an atomic checkpoint. Repeating `run` resumes an unfinished
task. Parallel processes use disjoint task strides and POSIX advisory locks.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import signal
import subprocess
import sys
import uuid

import search375
from elkies_jahnel import minimum_index
from equation375 import validate_point

ROOT = Path(__file__).resolve().parent
SCHEMA = "algorithm-ii-campaign-v1"


def decimal(value: object) -> int:
    if type(value) is not str or not value.isascii() or not value.isdecimal():
        raise ValueError("campaign mathematical bounds must be nonnegative decimal strings")
    return int(value)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def source_hashes() -> dict[str, str]:
    return {**search375.source_hashes(), "campaign375.py": digest(Path(__file__).read_bytes())}


def plan_hash(plan: dict) -> str:
    return digest(encoded(plan))


def family_count(family: dict) -> int:
    lo, hi, width = (decimal(family[key]) for key in ("start", "stop", "task_width"))
    if width < 1 or hi <= lo:
        raise ValueError("each family needs start < stop and positive task_width")
    return (hi - lo + width - 1) // width


def validate_plan(plan: dict, *, check_sources: bool = True) -> None:
    from booker_native import validate_gap
    if plan.get("schema") != SCHEMA or plan.get("target") != "375":
        raise ValueError("unsupported campaign schema or target")
    if plan.get("optional_filters") != "none":
        raise ValueError("this campaign version searches every strict chart without optional d/n filters")
    families = plan.get("families")
    if not isinstance(families, list) or not families:
        raise ValueError("campaign needs at least one finite family")
    total = 0
    for family in families:
        total += family_count(family)
        lo, hi = decimal(family["start"]), decimal(family["stop"])
        if family["engine"] == "booker":
            width, ratio = decimal(family["task_width"]), decimal(family["ratio_max"])
            validate_gap(lo, min(hi, lo + width), ratio)
            # Counter limits apply to individual native tasks, not the sum of
            # every task in the campaign. The uppermost full-width task is a
            # conservative bound for all of them.
            validate_gap(max(lo, hi - width), hi, ratio)
        elif family["engine"] == "elkies":
            height = decimal(family["height"])
            if not minimum_index(height) <= lo < hi <= 4 * height:
                raise ValueError("EJ family lies outside the proved ratio domain")
            if Fraction(family["tile_scale"]) <= 0:
                raise ValueError("tile scale must be positive")
        else:
            raise ValueError("unknown campaign engine")
    if decimal(plan["task_count"]) != total:
        raise ValueError("task_count does not match the exact partitions")
    hashes = plan.get("source_sha256")
    if not isinstance(hashes, dict) or check_sources and hashes != source_hashes():
        raise ValueError("campaign source fingerprints differ; use matching code or create a new plan/state directory")


def load_plan(path: Path) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    validate_plan(plan)
    return plan


def make_plan(args: argparse.Namespace) -> dict:
    families = []
    if args.engine in ("both", "booker"):
        families.append({"engine": "booker", "start": str(args.bs_start),
                         "stop": str(args.bs_stop), "task_width": str(args.bs_width),
                         "ratio_max": str(args.ratio_max)})
    if args.engine in ("both", "elkies"):
        height = args.ej_height
        if height >= args.ej_stop:
            raise ValueError("ej-height must be below ej-stop")
        while height < args.ej_stop:
            families.append({"engine": "elkies", "height": str(height),
                             "start": str(minimum_index(height)), "stop": str(4 * height),
                             "task_width": str(args.ej_width), "tile_scale": str(args.tile_scale)})
            height *= 2
        if height != args.ej_stop:
            raise ValueError("ej-stop must equal ej-height times an integral power of two")
    plan = {"schema": SCHEMA, "target": "375", "name": args.name,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "status": "planned_only_no_completed_search_implied",
            "optional_filters": "none", "families": families,
            "task_count": str(sum(family_count(f) for f in families)),
            "source_sha256": source_hashes()}
    validate_plan(plan)
    return plan


def get_task(plan: dict, task_id: int) -> dict:
    if not 0 <= task_id < decimal(plan["task_count"]):
        raise ValueError("task id is outside the campaign")
    offset = 0
    for family in plan["families"]:
        count = family_count(family)
        if task_id < offset + count:
            start = decimal(family["start"]) + (task_id - offset) * decimal(family["task_width"])
            stop = min(decimal(family["stop"]), start + decimal(family["task_width"]))
            return {**family, "id": str(task_id), "start": str(start), "stop": str(stop)}
        offset += count
    raise AssertionError("unreachable task partition")


def task_argv(task: dict, *, bs_seconds: int = 30, ej_max_tiles: int = 1000) -> list[str]:
    if task["engine"] == "booker":
        return ["booker-gap", "--D-start", task["start"], "--D-stop", task["stop"],
                "--ratio-max", task["ratio_max"], "--deadline-seconds", str(bs_seconds),
                "--chunk", "65536", "--progress-every", "0"]
    return ["elkies-shell", "--height", task["height"],
            "--index-start", task["start"], "--index-stop", task["stop"],
            "--tile-scale", task["tile_scale"], "--max-tiles", str(ej_max_tiles),
            "--progress-every", "0"]


def expected_scope(task: dict) -> dict:
    if task["engine"] == "booker":
        return {"kind": "native_integer_gap_and_ratio_band", "D_start": task["start"],
                "D_stop_exclusive": task["stop"], "ratio_max": task["ratio_max"],
                "absolute_z_min": "floor(3847*D/1000)", "absolute_z_max": "ratio_max*D",
                "D_definition": "abs(u+v), integer; distinct from signed rational d",
                "sign_sector": "(u+v)*w<0; native pair ordered u>=v",
                "permutations": "all original-equation charts of each cube triple"}
    height = decimal(task["height"])
    return {"kind": "cube_height_shell_and_ratio_band", "height_min": str(height),
            "height_stop_exclusive": str(2 * height), "index_start": task["start"],
            "index_stop": task["stop"], "grid_denominator": str(5 * height),
            "cube_height_max": None,
            "global_right_endpoint_included": decimal(task["stop"]) == 4 * height}


def point_in_task(cubes: tuple[int, int, int], task: dict) -> bool:
    lo, hi = decimal(task["start"]), decimal(task["stop"])
    if task["engine"] == "booker":
        ratio = decimal(task["ratio_max"])
        for u, v, w in itertools.permutations(cubes):
            gap = abs(u + v)
            if (lo <= gap < hi and (u + v) * w < 0
                    and 3847 * gap // 1000 <= abs(w) <= ratio * gap):
                return True
        return False
    a, b, c = sorted(abs(value) for value in cubes)
    height = decimal(task["height"])
    return (0 < a <= b < c and height <= c < 2 * height
            and lo * c <= 5 * height * a
            and (5 * height * a < hi * c or hi == 4 * height and 5 * height * a == hi * c))


def read_attempt(path: Path, task: dict, plan: dict, returncode: int) -> tuple[dict, bool, str]:
    """Verify an attempt before advancing any boundary or accepting completion."""
    if returncode not in (0, 3):
        raise ValueError("interrupted/failed attempts cannot advance certified coverage")
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    if len(rows) < 2 or rows[0].get("type") != "start" or rows[-1].get("type") != "end":
        raise ValueError("attempt needs a start and a terminal record")
    start, end = rows[0], rows[-1]
    scope = expected_scope(task)
    expected_sources = {key: value for key, value in plan["source_sha256"].items()
                        if key != "campaign375.py"}
    command = "booker-gap" if task["engine"] == "booker" else "elkies-shell"
    if (start.get("schema") != "algorithm-ii-375-v1" or start.get("command") != command
            or start.get("version") != search375.VERSION
            or start.get("target") != 375 or start.get("scope") != scope or end.get("scope") != scope
            or start.get("source_sha256") != expected_sources
            or start.get("required") != {"integer_n": True, "odd_X_Y": True,
                                         "gcd_X_Y": 1, "positive_Y": True}
            or start.get("n_filter") != {"minimum": None, "maximum": None}
            or start.get("rational_d_filter") != search375.RationalDFilter().as_dict()):
        raise ValueError("attempt scope, sources, or strict acceptance rules differ from the plan")
    seen = set()
    for row in rows[1:-1]:
        if row.get("type") != "solution":
            raise ValueError("unexpected record inside attempt")
        for name in ("n", "X", "Y"):
            value = row[name]
            if type(value) is not str or str(int(value)) != value:
                raise ValueError("point coordinates must be canonical decimal strings")
        if type(row["d"]) is not str or str(Fraction(row["d"])) != row["d"]:
            raise ValueError("point parameter must be a reduced exact rational string")
        point = validate_point(int(row["n"]), int(row["X"]), int(row["Y"]), Fraction(row["d"]))
        if (row.get("verified_original_equation") is not True
                or any(row.get(key) != value for key, value in point.as_dict().items())):
            raise ValueError("solution fields disagree with exact point reconstruction")
        if not point_in_task(point.cubes, task):
            raise ValueError("solution is outside the assigned task")
        seen.add((point.n, point.X, point.Y))
    if end.get("solutions") != len(seen):
        raise ValueError("terminal solution count differs from verified output")
    complete = returncode == 0
    if end.get("complete") is not complete or end.get("status") != ("complete" if complete else "partial"):
        raise ValueError("exit code and completion record disagree")
    terminal = end.get("backend_terminal", {})
    next_task = dict(task)
    lo, hi = decimal(task["start"]), decimal(task["stop"])
    if task["engine"] == "booker":
        next_value = decimal(terminal["d_next"])
        if not lo <= next_value <= hi or (next_value == hi) != complete:
            raise ValueError("invalid Booker continuation boundary")
        if terminal.get("state") != ("complete" if complete else "partial"):
            raise ValueError("Booker native terminal disagrees")
        next_task["start"] = str(next_value)
    else:
        next_value = decimal(terminal["next_index"])
        if not lo <= next_value <= hi or (next_value == lo) != complete:
            raise ValueError("invalid lattice continuation boundary")
        if terminal.get("complete") is not complete:
            raise ValueError("lattice native terminal disagrees")
        next_task["stop"] = str(next_value)
    return next_task, complete, digest(raw)


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded(value))
            stream.flush()
            import os
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def audit_task(plan: dict, original: dict, directory: Path) -> tuple[dict, bool, list[dict]]:
    state_path = directory / "state.json"
    if not state_path.is_file():
        return original, False, []
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("plan_sha256") != plan_hash(plan) or state.get("task") != original:
        raise ValueError("checkpoint belongs to a different plan or task")
    task, complete = original, False
    attempts = state["attempts"]
    for attempt in attempts:
        if complete:
            raise ValueError("checkpoint contains attempts after completion")
        filename = attempt["output"]
        if Path(filename).name != filename:
            raise ValueError("attempt output must be a basename within the task directory")
        task, complete, sha = read_attempt(directory / filename, task, plan, attempt["returncode"])
        if sha != attempt["sha256"]:
            raise ValueError("saved attempt output fingerprint differs")
    if state.get("complete") is not complete or state.get("remaining") != task:
        raise ValueError("checkpoint boundaries differ from its verified attempt history")
    return task, complete, attempts


def state_directory(plan: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    identity = directory / "campaign.json"
    expected = {"plan_sha256": plan_hash(plan), "target": "375"}
    with (directory / "campaign.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if identity.exists():
            if json.loads(identity.read_text(encoding="utf-8")) != expected:
                raise ValueError("state directory belongs to a different plan")
        else:
            atomic_json(identity, expected)


def assigned_ids(plan: dict, engine: str, workers: int, worker_index: int):
    """Jump over excluded families without expanding their task partitions."""
    offset = 0
    for family in plan["families"]:
        stop = offset + family_count(family)
        if engine == "both" or family["engine"] == engine:
            first = offset + (worker_index - offset) % workers
            yield from range(first, stop, workers)
        offset = stop


@contextmanager
def task_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "task.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def run_one(plan: dict, original: dict, directory: Path, args: argparse.Namespace) -> str:
    with task_lock(directory) as acquired:
        if not acquired:
            return "locked"
        task, complete, attempts = audit_task(plan, original, directory)
        if complete:
            return "already_complete"
        output = directory / ("attempt-" + uuid.uuid4().hex + ".jsonl")
        argv = task_argv(task, bs_seconds=args.bs_seconds, ej_max_tiles=args.ej_max_tiles)
        print(json.dumps({"type": "task_start", "task": original["id"], "remaining": task,
                          "output": str(output), "argv": argv}), flush=True)
        child = subprocess.Popen([sys.executable, str(ROOT / "search375.py"), *argv,
                                  "--output", str(output)], cwd=ROOT)
        try:
            returncode = child.wait()
        except KeyboardInterrupt:
            if child.poll() is None:
                child.send_signal(signal.SIGINT)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            print(json.dumps({"type": "task_interrupted", "task": original["id"],
                              "coverage_advanced": False, "output": str(output)}), flush=True)
            raise
        validate_plan(plan)  # A changed source tree cannot certify this attempt.
        if returncode not in (0, 3):
            raise RuntimeError(f"task {original['id']} failed with exit {returncode}; no coverage advanced; output {output}")
        remaining, complete, sha = read_attempt(output, task, plan, returncode)
        attempts = [*attempts, {"output": output.name, "sha256": sha, "returncode": returncode}]
        atomic_json(directory / "state.json",
                    {"plan_sha256": plan_hash(plan), "task": original, "remaining": remaining,
                     "complete": complete, "attempts": attempts})
        print(json.dumps({"type": "task_end", "task": original["id"], "complete": complete,
                          "remaining": remaining, "output": str(output)}), flush=True)
        return "complete" if complete else "partial"


def run_campaign(plan: dict, args: argparse.Namespace) -> int:
    directory = args.state_dir.resolve()
    state_directory(plan, directory)
    if args.worker_index >= args.workers:
        raise ValueError("worker-index must be less than workers")
    if args.task_id is not None:
        if args.engine != "both" and get_task(plan, args.task_id)["engine"] != args.engine:
            raise ValueError("explicit task-id belongs to a different engine")
        ids = [args.task_id]
    else:
        ids = assigned_ids(plan, args.engine, args.workers, args.worker_index)
    done = 0
    for task_id in ids:
        original = get_task(plan, task_id)
        result = run_one(plan, original, directory / ("task-" + str(task_id)), args)
        if result in ("already_complete", "locked"):
            if args.task_id is not None:
                print(json.dumps({"type": "task_status", "task": str(task_id), "status": result}))
                return 0 if result == "already_complete" else 3
            continue
        done += 1
        if result == "partial":
            return 3
        if done >= args.max_tasks:
            return 0
    print(json.dumps({"type": "worker_end", "message": "no uncompleted unlocked tasks in this assignment"}))
    return 0


def campaign_status(plan: dict, directory: Path) -> dict:
    # Audit existing evidence only; an enormous untouched partition is never expanded.
    complete = partial = 0
    completed_booker_D = completed_ej_indices = 0
    seen_ids = set()
    if directory.exists():
        state_directory(plan, directory)
        for path in directory.glob("task-*/state.json"):
            task_id = int(path.parent.name.removeprefix("task-"))
            if path.parent.name != "task-" + str(task_id) or task_id in seen_ids:
                raise ValueError("noncanonical or duplicate task directory would double-count coverage")
            seen_ids.add(task_id)
            original = get_task(plan, task_id)
            remaining, finished, attempts = audit_task(plan, original, path.parent)
            complete += int(finished)
            if original["engine"] == "booker":
                width = decimal(remaining["start"]) - decimal(original["start"])
                completed_booker_D += width
            else:
                width = decimal(original["stop"]) - decimal(remaining["stop"])
                completed_ej_indices += width
            partial += int(width > 0 and not finished)
    return {"type": "campaign_status", "name": plan["name"], "task_count": plan["task_count"],
            "complete_tasks": str(complete), "partial_tasks": str(partial),
            "tasks_without_certified_progress": str(decimal(plan["task_count"]) - complete - partial),
            "certified_Booker_D_values": str(completed_booker_D),
            "certified_EJ_ratio_index_width_across_shells": str(completed_ej_indices),
            "entire_campaign_complete": complete == decimal(plan["task_count"]),
            "meaning": "Only validated attempt outputs advance coverage; planned ranges are not completed ranges."}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    command = commands.add_parser("plan", help="write a compact finite plan; defaults are the large preset")
    command.add_argument("--name", default="large-375")
    command.add_argument("--engine", choices=("both", "booker", "elkies"), default="both")
    command.add_argument("--bs-start", type=search375.positive_int, default=1)
    command.add_argument("--bs-stop", type=search375.positive_int, default=10**12 + 1)
    command.add_argument("--bs-width", type=search375.positive_int, default=2**20)
    command.add_argument("--ratio-max", type=search375.positive_int, default=1024)
    command.add_argument("--ej-height", type=search375.positive_int, default=10**15)
    command.add_argument("--ej-stop", type=search375.positive_int, default=16 * 10**15)
    command.add_argument("--ej-width", type=search375.positive_int, default=100000)
    command.add_argument("--tile-scale", type=search375.exact_fraction, default=Fraction(11, 2))
    command.add_argument("--output", type=Path, required=True)
    for name in ("task", "run", "status"):
        command = commands.add_parser(name)
        command.add_argument("--plan", type=Path, required=True)
        if name == "task":
            command.add_argument("--task-id", type=search375.nonnegative_int, required=True)
        else:
            command.add_argument("--state-dir", type=Path, required=True)
        if name == "run":
            command.add_argument("--task-id", type=search375.nonnegative_int)
            command.add_argument("--engine", choices=("both", "booker", "elkies"), default="both")
            command.add_argument("--workers", type=search375.positive_int, default=1)
            command.add_argument("--worker-index", type=search375.nonnegative_int, default=0)
            command.add_argument("--max-tasks", type=search375.positive_int, default=1)
            command.add_argument("--bs-seconds", type=search375.nonnegative_int, default=30)
            command.add_argument("--ej-max-tiles", type=search375.nonnegative_int, default=1000)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "plan":
            plan = make_plan(args)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("xb") as stream:
                stream.write(encoded(plan))
            print(json.dumps({"type": "plan_created", "path": str(args.output),
                              "task_count": plan["task_count"], "completed_tasks": "0"}))
            return 0
        plan = load_plan(args.plan)
        if args.command == "task":
            task = get_task(plan, args.task_id)
            print(json.dumps({"task": task, "argv": task_argv(task)}, indent=2))
            return 0
        if args.command == "status":
            print(json.dumps(campaign_status(plan, args.state_dir), indent=2))
            return 0
        return run_campaign(plan, args)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f"campaign375: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
