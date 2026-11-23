#!/usr/bin/env python3
"""Exact Elkies--Jahnel height-shell jobs. A complementary engine, not gap coverage.

plan emits a finite page and an unbounded next-page cursor. run executes one
finite task, checkpoints only completed tiles, and verifies hits independently.
collect accepts only validated results for that page and one worker binary.
"""
from __future__ import annotations

import argparse
import fcntl
from fractions import Fraction
import hashlib
import json
from math import gcd
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading

ENGINE = "elkies-jahnel"
TASK_SCHEMA = "ce375-ej-task-v1"
PAGE_SCHEMA = "ce375-ej-page-v1"
CHECKPOINT_SCHEMA = "ce375-ej-checkpoint-v1"
DEFAULT_WORKER = Path(__file__).resolve().parent / "bin" / "elkies375_worker"


def integer(value):
    if isinstance(value, bool) or not re.fullmatch(r"-?(0|[1-9][0-9]*)", str(value)):
        raise ValueError(f"expected an exact decimal integer: {value!r}")
    return int(value)


def icbrt(n):
    if n < 0:
        raise ValueError("cube-root argument must be nonnegative")
    if not n:
        return 0
    r = 1 << ((n.bit_length() + 2) // 3)
    while True:
        s = (2*r + n // (r*r)) // 3
        if s >= r:
            return r
        r = s


def lower_index(h, k):
    if h < 25 or k <= 0 or icbrt(k)**3 == k:
        raise ValueError("need height >=25 and a positive noncube target")
    n = 3*h*h - 3*h + 1 - k
    if n <= 0 or 125*k > 3*h**3:
        raise ValueError("height is too small for the proved canonical region")
    a = icbrt(n)
    return 5*(a + (a**3 < n)) // 2


def upper_index(h, k):
    """Safe default top of a shell, retaining exact half-open boundaries.

    For j=5H*a/c, a<=b and |a^3+b^3-c^3|=K imply
    j^3 <= 125*(H^3+K)/2.  Normally j must be strictly below the
    task's right endpoint, so an integral cube-root bound needs +1 too.
    The existing global endpoint 4H is inclusive and may be kept exactly.
    """
    lower_index(h, k)  # apply the same proved-shell preconditions
    return min(4*h, icbrt(125*(h**3+k)//2)+1)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def validate_task(task):
    if task.get("schema") != TASK_SCHEMA or task.get("engine") != ENGINE:
        raise ValueError("not an Elkies--Jahnel task; other engines' coverage is incompatible")
    for key in ("campaign_id", "task_id"):
        if not isinstance(task.get(key), str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", task[key]):
            raise ValueError(f"invalid {key}")
    k, h, lo, hi = (integer(task[key]) for key in ("k", "height", "index_start", "index_stop"))
    if not lower_index(h, k) <= lo < hi <= 4*h:
        raise ValueError("task ratio band is outside the proved shell region")
    primitive = task.get("primitive")
    if not isinstance(primitive, bool):
        raise ValueError("primitive must be an explicit boolean")
    scale = Fraction(task.get("tile_scale", "11/2"))
    if scale <= 0:
        raise ValueError("tile_scale must be positive")
    for key in ("max_tiles", "deadline_seconds"):
        if integer(task.get(key, 0)) < 0:
            raise ValueError(f"{key} must be nonnegative")
    if integer(task.get("checkpoint_every", 100)) < 1:
        raise ValueError("checkpoint_every must be positive")
    expected = task.get("worker_sha256")
    if expected is not None and not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("worker_sha256 must be a lowercase SHA-256 digest")
    return k, h, lo, hi, primitive, scale


def verify_hit(record, task):
    k, h, lo, hi, primitive, _ = validate_task(task)
    if record.get("type") != "hit" or integer(record.get("k")) != k:
        raise ValueError("wrong hit type or target")
    xyz = tuple(integer(record[key]) for key in ("x", "y", "z"))
    if sum(v**3 for v in xyz) != k:
        raise ValueError("incorrect sum of cubes")
    a, b, c = sorted(abs(v) for v in xyz)
    if not (0 < a <= b < c and h <= c < 2*h):
        raise ValueError("hit outside the canonical height shell")
    if xyz not in ((a, b, -c), (-a, -b, c)):
        raise ValueError("hit is not in canonical order")
    if not (lo*c <= 5*h*a and (5*h*a < hi*c or hi == 4*h and 5*h*a == hi*c)):
        raise ValueError("hit outside its assigned ratio band")
    actual = gcd(gcd(a, b), c) == 1
    if record.get("primitive") is not actual or primitive and not actual:
        raise ValueError("incorrect primitive status")
    if "height" in record and integer(record["height"]) != c:
        raise ValueError("incorrect reported cube height")
    return xyz


def original_points(xyz, k):
    """Conversation x is n here; conversation m is the rational point coordinate."""
    total = sum(xyz)
    if (total-3) % 6:
        return []
    n = (total-3)//6
    points, seen = [], set()
    for i in range(3):
        u = xyz[i]
        v, w = sorted((xyz[(i+1)%3], xyz[(i+2)%3]))
        M, Y = -v-w, w-v
        if not M or (M, Y) in seen:
            continue
        seen.add((M, Y))
        m, y = Fraction(M, 2), Fraction(Y, 2)
        N = Fraction(total**3-k, 6)
        if y*y != (m+total)**2 + N/m:
            raise ValueError("original equation identity failed")
        odd = bool(M % 2)
        pg = gcd(M, Y) if odd else gcd(gcd(n, M//2), Y//2)
        points.append({"n": str(n), "M": str(M), "Y_abs": str(Y),
                       "m": str(m), "y_abs": str(y),
                       "chart": "half" if odd else "integer",
                       "point_gcd": str(pg), "primitive_point": pg == 1,
                       "y_signs": [1, -1] if Y else [0]})
    return points


def plan(args):
    if args.cursor:
        state = load(args.cursor)
        if state.get("schema") != "ce375-ej-plan-cursor-v1":
            raise ValueError("incorrect planning cursor")
        h, right = integer(state["height"]), integer(state["next_index"])
        k, campaign = integer(state["k"]), state["campaign_id"]
        primitive, scale = state["primitive"], state["tile_scale"]
        span, page_size = integer(state["grid_span"]), integer(state["page_size"])
        max_tiles, deadline = state["max_tiles"], state["deadline_seconds"]
        checkpoint_every = state.get("checkpoint_every", 100)
        expected = state.get("worker_sha256")
    else:
        h, k, campaign = args.height, args.k, args.campaign_id
        if h is None or not campaign:
            raise ValueError("give --height and --campaign-id, or --cursor")
        right = args.right_index if args.right_index is not None else upper_index(h, k)
        primitive, scale = not args.include_nonprimitive, str(Fraction(args.tile_scale))
        span, page_size = args.grid_span, args.page_size
        max_tiles, deadline, expected = args.max_tiles, args.deadline_seconds, args.worker_sha256
        checkpoint_every = args.checkpoint_every
    if span < 1 or page_size < 1:
        raise ValueError("grid span and page size must be positive")
    out = args.output_dir
    if (out / "page.json").exists():
        raise ValueError("output page already exists; use a new directory")
    entries = []
    for _ in range(page_size):
        low = lower_index(h, k)
        if not low <= right <= 4*h:
            raise ValueError("planning cursor lies outside its shell")
        if right == low:
            h *= 2
            right = upper_index(h, k)
            low = lower_index(h, k)
        left = max(low, right-span)
        identity = digest([campaign, k, str(h), str(left), str(right), primitive, scale])[:20]
        task = {"schema": TASK_SCHEMA, "engine": ENGINE, "campaign_id": campaign,
                "task_id": f"ej-{identity}", "k": k, "height": str(h),
                "index_start": str(left), "index_stop": str(right),
                "primitive": primitive, "tile_scale": scale,
                "max_tiles": max_tiles, "deadline_seconds": deadline,
                "checkpoint_every": checkpoint_every}
        if expected is not None:
            task["worker_sha256"] = expected
        validate_task(task)
        path = f"tasks/{task['task_id']}.json"
        atomic_json(out / path, task)
        entries.append({"task_id": task["task_id"], "path": path, "sha256": digest(task)})
        right = left
    page = {"schema": PAGE_SCHEMA, "engine": ENGINE, "campaign_id": campaign, "tasks": entries}
    atomic_json(out / "page.json", page)
    state = {"schema": "ce375-ej-plan-cursor-v1", "campaign_id": campaign,
             "height": str(h), "next_index": str(right), "k": k,
             "primitive": primitive, "tile_scale": scale, "grid_span": span,
             "page_size": page_size, "max_tiles": max_tiles, "deadline_seconds": deadline,
             "checkpoint_every": checkpoint_every}
    if expected is not None:
        state["worker_sha256"] = expected
    atomic_json(out / "next_plan.json", state)
    print(json.dumps({"tasks": len(entries), "page": str(out / "page.json"),
                      "next_plan": str(out / "next_plan.json"), "final_height_bound": None}))
    return 0


def run(args):
    task = load(args.task)
    validate_task(task)
    worker = args.worker.resolve()
    worker_hash, task_hash = file_hash(worker), digest(task)
    if task.get("worker_sha256", worker_hash) != worker_hash:
        raise ValueError("worker does not match the pinned binary hash")
    out = args.output_dir
    cp_path = out / "checkpoint.json"
    if cp_path.exists() and load(cp_path).get("worker_sha256") != worker_hash:
        raise ValueError("checkpoint belongs to a different task or worker binary")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "runner.lock").open("a") as runner_lock:
        try:
            fcntl.flock(runner_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("another EJ runner already owns this result directory") from None
        return run_locked(args, task, worker, worker_hash, task_hash)


def run_locked(args, task, worker, worker_hash, task_hash):
    k, h, lo, hi, primitive, scale = validate_task(task)
    out = args.output_dir
    cp_path, hit_path = out / "checkpoint.json", out / "hits.jsonl"
    cp = {"schema": CHECKPOINT_SCHEMA, "task_sha256": task_hash,
          "worker_sha256": worker_hash, "next_index": str(hi),
          "tiles": 0, "lattice_points": "0", "complete": False}
    if cp_path.exists():
        old = load(cp_path)
        if any(old.get(key) != cp[key] for key in ("schema", "task_sha256", "worker_sha256")):
            raise ValueError("checkpoint belongs to a different task or worker binary")
        cp = old
    cursor = integer(cp["next_index"])
    if not lo <= cursor <= hi:
        raise ValueError("checkpoint cursor outside task")
    if (out / "task.json").exists() and digest(load(out / "task.json")) != task_hash:
        raise ValueError("output directory belongs to another task")
    seen = set()
    if hit_path.exists():
        for line in hit_path.read_text().splitlines():
            rec = json.loads(line)
            if rec.get("worker_sha256") != worker_hash:
                raise ValueError("saved hit has a different worker hash")
            seen.add(verify_hit(rec, task))
    old_status_path = out / "status.json"
    if old_status_path.exists():
        old_status = load(old_status_path)
        if old_status.get("state") in ("complete", "partial"):
            # Validate successful saved artifacts before rewriting any status.
            # A running/error status can legitimately predate a crash-replayed
            # checkpoint or append, so only terminal successful states assert
            # this exact cumulative unique-hit count.
            if not hit_path.is_file():
                raise ValueError("saved successful result is missing hits.jsonl")
            if old_status.get("task_sha256") != task_hash \
                    or old_status.get("worker_sha256") != worker_hash \
                    or old_status.get("checkpoint") != cp:
                raise ValueError("saved successful status differs from task/checkpoint")
            if len(seen) != integer(old_status["hits"]):
                raise ValueError("saved unique hit count differs from successful status")
    atomic_json(out / "task.json", task)

    def status(state, error=None):
        atomic_json(out / "status.json", {"schema": "ce375-ej-status-v1", "engine": ENGINE,
            "task_id": task["task_id"], "state": state, "error": error,
            "task_sha256": task_hash, "worker_sha256": worker_hash,
            "height": str(h), "covered_index_start": str(cursor),
            "covered_index_stop": str(hi), "hits": len(seen),
            "primitive_hits": sum(gcd(gcd(a,b),c) == 1 for a,b,c in seen),
            "checkpoint": cp})

    if cursor == lo and cp["complete"]:
        status("complete")
        return 0
    if cursor == lo:
        # A cursor alone is not a successful terminal record; re-run this finite unit.
        cursor = hi
        cp.update(next_index=str(hi), tiles=0, lattice_points="0", complete=False)
    base_tiles, base_points = integer(cp["tiles"]), integer(cp["lattice_points"])
    cmd = [str(worker), "--height", str(h), "--index-start", str(lo),
           "--index-stop", str(cursor), "--target", str(k), "--tile-scale", str(scale),
           "--max-tiles", str(task.get("max_tiles", 0)),
           "--progress-every", str(task.get("checkpoint_every", 100))]
    if not primitive:
        cmd.append("--include-nonprimitive")
    initial_cursor = cursor
    atomic_json(cp_path, cp)
    status("running")
    pending = []
    end = None
    started = False
    interrupted = False
    proc = None

    def stop(_signum=None, _frame=None):
        nonlocal interrupted
        interrupted = True
        if proc is not None and proc.poll() is None:
            proc.terminate()

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    timer = None

    def commit(rec):
        nonlocal cursor
        nxt, tiles, points = (integer(rec[key]) for key in ("next_index", "tiles", "lattice_points"))
        if not lo <= nxt <= cursor or tiles < integer(cp["tiles"])-base_tiles \
                or points < integer(cp["lattice_points"])-base_points:
            raise ValueError("invalid or backwards progress")
        with hit_path.open("a", encoding="utf-8") as f:
            for hit in pending:
                xyz = verify_hit(hit, task)
                if xyz not in seen:
                    hit = dict(hit, worker_sha256=worker_hash, original_points=original_points(xyz, k))
                    f.write(json.dumps(hit, sort_keys=True)+"\n")
                    seen.add(xyz)
            f.flush()
            os.fsync(f.fileno())
        pending.clear()
        cursor = nxt
        cp.update(next_index=str(cursor), tiles=base_tiles+tiles,
                  lattice_points=str(base_points+points), complete=False)
        atomic_json(cp_path, cp)

    try:
        with (out / "worker.stderr.log").open("a") as stderr, (out / "worker.jsonl").open("a") as raw:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
            deadline = integer(task.get("deadline_seconds", 0))
            if deadline:
                timer = threading.Timer(deadline, stop)
                timer.daemon = True
                timer.start()
            for line in proc.stdout:
                raw.write(line)
                raw.flush()
                rec = json.loads(line)
                if end is not None:
                    raise ValueError("worker emitted data after its terminal record")
                typ = rec.get("type")
                if typ == "start":
                    if started or rec.get("engine") != ENGINE or integer(rec["k"]) != k \
                       or integer(rec["height"]) != h or integer(rec["index_start"]) != lo \
                       or integer(rec["index_stop"]) != initial_cursor or rec.get("primitive") is not primitive:
                        raise ValueError("worker start does not match the task")
                    started = True
                elif not started:
                    raise ValueError("worker did not start with a matching start record")
                elif typ == "hit":
                    verify_hit(rec, task)
                    pending.append(rec)
                elif typ == "progress":
                    commit(rec)
                elif typ == "end":
                    # A terminal batch is provisional until its scope, reason,
                    # counters AND the process exit have all been accepted.
                    if not isinstance(rec.get("complete"), bool) \
                            or rec["complete"] != (integer(rec["next_index"]) == lo):
                        raise ValueError("terminal completion disagrees with its cursor")
                    if rec.get("reason") not in (("complete",) if rec["complete"] else ("tile_budget", "signal")):
                        raise ValueError("unrecognized terminal reason")
                    end = rec
                else:
                    raise ValueError(f"unknown worker record: {typ}")
            rc = proc.wait()
        if rc != 0:
            raise ValueError(f"worker exited with status {rc}")
        if end is None:
            raise ValueError("worker exited without a valid terminal record")
        commit(end)
        cp["complete"] = end["complete"]
        atomic_json(cp_path, cp)
        status("complete" if cp["complete"] else "partial")
        if not cp["complete"]:
            continuation = dict(task, index_stop=str(cursor))
            continuation["task_id"] = "ej-"+digest(continuation)[:20]
            continuation["continues_task"] = task.get("continues_task", task["task_id"])
            continuation["root_task_sha256"] = task.get("root_task_sha256", task_hash)
            atomic_json(out / "continuation.task.json", continuation)
        else:
            (out / "continuation.task.json").unlink(missing_ok=True)
        return 0
    except BaseException as exc:
        status("error", str(exc))
        raise
    finally:
        if timer:
            timer.cancel()
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def collect(args):
    if args.expected_worker_sha256 is not None \
            and not re.fullmatch(r"[0-9a-f]{64}", args.expected_worker_sha256):
        raise ValueError("expected worker hash must be a lowercase SHA-256 digest")
    page = load(args.page)
    if page.get("schema") != PAGE_SCHEMA or page.get("engine") != ENGINE:
        raise ValueError("not an Elkies--Jahnel page")
    tasks = {}
    for entry in page["tasks"]:
        task = load(args.page.parent / entry["path"])
        validate_task(task)
        if digest(task) != entry["sha256"] or task["task_id"] != entry["task_id"]:
            raise ValueError("page/task identity mismatch")
        tasks[task["task_id"]] = task
    staged, errors, hashes = [], [], set()
    for path in sorted(args.results.rglob("status.json")):
        try:
            status_rec, task = load(path), load(path.parent / "task.json")
            root_id = task.get("continues_task", task["task_id"])
            if root_id not in tasks:
                raise ValueError("result task is not in this page")
            root_task = tasks[root_id]
            if task["task_id"] == root_id:
                if digest(task) != digest(root_task):
                    raise ValueError("result task differs from page")
            else:
                if task.get("root_task_sha256") != digest(root_task):
                    raise ValueError("continuation does not identify the original task")
                for key in ("schema", "engine", "campaign_id", "k", "height",
                            "index_start", "primitive", "tile_scale"):
                    if task.get(key) != root_task.get(key):
                        raise ValueError("continuation changed the search scope")
                if integer(task["index_stop"]) > integer(root_task["index_stop"]):
                    raise ValueError("continuation extends outside the original task")
            _, h, lo, hi, _, _ = validate_task(task)
            cp = load(path.parent / "checkpoint.json")
            wh = status_rec["worker_sha256"]
            if not re.fullmatch(r"[0-9a-f]{64}", wh):
                raise ValueError("invalid worker hash")
            pins = {p for p in (args.expected_worker_sha256,
                               root_task.get("worker_sha256"), task.get("worker_sha256"))
                    if p is not None}
            if len(pins) > 1:
                raise ValueError("conflicting worker binary pins")
            expected = next(iter(pins), wh)
            if wh != expected or cp.get("worker_sha256") != wh:
                raise ValueError("unexpected worker binary")
            if status_rec.get("schema") != "ce375-ej-status-v1" \
                    or status_rec.get("engine") != ENGINE \
                    or status_rec.get("task_id") != task["task_id"] \
                    or status_rec.get("state") not in ("complete", "partial"):
                raise ValueError("result is not a successful complete/partial execution")
            if cp.get("schema") != CHECKPOINT_SCHEMA or cp.get("task_sha256") != digest(task) \
                    or status_rec.get("task_sha256") != digest(task) or status_rec.get("checkpoint") != cp:
                raise ValueError("checkpoint/status/task disagree")
            cursor = integer(cp["next_index"])
            if not lo <= cursor <= hi or cp.get("complete") != (cursor == lo) \
                    or (status_rec["state"] == "complete") != cp["complete"]:
                raise ValueError("invalid completed interval")
            if integer(status_rec["height"]) != h \
                    or integer(status_rec["covered_index_start"]) != cursor \
                    or integer(status_rec["covered_index_stop"]) != hi:
                raise ValueError("status coverage differs from checkpoint")
            hits = {}
            for line in (path.parent / "hits.jsonl").read_text().splitlines():
                rec = json.loads(line)
                if rec.get("worker_sha256") != wh:
                    raise ValueError("hit worker hash mismatch")
                xyz = verify_hit(rec, task)
                # Derived point metadata is re-created from verified cubes.
                # It is not an additional trusted assertion from the worker.
                hits[xyz] = dict(rec, original_points=original_points(xyz, integer(task["k"])))
            if len(hits) != integer(status_rec["hits"]):
                raise ValueError("verified unique hit count differs from saved status")
            staged.append((root_id, task, cursor, list(hits.values())))
            hashes.add(wh)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"path": str(path.parent), "error": str(exc)})
    if len(hashes) > 1:
        errors.append({"error": "mixed worker binaries: use one pinned build per page"})
        staged = []
    covered, gaps, unique = [], [], {}
    for task in tasks.values():
        _, h, lo, hi, _, _ = validate_task(task)
        relevant = [r for r in staged if r[0] == task["task_id"]]
        intervals = sorted((cursor, integer(subtask["index_stop"]))
                           for _, subtask, cursor, _ in relevant
                           if cursor < integer(subtask["index_stop"]))
        merged = []
        for left, right in intervals:
            if merged and left <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], right)
            else:
                merged.append([left, right])
        position = lo
        for left, right in merged:
            if position < left:
                gaps.append({"height": str(h), "index_start": str(position), "index_stop": str(left)})
            covered.append({"height": str(h), "index_start": str(left), "index_stop": str(right)})
            position = right
        if position < hi:
            gaps.append({"height": str(h), "index_start": str(position), "index_stop": str(hi)})
        for _, _, _, hits in relevant:
            for hit in hits:
                unique[(integer(hit["k"]), tuple(integer(hit[key]) for key in ("x", "y", "z")))] = hit
    summary = {"schema": "ce375-ej-summary-v1", "engine": ENGINE,
               "complete": not gaps and not errors, "covered": covered, "gaps": gaps,
               "errors": errors, "worker_hashes": sorted(hashes), "hits": len(unique),
               "coverage_scope": "listed cube-height shells and exact ratio-index bands only"}
    atomic_json(args.output_dir / "summary.json", summary)
    with (args.output_dir / "hits.jsonl").open("w") as f:
        for key in sorted(unique):
            f.write(json.dumps(unique[key], sort_keys=True)+"\n")
    print(json.dumps(summary))
    return 1 if errors or args.require_complete and gaps else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan", help="finite page; next_plan.json continues without a final height bound")
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--cursor", type=Path)
    p.add_argument("--height", type=int)
    p.add_argument("--right-index", type=int)
    p.add_argument("--campaign-id")
    p.add_argument("--k", type=int, default=375)
    p.add_argument("--grid-span", type=int, default=10000)
    p.add_argument("--page-size", type=int, default=10)
    p.add_argument("--tile-scale", default="11/2")
    p.add_argument("--max-tiles", type=int, default=0)
    p.add_argument("--deadline-seconds", type=int, default=0)
    p.add_argument("--checkpoint-every", type=int, default=100)
    p.add_argument("--include-nonprimitive", action="store_true")
    p.add_argument("--worker-sha256")
    p.set_defaults(func=plan)
    p = sub.add_parser("run")
    p.add_argument("--task", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--worker", type=Path, default=DEFAULT_WORKER)
    p.set_defaults(func=run)
    p = sub.add_parser("collect")
    p.add_argument("--page", type=Path, required=True)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--expected-worker-sha256")
    p.add_argument("--require-complete", action="store_true")
    p.set_defaults(func=collect)
    args = parser.parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ej375: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
