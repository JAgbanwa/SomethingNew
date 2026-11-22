"""Shared, independent Python logic for the CE375 n-first search.

Nothing here calls the native worker. It re-implements, in exact integer and
rational arithmetic, everything a result must satisfy, so the runner and the
collector check the worker instead of trusting it.

Equation (production k = 375):

    y^2 = (x + 6n+3)^2 + N(n)/x,     N(n) = 36n^3 + 54n^2 + 27n + (27 - k)/6
                                           (= 36n^3 + 54n^2 + 27n - 58)

with n an integer and x, y rational, in either accepted form:

    integer form: x, y integers                    (result 1)
    half form:    x = X/2, y = Y/2 with X, Y odd   (result 2)

Every hit records X = 2x and Y = 2|y| and carries the primitivity flags

    primitive_point: gcd(n, x) = 1 (integer form), gcd(X, Y) = 1 (half form)
    primitive_cubes: gcd(A, B, C) = 1, A = -x+y, B = -x-y, C = 2x+6n+3
    desired:         both
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from math import gcd
from pathlib import Path
from typing import Any

PRODUCTION_K = 375
TASK_SCHEMA = "ce375-xy-task-v1"
PAGE_SCHEMA = "ce375-xy-page-v1"
STATUS_SCHEMA = "ce375-xy-status-v1"
CHECKPOINT_SCHEMA = "ce375-xy-checkpoint-v1"
METHOD = "ce375-nfirst-divisors-v1"
COUNTERS = ("ns", "divisors", "candidates", "exact_checks", "hits", "incomplete", "rho_calls")
N_LIMIT = 10 ** 12


# ---------------------------------------------------------------- utilities
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
    tmp.replace(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check_k(k: int) -> None:
    if k % 2 == 0 or k % 9 not in (3, 6) or abs(k) > 10 ** 9:
        raise ValueError("k must be odd, +-3 (mod 9) and |k| <= 10^9")


def n_mod3(k: int) -> int:
    """The residue of n (mod 3) forced by k (METHOD.md section 2); 2 for k = 375."""
    check_k(k)
    s9 = ((k + 6) // 3) % 9 if k % 9 == 3 else ((k - 6) // 3) % 9   # S mod 9
    s18 = next(v for v in range(3, 18, 6) if v % 9 == s9)            # S mod 18, S = 3 (mod 6)
    return (s18 - 3) // 6


def N_of(n: int, k: int = PRODUCTION_K) -> int:
    return 36 * n ** 3 + 54 * n ** 2 + 27 * n + (27 - k) // 6


def ns_in(a: int, b: int, k: int = PRODUCTION_K) -> int:
    """How many n in [a, b) have n = n_mod3(k) (mod 3): the n the worker processes."""
    r = n_mod3(k)
    return (b - 1 - r) // 3 - (a - 1 - r) // 3


# ------------------------------------------------------------- verification
def _int(record: dict, key: str) -> int:
    value = record[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a decimal string")
    return int(value, 10)


def primitivity(form: str, n: int, x: Fraction, y: Fraction, cubes: tuple[int, int, int]) -> dict:
    pg = gcd(n, int(x)) if form == "integer" else gcd(int(2 * x), int(2 * y))
    cg = gcd(gcd(cubes[0], cubes[1]), cubes[2])
    return {"primitive_point": pg == 1, "primitive_cubes": cg == 1, "desired": pg == 1 and cg == 1,
            "point_gcd": str(pg), "cube_gcd": str(cg)}


def verify_hit(record: dict, k: int | None = None) -> dict:
    """Exact re-verification of one worker hit; returns a normalized record."""
    rk = _int(record, "k")
    if k is not None and rk != k:
        raise ValueError(f"hit is for k={rk}, expected {k}")
    check_k(rk)
    n, X, Y = _int(record, "n"), _int(record, "X"), _int(record, "Y")
    if X == 0 or Y < 0 or X % 2 != Y % 2:
        raise ValueError("need X != 0, Y >= 0 and X, Y of equal parity")
    form = "integer" if X % 2 == 0 else "half"
    if record.get("form") != form:
        raise ValueError("reported form is wrong")
    x, y, S = Fraction(X, 2), Fraction(Y, 2), 6 * n + 3
    if x != Fraction(_int(record, "x_num"), _int(record, "x_den")) or \
            y != Fraction(_int(record, "y_num"), _int(record, "y_den")):
        raise ValueError("x, y fields disagree with X, Y")
    N = N_of(n, rk)
    if y * y != (x + S) ** 2 + N / x:
        raise ValueError("y^2 != (x+6n+3)^2 + N(n)/x")
    a, b, c = -x + y, -x - y, 2 * x + S
    if any(v.denominator != 1 for v in (a, b, c)) or a ** 3 + b ** 3 + c ** 3 != rk:
        raise ValueError("cube identity fails")
    if (a, b, c) != tuple(Fraction(_int(record, key)) for key in ("cube_a", "cube_b", "cube_c")):
        raise ValueError("reported cube components are wrong")
    if n % 3 != n_mod3(rk):
        raise ValueError(f"invariant n == {n_mod3(rk)} (mod 3) fails")
    prim = primitivity(form, n, x, y, (int(a), int(b), int(c)))
    for key, value in prim.items():
        if record.get(key) != value:
            raise ValueError(f"reported {key} is wrong")
    return {"k": str(rk), "form": form, "n": str(n), "x": str(x), "y": str(y), "X": str(X), "Y": str(Y),
            "cubes": [str(a), str(b), str(c)], **prim}


def hit_key(record: dict) -> str:
    return "|".join(str(record[key]) for key in ("k", "n", "X", "Y"))


def validate_task(task: dict) -> dict:
    if task.get("schema") != TASK_SCHEMA:
        raise ValueError(f"task schema must be {TASK_SCHEMA}")
    k = int(task["k"])
    check_k(k)
    n_start, n_stop = int(task["n_start"]), int(task["n_stop"])
    if not -N_LIMIT <= n_start < n_stop <= N_LIMIT + 1:
        raise ValueError("need -10^12 <= n_start < n_stop <= 10^12 + 1")
    deadline = int(task.get("deadline_seconds", 0))
    if deadline < 0:
        raise ValueError("deadline_seconds must be >= 0")
    for key in ("campaign_id", "task_id"):
        if not isinstance(task.get(key), str) or not task[key]:
            raise ValueError(f"{key} must be a nonempty string")
    return {"k": k, "n_start": n_start, "n_stop": n_stop, "deadline_seconds": deadline}
