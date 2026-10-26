"""Shared definitions for the d-first half-chart engine (see D_FIRST.md).

Everything here is an INDEPENDENT Python implementation of what the native
worker (src/dthue_worker.cpp) does, so the two can be checked against each
other: admissibility of d = p/q, the shell ordering, and exact verification of
a reported point against the ORIGINAL equation using fractions.Fraction.
"""
from __future__ import annotations

from fractions import Fraction
from math import gcd, isqrt
from typing import Any, Iterator

from run_task import digest, integer, keys

PARAMETERIZATION = "dfirst-thue-height-shells-v1"
TASK_SCHEMA = "ce390-dfirst-task-v1"
STATUS_SCHEMA = "ce390-dfirst-status-v1"
CHECKPOINT_SCHEMA = "ce390-dfirst-checkpoint-v1"
PAGE_SCHEMA = "ce390-dfirst-page-v1"
COUNTERS = ("pairs", "admissible", "convergents", "small_g_values", "thue_solutions",
            "other_chart", "other_branch", "refinements", "exact_roots")
MAX_H = 200_000_000


# ---------------------------------------------------------------------------
# Admissibility of d = p/q (proved in D_FIRST.md, section 3).

def _factor(n: int) -> dict[int, int]:
    n = abs(n)
    out: dict[int, int] = {}
    d = 2
    while d * d <= n:
        while n % d == 0:
            out[d] = out.get(d, 0) + 1
            n //= d
        d += 1 if d == 2 else 2
    if n > 1:
        out[n] = out.get(n, 0) + 1
    return out


def _valuation(n: int, p: int) -> int:
    v = 0
    while n % p == 0:
        n //= p
        v += 1
    return v


def prime_cap(prime: int, m: int) -> int | None:
    """Largest allowed exponent of `prime` in p*q (None = unlimited, 0 = forbidden)."""
    if prime == 2:
        return 1 if m % 2 else None
    if prime == 3:
        return 0
    vm = _valuation(abs(m), prime)
    if vm:
        return vm if vm <= 2 else None
    if prime % 3 == 2:
        return None
    e = (prime - 1) // 3
    return None if pow(m % prime, e, prime) == pow(36, e, prime) else 0


def admissible(p: int, q: int, m: int) -> bool:
    """Necessary conditions on d = p/q (lowest terms, q > 0) for a half-chart point."""
    if q <= 0 or p == 0 or gcd(p, q) != 1 or q % 2 == 0:
        return False
    if p % 3 == 0 or q % 3 == 0 or p % 3 != q % 3:
        return False
    for value in (p, q):
        for prime, exponent in _factor(value).items():
            cap = prime_cap(prime, m)
            if cap is not None and exponent > cap:
                return False
    return True


def shell_pairs(h: int) -> Iterator[tuple[int, int]]:
    """All (p, q) with max(|p|, q) = h, in the worker's order."""
    for p in range(-h, h + 1):
        yield p, h
    for q in range(1, h):
        yield -h, q
        yield h, q


def pairs_in_shells(start: int, stop: int) -> int:
    """Number of (p, q) pairs in shells start <= h < stop (4h - 1 per shell)."""
    if stop <= start:
        return 0
    return 2 * (stop - 1) * stop - 2 * (start - 1) * start - (stop - start)


def thue_form(p: int, q: int, n: int, g: int) -> int:
    return 72 * n ** 3 - 12 * p * q * n * g * g + p * q * (p + q) * g ** 3


# ---------------------------------------------------------------------------
# Tasks.

def validate_search(search: Any) -> dict[str, Any]:
    keys(search, {"parameterization", "m", "chart", "g_max_digits"}, set(), "search")
    if search["parameterization"] != PARAMETERIZATION:
        raise ValueError("unknown parameterization")
    if search["chart"] != "half":
        raise ValueError("only the half chart (x = X/2, y = Y/2) is supported")
    m = integer(search["m"], "search.m", signed=True)
    if m == 0 or m % 3 == 0 or abs(m) > 10**9:
        raise ValueError("m must be nonzero, not divisible by 3, and |m| <= 10^9")
    digits = search["g_max_digits"]
    if isinstance(digits, bool) or not isinstance(digits, int) or not 1 <= digits <= 100000:
        raise ValueError("g_max_digits must be an integer between 1 and 100000")
    return {"m": m, "g_max_digits": digits}


def task_identity(task: dict[str, Any]) -> str:
    return digest({k: task[k] for k in ("schema", "campaign_id", "ordinal", "search", "shells")})


def validate_task(task: Any) -> dict[str, Any]:
    keys(task, {"schema", "campaign_id", "ordinal", "search", "shells", "seconds", "task_id"},
         {"worker", "resume"}, "task")
    if task["schema"] != TASK_SCHEMA:
        raise ValueError("not a d-first task")
    if not isinstance(task["campaign_id"], str) or not task["campaign_id"]:
        raise ValueError("campaign_id must be a nonempty string")
    integer(task["ordinal"], "ordinal")
    search = validate_search(task["search"])
    keys(task["shells"], {"start", "stop"}, set(), "shells")
    start = integer(task["shells"]["start"], "shells.start", positive=True)
    stop = integer(task["shells"]["stop"], "shells.stop", positive=True)
    if not start < stop <= MAX_H + 1:
        raise ValueError("shells must satisfy 1 <= start < stop <= 200000001")
    seconds = task["seconds"]
    if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= 86400:
        raise ValueError("seconds must be an integer between 1 and 86400")
    if task["task_id"] != task_identity(task):
        raise ValueError("task_id does not match the task definition")
    worker = task.get("worker", {})
    keys(worker, set(), {"precision_bits", "max_precision_bits"}, "worker")
    resume = start
    if "resume" in task:
        keys(task["resume"], {"next_h", "expected_worker_sha256", "expected_implementation_sha256"}, set(), "resume")
        resume = integer(task["resume"]["next_h"], "resume.next_h", positive=True)
        if not start <= resume <= stop:
            raise ValueError("resume.next_h lies outside the task shells")
    return {**search, "start": start, "stop": stop, "resume": resume, "seconds": seconds,
            "precision_bits": worker.get("precision_bits", 128),
            "max_precision_bits": worker.get("max_precision_bits", 262144)}


# ---------------------------------------------------------------------------
# Exact verification of a reported half-chart point.

def _decimal(record: dict[str, Any], name: str) -> int:
    value = record.get(name)
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a decimal string")
    return integer(value, name, signed=True)


def hit_key(record: dict[str, Any]) -> str:
    return f"{record['d_num']}/{record['d_den']}|{record['n_num']}|{record['x_num']}"


def verify_hit(record: Any, m: int, shells: tuple[int, int] | None = None) -> dict[str, Any]:
    """Re-check a hit against the original, unsquared equation. Raises ValueError."""
    if not isinstance(record, dict) or record.get("type") != "hit" or record.get("chart") != "half":
        raise ValueError("not a half-chart hit record")
    if record.get("m") != str(m):
        raise ValueError("hit belongs to a different m")
    d = Fraction(_decimal(record, "d_num"), _decimal(record, "d_den"))
    if d.numerator != _decimal(record, "d_num") or d.denominator != _decimal(record, "d_den"):
        raise ValueError("d is not reduced")
    if _decimal(record, "n_den") != 1 or _decimal(record, "x_den") != 2 or _decimal(record, "y_den") != 2:
        raise ValueError("expected integer n and x, y with denominator 2")
    n = _decimal(record, "n_num")
    X, Y = _decimal(record, "x_num"), _decimal(record, "y_num")
    if X % 2 == 0 or Y % 2 == 0 or Y <= 0:
        raise ValueError("X and Y must be odd and Y positive")
    x, y = Fraction(X, 2), Fraction(Y, 2)
    s = x + 6 * n
    a = Fraction(36 * n ** 3 - m)
    radicand = s * s + a / x
    if radicand != y * y:
        raise ValueError("y is not the square root of the radicand")
    if a != -2 * d * x * x * (y - s):
        raise ValueError("original equation fails")
    if d != -(y + s) / (2 * x):
        raise ValueError("d is not -(y + x + 6n)/(2x)")
    A, B, C = -x + y, -x - y, 2 * x + 6 * n
    if any(v.denominator != 1 for v in (A, B, C)):
        raise ValueError("cube components are not integers")
    comps = (int(A), int(B), int(C))
    names = ("cube_plus", "cube_minus", "cube_third")
    if any(_decimal(record, k) != v for k, v in zip(names, comps)):
        raise ValueError("cube components disagree with x, y, n")
    if sum(v ** 3 for v in comps) != 6 * m or _decimal(record, "cube_sum") != 6 * m:
        raise ValueError("cube sum is not 6m")
    if shells is not None:
        h = max(abs(d.numerator), d.denominator)
        if not shells[0] <= h < shells[1]:
            raise ValueError("d lies outside the claimed height shells")
    return {"d": d, "n": n, "x": x, "y": y, "components": comps}
