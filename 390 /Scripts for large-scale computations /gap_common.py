"""Shared, independent Python logic for the gap search (GAP_SEARCH.md).

Nothing here trusts the native worker: hits are re-verified exactly and task
files are validated before use.
"""
from __future__ import annotations

import hashlib
import json
import os
from math import log, sqrt
from pathlib import Path
from typing import Any

TASK_SCHEMA = "ce390-gap-task-v1"
PAGE_SCHEMA = "ce390-gap-page-v1"
STATUS_SCHEMA = "ce390-gap-status-v1"
CHECKPOINT_SCHEMA = "ce390-gap-checkpoint-v1"
METHOD = "booker-sutherland-gap-v1"
COUNTERS = ("d_total", "d_skipped_mod3", "d_no_roots", "d_live", "roots", "candidates",
            "pass_2adic", "pass_residue", "exact_checks", "hits")
ALPHA = 2 ** (1 / 3) - 1

# Booker-Sutherland 2021 (PNAS), Table 1: Heath-Brown density rho_sol, e(B) = rho log B.
RHO = {390: 0.032935, 627: 0.129565}

# Their 2020 search of k in {114, 390, 579, 627, 633, 732, 921, 975}: z_max = 10^19,
# d_max = z_max/54. Everything with d above this is unsearched by them for any z.
BS_D_MAX = 10 ** 19 // 54                 # 185185185185185185
DEFAULT_D_START = BS_D_MAX + 1
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


def verify_hit(record: dict, k: int | None = None) -> tuple[int, int, int]:
    """Exactly re-check one worker hit; returns (x, y, z)."""
    rk = int(record["k"])
    if k is not None and rk != k:
        raise ValueError(f"hit is for k={rk}, expected {k}")
    x, y, z, d = (int(record[key]) for key in ("x", "y", "z", "d"))
    if x ** 3 + y ** 3 + z ** 3 != rk:
        raise ValueError("x^3 + y^3 + z^3 != k")
    if abs(x + y) != d:
        raise ValueError("reported d != |x + y|")
    return x, y, z


def coverage_fraction(ratio_max: float) -> float:
    """Heuristic share of the solutions attached to a given d with |z| <= ratio_max * d.

    Booker-Sutherland's model (their K(R) ~ R^(-1/2), c*sqrt(alpha) ~ 1): among
    solutions with a given d, the share with |z|/d >= R is sqrt(1/(alpha R)) for R >= 1/alpha.
    """
    return max(0.0, 1.0 - 1.0 / sqrt(ALPHA * ratio_max))


def expected_solutions(rho: float, d_start: int, d_stop: int, ratio_max: float) -> float:
    """Heuristic expected number of solutions in d in [d_start, d_stop), z <= ratio_max d.

    Under the same model the solutions are log-uniform in d with density rho per
    unit log d, so the region holds rho * coverage * log(d_stop/d_start).
    """
    return rho * coverage_fraction(ratio_max) * log(d_stop / d_start)


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
    if ratio < 4 or ratio * d_stop + 18 * d_stop >= 2 ** 64:
        raise ValueError("ratio_max out of range")
    deadline = int(task.get("deadline_seconds", 0))
    if deadline < 0:
        raise ValueError("deadline_seconds must be >= 0")
    return {"k": k, "d_start": d_start, "d_stop": d_stop, "ratio_max": ratio, "deadline_seconds": deadline}
