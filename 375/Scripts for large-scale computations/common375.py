"""Shared, independent Python logic for the CE375 unit-g search.

Nothing here calls the native worker. It re-implements, in exact integer and
rational arithmetic, everything a result must satisfy, so the runner and the
collector can check the worker instead of trusting it.

Equation (production K = 375):

    N(n) = 36n^3 + 54n^2 + 27n + (27 - K)/6        (= 36n^3+54n^2+27n-58)
    N(n) = -2*d*x^2*( -(x+6n+3) + s ),  s = sqrt((x+6n+3)^2 + N(n)/x) >= 0

accepted in either chart:
    integer chart: x, s integers
    half chart:    x = X/2, s = Y/2 with X, Y odd.

Production campaigns use only g in {-1, 1}. Either primitive chart is enough:
    primitive_point: gcd(n, x, s) = 1 (integer chart), gcd(X, Y) = 1 (half chart)
    primitive_cubes: gcd(A, B, C) = 1, reported as an independent diagnostic
    desired = primitive_point

Mode "xy-half" (DERIVATION.md sections 1-3) searches only for rational (x, y) on
    y^2 = (x+6n+3)^2 + N(n)/x,  x = X/2, y = Y/2, X, Y odd, gcd(X, Y) = 1,
both signs of y; its hit records carry "mode": "xy-half" and are checked by
verify_xy_hit().
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from math import gcd, isqrt
from pathlib import Path
from typing import Any

PRODUCTION_K = 375
TASK_SCHEMA = "ce375-dfirst-task-v2"
PAGE_SCHEMA = "ce375-dfirst-page-v2"
STATUS_SCHEMA = "ce375-dfirst-status-v2"
CHECKPOINT_SCHEMA = "ce375-dfirst-checkpoint-v2"
PARAMETERIZATION = "ce375-dfirst-unit-g-both-charts-v2"
G_VALUES = (-1, 1)
COUNTERS = ("pairs", "admissible", "convergents", "small_g_values", "thue_solutions",
            "integer_chart", "half_chart", "other_branch", "refinements", "exact_roots")
MAX_H = 200_000_000
MODES = ("both", "xy", "xy-half")
XY_MODES = ("xy", "xy-half")


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


def n_mod3(k: int) -> int:
    """The residue n (mod 3) forced by k (DERIVATION.md section 5); 2 for k = 375."""
    check_k(k)
    s9 = ((k + 6) // 3) % 9 if k % 9 == 3 else ((k - 6) // 3) % 9   # S mod 9
    s18 = next(v for v in range(3, 18, 6) if v % 9 == s9)            # S mod 18, S = 3 (mod 6)
    return (s18 - 3) // 6


def primitivity(chart: str, n: int, x: Fraction, s: Fraction, cubes: tuple[int, int, int]) -> dict:
    """Independent primitivity flags; see the module docstring."""
    if chart == "integer":
        pg = gcd(n, int(x), int(s))
    else:
        pg = gcd(int(2 * x), int(2 * s))
    cg = gcd(gcd(cubes[0], cubes[1]), cubes[2])
    return {"primitive_point": pg == 1, "primitive_cubes": cg == 1,
            "desired": pg == 1, "point_gcd": str(pg), "cube_gcd": str(cg)}


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

    def __init__(self, k: int, mode: str = "both"):
        check_k(k)
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.k = k
        self.half = mode == "xy-half"
        self.tables = mode in XY_MODES
        # xy-half: for l with v_l(k) >= 3 (l = 5 at k = 375) a primitive point has
        # (S, g) != (0, 0) mod l. Since k = 0 (mod l), g = 0 (mod l) would force
        # S = 0 (mod l); so g is a unit mod l^3 and b = pq(p+q) is determined by
        # (S, g, a = pq). Built here by solving for b, independently of the
        # worker's exhaustive (S, g, a, b) loop.
        self.cube_tables: dict[int, set[tuple[int, int]]] = {}
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
        if self.tables:
            for l, v in self.kfac.items():
                if l < 5 or v < 3 or l ** 3 > 4000:
                    continue
                m = l ** 3
                ab = set()
                for S in range(m):
                    for g in range(m):
                        if g % l == 0:
                            continue
                        inv = pow(3 * g ** 3, -1, m)
                        for a in range(m):
                            ab.add((a, (k - S ** 3 + 6 * a * S * g * g) * inv % m))
                self.cube_tables[m] = ab
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
        if self.half and q % 2 == 0:
            return False
        for m, ab in self.cube_tables.items():
            a = p * q % m
            if (a, a * (p + q) % m) not in ab:
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


def verify_xy_hit(record: dict, k: int | None = None) -> dict:
    """Exact re-verification of one xy / xy-half hit (either branch of the Thue solution)."""
    rk = _int(record, "k")
    if k is not None and rk != k:
        raise ValueError(f"hit is for k={rk}, expected {k}")
    check_k(rk)
    n, X, Y = _int(record, "n"), _int(record, "X"), _int(record, "Y")
    if X % 2 != Y % 2 or Y < 0 or X == 0:
        raise ValueError("need X, Y of equal parity, X != 0 and Y >= 0")
    chart = "integer" if X % 2 == 0 else "half"
    mode = record.get("mode")
    if mode not in XY_MODES or (mode == "xy-half" and chart != "half"):
        raise ValueError("bad mode for this point")
    if (_int(record, "x_num"), _int(record, "x_den"), _int(record, "y_num"), _int(record, "y_den")) != (X, 2, Y, 2):
        raise ValueError("x, y fields do not match X/2, Y/2")
    x, y, S = Fraction(X, 2), Fraction(Y, 2), 6 * n + 3
    N = 36 * n ** 3 + 54 * n ** 2 + 27 * n + (27 - rk) // 6
    if y * y != (x + S) ** 2 + N / x:
        raise ValueError("y^2 != (x+6n+3)^2 + N/x")
    p, q, g = _int(record, "thue_p"), _int(record, "thue_q"), _int(record, "g")
    if g not in G_VALUES:
        raise ValueError("production hits require g in {-1, 1}")
    if q <= 0 or gcd(p, q) != 1 or X != -q * g or abs((2 * p + q) * g - 2 * S) != Y or _form(p, q, S, g) != rk:
        raise ValueError("Thue certificate (p, q, g) does not match the point")
    d = -(x + S + y) / (2 * x)
    if Fraction(_int(record, "d_num"), _int(record, "d_den")) != d or N != -2 * d * x * x * (-(x + S) + y):
        raise ValueError("principal d is wrong")
    a, b, c = -x + y, -x - y, 2 * x + S
    if any(v.denominator != 1 for v in (a, b, c)) or a ** 3 + b ** 3 + c ** 3 != rk:
        raise ValueError("cube identity fails")
    if (a, b, c) != tuple(Fraction(_int(record, key)) for key in ("cube_a", "cube_b", "cube_c")):
        raise ValueError("reported cube components are wrong")
    if n % 3 != n_mod3(rk):
        raise ValueError(f"invariant n == {n_mod3(rk)} (mod 3) fails")
    if record.get("chart") != chart:
        raise ValueError("reported chart is wrong")
    prim = primitivity(chart, n, x, y, (int(a), int(b), int(c)))
    for key, value in prim.items():
        if key in record and record[key] != value:
            raise ValueError(f"reported {key} is wrong")
    return {"k": str(rk), "chart": chart, "mode": mode, "d": f"{d.numerator}/{d.denominator}",
            "n": str(n), "x": str(x), "s": str(y), "y": str(y), "X": str(X), "Y": str(Y),
            "cubes": [str(a), str(b), str(c)], "g": str(g), **prim}


def verify_hit(record: dict, k: int | None = None) -> dict:
    """Exact re-verification of one worker hit; returns a normalized record."""
    if record.get("mode") in XY_MODES:
        return verify_xy_hit(record, k)
    rk = _int(record, "k")
    if k is not None and rk != k:
        raise ValueError(f"hit is for k={rk}, expected {k}")
    check_k(rk)
    p, q = _int(record, "d_num"), _int(record, "d_den")
    g, n = _int(record, "g"), _int(record, "n")
    if g not in G_VALUES:
        raise ValueError("production hits require g in {-1, 1}")
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
    if n % 3 != n_mod3(rk):
        raise ValueError(f"invariant n == {n_mod3(rk)} (mod 3) fails")
    prim = primitivity(chart, n, x, s, (int(a), int(b), int(c)))
    for key, value in prim.items():
        if key in record and record[key] != value:
            raise ValueError(f"reported {key} is wrong")
    return {"k": str(rk), "chart": chart, "d": f"{p}/{q}", "n": str(n),
            "x": str(x), "s": str(s), "cubes": [str(a), str(b), str(c)], "g": str(g), **prim}


def hit_key(record: dict) -> str:
    if record.get("mode") in XY_MODES:   # one key per point (n, X, |Y|), whichever d found it
        return "xy|" + "|".join(str(record[k]) for k in ("k", "n", "X", "Y"))
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


def validate_scope(record: dict, schema: str | None = None) -> None:
    """Reject legacy or mixed search scopes before resuming or counting coverage."""
    if schema is not None and record.get("schema") != schema:
        raise ValueError(f"schema must be {schema}")
    if record.get("parameterization") != PARAMETERIZATION:
        raise ValueError(f"parameterization must be {PARAMETERIZATION}")
    if "g_max_digits" in record:
        raise ValueError("g_max_digits is obsolete: production uses only g in {-1, 1}")
    values = record.get("g_values")
    if values != list(G_VALUES) or any(type(v) is not int for v in values):
        raise ValueError("g_values must be [-1, 1]")


def validate_task(task: dict) -> dict:
    validate_scope(task, TASK_SCHEMA)
    k = int(task["k"])
    check_k(k)
    h_start, h_stop = int(task["h_start"]), int(task["h_stop"])
    if not 1 <= h_start < h_stop <= MAX_H + 1:
        raise ValueError("need 1 <= h_start < h_stop")
    deadline = int(task.get("deadline_seconds", 0))
    if deadline < 0:
        raise ValueError("deadline_seconds must be >= 0")
    for key in ("campaign_id", "task_id"):
        if not isinstance(task.get(key), str) or not task[key]:
            raise ValueError(f"{key} must be a nonempty string")
    mode = task.get("mode", "xy")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    return {"k": k, "h_start": h_start, "h_stop": h_stop, "g_values": list(G_VALUES),
            "deadline_seconds": deadline, "mode": mode}


def isqrt_exact(v: int) -> int | None:
    if v < 0:
        return None
    r = isqrt(v)
    return r if r * r == v else None
