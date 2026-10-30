"""Shared, independent Python logic for the CE627 d-first search.

Nothing here calls the native worker. It re-implements, in exact integer and
rational arithmetic, everything a result must satisfy, so the runner and the
collector can check the worker instead of trusting it.

Equation (production K = 627):

    N(n) = 36n^3 + 54n^2 + 27n + (27 - K)/6        (= 36n^3+54n^2+27n-100)
    N(n) = -2*d*x^2*( -(x+6n+3) + s ),  s = sqrt((x+6n+3)^2 + N(n)/x) >= 0

accepted in either chart:
    integer chart: x, s integers
    half chart:    x = X/2, s = Y/2 with X, Y odd.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from math import gcd, isqrt
from pathlib import Path
from typing import Any

PRODUCTION_K = 627
TASK_SCHEMA = "ce627-dfirst-task-v1"
PAGE_SCHEMA = "ce627-dfirst-page-v1"
STATUS_SCHEMA = "ce627-dfirst-status-v1"
CHECKPOINT_SCHEMA = "ce627-dfirst-checkpoint-v1"
PARAMETERIZATION = "ce627-dfirst-thue-both-charts-v1"
COUNTERS = ("pairs", "admissible", "convergents", "small_g_values", "thue_solutions",
            "integer_chart", "half_chart", "other_branch", "refinements", "exact_roots")
MAX_H = 200_000_000


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


def pairs_through(h: int) -> int:
    """Raw (p, q) pairs in shells 1..h: shell H has 4H - 1 pairs."""
    return 2 * h * h + h if h > 0 else 0


def pairs_in(h_start: int, h_stop: int) -> int:
    return pairs_through(h_stop - 1) - pairs_through(h_start - 1)


def check_k(k: int) -> None:
    if k % 2 == 0 or k % 9 not in (3, 6):
        raise ValueError("k must be odd and +-3 (mod 9)")


# ------------------------------------------------------------ admissibility
def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


def _factor(n: int) -> dict[int, int]:
    n, out, f = abs(n), {}, 2
    while f * f <= n:
        while n % f == 0:
            out[f] = out.get(f, 0) + 1
            n //= f
        f += 1
    if n > 1:
        out[n] = out.get(n, 0) + 1
    return out


def _form(p: int, q: int, S: int, g: int) -> int:
    return S ** 3 - 6 * p * q * S * g * g + 3 * p * q * (p + q) * g ** 3


class Admissibility:
    """Independent mirror of the worker's proved necessary conditions."""

    def __init__(self, k: int):
        check_k(k)
        self.k = k
        self.kfac = _factor(k)
        self.local: dict[int, set[tuple[int, int]]] = {}
        for l, v in self.kfac.items():
            if l < 5 or l > 4000 or v >= 3:
                continue
            allowed = set()
            for pr in range(l):
                for qr in range(l):
                    if any((S or g) and (_form(pr, qr, S, g) - k) % l == 0
                           for S in range(l) for g in range(l)):
                        allowed.add((pr, qr))
            self.local[l] = allowed
        self._cap: dict[int, int] = {}

    def cap(self, l: int) -> int:
        if l not in self._cap:
            if l == 2:
                c = 10 ** 9
            elif l == 3:
                c = 0
            elif l in self.kfac:
                c = self.kfac[l] if self.kfac[l] <= 2 else 10 ** 9
            elif l % 3 == 2:
                c = 10 ** 9
            else:
                c = 10 ** 9 if pow(self.k % l, (l - 1) // 3, l) == 1 else 0
            self._cap[l] = c
        return self._cap[l]

    def __call__(self, p: int, q: int) -> bool:
        if q <= 0 or p == 0 or gcd(p, q) != 1:
            return False
        if p % 3 == 0 or q % 3 == 0 or p % 3 != q % 3:
            return False
        for value in (p, q):
            for l, e in _factor(value).items():
                if e > self.cap(l):
                    return False
        for l, allowed in self.local.items():
            if (p % l, q % l) not in allowed:
                return False
        return True


def shell(h: int):
    """The worker's order inside shell h: q = h, -h <= p <= h; then q < h, p = -h, +h."""
    for p in range(-h, h + 1):
        yield p, h
    for q in range(1, h):
        yield -h, q
        yield h, q


# ------------------------------------------------------------- verification
def _int(record: dict, key: str) -> int:
    value = record[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a decimal string")
    return int(value, 10)


def verify_hit(record: dict, k: int | None = None) -> dict:
    """Exact re-verification of one worker hit; returns a normalized record."""
    rk = _int(record, "k")
    if k is not None and rk != k:
        raise ValueError(f"hit is for k={rk}, expected {k}")
    check_k(rk)
    p, q = _int(record, "d_num"), _int(record, "d_den")
    g, n = _int(record, "g"), _int(record, "n")
    if q <= 0 or gcd(p, q) != 1:
        raise ValueError("d is not a reduced fraction with positive denominator")
    d = Fraction(p, q)
    x = Fraction(_int(record, "x_num"), _int(record, "x_den"))
    s = Fraction(_int(record, "s_num"), _int(record, "s_den"))
    S = 6 * n + 3
    if x != Fraction(-q * g, 2) or s != Fraction((2 * p + q) * g, 2) - S:
        raise ValueError("x or s does not match (d, g, n)")
    if x == 0 or s < 0:
        raise ValueError("x must be nonzero and s nonnegative")
    N = 36 * n ** 3 + 54 * n ** 2 + 27 * n + (27 - rk) // 6
    U = x + S
    if s * s != U * U + N / x:
        raise ValueError("s is not sqrt((x+6n+3)^2 + N/x)")
    if N != -2 * d * x * x * (-U + s):
        raise ValueError("original equation fails")
    if x.denominator == 1 and s.denominator == 1:
        chart = "integer"
    elif x.denominator == 2 and s.denominator == 2:
        chart = "half"
    else:
        raise ValueError("point is in neither accepted chart")
    if record.get("chart") != chart:
        raise ValueError("reported chart is wrong")
    a, b, c = -x + s, -x - s, 2 * x + S
    if any(v.denominator != 1 for v in (a, b, c)) or a ** 3 + b ** 3 + c ** 3 != rk:
        raise ValueError("cube identity fails")
    if (a, b, c) != tuple(Fraction(_int(record, key)) for key in ("cube_a", "cube_b", "cube_c")):
        raise ValueError("reported cube components are wrong")
    if rk == PRODUCTION_K and n % 3 != 1:
        raise ValueError("production invariant n == 1 (mod 3) fails")
    return {"k": str(rk), "chart": chart, "d": f"{p}/{q}", "n": str(n),
            "x": str(x), "s": str(s), "cubes": [str(a), str(b), str(c)], "g": str(g)}


def hit_key(record: dict) -> str:
    return "|".join(str(record[k]) for k in ("k", "d_num", "d_den", "g", "n"))


def d_values_from_cubes(a: int, b: int, c: int, k: int) -> list[dict]:
    """All accepted (d, chart, x, s) produced by one representation a^3+b^3+c^3 = k.

    Used by tests: every ordered choice of the third component C and the
    order A >= B of the other two gives x = -(A+B)/2, s = (A-B)/2 and
    d = (A+C)/(A+B), provided A+B != 0.
    """
    if a ** 3 + b ** 3 + c ** 3 != k:
        raise ValueError("not a representation")
    out = []
    trip = (a, b, c)
    for i in range(3):
        C = trip[i]
        A, B = sorted((trip[(i + 1) % 3], trip[(i + 2) % 3]), reverse=True)
        if A + B == 0:
            continue
        d = Fraction(A + C, A + B)
        x, s = Fraction(-(A + B), 2), Fraction(A - B, 2)
        chart = "integer" if x.denominator == 1 else "half"
        out.append({"d": d, "chart": chart, "x": x, "s": s, "n": (A + B + C - 3) // 6})
    return out


def validate_task(task: dict) -> dict:
    if task.get("schema") != TASK_SCHEMA:
        raise ValueError(f"task schema must be {TASK_SCHEMA}")
    k = int(task["k"])
    check_k(k)
    h_start, h_stop = int(task["h_start"]), int(task["h_stop"])
    if not 1 <= h_start < h_stop <= MAX_H + 1:
        raise ValueError("need 1 <= h_start < h_stop")
    digits = int(task.get("g_max_digits", 100))
    if not 1 <= digits <= 100000:
        raise ValueError("g_max_digits out of range")
    deadline = int(task.get("deadline_seconds", 0))
    if deadline < 0:
        raise ValueError("deadline_seconds must be >= 0")
    for key in ("campaign_id", "task_id"):
        if not isinstance(task.get(key), str) or not task[key]:
            raise ValueError(f"{key} must be a nonempty string")
    return {"k": k, "h_start": h_start, "h_stop": h_stop, "g_max_digits": digits,
            "deadline_seconds": deadline}


def isqrt_exact(v: int) -> int | None:
    if v < 0:
        return None
    r = isqrt(v)
    return r if r * r == v else None
