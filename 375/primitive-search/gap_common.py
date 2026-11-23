"""Shared exact checks and planning logic for the primitive 375 search.

Nothing here trusts the native worker: hits are re-verified exactly and task
files are validated before use.
"""
from __future__ import annotations

import hashlib
import json
import os
from math import gcd, isfinite, log, log1p, sqrt
from pathlib import Path
from typing import Any

TASK_SCHEMA = "ce375-primitive-task-v1"
PAGE_SCHEMA = "ce375-primitive-page-v1"
STATUS_SCHEMA = "ce375-primitive-status-v1"
CHECKPOINT_SCHEMA = "ce375-primitive-checkpoint-v1"
METHOD = "booker-sutherland-primitive-v1"
COUNTERS = ("d_total", "d_skipped_mod3", "d_no_roots", "d_live", "roots", "candidates",
            "pass_2adic", "pass_residue", "exact_checks", "hits", "d_skipped_primitive")
ALPHA = 2 ** (1 / 3) - 1

# Booker-Sutherland 2021 (PNAS), Table 1: Heath-Brown density rho_sol, e(B) = rho log B.
RHO = {114: 0.058459, 390: 0.032935, 627: 0.129565}
PRIMITIVE_RHO = {375: (24 / 25) * 0.061052}

# Their 2020 search of k in {114, 390, 579, 627, 633, 732, 921, 975}: z_max = 10^19,
# d_max = z_max/54. Everything with d above this is unsearched by them for any z.
BS_D_MAX = 10 ** 19 // 54                 # 185185185185185185
DEFAULT_D_START = 10 ** 10
D_LIMIT = 2 ** 63 // 27                   # the worker needs 27 d < 2^63


def load_json(path: Path) -> Any:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_json(path: Path, value: Any) -> None:
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())          # survive power loss on volunteer hosts
    tmp.replace(path)
    try:
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def is_prime(n: int) -> bool:
    """Deterministic Miller-Rabin for n < 3.3e24."""
    if n < 2:
        return False
    small = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
    for p in small:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in small:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def check_k(k: int) -> None:
    if k == 0 or k % 9 not in (3, 6):
        raise ValueError("the worker requires k == +-3 (mod 9)")


def verify_hit(record: dict, k: int | None = None, *, primitive_only: bool = False,
               height_min: int = 0) -> tuple[int, int, int]:
    """Exactly re-check one worker hit; returns (x, y, z)."""
    rk = int(record["k"])
    if k is not None and rk != k:
        raise ValueError(f"hit is for k={rk}, expected {k}")
    x, y, z, d = (int(record[key]) for key in ("x", "y", "z", "d"))
    if x ** 3 + y ** 3 + z ** 3 != rk:
        raise ValueError("x^3 + y^3 + z^3 != k")
    if abs(x + y) != d:
        raise ValueError("reported d != |x + y|")
    if primitive_only and gcd(x, y, z) != 1:
        raise ValueError("hit is not primitive")
    if max(abs(x), abs(y), abs(z)) <= height_min:
        raise ValueError("hit does not exceed the required height")
    return x, y, z


Z_LIMIT = 2 ** 126          # the worker holds z in 128 bits: (ratio_max + 18) * d_stop < 2^126
RATIO_LIMIT = 2 ** 40


def ratio_ok(ratio: int, d_stop: int) -> bool:
    """ratio_max accepted by worker 1.1.0 for d < d_stop."""
    return 4 <= ratio <= RATIO_LIMIT and (ratio + 18) * d_stop < Z_LIMIT


def coverage_fraction(ratio_max: float) -> float:
    """Heuristic share of the solutions attached to a given d with |z| <= ratio_max * d.

    Booker-Sutherland's model (their K(R) ~ R^(-1/2), c*sqrt(alpha) ~ 1): among
    solutions with a given d, the share with |z|/d >= R is sqrt(1/(alpha R)) for R >= 1/alpha.
    """
    return max(0.0, 1.0 - 1.0 / sqrt(ALPHA * ratio_max))


def new_fraction(d: float, ratio_max: float, height_min: int = 0) -> float:
    """Asymptotic angular mass remaining above a maximum-coordinate height cutoff.

    Neglecting the fixed k, a triple of height H and pair sum d has
    (|z|/d)^3 = 3(H/d)^2 - 3(H/d) + 1. The 1/sqrt(alpha*r)
    angular tail is the same approximation used by the upstream planner.
    This is a heuristic weight, never an enumeration or exclusion test.
    """
    lower = 1 / ALPHA
    if height_min > 0 and d < height_min:
        h = height_min / d
        lower = max(lower, (3 * h * h - 3 * h + 1) ** (1 / 3))
    return max(0.0, 1 / sqrt(ALPHA * lower) - 1 / sqrt(ALPHA * ratio_max))


def expected_solutions(rho: float, d_start: int, d_stop: int, ratio_max: float,
                       height_min: int = 0) -> float:
    """Heuristic expected number of solutions in d in [d_start, d_stop), z <= ratio_max d.

    Under the same model the solutions are log-uniform in d with density rho per
    unit log d, so the region holds rho * coverage * log(d_stop/d_start).
    """
    if not isfinite(rho) or rho < 0 or not 0 < d_start < d_stop:
        raise ValueError("invalid expected-yield parameters")
    width = log1p((d_stop - d_start) / d_start)
    if height_min <= 0:
        return rho * coverage_fraction(ratio_max) * width
    # Simpson integration in log(d), with enough panels even for broad bands.
    from math import exp
    n = max(64, int(width * 32))
    n += n % 2
    step = width / n
    total = new_fraction(d_start, ratio_max, height_min) + new_fraction(d_stop, ratio_max, height_min)
    for i in range(1, n):
        total += (4 if i % 2 else 2) * new_fraction(d_start * exp(i * step), ratio_max, height_min)
    return rho * step * total / 3


def search_options(record: dict) -> dict:
    """Normalize coverage-affecting options; task identity must include both."""
    primitive = record.get("primitive_only", False)
    if not isinstance(primitive, bool):
        raise ValueError("primitive_only must be a JSON boolean")
    height = int(record.get("height_min", 0))
    if height < 0 or height >= 2 ** 126:
        raise ValueError("height_min must be nonnegative and less than 2^126")
    return {"primitive_only": primitive, "height_min": height}


def worker_options(record: dict) -> list[str]:
    options = search_options(record)
    args = ["--height-min", str(options["height_min"])]
    if options["primitive_only"]:
        args.append("--primitive-only")
    return args


def registered_tasks(page: dict) -> dict[str, dict]:
    """Validate a page's exact, disjoint task partition before crediting work."""
    lo, hi = int(page["d_start"]), int(page["d_stop"])
    if not 1 <= lo < hi <= D_LIMIT:
        raise ValueError("invalid page interval")
    entries = page.get("tasks")
    if not isinstance(entries, list) or not entries:
        raise ValueError("page needs a nonempty registered task list")
    tasks = {}
    cursor = lo
    for entry in sorted(entries, key=lambda e: int(e["d_start"])):
        task_id = entry.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id in tasks:
            raise ValueError("page task identifiers must be nonempty and unique")
        start, stop = int(entry["d_start"]), int(entry["d_stop"])
        if start != cursor or not start < stop <= hi:
            raise ValueError("page tasks must exactly partition the page without gaps or overlap")
        tasks[task_id] = entry
        cursor = stop
    if cursor != hi:
        raise ValueError("page tasks do not reach the page endpoint")
    return tasks


def validate_task(task: dict) -> dict:
    if task.get("schema") != TASK_SCHEMA:
        raise ValueError(f"task schema must be {TASK_SCHEMA}")
    for key in ("campaign_id", "task_id"):
        if not isinstance(task.get(key), str) or not task[key]:
            raise ValueError(f"{key} must be a nonempty string")
    k = int(task["k"])
    check_k(k)
    d_start, d_stop, ratio = int(task["d_start"]), int(task["d_stop"]), int(task["ratio_max"])
    if not 1 <= d_start < d_stop <= D_LIMIT:
        raise ValueError("need 1 <= d_start < d_stop <= 2^63/27")
    if not ratio_ok(ratio, d_stop):
        raise ValueError("ratio_max out of range")
    deadline = int(task.get("deadline_seconds", 0))
    if deadline < 0:
        raise ValueError("deadline_seconds must be >= 0")
    return {"k": k, "d_start": d_start, "d_stop": d_stop, "ratio_max": ratio,
            "deadline_seconds": deadline, **search_options(task)}
