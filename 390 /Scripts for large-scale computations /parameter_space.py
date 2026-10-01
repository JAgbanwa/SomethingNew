"""Exact, resumable enumeration of the general CE390 auxiliary fractions.

``GeneralAQ`` derives a conservative *complete enclosure* from the integer
search bounds.  Its indices include pairs with gcd(a, q) > 1; the existing
search supervisor rejects those cheaply.  Both a and q are positive and
coprime to 6.  Rows are ordered by increasing q, then increasing a.  There
is no selected numerator list or independently chosen numerator ceiling.

The enclosure is not a prediction of where a solution lies.  Completing a
finite prefix covers that prefix only, not the full integer search region.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any


def _integer(value: Any, label: str) -> int:
    if type(value) is int:
        return value
    if isinstance(value, str) and value and value.isascii() and value.isdecimal():
        return int(value)
    raise ValueError(f"{label} must be an integer or an unsigned decimal string")


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def _count_six(limit: int) -> int:
    """Count positive integers <= limit that are coprime to 6."""
    if limit <= 0:
        return 0
    return (limit + 5) // 6 + (limit + 1) // 6


def _six_at(index: int) -> int:
    return 6 * (index // 2) + (1 if index % 2 == 0 else 5)


def _next_six(value: int) -> int:
    return value + (4 if value % 6 == 1 else 2)


def _first_six(value: int) -> int:
    return _six_at(_count_six(value - 1))


def _floor_sum(n: int, modulus: int, slope: int, intercept: int) -> int:
    """Sum floor((slope*i + intercept)/modulus), 0 <= i < n.

    Euclidean reduction gives logarithmic complexity; signed coefficients
    are supported so the helper can be checked independently by brute force.
    """
    if n < 0 or modulus <= 0:
        raise ValueError("floor_sum requires n >= 0 and modulus > 0")
    answer = 0
    while True:
        quotient, slope = divmod(slope, modulus)
        answer += n * (n - 1) // 2 * quotient
        quotient, intercept = divmod(intercept, modulus)
        answer += n * quotient
        top = slope * n + intercept
        if top < modulus:
            return answer
        n, intercept = divmod(top, modulus)
        modulus, slope = slope, modulus


def _sum_over_q(limit: int, slope: int, intercept: int, modulus: int) -> int:
    """Sum one affine floor over q <= limit with q == 1 or 5 (mod 6)."""
    result = 0
    for residue in (1, 5):
        if limit >= residue:
            rows = (limit - residue) // 6 + 1
            result += _floor_sum(rows, modulus, 6 * slope,
                                 slope * residue + intercept)
    return result


def _sum_count_six(limit: int, numerator: int, denominator: int,
                   offset: int = 0) -> int:
    """Sum C(floor((numerator*q+offset)/denominator)) over eligible q.

    All callers ensure the inner floor is nonnegative.  Nested floor
    identities turn each count into two ordinary affine floor sums.
    """
    return (_sum_over_q(limit, numerator, offset + 5 * denominator, 6 * denominator)
            + _sum_over_q(limit, numerator, offset + denominator, 6 * denominator))


class GeneralAQ:
    """Derived general-a/q enclosure, optionally restricted to an explicit q window.

    ``bounds`` contains n_min, n_max, x_min and x_max as positive magnitudes.
    The calling task validator must require integer-square-root mode; when a
    ``require_integer_sqrt`` key is supplied here it must be exactly True.
    q_min and q_max are inclusive and need not themselves be coprime to 6.
    """

    MODE = "general-aq-v1"

    def __init__(self, bounds: Mapping[str, Any], q_min: int, q_max: int):
        if "require_integer_sqrt" in bounds and bounds["require_integer_sqrt"] is not True:
            raise ValueError("general-aq-v1 requires integer-square-root mode")
        for key in ("n_min", "n_max", "x_min", "x_max"):
            if key not in bounds:
                raise ValueError(f"missing search magnitude bound: {key}")
            setattr(self, key, _integer(bounds[key], key))
        if not (0 < self.n_min <= self.n_max and 0 < self.x_min <= self.x_max):
            raise ValueError("search magnitude bounds must be positive and ordered")
        if 36 * self.n_min**3 <= 65:
            raise ValueError("general-aq-v1 requires 36*n_min^3 > 65")
        if self.x_min <= 6 * self.n_max:
            raise ValueError("general-aq-v1 requires x_min > 6*n_max")
        self.k_max = ((36 * self.n_max**3 + 65)
                      // (self.x_min * (self.x_min - 6 * self.n_max)))
        self.m_min = 12 * self.n_min + 1
        self.m_max = 12 * self.n_max + self.k_max
        if self.m_max >= self.x_min:
            raise ValueError("general-aq-v1 requires derived M_max < x_min")
        self.q_min = _integer(q_min, "q_min")
        self.q_max = _integer(q_max, "q_max")
        if not 1 <= self.q_min <= self.q_max <= self.x_max:
            raise ValueError("q window must satisfy 1 <= q_min <= q_max <= x_max")
        self._base = self._prefix(self.q_min - 1)
        self.count = self._prefix(self.q_max) - self._base

    def numerator_bounds(self, q: int) -> tuple[int, int]:
        """Inclusive integer enclosure before the coprime-to-6 filter."""
        return (_ceil_div(self.m_min * q, self.x_max),
                min(self.m_max * q // self.x_min, self.m_max))

    def _prefix(self, q_limit: int) -> int:
        """Count all indices with denominators <= q_limit (before q_min)."""
        if q_limit <= 0 or self.k_max == 0:
            return 0
        if q_limit > self.x_max:
            raise ValueError("prefix denominator exceeds x_max")
        first = min(q_limit, self.x_min)
        upper = _sum_count_six(first, self.m_max, self.x_min)
        if q_limit > self.x_min:
            upper += (_count_six(q_limit) - _count_six(self.x_min)) * _count_six(self.m_max)
        # ceil(M_min*q/X_max) - 1 == floor((M_min*q - 1)/X_max).
        lower = _sum_count_six(q_limit, self.m_min, self.x_max, -1)
        return upper - lower

    def candidate(self, index: int) -> tuple[int, int]:
        """Return (a, q) for one zero-based index using exact prefix inversion."""
        index = _integer(index, "index")
        if not 0 <= index < self.count:
            raise ValueError("candidate index is outside the selected parameter space")
        target = self._base + index
        lo, hi = self.q_min, self.q_max
        while lo < hi:
            mid = (lo + hi) // 2
            if self._prefix(mid) > target:
                hi = mid
            else:
                lo = mid + 1
        q = lo
        lower, _ = self.numerator_bounds(q)
        offset = target - self._prefix(q - 1)
        a = _six_at(_count_six(lower - 1) + offset)
        return a, q

    def index(self, a: int, q: int) -> int:
        """Return the zero-based index; nonreduced pairs deliberately remain valid."""
        a, q = _integer(a, "a"), _integer(q, "q")
        if (a <= 0 or a % 6 not in (1, 5) or q % 6 not in (1, 5)
                or not self.q_min <= q <= self.q_max or self.k_max == 0):
            raise ValueError("a/q is outside the selected parameter enclosure")
        lower, upper = self.numerator_bounds(q)
        if not lower <= a <= upper:
            raise ValueError("a/q is outside the derived numerator bounds")
        return (self._prefix(q - 1) - self._base
                + _count_six(a - 1) - _count_six(lower - 1))

    def iter_candidates(self, start: int = 0, stop: int | None = None) -> Iterator[tuple[int, int]]:
        """Stream a half-open index slice, unranking its start exactly once."""
        start = _integer(start, "start")
        stop = self.count if stop is None else _integer(stop, "stop")
        if not 0 <= start <= stop <= self.count:
            raise ValueError("iterator slice must satisfy 0 <= start <= stop <= count")
        if start == stop:
            return
        a, q = self.candidate(start)
        _, upper = self.numerator_bounds(q)
        remaining = stop - start
        while remaining:
            yield a, q
            remaining -= 1
            if not remaining:
                return
            a = _next_six(a)
            if a <= upper:
                continue
            q = _next_six(q)
            while q <= self.q_max:
                lower, upper = self.numerator_bounds(q)
                a = _first_six(lower)
                if a <= upper:
                    break
                # Any later eligible numerator is at least a.  Jump to the
                # earliest denominator at which the upper enclosure reaches a;
                # this avoids scanning long empty intervals at small slopes.
                earliest = _ceil_div(a * self.x_min, self.m_max)
                q = _first_six(max(q + 1, earliest))
            else:
                raise RuntimeError("parameter iterator exhausted before its counted stop")

    def bounds_info(self) -> dict[str, str | bool]:
        """JSON-safe provenance; count is an enclosure size, not a hit prediction."""
        return {
            "mode": self.MODE,
            "ordering": "increasing q, then increasing a; both coprime to 6",
            "q_min": str(self.q_min), "q_max": str(self.q_max),
            "n_min": str(self.n_min), "n_max": str(self.n_max),
            "x_min": str(self.x_min), "x_max": str(self.x_max),
            "k_max": str(self.k_max), "m_min": str(self.m_min), "m_max": str(self.m_max),
            "slope_lower_numerator": str(self.m_min),
            "slope_lower_denominator": str(self.x_max),
            "slope_upper_numerator": str(self.m_max),
            "slope_upper_denominator": str(self.x_min),
            "total_candidate_indices": str(self.count),
            "full_denominator_window": self.q_min == 1 and self.q_max == self.x_max,
            "gcd_filter": "noncoprime pairs remain indexed and are rejected by the search runner",
            "coverage_note": "Completing a prefix or q window covers only those parameter indices; full-region coverage requires completion of the entire derived enclosure.",
        }
