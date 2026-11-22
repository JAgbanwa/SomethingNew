"""Shared, independent Python logic for the k = 375 primitive gap search (README.md).

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

TASK_SCHEMA = "ce375-gap-task-v1"
PAGE_SCHEMA = "ce375-gap-page-v1"
STATUS_SCHEMA = "ce375-gap-status-v1"
CHECKPOINT_SCHEMA = "ce375-gap-checkpoint-v1"
METHOD = "booker-sutherland-gap-v1"
COUNTERS = ("d_total", "d_skipped_mod3", "d_skipped_prim", "d_no_roots", "d_live", "roots", "candidates",
            "pass_2adic", "pass_residue", "exact_checks", "hits", "hits_primitive")
ALPHA = 2 ** (1 / 3) - 1

# Heath-Brown density rho for primitive solutions. Booker-Sutherland's Table 1 covers cube-free
# k only; the constant for primitive solutions of 375 = 3*5^3 has not been computed here, so
# the planner reports E/rho unless --rho is given.
RHO: dict[int, float] = {}

# Frontier: every primitive solution with max(|x|, |y|, |z|) <= FRONTIER is assumed already
# excluded. Default 10^14: Elsenhans-Jahnel's Elkies-type search of all k < 1000 (Sutherland,
# "Mordell's question", 2022 slides). Confirm before a campaign; pass --frontier.
DEFAULT_FRONTIER = 10 ** 14
DEFAULT_D_START = 1
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


def cube_primes(k: int) -> list[int]:
    """Primes p with p^3 | k (all are != 3 since k == +-3 mod 9)."""
    a, out, p = abs(k), [], 2
    while p * p * p <= a:
        if a % p == 0:
            v = 0
            while a % p == 0:
                a //= p
                v += 1
            if v >= 3:
                out.append(p)
        p += 1
    return out


def primitive_d_ok(k: int, d: int) -> bool:
    """Necessary condition on d = |x+y| for a primitive solution (README.md, section 2)."""
    for p in cube_primes(k):
        v = 0
        while d % p == 0:
            d //= p
            v += 1
        if v in (1, 2):
            return False
    return True


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
    if "primitive" in record:
        from math import gcd
        if bool(record["primitive"]) != (gcd(gcd(x, y), z) == 1):
            raise ValueError("primitive flag disagrees with gcd(x, y, z)")
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


def z_frontier(d: float, frontier: float) -> float:
    """Smallest |z| whose solution can have max coordinate > frontier, for this d.

    With t = |x - y| = sqrt(Delta), 3 d Delta = 4(z^3 - K) - d^3, the largest coordinate is
    (d + t)/2. It exceeds N exactly when Delta > (2N - d)^2, i.e. (K negligible)
    z^3 > d (3 (2N - d)^2 + d^2) / 4.
    """
    if frontier <= 0 or 2 * frontier <= d:
        return 0.0
    return (d * (3 * (2 * frontier - d) ** 2 + d * d) / 4) ** (1 / 3)


def yield_per_d(d: float, ratio_max: float, frontier: float = 0) -> float:
    """E/rho per unit d at d: the Booker-Sutherland density
    dE = rho/(2 sqrt(alpha)) d^(-1/2) z^(-3/2) dd dz over d/alpha < z <= ratio_max d,
    keeping only z beyond the frontier."""
    lo = max(d / ALPHA, z_frontier(d, frontier))
    hi = ratio_max * d
    if lo >= hi:
        return 0.0
    return (lo ** -0.5 - hi ** -0.5) / (sqrt(ALPHA) * sqrt(d))


def expected_solutions(rho: float, d_start: int, d_stop: int, ratio_max: float, frontier: float = 0) -> float:
    """Heuristic expected number of (primitive) solutions with d in [d_start, d_stop),
    z <= ratio_max d and max coordinate above the frontier.

    Without a frontier this is rho * coverage * log(d_stop/d_start) (solutions log-uniform in d).
    With one, the density is integrated numerically in log d.
    """
    if frontier <= 0:
        return rho * coverage_fraction(ratio_max) * log(d_stop / d_start)
    lo, hi, n = log(d_start), log(d_stop), 2000
    h = (hi - lo) / n
    total = 0.0
    for i in range(n):
        from math import exp
        d = exp(lo + (i + 0.5) * h)
        total += yield_per_d(d, ratio_max, frontier) * d * h
    return rho * total


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
    primitive = task.get("primitive", True)
    if not isinstance(primitive, bool):
        raise ValueError("primitive must be true or false")
    if primitive and any(p % 3 != 2 for p in cube_primes(k)):
        raise ValueError("primitive mode needs every p with p^3 | k to be == 2 (mod 3)")
    return {"k": k, "d_start": d_start, "d_stop": d_stop, "ratio_max": ratio, "deadline_seconds": deadline,
            "primitive": primitive}
